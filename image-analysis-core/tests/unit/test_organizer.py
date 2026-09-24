"""Unit tests for shared.band_detection.organizer."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from shared.band_detection.models import (
    BandGroup,
    BandType,
    DatasetBandManifest,
    DroneManufacturer,
    ImageBandInfo,
)
from shared.band_detection.organizer import (
    BAND_FOLDER_NAMES,
    _cleanup_empty_source_dirs,
    get_band_folder,
    get_rgb_folder,
    load_manifest,
    organize_by_band,
)


def _make_manifest(dataset_dir, band_images=None):
    """Helper to create a manifest with images at given paths."""
    bands = {}
    if band_images:
        for band_key, filenames in band_images.items():
            bt = BandType(band_key)
            images = []
            for fn in filenames:
                fp = dataset_dir / "images" / fn
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_bytes(b"\x00" * 10)
                images.append(ImageBandInfo(
                    file_path=str(fp), file_name=fn, band_type=bt,
                ))
            bands[band_key] = BandGroup(
                band_type=bt, images=images,
            )

    return DatasetBandManifest(
        dataset_id="ds1",
        total_images=sum(len(v) for v in (band_images or {}).values()),
        is_multispectral=True,
        manufacturer=DroneManufacturer.DJI,
        bands=bands,
    )


class TestOrganizeByBand(unittest.TestCase):
    """Tests for organize_by_band."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_move_images(self):
        manifest = _make_manifest(self.tmpdir, {"rgb": ["img1.jpg", "img2.jpg"]})
        dirs = organize_by_band(manifest, self.tmpdir, move=True)

        self.assertIn("rgb", dirs)
        self.assertTrue((self.tmpdir / "rgb" / "img1.jpg").exists())
        self.assertTrue((self.tmpdir / "rgb" / "img2.jpg").exists())
        self.assertFalse((self.tmpdir / "images" / "img1.jpg").exists())

    def test_copy_images(self):
        manifest = _make_manifest(self.tmpdir, {"nir": ["nir1.tif"]})
        dirs = organize_by_band(manifest, self.tmpdir, move=False)

        self.assertTrue((self.tmpdir / "nir" / "nir1.tif").exists())
        self.assertTrue((self.tmpdir / "images" / "nir1.tif").exists())

    def test_skip_missing_source(self):
        manifest = _make_manifest(self.tmpdir, {"green": ["g1.tif"]})
        (self.tmpdir / "images" / "g1.tif").unlink()
        dirs = organize_by_band(manifest, self.tmpdir, move=True)
        self.assertFalse((self.tmpdir / "green" / "g1.tif").exists())

    def test_skip_existing_destination(self):
        manifest = _make_manifest(self.tmpdir, {"red": ["r1.tif"]})
        dst = self.tmpdir / "red" / "r1.tif"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"\xff" * 5)
        dirs = organize_by_band(manifest, self.tmpdir, move=True)
        self.assertEqual(dst.read_bytes(), b"\xff" * 5)

    def test_manifest_saved(self):
        manifest = _make_manifest(self.tmpdir, {"blue": ["b1.tif"]})
        organize_by_band(manifest, self.tmpdir)
        manifest_path = self.tmpdir / "metadata" / "band_manifest.json"
        self.assertTrue(manifest_path.exists())
        data = json.loads(manifest_path.read_text())
        self.assertEqual(data["dataset_id"], "ds1")

    def test_empty_manifest(self):
        manifest = _make_manifest(self.tmpdir)
        dirs = organize_by_band(manifest, self.tmpdir)
        self.assertIn("metadata", dirs)


class TestCleanupEmptySourceDirs(unittest.TestCase):
    """Tests for _cleanup_empty_source_dirs."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_images_dir(self):
        manifest = _make_manifest(self.tmpdir)
        _cleanup_empty_source_dirs(manifest, self.tmpdir)

    def test_empty_images_dir_removed(self):
        images_dir = self.tmpdir / "images"
        images_dir.mkdir()
        manifest = _make_manifest(self.tmpdir)
        _cleanup_empty_source_dirs(manifest, self.tmpdir)
        self.assertFalse(images_dir.exists())

    def test_non_empty_images_dir_kept(self):
        images_dir = self.tmpdir / "images"
        images_dir.mkdir()
        (images_dir / "leftover.tif").write_bytes(b"\x00")
        manifest = _make_manifest(self.tmpdir)
        _cleanup_empty_source_dirs(manifest, self.tmpdir)
        self.assertTrue(images_dir.exists())


class TestGetRGBFolder(unittest.TestCase):
    """Tests for get_rgb_folder."""

    def test_exists(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "rgb").mkdir()
            self.assertEqual(get_rgb_folder(Path(d)), Path(d) / "rgb")

    def test_not_exists(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(get_rgb_folder(Path(d)))


class TestGetBandFolder(unittest.TestCase):
    """Tests for get_band_folder."""

    def test_exists(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "nir").mkdir()
            self.assertEqual(get_band_folder(Path(d), BandType.NIR), Path(d) / "nir")

    def test_not_exists(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(get_band_folder(Path(d), BandType.THERMAL))


class TestLoadManifest(unittest.TestCase):
    """Tests for load_manifest."""

    def test_loads_valid_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            meta = Path(d) / "metadata"
            meta.mkdir()
            data = {
                "dataset_id": "ds1",
                "total_images": 5,
                "is_multispectral": True,
                "manufacturer": "dji",
                "bands": {},
            }
            (meta / "band_manifest.json").write_text(json.dumps(data))
            result = load_manifest(Path(d))
            self.assertIsNotNone(result)
            self.assertEqual(result.dataset_id, "ds1")

    def test_no_manifest_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(load_manifest(Path(d)))

    def test_corrupt_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            meta = Path(d) / "metadata"
            meta.mkdir()
            (meta / "band_manifest.json").write_text("not json{{{")
            self.assertIsNone(load_manifest(Path(d)))


if __name__ == "__main__":
    unittest.main()
