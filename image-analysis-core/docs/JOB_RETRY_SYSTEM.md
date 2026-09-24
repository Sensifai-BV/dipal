# Job Retry System Documentation

## Overview

The PhotoGear job retry system allows failed processing jobs to be retried, optionally resuming from the last successful processing stage. This reduces processing time and cost by avoiding reprocessing of already-completed stages.

---

## Key Features

### 1. **Stage Tracking**
- Each processing stage completion is tracked in `last_successful_stage` field
- Stages: `queued` → `sfm` → `mvs` → `publishing`
- When a stage completes successfully, it's marked for resume capability

### 2. **Retry Limits**
- Maximum 3 retries per original job
- Retry chain is tracked via `original_job_id`
- Prevents infinite retry loops

### 3. **Resume from Last Stage**
- Failed jobs can resume from the next stage after `last_successful_stage`
- Example: If SFM completed but MVS failed, retry starts from MVS
- Optionally force restart from beginning with `?force_restart=true`

### 4. **Retry Relationship Tracking**
- Original job ID preserved in retry chain
- Retry count increments with each attempt
- Easy to trace job history

---

## API Usage

### Retry a Failed Job

**Endpoint:** `POST /v1/api/jobs/{job_id}/retry/`

**Authentication:** Required

**Parameters:**
- `job_id` (path): UUID of the failed job to retry
- `force_restart` (query, optional): Set to `true` to restart from beginning (default: `false`)

**Request Example:**
```bash
# Resume from last successful stage (recommended)
curl -X POST "https://api.example.com/v1/api/jobs/550e8400-e29b-41d4-a716-446655440000/retry/" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Force restart from beginning
curl -X POST "https://api.example.com/v1/api/jobs/550e8400-e29b-41d4-a716-446655440000/retry/?force_restart=true" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Success Response (201):**
```json
{
  "new_job_id": "660e8400-e29b-41d4-a716-446655440001",
  "original_job_id": "550e8400-e29b-41d4-a716-446655440000",
  "retry_count": 1,
  "resume_from_stage": "mvs",
  "force_restart": false,
  "message": "Job retry initiated successfully. Resuming from stage: mvs",
  "dataset": {
    "id": "4ee43b40-d3fb-4ae6-8c5e-0c5b4288a6f0",
    "name": "UAV Survey 2024-01-15"
  }
}
```

**Error Responses:**
```json
// Job not in failed status
{
  "error": "Cannot retry job with status \"processing\". Only failed jobs can be retried.",
  "current_status": "processing"
}

// Max retries exceeded
{
  "error": "Maximum retry limit reached (3 retries)",
  "retry_count": 3,
  "suggestion": "Please check the error logs and fix the issue before creating a new job"
}

// Retry disabled
{
  "error": "This job cannot be retried (retry disabled)",
  "reason": "Job marked as non-retryable"
}
```

---

## Database Schema

### New Fields in `ProcessingJob` Model

```python
retry_count = models.PositiveIntegerField(
    default=0,
    help_text="Number of times this job has been retried"
)

last_successful_stage = models.CharField(
    max_length=20,
    choices=STAGE_CHOICES,
    null=True,
    blank=True,
    help_text="Last stage completed successfully (for resume on retry)"
)

original_job_id = models.UUIDField(
    null=True,
    blank=True,
    help_text="Original job ID if this is a retry"
)

can_retry = models.BooleanField(
    default=True,
    help_text="Whether this job can be retried if it fails"
)
```

### Migration

```bash
cd backend
python manage.py migrate jobs
```

Migration file: `apps/jobs/migrations/0003_add_retry_fields.py`

---

## Stage Resume Logic

### Stage Flow
```
queued (0-30%) → sfm (30-60%) → mvs (60-90%) → publishing (90-100%)
```

### Resume Examples

**Example 1: SFM Failed**
- Original Job:
  - Status: `failed`
  - Last Successful Stage: `queued`
  - Progress: `25%`
- Retry Job:
  - Resumes from: `sfm`
  - Starting Progress: `30%`

**Example 2: MVS Failed**
- Original Job:
  - Status: `failed`
  - Last Successful Stage: `sfm`
  - Progress: `55%`
- Retry Job:
  - Resumes from: `mvs`
  - Starting Progress: `60%`

**Example 3: No Successful Stage**
- Original Job:
  - Status: `failed`
  - Last Successful Stage: `null`
  - Progress: `5%`
- Retry Job:
  - Resumes from: `queued` (beginning)
  - Starting Progress: `0%`

---

## Frontend Integration

### Retry Button Visibility

Show retry button when:
```javascript
const canRetry = (job) => {
  return job.status === 'failed' && 
         job.can_retry === true &&
         (job.retry_count || 0) < 3;
};
```

### Display Retry Information

```javascript
// Show retry relationship
if (job.original_job_id) {
  console.log(`This is retry #${job.retry_count} of job ${job.original_job_id}`);
}

// Show resume information
if (job.last_successful_stage) {
  console.log(`Can resume from: ${getNextStage(job.last_successful_stage)}`);
} else {
  console.log('Will restart from beginning');
}

