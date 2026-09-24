"""Unit tests for Product Upload API Views"""
import unittest
from unittest.mock import patch, MagicMock
import json
import uuid

from django.test import TestCase, RequestFactory
from django.conf import settings
from rest_framework import status

from products.views import (
    ProductUploadInitView,
    ProductChunkUploadView,
    ProductUploadCompleteView,
    UPLOAD_SESSIONS
)
from products.models import Product
from apps.uploads.infrastructure.models import Dataset
from apps.jobs.infra.db.models.models import ProcessingJob
from accounts.models import Organization, UserModel


class ProductUploadAPITest(TestCase):
    """Test Product upload API endpoints"""
    
    def setUp(self):
        """Set up test data and request factory"""
        self.factory = RequestFactory()
        self.secret_key = settings.AI_GATEWAY_SECRET_KEY
        
        # Create test user
        self.user = UserModel.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        
        # Create test organization
        self.org = Organization.objects.create(
            name="Test Org",
            user=self.user
        )
        
        # Create test dataset
        self.dataset = Dataset.objects.create(
            name="Test Dataset",
            org=self.org,
            crs="EPSG:4326"
        )
        
        # Create test job
        self.job = ProcessingJob.objects.create(
            dataset=self.dataset,
            resolution_gsd=10.0,
            radiometric_calibration=True,
            status='processing'
        )
        
        # Clear upload sessions
        UPLOAD_SESSIONS.clear()
    
    def tearDown(self):
        """Clean up after tests"""
        UPLOAD_SESSIONS.clear()
    
    @patch('products.views.S3Service')
    def test_init_upload_success(self, mock_s3_service):
        """Test successful product upload initialization"""
        # Mock S3 service
        mock_s3_instance = MagicMock()
        mock_s3_instance.init_multipart_upload.return_value = 'test-upload-id'
        mock_s3_service.return_value = mock_s3_instance
        
        # Create request
        request_data = {
            'job_id': str(self.job.id),
            'dataset_id': str(self.dataset.id),
            'product_type': 'orthomosaic',
            'file_name': 'orthomosaic.tif',
            'file_size': 1024000,
            'content_type': 'image/tiff',
            'resolution_cm': 10.0
        }
        
        request = self.factory.post(
            '/v1/api/products/upload/init/',
            data=json.dumps(request_data),
            content_type='application/json',
            HTTP_X_API_SECRET_KEY=self.secret_key
        )
        
        # Call view
        view = ProductUploadInitView.as_view()
        response = view(request)
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('product_id', response.data)
        self.assertIn('upload_id', response.data)
        self.assertIn('s3_upload_id', response.data)
        self.assertIn('s3_key', response.data)
        
        # Verify product created
        product_id = response.data['product_id']
        product = Product.objects.get(id=product_id)
        self.assertEqual(product.type, 'orthomosaic')
        self.assertEqual(product.dataset, self.dataset)
        self.assertEqual(product.job, self.job)
        
        # Verify upload session created
        upload_id = response.data['upload_id']
        self.assertIn(upload_id, UPLOAD_SESSIONS)
    
    def test_init_upload_unauthorized(self):
        """Test upload init with invalid secret key"""
        request_data = {
            'job_id': str(self.job.id),
            'dataset_id': str(self.dataset.id),
            'product_type': 'orthomosaic',
            'file_name': 'orthomosaic.tif',
            'file_size': 1024000
        }
        
        request = self.factory.post(
            '/v1/api/products/upload/init/',
            data=json.dumps(request_data),
            content_type='application/json',
            HTTP_X_API_SECRET_KEY='wrong-key'
        )
        
        view = ProductUploadInitView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_init_upload_job_not_found(self):
        """Test upload init with non-existent job"""
        request_data = {
            'job_id': str(uuid.uuid4()),
            'dataset_id': str(self.dataset.id),
            'product_type': 'orthomosaic',
            'file_name': 'orthomosaic.tif',
            'file_size': 1024000
        }
        
        request = self.factory.post(
            '/v1/api/products/upload/init/',
            data=json.dumps(request_data),
            content_type='application/json',
            HTTP_X_API_SECRET_KEY=self.secret_key
        )
        
        view = ProductUploadInitView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('products.views.S3Service')
    def test_chunk_upload_success(self, mock_s3_service):
        """Test successful chunk URL generation"""
        # Mock S3 service
        mock_s3_instance = MagicMock()
        mock_s3_instance.generate_presigned_url_part.return_value = 'https://s3.amazonaws.com/presigned-url'
        mock_s3_service.return_value = mock_s3_instance
        
        # Create upload session
        upload_id = str(uuid.uuid4())
        s3_upload_id = 'test-s3-upload-id'
        s3_key = 'products/test/orthomosaic.tif'
        
        UPLOAD_SESSIONS[upload_id] = {
            'product_id': str(uuid.uuid4()),
            's3_upload_id': s3_upload_id,
            's3_key': s3_key,
            'dataset_id': str(self.dataset.id),
            'job_id': str(self.job.id),
        }
        
        # Create request
        request_data = {
            'upload_id': upload_id,
            's3_upload_id': s3_upload_id,
            's3_key': s3_key,
            'part_number': 1
        }
        
        request = self.factory.post(
            '/v1/api/products/upload/chunk/',
            data=json.dumps(request_data),
            content_type='application/json',
            HTTP_X_API_SECRET_KEY=self.secret_key
        )
        
        view = ProductChunkUploadView.as_view()
        response = view(request)
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('url', response.data)
        self.assertIn('part_number', response.data)
        self.assertEqual(response.data['part_number'], 1)
    
    def test_chunk_upload_session_not_found(self):
        """Test chunk upload with invalid session"""
        request_data = {
            'upload_id': str(uuid.uuid4()),
            's3_upload_id': 'test-upload-id',
            's3_key': 'products/test/file.tif',
            'part_number': 1
        }
        
        request = self.factory.post(
            '/v1/api/products/upload/chunk/',
            data=json.dumps(request_data),
            content_type='application/json',
            HTTP_X_API_SECRET_KEY=self.secret_key
        )
        
        view = ProductChunkUploadView.as_view()
        response = view(request)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('products.views.S3Service')
    def test_complete_upload_success(self, mock_s3_service):
        """Test successful upload completion"""
        # Mock S3 service
        mock_s3_instance = MagicMock()
        mock_s3_service.return_value = mock_s3_instance
        
        # Create product and upload session
        product = Product.objects.create(
            dataset=self.dataset,
            job=self.job,
            type='orthomosaic',
            uri=''
        )
        
        upload_id = str(uuid.uuid4())
        s3_upload_id = 'test-s3-upload-id'
        s3_key = 'products/test/orthomosaic.tif'
        
        UPLOAD_SESSIONS[upload_id] = {
            'product_id': str(product.id),
            's3_upload_id': s3_upload_id,
            's3_key': s3_key,
            'dataset_id': str(self.dataset.id),
            'job_id': str(self.job.id),
        }
        
        # Create request
        parts = [
            {'ETag': 'etag1', 'PartNumber': 1},
            {'ETag': 'etag2', 'PartNumber': 2}
        ]
        
        request_data = {
            'upload_id': upload_id,
            's3_upload_id': s3_upload_id,
            's3_key': s3_key,
            'parts': parts
        }
        
        request = self.factory.post(
            '/v1/api/products/upload/complete/',
            data=json.dumps(request_data),
            content_type='application/json',
            HTTP_X_API_SECRET_KEY=self.secret_key
        )
        
        view = ProductUploadCompleteView.as_view()
        response = view(request)
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('product_id', response.data)
        self.assertIn('s3_uri', response.data)
        self.assertEqual(response.data['status'], 'completed')
        
        # Verify product URI updated
        product.refresh_from_db()
        self.assertEqual(product.uri, s3_key)
        
        # Verify session cleaned up
        self.assertNotIn(upload_id, UPLOAD_SESSIONS)


if __name__ == '__main__':
    unittest.main()
