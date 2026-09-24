"""Unit tests for GSD to max_image_size conversion utility"""
import unittest
import sys
from pathlib import Path

# Add root to path and import module directly to avoid cv2 dependency from __init__.py
root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_path))

# Import the module file directly to bypass __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "gsd_conversion",
    root_path / "shared" / "utils" / "gsd_conversion.py"
)
gsd_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gsd_module)

gsd_to_max_image_size = gsd_module.gsd_to_max_image_size
get_colmap_settings_for_gsd = gsd_module.get_colmap_settings_for_gsd


class TestGSDConversion(unittest.TestCase):
    """Test GSD conversion utility functions"""
    
    def test_gsd_to_max_image_size_basic(self):
        """Test basic GSD to max_image_size conversion"""
        # Base: GSD 5.0 → 2640px
        # GSD 10.0 (half resolution) → 1320px
        result = gsd_to_max_image_size(10.0)
        self.assertEqual(result, 1320)
    
    def test_gsd_to_max_image_size_higher_resolution(self):
        """Test conversion for higher resolution (lower GSD)"""
        # GSD 2.5 (double resolution) → 5280px
        result = gsd_to_max_image_size(2.5)
        self.assertEqual(result, 5280)
    
    def test_gsd_to_max_image_size_minimum_bound(self):
        """Test minimum bound is enforced (640px)"""
        # Very high GSD should clamp to 640
        result = gsd_to_max_image_size(100.0)
        self.assertEqual(result, 640)
    
    def test_gsd_to_max_image_size_maximum_bound(self):
        """Test maximum bound is enforced (8192px)"""
        # Very low GSD should clamp to 8192
        result = gsd_to_max_image_size(0.1)
        self.assertEqual(result, 8192)
    
    def test_gsd_to_max_image_size_custom_base(self):
        """Test conversion with custom base values"""
        # Custom base: 3000px at GSD 7.5
        result = gsd_to_max_image_size(
            gsd=15.0,
            base_size=3000,
            base_gsd=7.5
        )
        # 15.0 is double 7.5, so half the pixels
        self.assertEqual(result, 1500)
    
    def test_gsd_to_max_image_size_inverse_relationship(self):
        """Test that higher GSD yields lower max_image_size"""
        size_at_5 = gsd_to_max_image_size(5.0)
        size_at_10 = gsd_to_max_image_size(10.0)
        size_at_20 = gsd_to_max_image_size(20.0)
        
        self.assertGreater(size_at_5, size_at_10)
        self.assertGreater(size_at_10, size_at_20)
    
    def test_get_colmap_settings_for_gsd(self):
        """Test COLMAP settings dictionary generation"""
        settings = get_colmap_settings_for_gsd(10.0)
        
        # Should return all 4 required settings
        self.assertIn('feature_extraction_max_image_size', settings)
        self.assertIn('undistort_max_image_size', settings)
        self.assertIn('patch_match_max_image_size', settings)
        self.assertIn('fusion_max_image_size', settings)
        
        # All should have the same value
        expected_size = gsd_to_max_image_size(10.0)
        self.assertEqual(settings['feature_extraction_max_image_size'], expected_size)
        self.assertEqual(settings['undistort_max_image_size'], expected_size)
        self.assertEqual(settings['patch_match_max_image_size'], expected_size)
        self.assertEqual(settings['fusion_max_image_size'], expected_size)
    
    def test_get_colmap_settings_returns_integers(self):
        """Test that COLMAP settings return integer values"""
        settings = get_colmap_settings_for_gsd(7.5)
        
        for key, value in settings.items():
            self.assertIsInstance(value, int)
    
    def test_gsd_conversion_formula_accuracy(self):
        """Test the inverse proportional relationship formula"""
        # Formula: max_size = base_size * (base_gsd / target_gsd)
        # If we double the GSD, size should halve
        base_gsd = 5.0
        base_size = gsd_to_max_image_size(base_gsd)
        
        double_gsd = 10.0
        half_size = gsd_to_max_image_size(double_gsd)
        
        self.assertEqual(half_size, base_size // 2)
    
    def test_none_or_zero_gsd_handling(self):
        """Test handling of None or zero GSD values"""
        # None should raise TypeError (cannot compare None <= 0)
        with self.assertRaises(TypeError):
            gsd_to_max_image_size(None)
        
        # Zero GSD returns base_size (default 5280) with warning
        result = gsd_to_max_image_size(0.0)
        self.assertEqual(result, 5280)  # base_size default
    
    def test_negative_gsd_handling(self):
        """Test handling of negative GSD values"""
        # Negative GSD returns base_size (default 5280) with warning
        result = gsd_to_max_image_size(-10.0)
        self.assertEqual(result, 5280)  # base_size default
    
    def test_typical_gsd_ranges(self):
        """Test conversion for typical GSD values in drone imagery"""
        # Typical drone GSD range: 1-20 cm/px
        gsds = [1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 20.0]
        
        for gsd in gsds:
            result = gsd_to_max_image_size(gsd)
            # Should be within reasonable bounds
            self.assertGreaterEqual(result, 640)
            self.assertLessEqual(result, 8192)
            # Should be positive
            self.assertGreater(result, 0)


class TestGSDConversionIntegration(unittest.TestCase):
    """Integration tests for GSD conversion with COLMAP"""
    
    def test_settings_ready_for_colmap(self):
        """Test that generated settings are ready for COLMAP use"""
        gsd = 10.0
        settings = get_colmap_settings_for_gsd(gsd)
        
        # Verify all keys match COLMAP parameter names
        expected_keys = [
            'feature_extraction_max_image_size',
            'undistort_max_image_size',
            'patch_match_max_image_size',
            'fusion_max_image_size'
        ]
        
        for key in expected_keys:
            self.assertIn(key, settings)
            # Values should be valid COLMAP parameters (positive integers)
            self.assertIsInstance(settings[key], int)
            self.assertGreater(settings[key], 0)
    
    def test_consistency_across_pipeline_stages(self):
        """Test that all pipeline stages get consistent max_image_size"""
        gsd = 12.5
        settings = get_colmap_settings_for_gsd(gsd)
        
        # All stages should use the same max_image_size value
        values = list(settings.values())
        self.assertEqual(len(set(values)), 1, "All max_image_size values should be identical")


if __name__ == '__main__':
    unittest.main()
