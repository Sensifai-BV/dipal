"""Real-world band detection tests on actual drone image datasets.

Validates scan_dataset + organize_by_band against three real datasets:
  1. DJI M3M multispectral (595 images: JPG visible + TIF MS bands)
  2. Parrot Sequoia 4-band (1217 TIF images: GRE, NIR, RED, REG)
  3. RGB-only JPGs (425 images)

Run with:
    python -m unittest tests.test_band_detection_real -v
    python tests/test_band_detection_real.py          # standalone mode
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.band_detection import (
    BandType,
    DatasetBandManifest,
    classify_image,
    organize_by_band,
    scan_dataset,
)

DATASETS: dict[str, Path] = {
    "dji_m3m": Path("/home/ali/Downloads/Compressed/DJI_202407190843_001_Mapping7"),
    "parrot_sequoia": Path("/home/ali/Downloads/Compressed/EP-11-09706_0065 (1)/EP-11-09706_0065"),
    "rgb_only": Path("/home/ali/Downloads/Compressed/100_0015"),
}


def _print_manifest(manifest: DatasetBandManifest) -> None:
    """Pretty-print a band manifest."""
    print(f"  Dataset ID:       {manifest.dataset_id}")
    print(f"  Total images:     {manifest.total_images}")
    print(f"  Manufacturer:     {manifest.manufacturer.value}")
    print(f"  Drone model:      {manifest.drone_model}")
    print(f"  Is multispectral: {manifest.is_multispectral}")
    print(f"  Available bands:  {[b.value for b in manifest.available_bands]}")
    print(f"  Errors:           {len(manifest.errors)}")
    for band_key, group in manifest.bands.items():
        first = group.images[0] if group.images else None
        print(
            f"    {band_key:12s} -> {group.count:4d} images  "
            f"(method={first.detection_method if first else 'n/a'}, "
            f"confidence={first.confidence if first else 'n/a'})"
        )


def _scan_and_print(name: str, path: Path) -> DatasetBandManifest:
    """Scan a dataset, print results, and return the manifest."""
    t0 = time.perf_counter()
    manifest = scan_dataset(path, dataset_id=f"test-{name}")
    elapsed = time.perf_counter() - t0
    _print_manifest(manifest)
    per_img = (elapsed / manifest.total_images * 1000) if manifest.total_images else 0
    print(f"  Scan time:  {elapsed:.2f}s  ({per_img:.1f}ms/img)")
    return manifest


class TestSingleImageClassify(unittest.TestCase):
    """Classify one sample image from each dataset."""

    def test_classify_first_image(self):
        """Classify first image from each available dataset."""
        for name, path in DATASETS.items():
            with self.subTest(dataset=name):
                if not path.exists():
                    self.skipTest(f"Dataset not found: {path}")

                images = sorted(
                    f for f in path.rglob("*")
                    if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".tif", ".tiff", ".dng", ".png"}
                )
                self.assertTrue(images, f"No images in {path}")

                sample = images[0]
                t0 = time.perf_counter()
                info = classify_image(sample)
                elapsed = time.perf_counter() - t0

                print(
                    f"\n  [{name}] {info.file_name}: band={info.band_type.value}, "
                    f"method={info.detection_method}, mfg={info.manufacturer.value}, "
                    f"time={elapsed*1000:.1f}ms"
                )

                self.assertIsNotNone(info.band_type)
                self.assertGreater(info.confidence, 0)


class TestDatasetScan(unittest.TestCase):
    """Scan full datasets and verify band detection."""

    def test_scan_dji_m3m(self):
        """Test scanning DJI M3M multispectral dataset."""
        path = DATASETS["dji_m3m"]
        if not path.exists():
            self.skipTest("DJI M3M dataset not found")

        manifest = _scan_and_print("dji_m3m", path)
        self.assertTrue(manifest.is_multispectral)
        self.assertEqual(manifest.manufacturer.value, "dji")
        self.assertIn("rgb", manifest.bands)
        self.assertTrue(any(b in manifest.bands for b in ["nir", "red", "green", "red_edge"]))
        self.assertEqual(manifest.errors, [])

    def test_scan_parrot_sequoia(self):
        """Test scanning Parrot Sequoia multispectral dataset."""
        path = DATASETS["parrot_sequoia"]
        if not path.exists():
            self.skipTest("Parrot Sequoia dataset not found")

        manifest = _scan_and_print("parrot_sequoia", path)
        self.assertTrue(manifest.is_multispectral)
        self.assertEqual(manifest.manufacturer.value, "parrot")
        self.assertTrue(any(b in manifest.bands for b in ["nir", "red", "green", "red_edge"]))
        self.assertEqual(manifest.errors, [])

    def test_scan_rgb_only(self):
        """Test scanning RGB-only dataset."""
        path = DATASETS["rgb_only"]
        if not path.exists():
            self.skipTest("RGB-only dataset not found")

        manifest = _scan_and_print("rgb_only", path)
        self.assertFalse(manifest.is_multispectral)
        self.assertIn("rgb", manifest.bands)
        self.assertEqual(manifest.bands["rgb"].count, manifest.total_images)
        self.assertEqual(manifest.errors, [])

    def test_performance_under_10s(self):
        """Each dataset must scan in under 10 seconds."""
        for name, path in DATASETS.items():
            with self.subTest(dataset=name):
                if not path.exists():
                    self.skipTest(f"Dataset not found: {path}")

                t0 = time.perf_counter()
                scan_dataset(path, dataset_id=f"perf-{name}")
                elapsed = time.perf_counter() - t0
                print(f"\n  [{name}] scan time: {elapsed:.2f}s")
                self.assertLess(elapsed, 10.0, f"Scan took {elapsed:.1f}s — exceeds 10s limit")


class TestOrganize(unittest.TestCase):
    """Test organizing images into band subfolders."""

    def test_organize_writes_manifest(self):
        """Organize a subset of images and check manifest is written."""
        for name, path in DATASETS.items():
            with self.subTest(dataset=name):
                if not path.exists():
                    self.skipTest(f"Dataset not found: {path}")

                manifest = scan_dataset(path, dataset_id=f"org-{name}")

                with tempfile.TemporaryDirectory(prefix="band_org_") as tmpdir:
                    tmp_path = Path(tmpdir)
                    images_dir = tmp_path / "images"
                    images_dir.mkdir()

                    copied = 0
                    for group in manifest.bands.values():
                        for info in group.images[:5]:
                            src = Path(info.file_path)
                            if src.exists():
                                shutil.copy2(str(src), str(images_dir / src.name))
                                copied += 1

                    sub_manifest = scan_dataset(images_dir, dataset_id=f"org-sub-{name}")
                    folders = organize_by_band(sub_manifest, tmp_path, move=False)

                    self.assertIn("metadata", folders)
                    manifest_file = tmp_path / "metadata" / "band_manifest.json"
                    self.assertTrue(manifest_file.exists())
                    data = json.loads(manifest_file.read_text())
                    self.assertIn("bands", data)
                    self.assertIn("dataset_id", data)

                    band_dirs = [k for k in folders if k != "metadata"]
                    print(f"\n  [{name}] organized {copied} images into {band_dirs}")


def run_all_tests() -> None:
    """Run all band detection tests in standalone mode."""
    sep = "=" * 70
    print(f"\n{sep}\nBAND DETECTION REAL-WORLD TEST SUITE\n{sep}")

    results: dict[str, dict] = {}

    for name, path in DATASETS.items():
        print(f"\n{sep}\nDATASET: {name}\n  Path: {path}\n{sep}")

        if not path.exists():
            print(f"  SKIPPED - path does not exist")
            continue

        manifest = _scan_and_print(name, path)
        results[name] = {
            "total": manifest.total_images,
            "multispectral": manifest.is_multispectral,
            "manufacturer": manifest.manufacturer.value,
            "bands": {k: v.count for k, v in manifest.bands.items()},
            "errors": len(manifest.errors),
        }

    print(f"\n{sep}\nSUMMARY\n{sep}")
    for name, r in results.items():
        status = "PASS" if r["errors"] == 0 else f"{r['errors']} errors"
        print(
            f"  {name:15s}: {r['total']:5d} images, "
            f"ms={r['multispectral']}, mfg={r['manufacturer']}, "
            f"bands={r['bands']}, {status}"
        )

    dji = results.get("dji_m3m", {})
    if dji:
        assert dji["multispectral"]
        assert dji["manufacturer"] == "dji"
        assert "rgb" in dji["bands"]

    seq = results.get("parrot_sequoia", {})
    if seq:
        assert seq["multispectral"]
        assert seq["manufacturer"] == "parrot"

    rgb = results.get("rgb_only", {})
    if rgb:
        assert not rgb["multispectral"]
        assert rgb["bands"].get("rgb", 0) == rgb["total"]

    print(f"\n{sep}\nALL TESTS PASSED\n{sep}")


if __name__ == "__main__":
    run_all_tests()
