"""Unit tests for pose-driven multispectral orthorectification helpers.

Covers the pure-math/parse helpers in pose_ortho that need no GDAL/COLMAP:
capture-sequence parsing, quaternion→rotation, the FULL_OPENCV projection
round-trip, bilinear sampling, and DewarpHMatrix/RelativeOpticalCenter parsing.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from services.orthomosaic_generation.app.core.algorithms import pose_ortho as po


class TestCaptureSeq(unittest.TestCase):
    def test_dji_rgb(self):
        self.assertEqual(po._capture_seq("DJI_20240719091600_0050_D.JPG"), "0050")

    def test_dji_ms(self):
        self.assertEqual(po._capture_seq("DJI_20240719091600_0050_MS_NIR.TIF"), "0050")

    def test_no_match(self):
        self.assertIsNone(po._capture_seq("random_name.tif"))


class TestQuatToRot(unittest.TestCase):
    def test_identity(self):
        R = po._quat_to_rot(np.array([1.0, 0.0, 0.0, 0.0]))
        np.testing.assert_allclose(R, np.eye(3), atol=1e-9)

    def test_orthonormal(self):
        q = np.array([-0.17016, 0.61186, 0.67526, -0.37509])  # real Sim3 quaternion
        q = q / np.linalg.norm(q)
        R = po._quat_to_rot(q)
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-6)
        self.assertAlmostEqual(np.linalg.det(R), 1.0, places=6)

    def test_180_about_z(self):
        R = po._quat_to_rot(np.array([0.0, 0.0, 0.0, 1.0]))
        np.testing.assert_allclose(R @ np.array([1, 0, 0]), np.array([-1, 0, 0]), atol=1e-9)


class TestProjectToRgb(unittest.TestCase):
    def _geom(self, dist):
        return po.SfmGeometry(
            fx=3713.0, fy=3713.0, cx=2640.0, cy=1978.0, rgb_w=5280, rgb_h=3956,
            dist=np.asarray(dist, dtype=float),
            pose_by_capture={}, sim_scale=1.0, sim_rot=np.eye(3),
            sim_t=np.zeros(3), utm_epsg=32634,
        )

    def test_on_axis_point_maps_to_principal_point(self):
        geom = self._geom(np.zeros(8))
        # a point straight ahead (x=0,y=0,z>0) maps to (cx, cy)
        p = np.array([[0.0, 0.0, 10.0]])
        u, v, front = po._project_to_rgb(p, np.eye(3), np.zeros(3), geom)
        self.assertTrue(front[0])
        self.assertAlmostEqual(u[0], geom.cx, places=6)
        self.assertAlmostEqual(v[0], geom.cy, places=6)

    def test_behind_camera_flagged(self):
        geom = self._geom(np.zeros(8))
        p = np.array([[0.0, 0.0, -5.0]])
        _u, _v, front = po._project_to_rgb(p, np.eye(3), np.zeros(3), geom)
        self.assertFalse(front[0])

    def test_no_distortion_is_pinhole(self):
        geom = self._geom(np.zeros(8))
        p = np.array([[1.0, 0.5, 10.0]])
        u, v, _ = po._project_to_rgb(p, np.eye(3), np.zeros(3), geom)
        # pinhole: u = fx * x/z + cx
        self.assertAlmostEqual(u[0], geom.fx * 0.1 + geom.cx, places=6)
        self.assertAlmostEqual(v[0], geom.fy * 0.05 + geom.cy, places=6)


class TestBilinearSample(unittest.TestCase):
    def test_exact_pixel(self):
        arr = np.arange(16, dtype=np.float32).reshape(4, 4)
        u = np.array([1.0, 2.0])
        v = np.array([1.0, 2.0])
        ok = np.array([True, True])
        val, valid = po._bilinear_sample(arr, u, v, ok)
        self.assertTrue(valid.all())
        self.assertAlmostEqual(val[0], arr[1, 1])
        self.assertAlmostEqual(val[1], arr[2, 2])

    def test_last_row_col_rejected(self):
        # bilinear needs the +1 neighbour, so the last row/col is out of range
        arr = np.zeros((4, 4), dtype=np.float32)
        _val, valid = po._bilinear_sample(arr, np.array([3.0]), np.array([3.0]), np.array([True]))
        self.assertFalse(valid[0])

    def test_midpoint_interpolates(self):
        arr = np.array([[0.0, 10.0], [0.0, 10.0]], dtype=np.float32)
        val, valid = po._bilinear_sample(arr, np.array([0.5]), np.array([0.0]), np.array([True]))
        self.assertTrue(valid[0])
        self.assertAlmostEqual(val[0], 5.0, places=5)

    def test_out_of_bounds_invalid(self):
        arr = np.zeros((4, 4), dtype=np.float32)
        val, valid = po._bilinear_sample(arr, np.array([-1.0, 99.0]), np.array([0.0, 0.0]),
                                         np.array([True, True]))
        self.assertFalse(valid.any())

    def test_not_ok_skipped(self):
        arr = np.ones((4, 4), dtype=np.float32)
        _val, valid = po._bilinear_sample(arr, np.array([1.0]), np.array([1.0]), np.array([False]))
        self.assertFalse(valid[0])


class TestReadBandGeometry(unittest.TestCase):
    def _write_xmp(self, body: bytes) -> str:
        f = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        f.write(body)
        f.close()
        return f.name

    def test_parses_hmatrix_and_offset(self):
        xmp = (
            b'<x:xmpmeta>'
            b'drone-dji:DewarpHMatrix="1.7162,0.0,415.75,0.0,1.7162,309.81,0.0,0.0,1.0"'
            b'drone-dji:RelativeOpticalCenterX="11.32"'
            b'drone-dji:RelativeOpticalCenterY="3.06"'
            b'</x:xmpmeta>' + b"\x00" * 1000
        )
        path = self._write_xmp(xmp)
        res = po._read_band_geometry(path)
        Path(path).unlink()
        self.assertIsNotNone(res)
        h_inv, off = res
        # H_inv @ H == I; recover the original H by inverting back
        h = np.linalg.inv(h_inv)
        self.assertAlmostEqual(h[0, 0], 1.7162, places=3)
        self.assertAlmostEqual(off[0], 11.32, places=2)
        self.assertAlmostEqual(off[1], 3.06, places=2)

    def test_hmatrix_maps_ms_center_to_offset_corner(self):
        # H = scale*I + translation → H @ [0,0,1] = translation
        xmp = (
            b'drone-dji:DewarpHMatrix="1.7162,0.0,415.75,0.0,1.7162,309.81,0.0,0.0,1.0"'
            b'drone-dji:RelativeOpticalCenterX="0.0"drone-dji:RelativeOpticalCenterY="0.0"'
            + b"\x00" * 1000
        )
        path = self._write_xmp(xmp)
        h_inv, _ = po._read_band_geometry(path)
        Path(path).unlink()
        h = np.linalg.inv(h_inv)
        np.testing.assert_allclose(h @ np.array([0, 0, 1.0]), [415.75, 309.81, 1.0], atol=1e-3)

    def test_missing_tag_returns_none(self):
        path = self._write_xmp(b"no xmp here" + b"\x00" * 100)
        self.assertIsNone(po._read_band_geometry(path))


class TestGroupCapturesByBand(unittest.TestCase):
    """Regression: calibrated reflectance stems carry a ``_reflectance`` suffix the
    raw-keyed manifest map lacks, so grouping must strip it (else 0 captures →
    silent GPS fallback → flight-line strips)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cal_root = Path(self.tmp.name)
        self.bands = ["green", "nir", "red", "red_edge"]
        self.suffix = {"green": "MS_G", "nir": "MS_NIR", "red": "MS_R", "red_edge": "MS_RE"}
        self.manifest = {"bands": {}}
        for band, suf in self.suffix.items():
            (self.cal_root / band).mkdir()
            images = []
            for seq in ("0100", "0101"):
                raw = f"DJI_20240719091917_{seq}_{suf}.TIF"
                (self.cal_root / band / f"DJI_20240719091917_{seq}_{suf}_reflectance.tif").touch()
                images.append({"file_path": f"/data/ds/{band}/{raw}"})
            self.manifest["bands"][band] = {"images": images}

    def tearDown(self):
        self.tmp.cleanup()

    def _build_map(self, manifest, band_name):
        band_group = manifest.get("bands", {}).get(band_name, {})
        return {Path(i["file_path"]).stem: i["file_path"] for i in band_group.get("images", [])}

    def test_reflectance_suffix_is_grouped(self):
        captures = po._group_captures_by_band(self.cal_root, self.manifest, self.bands, self._build_map)
        self.assertEqual(set(captures), {"0100", "0101"})
        self.assertEqual(set(captures["0100"]), set(self.bands))
        refl, orig = captures["0100"]["green"]
        self.assertTrue(str(refl).endswith("_MS_G_reflectance.tif"))
        self.assertTrue(orig.endswith("_MS_G.TIF"))

    def test_empty_manifest_yields_no_captures(self):
        self.assertEqual(po._group_captures_by_band(self.cal_root, {"bands": {}}, self.bands, self._build_map), {})


class TestErodeMask(unittest.TestCase):
    def test_one_iteration_trims_border(self):
        mask = np.ones((5, 5), dtype=bool)
        eroded = po._erode_mask(mask, 1)
        self.assertTrue(eroded[1:-1, 1:-1].all())
        self.assertFalse(eroded[0, :].any())
        self.assertFalse(eroded[:, 0].any())

    def test_zero_iterations_is_identity(self):
        mask = np.array([[True, False], [True, True]])
        np.testing.assert_array_equal(po._erode_mask(mask, 0), mask)

    def test_erosion_removes_thin_protrusion(self):
        mask = np.zeros((5, 5), dtype=bool)
        mask[2, :] = True  # 1-px-wide horizontal spike
        self.assertFalse(po._erode_mask(mask, 1).any())


if __name__ == "__main__":
    unittest.main()
