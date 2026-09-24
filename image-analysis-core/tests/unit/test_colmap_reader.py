"""Unit tests for COLMAP binary model reader."""
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from shared.colmap.model_reader import (
    ColmapCamera,
    ColmapImage,
    read_cameras_binary,
    read_images_binary,
)


class TestColmapCamera(unittest.TestCase):
    """Test ColmapCamera properties."""

    def test_simple_pinhole_focal_length(self):
        """Focal length for SIMPLE_PINHOLE model."""
        cam = ColmapCamera(
            camera_id=1,
            model_name="SIMPLE_PINHOLE",
            width=4000,
            height=3000,
            params=np.array([2800.0, 2000.0, 1500.0]),
        )
        self.assertAlmostEqual(cam.focal_length_x, 2800.0)
        self.assertAlmostEqual(cam.focal_length_y, 2800.0)
        self.assertAlmostEqual(cam.principal_point_x, 2000.0)
        self.assertAlmostEqual(cam.principal_point_y, 1500.0)

    def test_pinhole_focal_length(self):
        """Focal length for PINHOLE model (separate fx, fy)."""
        cam = ColmapCamera(
            camera_id=1,
            model_name="PINHOLE",
            width=4000,
            height=3000,
            params=np.array([2800.0, 2900.0, 2000.0, 1500.0]),
        )
        self.assertAlmostEqual(cam.focal_length_x, 2800.0)
        self.assertAlmostEqual(cam.focal_length_y, 2900.0)
        self.assertAlmostEqual(cam.principal_point_x, 2000.0)
        self.assertAlmostEqual(cam.principal_point_y, 1500.0)


class TestColmapImage(unittest.TestCase):
    """Test ColmapImage methods."""

    def test_rotation_matrix_identity(self):
        """Identity quaternion → identity rotation matrix."""
        img = ColmapImage(
            image_id=1,
            qvec=np.array([1.0, 0.0, 0.0, 0.0]),
            tvec=np.array([0.0, 0.0, 0.0]),
            camera_id=1,
            name="test.jpg",
        )
        rot = img.rotation_matrix()
        np.testing.assert_array_almost_equal(rot, np.eye(3))

    def test_projection_center_zero_translation(self):
        """Zero translation → projection center at origin."""
        img = ColmapImage(
            image_id=1,
            qvec=np.array([1.0, 0.0, 0.0, 0.0]),
            tvec=np.array([0.0, 0.0, 0.0]),
            camera_id=1,
            name="test.jpg",
        )
        center = img.projection_center()
        np.testing.assert_array_almost_equal(center, np.zeros(3))

    def test_projection_center_with_translation(self):
        """Non-zero translation → projection center = -R^T @ t."""
        img = ColmapImage(
            image_id=1,
            qvec=np.array([1.0, 0.0, 0.0, 0.0]),
            tvec=np.array([1.0, 2.0, 3.0]),
            camera_id=1,
            name="test.jpg",
        )
        center = img.projection_center()
        np.testing.assert_array_almost_equal(center, np.array([-1.0, -2.0, -3.0]))


class TestReadCamerasBinary(unittest.TestCase):
    """Test reading cameras.bin files."""

    def test_read_single_pinhole_camera(self):
        """Read a cameras.bin with one PINHOLE camera."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(struct.pack("<Q", 1))
            f.write(struct.pack("<I", 1))
            f.write(struct.pack("<i", 1))
            f.write(struct.pack("<Q", 4000))
            f.write(struct.pack("<Q", 3000))
            f.write(struct.pack("<4d", 2800.0, 2900.0, 2000.0, 1500.0))
            path = Path(f.name)

        cameras = read_cameras_binary(path)
        path.unlink()

        self.assertEqual(len(cameras), 1)
        cam = cameras[1]
        self.assertEqual(cam.model_name, "PINHOLE")
        self.assertEqual(cam.width, 4000)
        self.assertEqual(cam.height, 3000)
        self.assertAlmostEqual(cam.focal_length_x, 2800.0)


class TestReadImagesBinary(unittest.TestCase):
    """Test reading images.bin files."""

    def test_read_single_image(self):
        """Read an images.bin with one image entry."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(struct.pack("<Q", 1))
            f.write(struct.pack("<I", 1))
            f.write(struct.pack("<4d", 1.0, 0.0, 0.0, 0.0))
            f.write(struct.pack("<3d", 1.0, 2.0, 3.0))
            f.write(struct.pack("<I", 1))
            name = b"test_image.jpg\x00"
            f.write(name)
            f.write(struct.pack("<Q", 0))
            path = Path(f.name)

        images = read_images_binary(path)
        path.unlink()

        self.assertEqual(len(images), 1)
        img = images[1]
        self.assertEqual(img.name, "test_image.jpg")
        self.assertEqual(img.camera_id, 1)
        np.testing.assert_array_almost_equal(img.tvec, [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
