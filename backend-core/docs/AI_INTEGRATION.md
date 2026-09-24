# Backend ↔ AI Gateway Integration

Complete integration between Django Backend and AI Gateway for photogrammetry processing.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Django Backend                            │
│  - Receives user requests                                   │
│  - Manages jobs in PostgreSQL                              │
│  - Generates S3 presigned URLs                             │
│  - Calls AI Gateway                                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ 1. POST /jobs/run
                 │ (job_id, dataset_id, presigned_url, parameters)
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                   AI Gateway (FastAPI)                      │
│  - Orchestrates processing pipeline                        │
│  - Downloads images from S3                                │
│  - Manages temp storage                                    │
│  - Uploads results to S3                                   │
│  - Sends callbacks to Backend                              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ 2. POST /api/jobs/ai-callback/
                 │ (progress updates, completion, errors)
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    Django Backend                            │
│  - Updates job status                                       │
│  - Stores S3 URLs for results                              │
│  - Notifies users                                           │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Job Submission (Backend → AI)

**Endpoint**: `POST http://api_gateway:8080/jobs/run`

**Backend sends**:
```json
{
  "dataset_id": "uuid",
  "download_url": "https://s3-presigned-url-for-images",
  "parameters": {
    "analysis_mode": "full",
    "calibration": {
      "enabled": true
    },
    "sfm": {
      "resolution_gsd": 5.0
    },
    "orthomosaic": {
      "generate_cog": true,
      "resolution_gsd": 5.0
    }
  }
}
```

> **`analysis_mode`** (optional, default `"fast"`): Controls pipeline depth.
> `"fast"` runs RGB processing only with GSD×2 for speed.
> `"full"` adds reflectance conversion, band orthorectification, and
> vegetation indices (NDVI, NDRE, GNDVI).
```

**AI Gateway returns**:
```json
{
  "job_id": "ai-generated-uuid",
  "status": "running",
  "progress": 0.0,
  "current_stage": "radiometric_calibration"
}
```

### 2. Progress Updates (AI → Backend)

**Endpoint**: `POST http://backend:8000/api/jobs/ai-callback/`

**AI sends periodic updates**:
```json
{
  "job_id": "backend-job-uuid",
  "type": "progress",
  "progress": 45.5,
  "current_stage": "sfm",
  "message": "Processing structure from motion: 45.5%"
}
```

**Backend responds**:
```json
{
  "acknowledged": true
}
```

### 3. Completion (AI → Backend)

**AI sends final results**:
```json
{
  "job_id": "backend-job-uuid",
  "dataset_id": "dataset-uuid",
  "type": "complete",
  "status": "completed",
  "outputs": {
    "orthomosaic": "s3://bucket/jobs/dataset_id/job_id/orthomosaic/ortho.tif",
    "dsm": "s3://bucket/jobs/dataset_id/job_id/dsm/dsm.tif",
    "mesh": "s3://bucket/jobs/dataset_id/job_id/mesh/model.ply",
    "sparse_model": "s3://bucket/jobs/dataset_id/job_id/sparse/model.ply"
  },
  "metadata": {
    "calibration": {...},
    "sfm": {...},
    "orthomosaic": {...}
  }
}
```

### 4. Error Handling (AI → Backend)

**AI sends error**:
```json
{
  "job_id": "backend-job-uuid",
  "type": "error",
  "status": "failed",
  "error_message": "Failed to process images",
  "error_details": {
    "error": "COLMAP feature extraction failed",
    "traceback": "..."
  }
}
```

## Configuration

### Backend (.env)

```env
# AI Gateway Integration
AI_GATEWAY_URL=http://api_gateway:8080
AI_GATEWAY_SECRET_KEY=your-shared-secret-key

# S3 Buckets
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_REGION_NAME=eu-north-1
AWS_S3_RAW_IMAGES_BUCKET=photogear-raw-images
AWS_S3_AI_DEV_BUCKET=photogear-production-ai-dev-bucket
AWS_S3_RESULTS_BUCKET=photogear-production-ai-dev-bucket
```

### AI Gateway (.env)

```env
# Backend Integration
BACKEND_API_URL=http://backend:8000
BACKEND_CALLBACK_ENDPOINT=/api/jobs/ai-callback/
BACKEND_API_SECRET_KEY=your-shared-secret-key

# S3 Configuration
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_REGION_NAME=eu-north-1
AWS_S3_RAW_IMAGES_BUCKET=photogear-raw-images
AWS_S3_AI_DEV_BUCKET=photogear-production-ai-dev-bucket
AWS_S3_RESULTS_BUCKET=photogear-production-ai-dev-bucket

# Temp Storage
TEMP_BASE_PATH=/app/data/temp
TEMP_CLEANUP_DAYS=1
```

## Security

### Authentication

Both services use **API Secret Key** authentication:

