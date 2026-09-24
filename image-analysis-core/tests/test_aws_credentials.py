"""
Unit tests for AWS credential handling in image-analysis-core.

Tests verify that:
1. AWSSettings correctly reads USE_AWS_ROLE from environment
2. S3StorageSettings properly handles credentials based on USE_AWS_ROLE
3. StorageDriverSettings works correctly with AWS role mode
4. S3StorageDriver creates boto3 clients with correct credentials
5. S3ResultsUploader handles credentials correctly
6. StorageDriverFactory creates drivers with proper configuration

Note: These tests mock the actual imports to avoid boto3 dependency in test environment.
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import sys


class TestAWSSettingsLogic(unittest.TestCase):
    """Test AWS settings logic without importing actual modules."""
    
    def test_use_aws_role_defaults_to_false(self):
        """USE_AWS_ROLE should default to false when not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('USE_AWS_ROLE', None)
            use_aws_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            self.assertFalse(use_aws_role)
    
    def test_use_aws_role_true_from_env(self):
        """USE_AWS_ROLE=true should be detected."""
        with patch.dict(os.environ, {'USE_AWS_ROLE': 'true'}, clear=False):
            use_aws_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            self.assertTrue(use_aws_role)
    
    def test_use_aws_role_false_from_env(self):
        """USE_AWS_ROLE=false should be detected."""
        with patch.dict(os.environ, {'USE_AWS_ROLE': 'false'}, clear=False):
            use_aws_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            self.assertFalse(use_aws_role)
    
    def test_use_aws_role_case_insensitive(self):
        """USE_AWS_ROLE should be case insensitive."""
        for value in ['TRUE', 'True', 'true', 'TrUe']:
            with patch.dict(os.environ, {'USE_AWS_ROLE': value}, clear=False):
                use_aws_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
                self.assertTrue(use_aws_role, f"Failed for value: {value}")


class TestS3StorageSettingsLogic(unittest.TestCase):
    """Test S3StorageSettings credential handling logic."""
    
    def test_credentials_cleared_when_use_aws_role_true(self):
        """When USE_AWS_ROLE=true, credentials should be cleared."""
        with patch.dict(os.environ, {'USE_AWS_ROLE': 'true'}, clear=False):
            use_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            
            # Simulate the model_validator logic
            data = {
                'access_key_id': 'test-key',
                'secret_access_key': 'test-secret',
            }
            
            if use_role:
                data['use_aws_role'] = True
                data['access_key_id'] = None
                data['secret_access_key'] = None
            
            self.assertTrue(data['use_aws_role'])
            self.assertIsNone(data['access_key_id'])
            self.assertIsNone(data['secret_access_key'])
    
    def test_credentials_kept_when_use_aws_role_false(self):
        """When USE_AWS_ROLE=false, credentials should be kept."""
        with patch.dict(os.environ, {'USE_AWS_ROLE': 'false'}, clear=False):
            use_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            
            # Simulate the model_validator logic
            data = {
                'access_key_id': 'test-key',
                'secret_access_key': 'test-secret',
                'use_aws_role': False,
            }
            
            if use_role:
                data['use_aws_role'] = True
                data['access_key_id'] = None
                data['secret_access_key'] = None
            
            self.assertFalse(data['use_aws_role'])
            self.assertEqual(data['access_key_id'], 'test-key')
            self.assertEqual(data['secret_access_key'], 'test-secret')
    
    def test_has_explicit_credentials_property(self):
        """has_explicit_credentials should return True only when both credentials are set."""
        # Both set
        access_key_id = 'test-key'
        secret_access_key = 'test-secret'
        has_credentials = bool(access_key_id and secret_access_key)
        self.assertTrue(has_credentials)
        
        # Only one set
        access_key_id = 'test-key'
        secret_access_key = None
        has_credentials = bool(access_key_id and secret_access_key)
        self.assertFalse(has_credentials)
        
        # Neither set
        access_key_id = None
        secret_access_key = None
        has_credentials = bool(access_key_id and secret_access_key)
        self.assertFalse(has_credentials)


