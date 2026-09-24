# Running Image Analysis Services

This directory contains 4 microservices for photogrammetry processing:
- **API Gateway** (Port 8080) - Orchestrates the processing pipeline
- **Radiometric Calibration Service** (Port 8001)
- **SFM Service** (Port 8002) - Structure from Motion using COLMAP
- **Orthomosaic Generation Service** (Port 8003)

## Quick Start

### 1. Setup Environment

Copy the example environment file and customize if needed:

```bash
cp .env.example .env
```

### 2. Create Docker Network

All services need to communicate, so create a shared network:

```bash
docker network create image_processing_network
```

### 3. Running Services

You have two options:

#### Option A: Run All Services Together (Recommended for development)

```bash
docker-compose up --build
```

This starts all 4 services in one command.

#### Option B: Run Services Individually

This gives you more control and is useful when:
- You want to run services on different machines
- You want to restart only specific services
- You're debugging a particular service

**Start API Gateway:**
```bash
docker-compose -f docker-compose.api-gateway.yml up --build
```

**Start Calibration Service:**
```bash
docker-compose -f docker-compose.calibration.yml up --build
```

**Start SFM Service:**
```bash
docker-compose -f docker-compose.sfm.yml up --build
```

**Start Orthomosaic Service:**
```bash
docker-compose -f docker-compose.orthomosaic.yml up --build
```

## Configuration

### Service URLs

When running all services with docker-compose, the default configuration works out of the box.

For external or distributed services, update `.env`:

```env
# Example: SFM service running on another machine
SFM_CLIENT_ADDRESS=http://192.168.1.100:8002

# Example: Running services on host network
CALIBRATION_CLIENT_ADDRESS=http://localhost:8001
SFM_CLIENT_ADDRESS=http://localhost:8002
ORTHOMOSAIC_CLIENT_ADDRESS=http://localhost:8003
```

### GPU Support

The SFM service can use GPU acceleration if available:

1. **To enable GPU**, uncomment the GPU section in `docker-compose.sfm.yml`:
   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: all
             capabilities: [gpu]
   ```

2. **Set device in `.env`:**
   ```env
   COLMAP_DEVICE=gpu
   ```

3. **Ensure you have:**
   - NVIDIA GPU
   - NVIDIA drivers installed
   - nvidia-docker2 package

**CPU Mode (Default):**
The services work without GPU. CPU processing is slower but functional.

## API Endpoints

### API Gateway (Port 8080)

**Submit Processing Job:**
```bash
curl -X POST http://localhost:8080/jobs/run \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "test123",
    "download_url": "https://your-s3-presigned-url",
    "parameters": {
      "calibration": {},
      "sfm": {},
      "orthomosaic": {"generate_cog": true}
    }
  }'
```

**Check Job Status:**
```bash
curl http://localhost:8080/jobs/{job_id}/status
```

**Cancel Job:**
```bash
curl -X POST http://localhost:8080/jobs/{job_id}/cancel
```

### Individual Services

Each service has similar endpoints:

**Calibration Service (8001):**
- POST `/calibration/run`
- GET `/calibration/jobs/{job_id}/status`

**SFM Service (8002):**
- POST `/sfm/run`
- GET `/sfm/jobs/{job_id}/status`

**Orthomosaic Service (8003):**
- POST `/orthomosaic/run`
- GET `/orthomosaic/jobs/{job_id}/status`

## Testing Services

Check if services are running:

```bash
# API Gateway
curl http://localhost:8080/

# Calibration
curl http://localhost:8001/

# SFM
curl http://localhost:8002/

# Orthomosaic
curl http://localhost:8003/
```

## Distributed Setup Example

Running services on different machines:

**Machine 1 (API Gateway):**
```bash
# Update .env with actual IPs
CALIBRATION_CLIENT_ADDRESS=http://192.168.1.10:8001
SFM_CLIENT_ADDRESS=http://192.168.1.11:8002
ORTHOMOSAIC_CLIENT_ADDRESS=http://192.168.1.12:8003

# Start only API Gateway
docker-compose -f docker-compose.api-gateway.yml up
```

**Machine 2 (Calibration):**
```bash
docker-compose -f docker-compose.calibration.yml up
```

**Machine 3 (SFM with GPU):**
```bash
# Enable GPU in docker-compose.sfm.yml
COLMAP_DEVICE=gpu
docker-compose -f docker-compose.sfm.yml up
```

**Machine 4 (Orthomosaic):**
```bash
docker-compose -f docker-compose.orthomosaic.yml up
```

## Troubleshooting

**Services can't communicate:**
- Ensure all services are on the same Docker network
- Check firewall rules if using multiple machines
- Verify service URLs in `.env`

**GPU not detected:**
- Install nvidia-docker2: `sudo apt-get install nvidia-docker2`
- Restart Docker: `sudo systemctl restart docker`
- Verify with: `docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`

**Out of memory:**
- Reduce `COLMAP_FEATURE_EXTRACTION_MAX_IMAGE_SIZE` in `.env`
- Reduce `COLMAP_PATCH_MATCH_MAX_IMAGE_SIZE` in `.env`
- Process fewer images at once

## Logs

View logs for all services:
```bash
docker-compose logs -f
```

View logs for specific service:
```bash
docker-compose -f docker-compose.sfm.yml logs -f
```

## Stopping Services

**Stop all:**
```bash
docker-compose down
```

**Stop specific service:**
```bash
docker-compose -f docker-compose.sfm.yml down
```

## Architecture

```
┌──────────────────────────────────────────┐
│         Backend (Django)                 │
│         http://backend:8000              │
└────────────────┬─────────────────────────┘
                 │
                 │ HTTP Request
                 ▼
┌──────────────────────────────────────────┐
│      API Gateway (Port 8080)             │
│  - Orchestrates pipeline                 │
│  - Downloads dataset                     │
│  - Tracks progress                       │
└────┬──────────┬──────────┬───────────────┘
     │          │          │
     ▼          ▼          ▼
┌─────────┐ ┌───────┐ ┌──────────────┐
│Calib    │ │  SFM  │ │ Orthomosaic  │
│:8001    │ │ :8002 │ │    :8003     │
└─────────┘ └───────┘ └──────────────┘
```

## Next Steps

- Connect with Backend (Django)
- Implement result upload to S3
- Add monitoring and metrics
- Set up production deployment
