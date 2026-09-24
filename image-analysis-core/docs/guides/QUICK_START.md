# PhotoGear Quick Start Guide

This guide will help you get started with the PhotoGear API Gateway and processing services.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ (for testing)
- `aiohttp` library (for test script)

## Step 1: Environment Setup

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

The default values should work for local development:

```env
CALIBRATION_CLIENT_ADDRESS=http://calibration:8001
SFM_CLIENT_ADDRESS=http://sfm:8002
ORTHOMOSAIC_CLIENT_ADDRESS=http://orthomosaic_generation:8003
```

## Step 2: Start Services

Start all services using Docker Compose:

```bash
docker-compose up --build
```

This will start:
- API Gateway on port 8080
- Radiometric Calibration Service on port 8001
- SFM Service on port 8002
- Orthomosaic Generation Service on port 8003

Wait for all services to start. You should see messages like:
```
api_gateway            | INFO:     Uvicorn running on http://0.0.0.0:8080
calibration           | INFO:     Uvicorn running on http://0.0.0.0:8001
sfm                   | INFO:     Uvicorn running on http://0.0.0.0:8002
orthomosaic_generation| INFO:     Uvicorn running on http://0.0.0.0:8003
```

## Step 3: Test the API

### Option A: Use the Test Script

Install required dependencies:
```bash
pip install aiohttp
```

Run the test script:
```bash
python test_api_gateway.py
```

The script will:
1. Submit a test job
2. Poll for status updates
3. Show progress through all stages
4. Display results when complete

### Option B: Use cURL

**Submit a Job:**
```bash
curl -X POST http://localhost:8080/jobs/run \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "test-dataset-001",
    "download_url": "https://example.com/presigned-url",
    "parameters": {
      "calibration": {},
      "sfm": {},
      "orthomosaic": {
        "generate_cog": true
      }
    }
  }'
```

Response:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "progress": 0.0,
  "current_stage": "radiometric_calibration",
  ...
}
```

**Check Job Status:**
```bash
# Replace JOB_ID with the actual job ID from previous response
curl http://localhost:8080/jobs/{JOB_ID}/status
```

**Cancel a Job:**
```bash
curl -X POST http://localhost:8080/jobs/{JOB_ID}/cancel
```

### Option C: Use Python Requests

```python
import requests
import time

# Submit job
response = requests.post('http://localhost:8080/jobs/run', json={
    "dataset_id": "test-dataset-001",
    "download_url": "https://example.com/presigned-url",
    "parameters": {}
})

job_id = response.json()['job_id']
print(f"Job submitted: {job_id}")

# Poll for status
while True:
    status_response = requests.get(f'http://localhost:8080/jobs/{job_id}/status')
    status_data = status_response.json()

    print(f"Status: {status_data['status']} | Progress: {status_data['progress']}%")

    if status_data['status'] in ['completed', 'failed', 'cancelled']:
        print(f"Final result: {status_data}")
        break

    time.sleep(2)
```

## Step 4: Understanding the Response

### Job Status Response

```json
{
  "job_id": "uuid",
  "status": "running",           // pending, running, completed, failed, cancelled
  "progress": 45.5,              // 0-100
  "current_stage": "sfm",        // calibration, sfm, orthomosaic, uploading, finalizing
  "result": null,                // Job result when completed
  "error": null,                 // Error message when failed
  "created_at": "2025-12-08...",
  "updated_at": "2025-12-08..."
}
```

### Processing Stages

The job progresses through these stages:

1. **radiometric_calibration** (0-30%) - Image calibration
2. **sfm** (30-70%) - Structure from Motion
3. **orthomosaic_generation** (70-90%) - Orthomosaic creation
4. **uploading_results** (90-95%) - Upload to storage
5. **finalizing** (95-100%) - Final steps

## Step 5: API Documentation

View the complete API documentation:
- [API Gateway Documentation](./API_GATEWAY.md)
- [Implementation Summary](./IMPLEMENTATION_SUMMARY.md)

Or access the interactive API docs when services are running:
- API Gateway: http://localhost:8080/docs
- Calibration: http://localhost:8001/docs
- SFM: http://localhost:8002/docs
- Orthomosaic: http://localhost:8003/docs

## Common Issues

### Services Not Starting

**Issue:** Services fail to start
**Solution:** Check logs with `docker-compose logs [service-name]`

### Port Already in Use

**Issue:** `Address already in use` error
**Solution:** Stop other services using those ports or change ports in docker-compose.yml

### Job Stuck in Pending

**Issue:** Job never starts processing
**Solution:** Check if background task handler is working and services are reachable

### Cannot Connect to Services

**Issue:** API Gateway can't reach other services
**Solution:** Verify all services are in the same Docker network and using correct addresses

## Development Workflow

### Making Changes

1. Modify code
2. Restart services: `docker-compose restart [service-name]`
3. Or rebuild: `docker-compose up --build [service-name]`

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api_gateway
docker-compose logs -f sfm
```

### Stopping Services

```bash
# Stop all
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Next Steps

1. **Integrate with your backend:**
   - Update the download_url to point to your actual storage
   - Implement upload functionality
   - Add backend notifications

2. **Configure radiometric calibration:**
   - Replace mock implementation with actual algorithms
   - Configure calibration parameters

3. **Customize processing:**
   - Adjust SFM parameters
   - Configure orthomosaic settings
   - Add custom processing steps

4. **Production deployment:**
   - Add authentication
   - Configure persistent storage
   - Set up monitoring
   - Add load balancing

## Support

For issues or questions:
- Check the [Implementation Summary](./IMPLEMENTATION_SUMMARY.md)
- Review the [API Documentation](./API_GATEWAY.md)
- Check service logs
- Review the source code in each service directory

## Example: Complete Workflow

```python
import requests
import time

BASE_URL = "http://localhost:8080"

# 1. Submit a job
job_request = {
    "dataset_id": "my-dataset",
    "download_url": "https://storage.example.com/my-dataset",
    "parameters": {
        "orthomosaic": {
            "generate_cog": True
        }
    }
}

response = requests.post(f"{BASE_URL}/jobs/run", json=job_request)
job_id = response.json()["job_id"]
print(f"✓ Job submitted: {job_id}")

# 2. Monitor progress
while True:
    status = requests.get(f"{BASE_URL}/jobs/{job_id}/status").json()

    print(f"[{status['progress']:.1f}%] {status['status']} - {status['current_stage']}")

    if status['status'] == 'completed':
        print("\n✓ Job completed!")
        print(f"Results: {status['result']}")
        break
    elif status['status'] in ['failed', 'cancelled']:
        print(f"\n✗ Job {status['status']}")
        print(f"Error: {status.get('error')}")
        break

    time.sleep(3)
```

Happy processing! 🚀