function getNextStage(lastStage) {
  const stages = ['queued', 'sfm', 'mvs', 'publishing'];
  const index = stages.indexOf(lastStage);
  return index >= 0 && index < stages.length - 1 
    ? stages[index + 1] 
    : 'beginning';
}
```

### Example UI Component

```jsx
function JobRetryButton({ job, onRetry }) {
  const [loading, setLoading] = useState(false);
  
  if (job.status !== 'failed' || !job.can_retry) {
    return null;
  }
  
  const retryCount = job.retry_count || 0;
  if (retryCount >= 3) {
    return <div className="error">Max retries reached</div>;
  }
  
  const handleRetry = async (forceRestart = false) => {
    setLoading(true);
    try {
      const url = `/v1/api/jobs/${job.id}/retry/${forceRestart ? '?force_restart=true' : ''}`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      const data = await response.json();
      onRetry(data);
    } catch (error) {
      console.error('Retry failed:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const resumeStage = job.last_successful_stage 
    ? getNextStage(job.last_successful_stage)
    : 'beginning';
  
  return (
    <div className="retry-controls">
      <button onClick={() => handleRetry(false)} disabled={loading}>
        Retry from {resumeStage}
      </button>
      {job.last_successful_stage && (
        <button onClick={() => handleRetry(true)} disabled={loading} className="secondary">
          Restart from beginning
        </button>
      )}
      <span className="retry-info">Attempt {retryCount + 1}/3</span>
    </div>
  );
}
```

---

## AI Gateway Integration

### Stage Completion Callbacks

The AI Gateway must send stage completion updates to enable resume functionality:

```python
# After each major stage completes successfully
await backend_client.send_progress_update(
    job_id=job_id,
    progress=stage_end_progress,
    current_stage=stage_name,
    stage_progress=100,  # Indicates stage completion
    message=f"Stage {stage_name} completed successfully"
)
```

### Example Callback Payloads

**SFM Completed:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "progress",
  "progress": 60.0,
  "current_stage": "sfm",
  "stage_progress": 100,
  "message": "SFM processing completed successfully"
}
```

**MVS Failed:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "error",
  "error_message": "MVS processing failed: Out of memory",
  "current_stage": "mvs",
  "error_details": {
    "stage": "mvs",
    "timestamp": "2024-01-29T12:45:00Z",
    "traceback": "..."
  }
}
```

---

## Best Practices

### 1. **Always Send Stage Completion**
- Send progress update with `stage_progress=100` when a stage completes
- This ensures `last_successful_stage` is properly updated
- Critical for resume functionality

### 2. **Meaningful Error Messages**
- Include detailed error information in failure callbacks
- Helps users understand why the job failed
- Assists in determining if retry will help

### 3. **Idempotent Processing**
- Ensure each stage can be safely rerun
- Check for existing outputs before reprocessing
- Use unique workspace directories per job

### 4. **Resource Cleanup**
- Clean up intermediate files from failed jobs
- Preserve final stage outputs for debugging
- Implement automated cleanup for old retry chains

### 5. **Monitoring**
- Track retry rates by failure reason
- Alert on high retry counts
- Monitor retry success rates

---

## Troubleshooting

### Retry Not Available

**Problem:** Retry button not showing for failed job

**Solutions:**
1. Check `job.status === 'failed'`
2. Verify `job.can_retry === true`
3. Check retry count < 3
4. Ensure user has permission for this organization

### Resume Not Working

**Problem:** Retry restarts from beginning instead of resuming

**Solutions:**
1. Verify AI Gateway sends `stage_progress=100` when stages complete
2. Check `last_successful_stage` is not `null` in database
3. Ensure stage names match exactly (`queued`, `sfm`, `mvs`, `publishing`)
4. Verify callback handler maps AI Gateway stages to Django stages

### Max Retries Reached

**Problem:** Cannot retry after 3 attempts

**Solutions:**
1. Review error logs to identify root cause
2. Fix underlying issue (e.g., insufficient resources, bad data)
3. Create a new job instead of retrying
4. Contact support if persistent infrastructure issues

---

## Monitoring Queries

### Find Jobs with Retries
```sql
SELECT id, dataset_id, status, retry_count, original_job_id, last_successful_stage
FROM jobs_processing_job
WHERE retry_count > 0
ORDER BY created_at DESC;
```

### Find Retry Chains
```sql
SELECT 
  original_job_id,
  COUNT(*) as retry_attempts,
  MAX(retry_count) as max_retry_count,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_retries
FROM jobs_processing_job
WHERE original_job_id IS NOT NULL
GROUP BY original_job_id
HAVING COUNT(*) >= 2;
```

### Find Failed Jobs Ready for Retry
```sql
SELECT id, dataset_id, error_message, last_successful_stage, retry_count
FROM jobs_processing_job
WHERE status = 'failed'
  AND can_retry = true
  AND retry_count < 3
ORDER BY created_at DESC;
```

---

## Related Documentation

- [Job Management API](ENDPOINT_CLARIFICATION.md)
- [AI Gateway Integration](../../image-analysis-core/docs/API_GATEWAY.md)
- [Directory Structure Guide](DIRECTORY_STRUCTURE.md)
