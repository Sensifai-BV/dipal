"""Unit tests for Product model"""
import unittest
from django.test import TestCase
from django.contrib.gis.geos import Polygon
import uuid

from products.models import Product
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.infra.db.models.models import ProcessingJob
from accounts.models import Organization, UserModel


class ProductModelTest(TestCase):
    """Test Product model functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = UserModel.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        
        # Create organization
        self.org = Organization.objects.create(
            name="Test Organization",
            user=self.user
        )
        
        # Create dataset
        self.dataset = Dataset.objects.create(
            name="Test Dataset",
            org=self.org,
            crs="EPSG:4326"
        )
        
        # Create processing job
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=10.0,
            radiometric_calibration=True,
            status='pending'
        )
    
    def test_create_product(self):
        """Test creating a product"""
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri='products/test/orthomosaic.tif',
            resolution_cm=10.0
        )
        
        self.assertIsNotNone(product.id)
        self.assertEqual(product.type, 'orthomosaic')
        self.assertEqual(product.dataset, self.dataset)
        self.assertEqual(product.job, self.job)
    
    def test_product_type_choices(self):
        """Test all product type choices are valid"""
        valid_types = [choice[0] for choice in Product.PRODUCT_TYPE_CHOICES]
        
        for product_type in valid_types:
            product = Product.objects.create(
                dataset=self.dataset,
                job=self.job,
                type=product_type,
                uri=f'products/test/{product_type}.tif'
            )
            self.assertEqual(product.type, product_type)
    
    def test_product_display_name(self):
        """Test get_type_display returns correct display name"""
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri='products/test/orthomosaic.tif'
        )
        
        self.assertEqual(product.get_type_display(), '2D Orthomosaic')
    
    def test_product_category(self):
        """Test get_category returns correct category"""
        # 2D Raster
        product_2d = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri='products/test/orthomosaic.tif'
        )
        self.assertEqual(product_2d.get_category(), '2D Raster')
        
        # 3D Model
        product_3d = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='pointcloud',
            uri='products/test/pointcloud.ply'
        )
        self.assertEqual(product_3d.get_category(), '3D Model')
        
        # Reconstruction
        product_recon = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='sparse_reconstruction',
            uri='products/test/sparse.bin'
        )
        self.assertEqual(product_recon.get_category(), 'Reconstruction')
    
    def test_product_with_footprint(self):
        """Test creating product with PostGIS footprint"""
        footprint = Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)))
        
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri='products/test/orthomosaic.tif',
            footprint=footprint
        )
        
        self.assertIsNotNone(product.footprint)
        self.assertEqual(product.footprint.srid, 4326)
    
    def test_product_with_bands(self):
        """Test creating product with spectral bands"""
        bands = ['Red', 'Green', 'Blue', 'NIR']
        
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri='products/test/orthomosaic.tif',
            bands=bands
        )
        
        self.assertEqual(product.bands, bands)
        self.assertEqual(len(product.bands), 4)
    
    def test_product_with_stats(self):
        """Test creating product with statistics"""
        stats = {
            'min': 0.0,
            'max': 255.0,
            'mean': 127.5,
            'std': 50.0
        }
        
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='dsm',
            uri='products/test/dsm.tif',
            stats=stats
        )
        
        self.assertEqual(product.stats, stats)
        self.assertEqual(product.stats['mean'], 127.5)
    
    def test_product_string_representation(self):
        """Test product __str__ method"""
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='mesh',
            uri='products/test/mesh.ply'
        )
        
        str_repr = str(product)
        self.assertIn('3D Mesh Model', str_repr)
        self.assertIn(str(product.id), str_repr)
    
    def test_product_created_at_auto_set(self):
        """Test created_at is automatically set"""
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri='products/test/orthomosaic.tif'
        )
        
        self.assertIsNotNone(product.created_at)
    
    def test_multiple_products_per_job(self):
        """Test multiple products can be created for one job"""
        product1 = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri='products/test/orthomosaic.tif'
        )
        
        product2 = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='dsm',
            uri='products/test/dsm.tif'
        )
        
        products = Product.objects.filter(job=self.job)
        self.assertEqual(products.count(), 2)
    
    def test_product_dataset_relationship(self):
        """Test product-dataset relationship via related_name"""
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri='products/test/orthomosaic.tif'
        )
        
        dataset_products = self.dataset.products.all()
        self.assertEqual(dataset_products.count(), 1)
        self.assertEqual(dataset_products.first(), product)


if __name__ == '__main__':
    unittest.main()
