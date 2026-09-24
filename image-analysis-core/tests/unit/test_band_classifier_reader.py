"""Unit tests for shared/band_detection/band_classifier.py and metadata_reader.py."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

from shared.band_detection.band_classifier import (
    _detect_manufacturer,
    _classify_from_xmp_band_name,
    _classify_from_filename,
    _classify_from_channels,
    classify_image,
)
from shared.band_detection.models import BandType, DroneManufacturer
from shared.band_detection.metadata_reader import (
    extract_exif,
    _read_xmp_bytes,
    _parse_xmp_xml,
    _parse_xmp_regex_fallback,
    extract_xmp,
    extract_all_metadata,
    XMP_START_MARKER,
    XMP_END_MARKER,
)


class TestDetectManufacturer(unittest.TestCase):
    """Tests for _detect_manufacturer."""

    def test_dji_from_make(self):
        m = _detect_manufacturer({"Make": "DJI"})
        self.assertEqual(m, DroneManufacturer.DJI)

    def test_dji_from_drone_model(self):
        m = _detect_manufacturer({"DroneModel": "DJI Mavic 3M"})
        self.assertEqual(m, DroneManufacturer.DJI)

    def test_micasense_from_make(self):
        m = _detect_manufacturer({"Make": "MicaSense"})
        self.assertEqual(m, DroneManufacturer.MICASENSE)

    def test_micasense_from_camera_model(self):
        m = _detect_manufacturer({"Model": "RedEdge-MX"})
        self.assertEqual(m, DroneManufacturer.MICASENSE)

    def test_altum_from_camera_model(self):
        m = _detect_manufacturer({"Model": "Altum-PT"})
        self.assertEqual(m, DroneManufacturer.MICASENSE)

    def test_parrot(self):
        m = _detect_manufacturer({"Make": "Parrot"})
        self.assertEqual(m, DroneManufacturer.PARROT)

    def test_unknown(self):
        m = _detect_manufacturer({"Make": "Canon"})
        self.assertEqual(m, DroneManufacturer.UNKNOWN)

    def test_empty_metadata(self):
        m = _detect_manufacturer({})
        self.assertEqual(m, DroneManufacturer.UNKNOWN)

    def test_dji_from_software(self):
        m = _detect_manufacturer({"Software": "DJI v1.0"})
        self.assertEqual(m, DroneManufacturer.DJI)


class TestClassifyFromXMPBandName(unittest.TestCase):
    """Tests for _classify_from_xmp_band_name."""

    def test_dji_red(self):
        result = _classify_from_xmp_band_name(
            {"BandName": "Red"}, DroneManufacturer.DJI
        )
        self.assertIsNotNone(result)
        self.assertEqual(result[0], BandType.RED)

    def test_dji_nir(self):
        result = _classify_from_xmp_band_name(
            {"BandName": "NIR"}, DroneManufacturer.DJI
        )
        self.assertIsNotNone(result)
        self.assertEqual(result[0], BandType.NIR)

    def test_micasense_green(self):
        result = _classify_from_xmp_band_name(
            {"BandName": "Green"}, DroneManufacturer.MICASENSE
        )
        self.assertIsNotNone(result)
        self.assertEqual(result[0], BandType.GREEN)

    def test_empty_band_name(self):
        result = _classify_from_xmp_band_name(
            {"BandName": ""}, DroneManufacturer.DJI
        )
        self.assertIsNone(result)

    def test_no_band_name(self):
        result = _classify_from_xmp_band_name({}, DroneManufacturer.DJI)
        self.assertIsNone(result)

    def test_unknown_band_name(self):
        result = _classify_from_xmp_band_name(
            {"BandName": "Ultraviolet"}, DroneManufacturer.DJI
        )
        self.assertIsNone(result)


class TestClassifyFromFilename(unittest.TestCase):
    """Tests for _classify_from_filename."""

    def test_dji_ms_nir(self):
        result = _classify_from_filename("DJI_0001_MS_NIR")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], BandType.NIR)

    def test_dji_ms_red(self):
        result = _classify_from_filename("DJI_0001_MS_R")
        self.assertIsNotNone(result)

    def test_dji_ms_green(self):
        result = _classify_from_filename("DJI_0001_MS_G")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], BandType.GREEN)

    def test_no_match(self):
        result = _classify_from_filename("random_photo")
        self.assertIsNone(result)

    def test_case_insensitive(self):
        result = _classify_from_filename("DJI_0001_ms_nir")
        self.assertIsNotNone(result)


class TestClassifyFromChannels(unittest.TestCase):
    """Tests for _classify_from_channels."""

    @patch("shared.band_detection.band_classifier.Image")
    def test_rgb_image(self, mock_pil):
        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock()
        mock_pil.open.return_value = mock_img
        result = _classify_from_channels(Path("/fake/img.jpg"))
        self.assertEqual(result[0], BandType.RGB)

    @patch("shared.band_detection.band_classifier.Image")
    def test_grayscale_image(self, mock_pil):
        mock_img = MagicMock()
        mock_img.mode = "L"
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock()
        mock_pil.open.return_value = mock_img
        result = _classify_from_channels(Path("/fake/img.tif"))
        self.assertEqual(result[0], BandType.UNKNOWN)

    @patch("shared.band_detection.band_classifier.Image")
    def test_open_error(self, mock_pil):
        mock_pil.open.side_effect = Exception("Corrupt file")
        result = _classify_from_channels(Path("/fake/bad.jpg"))
        self.assertEqual(result[0], BandType.UNKNOWN)


class TestClassifyImage(unittest.TestCase):
    """Tests for classify_image."""

    @patch("shared.band_detection.band_classifier.extract_all_metadata")
    @patch("shared.band_detection.band_classifier.Image")
    def test_classify_xmp(self, mock_pil, mock_meta):
        mock_meta.return_value = {
            "Make": "DJI",
            "BandName": "Red",
            "DroneModel": "Mavic 3M",
        }
        result = classify_image(Path("/fake/img.tif"))
        self.assertEqual(result.band_type, BandType.RED)
        self.assertEqual(result.detection_method, "xmp_band_name")
        self.assertAlmostEqual(result.confidence, 0.95)

    @patch("shared.band_detection.band_classifier.extract_all_metadata")
    def test_classify_filename(self, mock_meta):
        mock_meta.return_value = {"Make": "DJI"}
        result = classify_image(Path("/fake/DJI_0001_MS_NIR.tif"))
        self.assertEqual(result.band_type, BandType.NIR)
        self.assertIn("filename_pattern", result.detection_method)
        self.assertAlmostEqual(result.confidence, 0.80)

    @patch("shared.band_detection.band_classifier.extract_all_metadata")
    @patch("shared.band_detection.band_classifier.Image")
    def test_classify_channels_fallback(self, mock_pil, mock_meta):
        mock_meta.return_value = {}
        mock_img = MagicMock()
        mock_img.mode = "RGB"
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock()
        mock_pil.open.return_value = mock_img
        result = classify_image(Path("/fake/photo.jpg"))
        self.assertEqual(result.band_type, BandType.RGB)
        self.assertIn("channel_heuristic", result.detection_method)

    @patch("shared.band_detection.band_classifier.extract_all_metadata")
    def test_classify_sensor_index(self, mock_meta):
        mock_meta.return_value = {
            "Make": "DJI",
            "BandName": "Green",
            "SensorIndex": "2",
            "CentralWavelength": "560",
        }
        result = classify_image(Path("/fake/img.tif"))
        self.assertEqual(result.sensor_index, 2)
        self.assertEqual(result.center_wavelength_nm, 560.0)


class TestExtractExif(unittest.TestCase):
    """Tests for extract_exif from metadata_reader."""

    @patch("shared.band_detection.metadata_reader.Image")
    def test_extract_basic(self, mock_pil):
        mock_img = MagicMock()
        mock_exif = {271: "DJI", 272: "Mavic 3M"}
        mock_img.getexif.return_value = mock_exif
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock()
        mock_pil.open.return_value = mock_img
        result = extract_exif(Path("/fake.jpg"))
        self.assertEqual(result["Make"], "DJI")

    @patch("shared.band_detection.metadata_reader.Image")
    def test_extract_empty(self, mock_pil):
        mock_img = MagicMock()
        mock_img.getexif.return_value = {}
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock()
        mock_pil.open.return_value = mock_img
        result = extract_exif(Path("/fake.jpg"))
        self.assertEqual(result, {})

    @patch("shared.band_detection.metadata_reader.Image")
    def test_extract_error(self, mock_pil):
        mock_pil.open.side_effect = Exception("Cannot open")
        result = extract_exif(Path("/bad.jpg"))
        self.assertEqual(result, {})


class TestReadXmpBytes(unittest.TestCase):
    """Tests for _read_xmp_bytes."""

    def test_with_xmp(self):
        xmp_content = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><data/></x:xmpmeta>'
        raw = b"PREFIX" + xmp_content + b"SUFFIX"
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(raw)
            f.flush()
            result = _read_xmp_bytes(Path(f.name))
        self.assertIsNotNone(result)
        self.assertIn(b"x:xmpmeta", result)

    def test_no_xmp(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"no xml here")
            f.flush()
            result = _read_xmp_bytes(Path(f.name))
        self.assertIsNone(result)

    def test_file_not_found(self):
        result = _read_xmp_bytes(Path("/nonexistent/img.jpg"))
        self.assertIsNone(result)


class TestParseXmpXml(unittest.TestCase):
    """Tests for _parse_xmp_xml."""

    def test_dji_xmp(self):
        xml = (
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            b'<rdf:Description'
            b' xmlns:drone-dji="http://www.dji.com/drone-dji/1.0/"'
            b' drone-dji:BandName="Red"'
            b' drone-dji:SensorIndex="1"'
            b'/>'
            b'</rdf:RDF></x:xmpmeta>'
        )
        result = _parse_xmp_xml(xml)
        self.assertIn("BandName", result)
        self.assertEqual(result["BandName"], "Red")

    def test_invalid_xml(self):
        result = _parse_xmp_xml(b"not valid xml")
        self.assertEqual(result, {})


class TestParseXmpRegexFallback(unittest.TestCase):
    """Tests for _parse_xmp_regex_fallback."""

    def test_dji_band_name(self):
        xmp = b'drone-dji:BandName="NIR" drone-dji:SensorIndex="3"'
        result = _parse_xmp_regex_fallback(xmp)
        self.assertEqual(result["BandName"], "NIR")
        self.assertEqual(result["SensorIndex"], "3")

    def test_camera_band_name(self):
        xmp = b'Camera:BandName="Green" Camera:CentralWavelength="560"'
        result = _parse_xmp_regex_fallback(xmp)
        self.assertEqual(result["BandName"], "Green")
        self.assertEqual(result["CentralWavelength"], "560")

    def test_empty(self):
        result = _parse_xmp_regex_fallback(b"no xmp properties here")
        self.assertEqual(result, {})


class TestExtractXmp(unittest.TestCase):
    """Tests for extract_xmp."""

    @patch("shared.band_detection.metadata_reader._read_xmp_bytes")
    def test_with_xmp(self, mock_read):
        mock_read.return_value = (
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            b'<rdf:Description '
            b'xmlns:drone-dji="http://www.dji.com/drone-dji/1.0/" '
            b'drone-dji:BandName="Red"/>'
            b'</rdf:RDF></x:xmpmeta>'
        )
        result = extract_xmp(Path("/fake.jpg"))
        self.assertIn("BandName", result)

    @patch("shared.band_detection.metadata_reader._read_xmp_bytes")
    def test_no_xmp(self, mock_read):
        mock_read.return_value = None
        result = extract_xmp(Path("/fake.jpg"))
        self.assertEqual(result, {})


class TestExtractAllMetadata(unittest.TestCase):
    """Tests for extract_all_metadata."""

    @patch("shared.band_detection.metadata_reader.extract_xmp")
    @patch("shared.band_detection.metadata_reader.extract_exif")
    def test_merge(self, mock_exif, mock_xmp):
        mock_exif.return_value = {"Make": "DJI", "Model": "FC330"}
        mock_xmp.return_value = {"BandName": "Red", "SensorIndex": "1"}
        result = extract_all_metadata(Path("/fake.jpg"))
        self.assertEqual(result["Make"], "DJI")
        self.assertEqual(result["BandName"], "Red")

    @patch("shared.band_detection.metadata_reader.extract_xmp")
    @patch("shared.band_detection.metadata_reader.extract_exif")
    def test_empty(self, mock_exif, mock_xmp):
        mock_exif.return_value = {}
        mock_xmp.return_value = {}
        result = extract_all_metadata(Path("/fake.jpg"))
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
