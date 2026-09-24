"""Simple unit tests for GSD conversion without logger dependency"""
import unittest

# Base values from gsd_conversion.py
BASE_GSD_CM_PER_PX = 5.0  # 5 cm/px GSD
BASE_MAX_IMAGE_SIZE_PX = 2640  # pixels
MIN_IMAGE_SIZE = 640
MAX_IMAGE_SIZE = 8192


def gsd_to_max_image_size(target_gsd_cm_per_px: float) -> int:
    """
    Convert GSD (cm/pixel) to COLMAP max_image_size parameter.
    Inverse relationship: lower GSD (higher resolution) → larger max_image_size
    """
    if target_gsd_cm_per_px <= 0:
        raise ValueError("GSD must be positive")
    
    # Calculate: size = base_size * (base_gsd / target_gsd)
    max_image_size = int(BASE_MAX_IMAGE_SIZE_PX * (BASE_GSD_CM_PER_PX / target_gsd_cm_per_px))
    
    # Enforce bounds
    max_image_size = max(MIN_IMAGE_SIZE, min(max_image_size, MAX_IMAGE_SIZE))
    
    return max_image_size


def get_colmap_settings_for_gsd(target_gsd_cm_per_px: float) -> dict:
    """Get COLMAP SfM settings for target GSD"""
    max_image_size = gsd_to_max_image_size(target_gsd_cm_per_px)
    
    return {
        "max_image_size": max_image_size,
        "target_gsd_cm_per_px": target_gsd_cm_per_px,
        "estimated_resolution": f"{max_image_size}px"
    }


class TestGSDConversion(unittest.TestCase):
    """Test GSD conversion utility functions"""
    
    def test_gsd_to_max_image_size_basic(self):
        """Test basic GSD to max_image_size conversion"""
        result = gsd_to_max_image_size(10.0)
        self.assertEqual(result, 1320)
    
    def test_gsd_to_max_image_size_inverse_relationship(self):
        """Test inverse relationship: lower GSD → higher max_image_size"""
        size_1cm = gsd_to_max_image_size(1.0)
        size_5cm = gsd_to_max_image_size(5.0)
        size_10cm = gsd_to_max_image_size(10.0)
        
        self.assertGreater(size_1cm, size_5cm)
        self.assertGreater(size_5cm, size_10cm)
    
    def test_gsd_at_base_value(self):
        """Test GSD at base value returns base max_image_size"""
        result = gsd_to_max_image_size(5.0)
        self.assertEqual(result, 2640)
    
    def test_gsd_bounds_enforcement_max(self):
        """Test max_image_size capped at MAX_IMAGE_SIZE"""
        result = gsd_to_max_image_size(0.1)
        self.assertEqual(result, 8192)
    
    def test_gsd_bounds_enforcement_min(self):
        """Test max_image_size floored at MIN_IMAGE_SIZE"""
        result = gsd_to_max_image_size(100.0)
        self.assertEqual(result, 640)
    
    def test_gsd_typical_drone_values(self):
        """Test typical drone GSD values"""
        gsd_2cm = gsd_to_max_image_size(2.0)
        gsd_3cm = gsd_to_max_image_size(3.0)
        gsd_15cm = gsd_to_max_image_size(15.0)
        
        self.assertEqual(gsd_2cm, 6600)
        self.assertEqual(gsd_3cm, 4400)
        self.assertEqual(gsd_15cm, 880)
    
    def test_gsd_invalid_zero(self):
        """Test zero GSD raises ValueError"""
        with self.assertRaises(ValueError):
            gsd_to_max_image_size(0.0)
    
    def test_gsd_invalid_negative(self):
        """Test negative GSD raises ValueError"""
        with self.assertRaises(ValueError):
            gsd_to_max_image_size(-5.0)
    
    def test_get_colmap_settings_structure(self):
        """Test COLMAP settings dictionary structure"""
        settings = get_colmap_settings_for_gsd(5.0)
        
        self.assertIn('max_image_size', settings)
        self.assertIn('target_gsd_cm_per_px', settings)
        self.assertIn('estimated_resolution', settings)
    
    def test_get_colmap_settings_values(self):
        """Test COLMAP settings values are correct"""
        settings = get_colmap_settings_for_gsd(10.0)
        
        self.assertEqual(settings['max_image_size'], 1320)
        self.assertEqual(settings['target_gsd_cm_per_px'], 10.0)
        self.assertEqual(settings['estimated_resolution'], '1320px')
    
    def test_formula_accuracy_double_gsd(self):
        """Test formula accuracy when doubling GSD"""
        size_5cm = gsd_to_max_image_size(5.0)
        size_10cm = gsd_to_max_image_size(10.0)
        
        self.assertEqual(size_10cm, size_5cm // 2)
    
    def test_formula_accuracy_half_gsd(self):
        """Test formula accuracy when halving GSD"""
        size_10cm = gsd_to_max_image_size(10.0)
        size_5cm = gsd_to_max_image_size(5.0)
        
        self.assertEqual(size_5cm, size_10cm * 2)
    
    def test_precision_rounding(self):
        """Test rounding to integer pixels"""
        result = gsd_to_max_image_size(7.5)
        self.assertIsInstance(result, int)
        self.assertEqual(result, 1760)
    
    def test_colmap_integration(self):
        """Test settings ready for COLMAP SfM pipeline"""
        settings = get_colmap_settings_for_gsd(3.5)
        
        self.assertIsInstance(settings['max_image_size'], int)
        self.assertGreater(settings['max_image_size'], MIN_IMAGE_SIZE)
        self.assertLessEqual(settings['max_image_size'], MAX_IMAGE_SIZE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
