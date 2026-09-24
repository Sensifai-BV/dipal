"""
Integration tests for the AI Job Pipeline.

Test environment:
- API Gateway: 192.168.254.8:8080
- Backend: 192.168.254.8:8000
- Redis: 192.168.254.8:6378
- Sub-services (SFM, Orthomosaic, Radiometric): 192.168.254.48

Tests verify the complete pipeline flow with:
- GSD: 10
- Radiometric Calibration: True
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any

import aiohttp
import pytest
import redis

# Test configuration
@dataclass
class IntegrationTestConfig:
    """Test environment configuration."""
    # Service URLs (full URLs, no host+port construction)
    api_gateway_url: str = "http://192.168.254.8:8080"
    backend_url: str = "http://192.168.254.8:8000"
    
    # Redis
    redis_host: str = "192.168.254.8"
    redis_port: int = 6378
    redis_db: int = 0
    redis_job_prefix: str = "photogear:job:"
    
    # Sub-service URLs
    calibration_url: str = "http://192.168.254.48:8001"
    sfm_url: str = "http://192.168.254.48:8002"
    orthomosaic_url: str = "http://192.168.254.48:8003"
    
    # Test parameters
    gsd: float = 10.0
    radiometric_calibration: bool = True
    
    @property
    def calibration_url(self) -> str:
        return f"http://{self.subservices_host}:{self.calibration_port}"
    
    @property
    def sfm_url(self) -> str:
        return f"http://{self.subservices_host}:{self.sfm_port}"
    
    @property
    def orthomosaic_url(self) -> str:
        return f"http://{self.subservices_host}:{self.orthomosaic_port}"


config = IntegrationTestConfig()


class TestServiceHealth:
    """Test that all services are running and healthy."""
    
    @pytest.mark.asyncio
    async def test_api_gateway_health(self):
        """Test API Gateway is accessible via OpenAPI docs."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{config.api_gateway_url}/openapi.json") as response:
                assert response.status == 200, f"API Gateway not accessible: {await response.text()}"
                data = await response.json()
                assert "openapi" in data
                print(f"✅ API Gateway running: {data.get('info', {}).get('title', 'Unknown')}")
    
    @pytest.mark.asyncio
    async def test_calibration_service_health(self):
        """Test Calibration service is accessible."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{config.calibration_url}/openapi.json", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    assert response.status == 200, f"Calibration service not accessible"
                    data = await response.json()
                    print(f"✅ Calibration service running: {data.get('info', {}).get('title', 'Unknown')}")
            except aiohttp.ClientError as e:
                pytest.fail(f"❌ Calibration service not reachable: {e}")
    
    @pytest.mark.asyncio
    async def test_sfm_service_health(self):
        """Test SFM service is accessible."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{config.sfm_url}/openapi.json", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    assert response.status == 200, f"SFM service not accessible"
                    data = await response.json()
                    print(f"✅ SFM service running: {data.get('info', {}).get('title', 'Unknown')}")
            except aiohttp.ClientError as e:
                pytest.fail(f"❌ SFM service not reachable: {e}")
    
    @pytest.mark.asyncio
    async def test_orthomosaic_service_health(self):
        """Test Orthomosaic service is accessible."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{config.orthomosaic_url}/openapi.json", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    assert response.status == 200, f"Orthomosaic service not accessible"
                    data = await response.json()
                    print(f"✅ Orthomosaic service running: {data.get('info', {}).get('title', 'Unknown')}")
            except aiohttp.ClientError as e:
                pytest.fail(f"❌ Orthomosaic service not reachable: {e}")
    
    def test_redis_connection(self):
        """Test Redis is accessible."""
        try:
            r = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                decode_responses=True,
            )
            pong = r.ping()
            assert pong is True, "Redis ping failed"
            print(f"✅ Redis connected: PONG={pong}")
            r.close()
        except redis.ConnectionError as e:
            pytest.fail(f"❌ Redis not reachable: {e}")


class TestRedisJobState:
    """Test Redis job state management."""
    
    def setup_method(self):
        """Set up Redis connection for each test."""
        self.redis = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True,
        )
    
    def teardown_method(self):
        """Clean up Redis connection."""
        self.redis.close()
    
    def test_redis_job_key_format(self):
        """Test that job keys follow expected format."""
        # Create a test job via API and check Redis key
        test_job_id = f"test-{uuid.uuid4()}"
        expected_key = f"{config.redis_job_prefix}{test_job_id}"
        
        # Set a test value
        self.redis.set(expected_key, '{"test": true}')
        
        # Verify it exists
        assert self.redis.exists(expected_key) == 1
        
        # Clean up
        self.redis.delete(expected_key)
        print(f"✅ Redis key format correct: {expected_key}")
    
    def test_list_existing_jobs(self):
        """List all existing job keys in Redis."""
        keys = self.redis.keys(f"{config.redis_job_prefix}*")
        print(f"📋 Found {len(keys)} job keys in Redis:")
        for key in keys[:10]:  # Show first 10
            print(f"   - {key}")
        if len(keys) > 10:
            print(f"   ... and {len(keys) - 10} more")


class TestJobSubmission:
    """Test job submission to the API Gateway."""
    
    @pytest.mark.asyncio
    async def test_submit_job_with_gsd_and_radiometric(self):
        """Test submitting a job with GSD=10 and radiometric_calibration=True."""
        job_id = f"integration-test-{uuid.uuid4()}"
        dataset_id = f"test-dataset-{uuid.uuid4()}"
        
        payload = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "download_url": "s3://test-bucket/test-dataset.zip",  # Mock URL for testing
            "parameters": {
                "gsd": config.gsd,
                "radiometric_calibration": config.radiometric_calibration,
            },
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.api_gateway_url}/jobs/run",
                json=payload,
            ) as response:
                assert response.status == 200, f"Job submission failed: {await response.text()}"
                data = await response.json()
                
                assert data["job_id"] == job_id
                assert data["status"] in ["running", "pending", "queued"]
                print(f"✅ Job submitted successfully:")
                print(f"   Job ID: {data['job_id']}")
                print(f"   Status: {data['status']}")
                print(f"   GSD: {config.gsd}")
                print(f"   Radiometric: {config.radiometric_calibration}")
                
                return data
    
    @pytest.mark.asyncio
    async def test_submit_job_and_check_redis_state(self):
        """Test that submitted job creates state in Redis."""
        job_id = f"redis-state-test-{uuid.uuid4()}"
        dataset_id = f"test-dataset-{uuid.uuid4()}"
        
        payload = {
            "job_id": job_id,
            "dataset_id": dataset_id,
            "download_url": "s3://test-bucket/test-dataset.zip",
            "parameters": {
                "gsd": config.gsd,
                "radiometric_calibration": config.radiometric_calibration,
            },
        }
        
        async with aiohttp.ClientSession() as session:
            # Submit job
            async with session.post(
                f"{config.api_gateway_url}/jobs/run",
                json=payload,
            ) as response:
                assert response.status == 200
        
        # Wait a moment for Redis state to be created
        await asyncio.sleep(0.5)
        
        # Check Redis
        r = redis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True,
        )
        
        job_key = f"{config.redis_job_prefix}{job_id}"
        exists = r.exists(job_key)
        
        if exists:
            job_data = r.get(job_key)
            print(f"✅ Job state found in Redis:")
            print(f"   Key: {job_key}")
            print(f"   Data: {job_data[:200]}..." if len(job_data) > 200 else f"   Data: {job_data}")
        else:
            print(f"⚠️ Job key not found in Redis: {job_key}")
        
        r.close()
        assert exists == 1, f"Job state not created in Redis for {job_id}"


class TestJobStatus:
    """Test job status retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_job_status(self):
        """Test retrieving job status."""
        # First submit a job
        job_id = f"status-test-{uuid.uuid4()}"
        
        payload = {
            "job_id": job_id,
            "dataset_id": f"test-dataset-{uuid.uuid4()}",
            "download_url": "s3://test-bucket/test-dataset.zip",
            "parameters": {
                "gsd": config.gsd,
                "radiometric_calibration": config.radiometric_calibration,
            },
        }
        
        async with aiohttp.ClientSession() as session:
            # Submit
            async with session.post(
                f"{config.api_gateway_url}/jobs/run",
                json=payload,
            ) as response:
                assert response.status == 200
            
            # Wait a moment
            await asyncio.sleep(0.5)
            
            # Get status
            async with session.get(
                f"{config.api_gateway_url}/jobs/{job_id}/status",
            ) as response:
                assert response.status == 200
                data = await response.json()
                
                print(f"✅ Job status retrieved:")
                print(f"   Job ID: {data['job_id']}")
                print(f"   Status: {data['status']}")
                print(f"   Progress: {data.get('progress')}")
                print(f"   Current Stage: {data.get('current_stage')}")
                
                assert data["job_id"] == job_id
                return data
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_job_status(self):
        """Test retrieving status of non-existent job."""
        fake_job_id = f"nonexistent-{uuid.uuid4()}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{config.api_gateway_url}/jobs/{fake_job_id}/status",
            ) as response:
                assert response.status == 200  # Should return 200 with not_found status
                data = await response.json()
                
                assert data["status"] == "not_found"
                print(f"✅ Non-existent job returns correct status: {data['status']}")


