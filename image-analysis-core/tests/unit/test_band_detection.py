"""Tests for shared/band_detection models, detector, organizer."""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from shared.band_detection.models import (
    BandType,
    DroneManufacturer,
    ImageBandInfo,
    BandGroup,
    DatasetBandManifest,
    DJI_BAND_NAME_MAP,
    MICASENSE_BAND_NAME_MAP,
    DJI_FILENAME_BAND_PATTERNS,
    GENERIC_FILENAME_BAND_PATTERNS,
    BAND_WAVELENGTH_MAP,
    IMAGE_EXTENSIONS,
)


class TestBandType(unittest.TestCase):
    """Tests for BandType enum."""

    def test_all_band_types(self):
        """Test all expected band types exist."""
        expected = {"rgb", "red", "green", "blue", "nir", "red_edge", "thermal", "panchromatic", "unknown"}
        actual = {bt.value for bt in BandType}
        self.assertEqual(actual, expected)

    def test_band_type_is_string(self):
        """Test BandType values are strings."""
        self.assertEqual(BandType.RGB, "rgb")
        self.assertEqual(BandType.NIR, "nir")


class TestDroneManufacturer(unittest.TestCase):
    """Tests for DroneManufacturer enum."""

    def test_manufacturers(self):
        """Test all manufacturers exist."""
        expected = {"dji", "micasense", "parrot", "unknown"}
        actual = {m.value for m in DroneManufacturer}
        self.assertEqual(actual, expected)


class TestImageBandInfo(unittest.TestCase):
    """Tests for ImageBandInfo model."""

    def test_create_band_info(self):
        """Test creating ImageBandInfo."""
        info = ImageBandInfo(
            file_path="/data/img.jpg",
            file_name="img.jpg",
            band_type=BandType.RGB,
            manufacturer=DroneManufacturer.DJI,
            drone_model="Mavic 3M",
            detection_method="xmp",
            confidence=0.95,
        )
        self.assertEqual(info.band_type, BandType.RGB)
        self.assertEqual(info.manufacturer, DroneManufacturer.DJI)
        self.assertAlmostEqual(info.confidence, 0.95)

    def test_path_property(self):
        """Test path property returns Path object."""
        info = ImageBandInfo(
            file_path="/data/test.tif",
            file_name="test.tif",
            band_type=BandType.NIR,
        )
        self.assertIsInstance(info.path, Path)
        self.assertEqual(info.path.name, "test.tif")

    def test_defaults(self):
        """Test default values."""
        info = ImageBandInfo(
            file_path="/data/img.jpg",
            file_name="img.jpg",
            band_type=BandType.UNKNOWN,
        )
        self.assertEqual(info.manufacturer, DroneManufacturer.UNKNOWN)
        self.assertEqual(info.detection_method, "unknown")
        self.assertAlmostEqual(info.confidence, 1.0)
        self.assertIsNone(info.band_name_raw)
        self.assertIsNone(info.sensor_index)
        self.assertIsNone(info.center_wavelength_nm)


class TestBandGroup(unittest.TestCase):
    """Tests for BandGroup model."""

    def test_empty_group(self):
        """Test empty band group."""
        group = BandGroup(band_type=BandType.RGB)
        self.assertEqual(group.count, 0)

    def test_group_with_images(self):
        """Test group with images."""
        images = [
            ImageBandInfo(file_path=f"/data/img{i}.jpg", file_name=f"img{i}.jpg", band_type=BandType.RGB)
            for i in range(3)
        ]
        group = BandGroup(band_type=BandType.RGB, images=images)
        self.assertEqual(group.count, 3)


class TestDatasetBandManifest(unittest.TestCase):
    """Tests for DatasetBandManifest model."""

    def setUp(self):
        rgb_images = [
            ImageBandInfo(file_path="/data/rgb1.jpg", file_name="rgb1.jpg", band_type=BandType.RGB)
        ]
        nir_images = [
            ImageBandInfo(file_path="/data/nir1.tif", file_name="nir1.tif", band_type=BandType.NIR)
        ]
        self.manifest = DatasetBandManifest(
            dataset_id="ds-1",
            total_images=2,
            bands={
                "rgb": BandGroup(band_type=BandType.RGB, images=rgb_images),
                "nir": BandGroup(band_type=BandType.NIR, images=nir_images),
            },
            manufacturer=DroneManufacturer.DJI,
            is_multispectral=True,
        )

    def test_has_rgb(self):
        """Test has_rgb property."""
        self.assertTrue(self.manifest.has_rgb)

    def test_has_nir(self):
        """Test has_nir property."""
        self.assertTrue(self.manifest.has_nir)

    def test_available_bands(self):
        """Test available_bands property."""
        bands = self.manifest.available_bands
        self.assertIn(BandType.RGB, bands)
        self.assertIn(BandType.NIR, bands)

    def test_get_band_paths(self):
        """Test get_band_paths method."""
        rgb_paths = self.manifest.get_band_paths(BandType.RGB)
        self.assertEqual(len(rgb_paths), 1)
        self.assertEqual(rgb_paths[0].name, "rgb1.jpg")

    def test_get_band_paths_empty(self):
        """Test get_band_paths for nonexistent band."""
        paths = self.manifest.get_band_paths(BandType.THERMAL)
        self.assertEqual(paths, [])

    def test_empty_manifest(self):
        """Test empty manifest."""
        m = DatasetBandManifest(dataset_id="empty", total_images=0)
        self.assertFalse(m.has_rgb)
        self.assertFalse(m.has_nir)
        self.assertFalse(m.is_multispectral)
        self.assertEqual(m.available_bands, [])


