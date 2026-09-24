"""Unit tests for shared/utils/image_preprocessing.py."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import numpy as np

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from shared.utils.image_preprocessing import (
    calculate_downsample_factor,
    downsample_image,
    downsample_dataset,
    estimate_gsd_from_exif,
)


class TestCalculateDownsampleFactor(unittest.TestCase):
    """Tests for calculate_downsample_factor."""

    def test_no_downsampling_needed(self):
        """Target GSD <= current GSD means factor=1.0."""
        factor = calculate_downsample_factor(4000, 3000, 5.0, 5.0)
        self.assertAlmostEqual(factor, 1.0)

    def test_no_downsampling_target_lower(self):
        factor = calculate_downsample_factor(4000, 3000, 5.0, 3.0)
        self.assertAlmostEqual(factor, 1.0)

    def test_half_resolution(self):
        factor = calculate_downsample_factor(4000, 3000, 2.5, 5.0)
        self.assertAlmostEqual(factor, 0.5)

    def test_quarter_resolution(self):
        factor = calculate_downsample_factor(4000, 3000, 2.5, 10.0)
        self.assertAlmostEqual(factor, 0.25)

    def test_minimum_clamp(self):
        """Factor clamped to 0.1 minimum."""
        factor = calculate_downsample_factor(4000, 3000, 1.0, 100.0)
        self.assertAlmostEqual(factor, 0.1)


class TestDownsampleImage(unittest.TestCase):
    """Tests for downsample_image."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        img = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
        import cv2
        self.input_path = self.tmpdir / "input.jpg"
        cv2.imwrite(str(self.input_path), img)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_downsampling_copies_file(self):
        out = self.tmpdir / "out.jpg"
        w, h = downsample_image(self.input_path, out, 1.0)
        self.assertTrue(out.exists())
        self.assertEqual(w, 200)
        self.assertEqual(h, 100)

    def test_half_downsampling_jpg(self):
        out = self.tmpdir / "out.jpg"
        w, h = downsample_image(self.input_path, out, 0.5)
        self.assertTrue(out.exists())
        self.assertEqual(w, 100)
        self.assertEqual(h, 50)

    def test_half_downsampling_png(self):
        out = self.tmpdir / "out.png"
        w, h = downsample_image(self.input_path, out, 0.5)
        self.assertTrue(out.exists())
        self.assertEqual(w, 100)
        self.assertEqual(h, 50)

    def test_half_downsampling_tif(self):
        out = self.tmpdir / "out.tif"
        w, h = downsample_image(self.input_path, out, 0.5)
        self.assertTrue(out.exists())
        self.assertEqual(w, 100)
        self.assertEqual(h, 50)

    def test_invalid_image(self):
        bad = self.tmpdir / "bad.jpg"
        bad.write_text("not an image")
        with self.assertRaises(ValueError):
            downsample_image(bad, self.tmpdir / "out.jpg", 0.5)

    def test_creates_parent_dirs(self):
        out = self.tmpdir / "sub" / "dir" / "out.jpg"
        w, h = downsample_image(self.input_path, out, 0.5)
        self.assertTrue(out.exists())


class TestDownsampleDataset(unittest.TestCase):
    """Tests for downsample_dataset."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.input_dir = self.tmpdir / "input"
        self.input_dir.mkdir()
        self.output_dir = self.tmpdir / "output"

        import cv2
        for i in range(3):
            img = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
            cv2.imwrite(str(self.input_dir / f"img_{i}.jpg"), img)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_downsampling(self):
        stats = downsample_dataset(self.input_dir, self.output_dir, 5.0, 5.0)
        self.assertEqual(stats["total_images"], 3)
        self.assertEqual(stats["processed"], 3)
        self.assertEqual(stats["failed"], 0)
        self.assertAlmostEqual(stats["downsample_factor"], 1.0)

    def test_with_downsampling(self):
        stats = downsample_dataset(self.input_dir, self.output_dir, 10.0, 5.0)
        self.assertEqual(stats["processed"], 3)
        self.assertAlmostEqual(stats["downsample_factor"], 0.5)

    def test_empty_directory(self):
        empty = self.tmpdir / "empty"
        empty.mkdir()
        with self.assertRaises(ValueError):
            downsample_dataset(empty, self.output_dir, 5.0, 5.0)

    def test_no_current_gsd_provided(self):
        stats = downsample_dataset(self.input_dir, self.output_dir, 5.0)
        self.assertEqual(stats["processed"], 3)
        self.assertAlmostEqual(stats["downsample_factor"], 1.0)


class TestEstimateGsdFromExif(unittest.TestCase):
    """Tests for estimate_gsd_from_exif."""

    def test_returns_none(self):
        result = estimate_gsd_from_exif(Path("/some/image.jpg"))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