class TestJobCancellation:
    """Test job cancellation."""
    
    @pytest.mark.asyncio
    async def test_cancel_job(self):
        """Test cancelling a running job."""
        job_id = f"cancel-test-{uuid.uuid4()}"
        
        payload = {
            "job_id": job_id,
            "dataset_id": f"test-dataset-{uuid.uuid4()}",
            "download_url": "s3://test-bucket/test-dataset.zip",
            "parameters": {
                "gsd": config.gsd,
                "radiometric_calibration": config.radiometric_calibration,
            },
        }
        
        async with aiohttp.ClientSession() as session:
            # Submit
            async with session.post(
                f"{config.api_gateway_url}/jobs/run",
                json=payload,
            ) as response:
                assert response.status == 200
            
            # Cancel immediately
            async with session.post(
                f"{config.api_gateway_url}/jobs/{job_id}/cancel",
            ) as response:
                assert response.status == 200
                data = await response.json()
                
                print(f"✅ Job cancellation response:")
                print(f"   Job ID: {data['job_id']}")
                print(f"   Cancelled: {data['cancelled']}")
                print(f"   Message: {data['message']}")


class TestPipelineStages:
    """Test individual pipeline stages."""
    
    @pytest.mark.asyncio
    async def test_radiometric_service_direct(self):
        """Test calling radiometric service directly."""
        job_id = f"radiometric-direct-{uuid.uuid4()}"
        
        payload = {
            "job_id": job_id,
            "dataset_id": f"test-dataset-{uuid.uuid4()}",
            "download_url": "s3://test-bucket/test-dataset.zip",
            "parameters": {},
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{config.calibration_url}/calibration/run",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    print(f"📡 Radiometric service response status: {response.status}")
                    data = await response.json()
                    print(f"   Response: {data}")
            except aiohttp.ClientError as e:
                print(f"⚠️ Radiometric service error: {e}")
    
    @pytest.mark.asyncio
    async def test_sfm_service_direct(self):
        """Test calling SFM service directly."""
        job_id = f"sfm-direct-{uuid.uuid4()}"
        
        payload = {
            "job_id": job_id,
            "dataset_id": f"test-dataset-{uuid.uuid4()}",
            "download_url": "s3://test-bucket/test-dataset.zip",
            "parameters": {
                "gsd": config.gsd,
            },
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{config.sfm_url}/sfm/run",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    print(f"📡 SFM service response status: {response.status}")
                    data = await response.json()
                    print(f"   Response: {data}")
            except aiohttp.ClientError as e:
                print(f"⚠️ SFM service error: {e}")
    
    @pytest.mark.asyncio
    async def test_orthomosaic_service_direct(self):
        """Test calling Orthomosaic service directly."""
        job_id = f"ortho-direct-{uuid.uuid4()}"
        
        payload = {
            "job_id": job_id,
            "dataset_id": f"test-dataset-{uuid.uuid4()}",
            "input_path": "s3://test-bucket/sfm-output",
            "parameters": {
                "gsd": config.gsd,
            },
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{config.orthomosaic_url}/orthomosaic/run",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    print(f"📡 Orthomosaic service response status: {response.status}")
                    data = await response.json()
                    print(f"   Response: {data}")
            except aiohttp.ClientError as e:
                print(f"⚠️ Orthomosaic service error: {e}")


class TestCallbackMechanism:
    """Test callback mechanism from sub-services."""
    
    @pytest.mark.asyncio
    async def test_subservice_callback_endpoint_exists(self):
        """Test that the subservice callback endpoint exists."""
        async with aiohttp.ClientSession() as session:
            # Test with a mock callback (should fail validation but endpoint should exist)
            payload = {
                "job_id": f"callback-test-{uuid.uuid4()}",
                "stage": "sfm",
                "status": "completed",
                "result": {"test": True},
            }
            
            async with session.post(
                f"{config.api_gateway_url}/jobs/subservice-callback",
                json=payload,
            ) as response:
                # We expect either 200 (success) or 4xx (validation error), not 404
                assert response.status != 404, "Callback endpoint not found"
                print(f"✅ Callback endpoint exists, response: {response.status}")


class TestEndToEndPipeline:
    """End-to-end pipeline tests (requires real data)."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_pipeline_with_real_data(self):
        """
        Test full pipeline with real data.
        
        NOTE: This test requires:
        - Real dataset in S3
        - All services running
        - Sufficient time for processing
        
        Skip if not in full integration mode.
        """
        pytest.skip("Full pipeline test requires real data - run manually with --run-slow")
    
    @pytest.mark.asyncio
    async def test_pipeline_job_flow_monitoring(self):
        """Monitor a job through its pipeline stages."""
        job_id = f"flow-monitor-{uuid.uuid4()}"
        
        payload = {
            "job_id": job_id,
            "dataset_id": f"test-dataset-{uuid.uuid4()}",
            "download_url": "s3://test-bucket/test-dataset.zip",
            "parameters": {
                "gsd": config.gsd,
                "radiometric_calibration": config.radiometric_calibration,
            },
        }
        
        async with aiohttp.ClientSession() as session:
            # Submit job
            async with session.post(
                f"{config.api_gateway_url}/jobs/run",
                json=payload,
            ) as response:
                assert response.status == 200
                print(f"✅ Job submitted: {job_id}")
            
            # Poll status for a few seconds
            stages_seen = set()
            for i in range(10):
                await asyncio.sleep(1)
                
                async with session.get(
                    f"{config.api_gateway_url}/jobs/{job_id}/status",
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        current_stage = data.get("current_stage")
                        status = data.get("status")
                        progress = data.get("progress", 0)
                        
                        if current_stage and current_stage not in stages_seen:
                            stages_seen.add(current_stage)
                            print(f"   [{i+1}s] Stage: {current_stage}, Status: {status}, Progress: {progress}%")
                        
                        if status in ["completed", "failed", "cancelled"]:
                            print(f"✅ Job finished with status: {status}")
                            break
            
            print(f"📊 Stages observed: {stages_seen}")


# Utility function to run a quick connectivity check
async def check_all_services():
    """Quick connectivity check for all services."""
    print("🔍 Checking all services connectivity...")
    
    services = [
        ("API Gateway", f"{config.api_gateway_url}/openapi.json"),
        ("Calibration", f"{config.calibration_url}/openapi.json"),
        ("SFM", f"{config.sfm_url}/openapi.json"),
        ("Orthomosaic", f"{config.orthomosaic_url}/openapi.json"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for name, url in services:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        print(f"   ✅ {name}: OK")
                    else:
                        print(f"   ⚠️ {name}: Status {response.status}")
            except Exception as e:
                print(f"   ❌ {name}: {e}")
    
    # Check Redis
    try:
        r = redis.Redis(host=config.redis_host, port=config.redis_port, db=config.redis_db)
        r.ping()
        print(f"   ✅ Redis: OK")
        r.close()
    except Exception as e:
        print(f"   ❌ Redis: {e}")


if __name__ == "__main__":
    # Run quick connectivity check
    asyncio.run(check_all_services())