class TestBandNameMaps(unittest.TestCase):
    """Tests for band name mapping dictionaries."""

    def test_dji_band_map_contains_rgb(self):
        """Test DJI map includes RGB mappings."""
        self.assertEqual(DJI_BAND_NAME_MAP["RGB"], BandType.RGB)
        self.assertEqual(DJI_BAND_NAME_MAP["NIR"], BandType.NIR)
        self.assertEqual(DJI_BAND_NAME_MAP["RedEdge"], BandType.RED_EDGE)

    def test_micasense_band_map(self):
        """Test MicaSense map."""
        self.assertEqual(MICASENSE_BAND_NAME_MAP["Blue"], BandType.BLUE)
        self.assertEqual(MICASENSE_BAND_NAME_MAP["NIR"], BandType.NIR)
        self.assertEqual(MICASENSE_BAND_NAME_MAP["Red edge"], BandType.RED_EDGE)

    def test_dji_filename_patterns(self):
        """Test DJI filename suffix patterns."""
        self.assertEqual(DJI_FILENAME_BAND_PATTERNS["_W"], BandType.RGB)
        self.assertEqual(DJI_FILENAME_BAND_PATTERNS["_MS_NIR"], BandType.NIR)

    def test_generic_filename_patterns(self):
        """Test generic filename patterns."""
        self.assertEqual(GENERIC_FILENAME_BAND_PATTERNS["_GRE"], BandType.GREEN)
        self.assertEqual(GENERIC_FILENAME_BAND_PATTERNS["_NIR"], BandType.NIR)

    def test_wavelength_map(self):
        """Test band wavelength map."""
        self.assertAlmostEqual(BAND_WAVELENGTH_MAP[BandType.NIR], 842.0)
        self.assertAlmostEqual(BAND_WAVELENGTH_MAP[BandType.RED], 668.0)

    def test_image_extensions(self):
        """Test image extensions set."""
        self.assertIn(".jpg", IMAGE_EXTENSIONS)
        self.assertIn(".tif", IMAGE_EXTENSIONS)
        self.assertIn(".dng", IMAGE_EXTENSIONS)