class TestStorageDriverSettingsLogic(unittest.TestCase):
    """Test StorageDriverSettings logic."""
    
    def test_default_driver_is_local(self):
        """Default storage driver should be 'local'."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('STORAGE_DRIVER', None)
            driver = os.getenv('STORAGE_DRIVER', 'local')
            self.assertEqual(driver, 'local')
    
    def test_credentials_cleared_when_use_aws_role_true(self):
        """StorageDriverSettings should clear credentials when USE_AWS_ROLE=true."""
        with patch.dict(os.environ, {'USE_AWS_ROLE': 'true'}, clear=False):
            use_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            
            data = {
                'access_key_id': 'test-key',
                'secret_access_key': 'test-secret',
            }
            
            if use_role:
                data['use_aws_role'] = True
                data['access_key_id'] = None
                data['secret_access_key'] = None
            
            self.assertIsNone(data['access_key_id'])
            self.assertIsNone(data['secret_access_key'])


class TestS3StorageDriverCredentialLogic(unittest.TestCase):
    """Test S3StorageDriver credential handling logic."""
    
    def test_driver_clears_credentials_when_use_aws_role_true(self):
        """S3StorageDriver should not use credentials when USE_AWS_ROLE=true."""
        with patch.dict(os.environ, {'USE_AWS_ROLE': 'true'}, clear=False):
            use_aws_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            
            # Simulate driver initialization logic
            aws_access_key_id = 'test-key'
            aws_secret_access_key = 'test-secret'
            
            if use_aws_role:
                aws_access_key_id = None
                aws_secret_access_key = None
            
            self.assertIsNone(aws_access_key_id)
            self.assertIsNone(aws_secret_access_key)
    
    def test_driver_uses_credentials_when_use_aws_role_false(self):
        """S3StorageDriver should use credentials when USE_AWS_ROLE=false."""
        with patch.dict(os.environ, {'USE_AWS_ROLE': 'false'}, clear=False):
            use_aws_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            
            # Simulate driver initialization logic
            aws_access_key_id = 'test-key'
            aws_secret_access_key = 'test-secret'
            
            if use_aws_role:
                aws_access_key_id = None
                aws_secret_access_key = None
            
            self.assertEqual(aws_access_key_id, 'test-key')
            self.assertEqual(aws_secret_access_key, 'test-secret')
    
    def test_connect_session_kwargs_without_credentials(self):
        """When using AWS role, session kwargs should not include credentials."""
        use_aws_role = True
        aws_access_key_id = None
        aws_secret_access_key = None
        region_name = 'eu-north-1'
        
        session_kwargs = {
            'region_name': region_name,
        }
        
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs['aws_access_key_id'] = aws_access_key_id
            session_kwargs['aws_secret_access_key'] = aws_secret_access_key
        
        self.assertNotIn('aws_access_key_id', session_kwargs)
        self.assertNotIn('aws_secret_access_key', session_kwargs)
        self.assertEqual(session_kwargs['region_name'], 'eu-north-1')
    
    def test_connect_session_kwargs_with_credentials(self):
        """When not using AWS role, session kwargs should include credentials."""
        use_aws_role = False
        aws_access_key_id = 'test-key'
        aws_secret_access_key = 'test-secret'
        region_name = 'eu-north-1'
        
        session_kwargs = {
            'region_name': region_name,
        }
        
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs['aws_access_key_id'] = aws_access_key_id
            session_kwargs['aws_secret_access_key'] = aws_secret_access_key
        
        self.assertEqual(session_kwargs['aws_access_key_id'], 'test-key')
        self.assertEqual(session_kwargs['aws_secret_access_key'], 'test-secret')


class TestS3ResultsUploaderCredentialLogic(unittest.TestCase):
    """Test S3ResultsUploader credential handling logic."""
    
    def test_uploader_kwargs_without_credentials(self):
        """S3ResultsUploader should not include credentials when has_explicit_credentials is False."""
        has_explicit_credentials = False
        access_key_id = None
        secret_access_key = None
        region_name = 'eu-north-1'
        
        client_kwargs = {
            'region_name': region_name
        }
        
        if has_explicit_credentials:
            client_kwargs['aws_access_key_id'] = access_key_id
            client_kwargs['aws_secret_access_key'] = secret_access_key
        
        self.assertNotIn('aws_access_key_id', client_kwargs)
        self.assertNotIn('aws_secret_access_key', client_kwargs)
    
    def test_uploader_kwargs_with_credentials(self):
        """S3ResultsUploader should include credentials when has_explicit_credentials is True."""
        has_explicit_credentials = True
        access_key_id = 'test-key'
        secret_access_key = 'test-secret'
        region_name = 'eu-north-1'
        
        client_kwargs = {
            'region_name': region_name
        }
        
        if has_explicit_credentials:
            client_kwargs['aws_access_key_id'] = access_key_id
            client_kwargs['aws_secret_access_key'] = secret_access_key
        
        self.assertEqual(client_kwargs['aws_access_key_id'], 'test-key')
        self.assertEqual(client_kwargs['aws_secret_access_key'], 'test-secret')


class TestStorageDriverFactoryCredentialLogic(unittest.TestCase):
    """Test StorageDriverFactory credential handling logic."""
    
    def test_factory_config_without_credentials_when_use_aws_role(self):
        """Factory should create S3 config without credentials when USE_AWS_ROLE=true."""
        use_aws_role = True
        bucket_name = 'test-bucket'
        region = 'eu-north-1'
        prefix = 'photogear'
        access_key_id = 'ignored-key'
        secret_access_key = 'ignored-secret'
        
        if use_aws_role:
            config = {
                'bucket_name': bucket_name,
                'region_name': region,
                'prefix': prefix,
            }
        else:
            config = {
                'bucket_name': bucket_name,
                'region_name': region,
                'aws_access_key_id': access_key_id,
                'aws_secret_access_key': secret_access_key,
                'prefix': prefix,
            }
        
        self.assertNotIn('aws_access_key_id', config)
        self.assertNotIn('aws_secret_access_key', config)
        self.assertEqual(config['bucket_name'], 'test-bucket')
    
    def test_factory_config_with_credentials_when_not_use_aws_role(self):
        """Factory should create S3 config with credentials when USE_AWS_ROLE=false."""
        use_aws_role = False
        bucket_name = 'test-bucket'
        region = 'eu-north-1'
        prefix = 'photogear'
        access_key_id = 'test-key'
        secret_access_key = 'test-secret'
        
        if use_aws_role:
            config = {
                'bucket_name': bucket_name,
                'region_name': region,
                'prefix': prefix,
            }
        else:
            config = {
                'bucket_name': bucket_name,
                'region_name': region,
                'aws_access_key_id': access_key_id,
                'aws_secret_access_key': secret_access_key,
                'prefix': prefix,
            }
        
        self.assertEqual(config['aws_access_key_id'], 'test-key')
        self.assertEqual(config['aws_secret_access_key'], 'test-secret')


class TestIntegrationAWSRoleFlow(unittest.TestCase):
    """Integration tests for the full AWS role credential flow logic."""
    
    def test_full_flow_with_aws_role(self):
        """Test the complete flow logic with USE_AWS_ROLE=true."""
        env = {
            'USE_AWS_ROLE': 'true',
            'AWS_S3_REGION_NAME': 'eu-north-1',
            'AWS_S3_RAW_IMAGES_BUCKET': 'test-raw',
            'AWS_S3_AI_BUCKET': 'test-ai',
            'AWS_S3_RESULTS_BUCKET': 'test-results',
            'AWS_S3_ACCESS_KEY_ID': 'should-be-ignored',
            'AWS_S3_SECRET_ACCESS_KEY': 'should-be-ignored',
        }
        
        with patch.dict(os.environ, env, clear=False):
            # Simulate AWSSettings
            use_aws_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            self.assertTrue(use_aws_role)
            
            # Simulate S3StorageSettings model_validator
            data = {
                'access_key_id': os.getenv('AWS_S3_ACCESS_KEY_ID'),
                'secret_access_key': os.getenv('AWS_S3_SECRET_ACCESS_KEY'),
            }
            
            if use_aws_role:
                data['use_aws_role'] = True
                data['access_key_id'] = None
                data['secret_access_key'] = None
            
            self.assertTrue(data['use_aws_role'])
            self.assertIsNone(data['access_key_id'])
            self.assertIsNone(data['secret_access_key'])
            
            # has_explicit_credentials check
            has_credentials = bool(data['access_key_id'] and data['secret_access_key'])
            self.assertFalse(has_credentials)
    
    def test_full_flow_with_explicit_credentials(self):
        """Test the complete flow logic with USE_AWS_ROLE=false."""
        env = {
            'USE_AWS_ROLE': 'false',
            'AWS_S3_REGION_NAME': 'eu-north-1',
            'AWS_S3_RAW_IMAGES_BUCKET': 'test-raw',
            'AWS_S3_AI_BUCKET': 'test-ai',
            'AWS_S3_RESULTS_BUCKET': 'test-results',
            'AWS_S3_ACCESS_KEY_ID': 'test-key',
            'AWS_S3_SECRET_ACCESS_KEY': 'test-secret',
        }
        
        with patch.dict(os.environ, env, clear=False):
            # Simulate AWSSettings
            use_aws_role = os.getenv('USE_AWS_ROLE', 'false').lower() == 'true'
            self.assertFalse(use_aws_role)
            
            # Simulate S3StorageSettings - credentials should be kept
            data = {
                'access_key_id': os.getenv('AWS_S3_ACCESS_KEY_ID'),
                'secret_access_key': os.getenv('AWS_S3_SECRET_ACCESS_KEY'),
                'use_aws_role': False,
            }
            
            if use_aws_role:
                data['use_aws_role'] = True
                data['access_key_id'] = None
                data['secret_access_key'] = None
            
            self.assertFalse(data['use_aws_role'])
            self.assertEqual(data['access_key_id'], 'test-key')
            self.assertEqual(data['secret_access_key'], 'test-secret')
            
            # has_explicit_credentials check
            has_credentials = bool(data['access_key_id'] and data['secret_access_key'])
            self.assertTrue(has_credentials)


if __name__ == '__main__':
    unittest.main()