- Backend → AI: Sends `X-API-Secret-Key` header with requests
- AI → Backend: Sends `X-API-Secret-Key` header with callbacks

**Important**: Use the same secret key in both services!

### Network Security

When running in Docker:
- Services communicate via internal Docker network
- No external exposure needed
- Use shared network: `image_processing_network`

## S3 Storage Structure

```
AI Dev Bucket (photogear-production-ai-dev-bucket)
└── jobs/
    └── {dataset_id}/
        └── {job_id}/
            ├── orthomosaic/
            │   └── orthomosaic.tif
            ├── dsm/
            │   └── dsm.tif
            ├── mesh/
            │   └── mesh.ply
            └── sparse/
                └── sparse_model.ply
```

## Temp Storage Management

### Location
`/app/data/temp/jobs/{job_id}/`

### Structure
```
temp/
└── jobs/
    └── {job_id}/
        ├── .timestamp          # Last access timestamp
        ├── images/             # Downloaded images
        ├── calibration/        # Calibration results
        ├── sfm/               # SFM intermediate files
        └── orthomosaic/       # Orthomosaic intermediate files
```

### Cleanup

**Automatic cleanup via cronjob**:

```bash
# Add to crontab (run daily at 2 AM)
0 2 * * * cd /app && python cleanup_temp.py >> /var/log/temp_cleanup.log 2>&1
```

**Manual cleanup**:

```bash
# Dry run (see what would be deleted)
python cleanup_temp.py --dry-run

# Actual cleanup
python cleanup_temp.py
```

**Cleanup logic**:
- Deletes folders not accessed for > 1 day (configurable via `TEMP_CLEANUP_DAYS`)
- Checks `.timestamp` file modification time
- Final results already uploaded to S3, so safe to delete

## Docker Network Setup

### Create Shared Network

```bash
docker network create image_processing_network
```

### Connect Backend to Network

Update `backend/docker-compose.yml`:

```yaml
services:
  web:
    networks:
      - image_processing_network

networks:
  image_processing_network:
    external: true
```

### Connect AI Services to Network

Already configured in `image-analysis-core/docker-compose.yml`

## Testing the Integration

### 1. Start All Services

```bash
# Start Backend
cd backend
docker-compose up

# Start AI Services
cd ../image-analysis-core
docker-compose up
```

### 2. Submit a Job

```bash
curl -X POST http://localhost:8000/api/jobs/start-job/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "dataset_id": "your-dataset-uuid",
    "resolution_gsd": 5.0,
    "radiometric_calibration": true
  }'
```

### 3. Monitor Progress

```bash
# Check job status in Backend
curl http://localhost:8000/api/jobs/list/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check AI Gateway directly
curl http://localhost:8080/jobs/{ai_job_id}/status
```

### 4. Check Logs

```bash
# Backend logs
docker-compose -f backend/docker-compose.yml logs -f web celery_worker

# AI Gateway logs
docker-compose -f image-analysis-core/docker-compose.yml logs -f api_gateway
```

## Troubleshooting

### Backend can't reach AI Gateway

**Check**:
1. Both on same Docker network?
2. AI Gateway URL correct in `.env`?
3. Firewall rules?

**Debug**:
```bash
# From backend container
docker exec -it photogear_backend ping api_gateway
docker exec -it photogear_backend curl http://api_gateway:8080/
```

### AI can't send callbacks to Backend

**Check**:
1. Backend URL correct in AI `.env`?
2. Callback endpoint exists?
3. Secret key matches?

**Debug**:
```bash
# From AI container
docker exec -it image-analysis-core-api_gateway-1 ping backend
docker exec -it image-analysis-core-api_gateway-1 curl http://backend:8000/api/jobs/ai-callback/ \
  -X POST -H "X-API-Secret-Key: your-key" -H "Content-Type: application/json" \
  -d '{"job_id":"test","type":"progress","progress":50}'
```

### S3 Upload Failures

**Check**:
1. AWS credentials valid?
2. Bucket names correct?
3. IAM permissions for S3 upload?

**Debug**:
```bash
# Test AWS credentials
aws s3 ls s3://your-bucket-name --profile your-profile
```

## Next Steps

1. **Add Result Fields to Model**: Update `ProcessingJob` model to store S3 URLs:
   ```python
   orthomosaic_s3_url = models.URLField(null=True, blank=True)
   dsm_s3_url = models.URLField(null=True, blank=True)
   mesh_s3_url = models.URLField(null=True, blank=True)
   ```

2. **WebSocket Notifications**: Real-time progress updates to frontend

3. **Monitoring**: Add Prometheus metrics for job tracking

4. **Error Recovery**: Implement retry logic for failed jobs

5. **Result Visualization**: Frontend components to display results

## API Reference

See:
- [Backend API docs](http://localhost:8000/api/docs/)
- [AI Gateway API docs](http://localhost:8080/docs/)