class TestScanDataset(unittest.TestCase):
    """Tests for scan_dataset function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_nonexistent_directory(self):
        """Test scanning nonexistent directory raises error."""
        from shared.band_detection.detector import scan_dataset
        with self.assertRaises(FileNotFoundError):
            scan_dataset(Path("/nonexistent/dir"), "ds-1")

    def test_scan_empty_directory(self):
        """Test scanning empty directory."""
        from shared.band_detection.detector import scan_dataset
        manifest = scan_dataset(Path(self.tmpdir), "ds-empty")
        self.assertEqual(manifest.total_images, 0)
        self.assertEqual(manifest.dataset_id, "ds-empty")

    @patch("shared.band_detection.detector.classify_image")
    def test_scan_with_images(self, mock_classify):
        """Test scanning directory with images."""
        from shared.band_detection.detector import scan_dataset

        (Path(self.tmpdir) / "img1.jpg").write_bytes(b"fake")
        (Path(self.tmpdir) / "img2.tif").write_bytes(b"fake")

        mock_classify.side_effect = [
            ImageBandInfo(
                file_path=str(Path(self.tmpdir) / "img1.jpg"),
                file_name="img1.jpg",
                band_type=BandType.RGB,
                manufacturer=DroneManufacturer.DJI,
                drone_model="Mavic",
            ),
            ImageBandInfo(
                file_path=str(Path(self.tmpdir) / "img2.tif"),
                file_name="img2.tif",
                band_type=BandType.NIR,
                manufacturer=DroneManufacturer.DJI,
                drone_model="Mavic",
            ),
        ]

        manifest = scan_dataset(Path(self.tmpdir), "ds-test")
        self.assertEqual(manifest.total_images, 2)
        self.assertTrue(manifest.is_multispectral)
        self.assertEqual(manifest.manufacturer, DroneManufacturer.DJI)
        self.assertIn("rgb", manifest.bands)
        self.assertIn("nir", manifest.bands)

    @patch("shared.band_detection.detector.classify_image")
    def test_scan_handles_errors(self, mock_classify):
        """Test scan handles classification errors."""
        from shared.band_detection.detector import scan_dataset

        (Path(self.tmpdir) / "broken.jpg").write_bytes(b"fake")
        mock_classify.side_effect = RuntimeError("corrupt image")

        manifest = scan_dataset(Path(self.tmpdir), "ds-err")
        self.assertEqual(manifest.total_images, 1)
        self.assertEqual(len(manifest.errors), 1)


class TestOrganizeByBand(unittest.TestCase):
    """Tests for organize_by_band function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dataset_dir = Path(self.tmpdir) / "dataset"
        self.dataset_dir.mkdir()
        self.images_dir = self.dataset_dir / "images"
        self.images_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_organize_moves_files(self):
        """Test organizing moves files into band folders."""
        from shared.band_detection.organizer import organize_by_band

        img1 = self.images_dir / "img1.jpg"
        img1.write_bytes(b"rgb-data")

        manifest = DatasetBandManifest(
            dataset_id="ds-org",
            total_images=1,
            bands={
                "rgb": BandGroup(
                    band_type=BandType.RGB,
                    images=[
                        ImageBandInfo(
                            file_path=str(img1),
                            file_name="img1.jpg",
                            band_type=BandType.RGB,
                        )
                    ],
                )
            },
        )

        dirs = organize_by_band(manifest, self.dataset_dir, move=True)
        self.assertIn("rgb", dirs)
        self.assertTrue((dirs["rgb"] / "img1.jpg").exists())

    def test_organize_copies_files(self):
        """Test organizing copies files when move=False."""
        from shared.band_detection.organizer import organize_by_band

        img1 = self.images_dir / "img2.tif"
        img1.write_bytes(b"nir-data")

        manifest = DatasetBandManifest(
            dataset_id="ds-org2",
            total_images=1,
            bands={
                "nir": BandGroup(
                    band_type=BandType.NIR,
                    images=[
                        ImageBandInfo(
                            file_path=str(img1),
                            file_name="img2.tif",
                            band_type=BandType.NIR,
                        )
                    ],
                )
            },
        )

        dirs = organize_by_band(manifest, self.dataset_dir, move=False)
        self.assertIn("nir", dirs)
        self.assertTrue((dirs["nir"] / "img2.tif").exists())
        self.assertTrue(img1.exists())

    def test_organize_missing_source_file_skips(self):
        """Test organizing with missing source file skips it gracefully."""
        from shared.band_detection.organizer import organize_by_band

        manifest = DatasetBandManifest(
            dataset_id="ds-org3",
            total_images=1,
            bands={
                "rgb": BandGroup(
                    band_type=BandType.RGB,
                    images=[
                        ImageBandInfo(
                            file_path="/nonexistent/img.jpg",
                            file_name="img.jpg",
                            band_type=BandType.RGB,
                        )
                    ],
                )
            },
        )

        dirs = organize_by_band(manifest, self.dataset_dir)
        self.assertIn("rgb", dirs)
        self.assertFalse((dirs["rgb"] / "img.jpg").exists())

    def test_organize_updates_path_when_destination_exists(self):
        """Test that file_path is updated even when destination already exists."""
        from shared.band_detection.organizer import organize_by_band

        src = self.images_dir / "img_dup.jpg"
        src.write_bytes(b"rgb-data")

        dst_dir = self.dataset_dir / "rgb"
        dst_dir.mkdir()
        dst = dst_dir / "img_dup.jpg"
        dst.write_bytes(b"rgb-data-existing")

        info = ImageBandInfo(
            file_path=str(src),
            file_name="img_dup.jpg",
            band_type=BandType.RGB,
        )
        manifest = DatasetBandManifest(
            dataset_id="ds-dup",
            total_images=1,
            bands={
                "rgb": BandGroup(
                    band_type=BandType.RGB,
                    images=[info],
                )
            },
        )

        organize_by_band(manifest, self.dataset_dir, move=True)

        self.assertEqual(info.file_path, str(dst))
        self.assertTrue(src.exists())
        self.assertTrue(dst.exists())


if __name__ == "__main__":
    unittest.main()
