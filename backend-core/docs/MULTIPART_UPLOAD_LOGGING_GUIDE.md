# Multipart Upload Logging Guide

## Overview
Comprehensive logging has been added to all multipart upload endpoints and their underlying services. This guide helps you track uploads through the system.

## Log Prefixes

All upload-related logs use prefixes to make them easy to filter:

| Prefix | Layer | Description |
|--------|-------|-------------|
| `[MULTIPART-INIT]` | API View | Init endpoint processing |
| `[MULTIPART-SIGN]` | API View | Sign-part endpoint processing |
| `[MULTIPART-COMPLETE]` | API View | Complete endpoint processing |
| `[USE-CASE:INIT]` | Business Logic | Init use case execution |
| `[USE-CASE:SIGN]` | Business Logic | Sign-part use case execution |
| `[USE-CASE:COMPLETE]` | Business Logic | Complete use case execution |
| `[S3:CREATE-MULTIPART]` | S3 Service | S3 multipart creation |
| `[S3:PRESIGNED-PART]` | S3 Service | Presigned URL generation |
| `[S3:COMPLETE-MULTIPART]` | S3 Service | S3 upload completion |
| `[REPO:CREATE]` | Repository | Database record creation |
| `[REPO:SET-MULTIPART-ID]` | Repository | Setting s3_upload_id |
| `[REPO:UPDATE-STATUS]` | Repository | Status updates |

## Upload Flow & Expected Logs

### Step 1: Initialize Upload
**Endpoint:** `POST /v1/api/uploads/multipart/init/`

**Expected Log Sequence:**
```
1. [MULTIPART-INIT] Received init request from user {user_id}
2. [MULTIPART-INIT] Starting upload - file: {filename}, size: {size} MB
3. [USE-CASE:INIT] Starting multipart upload initialization
4. [USE-CASE:INIT] File extension detected: {ext}
5. [USE-CASE:INIT] Detected ARCHIVE/IMAGE type
6. [USE-CASE:INIT] Dataset resolved - dataset_id: {id}
7. [USE-CASE:INIT] S3 key generated: {key}
8. [USE-CASE:INIT] Calling S3Service.create_multipart_upload...
9. [S3:CREATE-MULTIPART] Starting multipart upload creation - key: {key}
10. [S3:CREATE-MULTIPART] ✅ SUCCESS - UploadId: {upload_id}
11. [USE-CASE:INIT] ✅ S3 multipart upload created
12. [REPO:CREATE] Creating upload record
13. [REPO:CREATE] ✅ Upload record created - id: {id}
14. [REPO:SET-MULTIPART-ID] Setting s3_upload_id
15. [REPO:SET-MULTIPART-ID] ✅ s3_upload_id set
16. [USE-CASE:INIT] ✅ COMPLETE - upload_id: {id}
17. [MULTIPART-INIT] ✅ SUCCESS - upload_id: {id}
18. [MULTIPART-INIT] Next step: Frontend should call sign-part endpoint
```

**Success Response:** HTTP 200 with upload_id

**Common Errors to Look For:**
- `❌ Failed to create S3 multipart upload` → S3 credentials/permissions issue
- `❌ Upload record creation failed` → Database connection issue
- `Status '{status}' does not exist in database` → Missing UploadStatus records

### Step 2: Get Presigned URLs for Parts
**Endpoint:** `POST /v1/api/uploads/multipart/sign-part/`
**Called:** For EACH chunk (e.g., 10 times for 10 chunks)

**Expected Log Sequence (per part):**
```
1. [MULTIPART-SIGN] Received sign-part request - upload_id: {id}, part_number: {n}
2. [USE-CASE:SIGN] Generating presigned URL - upload_id: {id}, part: {n}
3. [USE-CASE:SIGN] Upload found - file: {filename}
4. [USE-CASE:SIGN] Calling S3Service.generate_presigned_url_part...
5. [S3:PRESIGNED-PART] Generating presigned URL - part: {n}
6. [S3:PRESIGNED-PART] ✅ SUCCESS - Generated URL for part {n}
7. [USE-CASE:SIGN] ✅ Presigned URL generated
8. [MULTIPART-SIGN] ✅ SUCCESS - Generated presigned URL for part: {n}
9. [MULTIPART-SIGN] Next step: Frontend should PUT chunk {n} to this URL
```

**Success Response:** HTTP 200 with presigned URL

**Common Errors to Look For:**
- `❌ Upload not found` → Invalid upload_id or upload expired
- `❌ Not a valid multipart upload session` → s3_upload_id missing (init failed)
- `❌ Failed to generate presigned URL` → S3 service issue

**CRITICAL:** If frontend doesn't call this endpoint at all after init returns 200:
- Check frontend network logs
- Verify upload_id was properly extracted from init response
- Check frontend error handling

### Step 3: Complete Upload
**Endpoint:** `POST /v1/api/uploads/multipart/complete/`

**Expected Log Sequence:**
```
1. [MULTIPART-COMPLETE] Received complete request - upload_id: {id}, parts_count: {n}
2. [USE-CASE:COMPLETE] Starting completion - upload_id: {id}
3. [USE-CASE:COMPLETE] Upload found - file: {filename}, type: {type}
4. [USE-CASE:COMPLETE] Calling S3Service.complete_multipart_upload
5. [S3:COMPLETE-MULTIPART] Starting completion - upload_id: {id}, parts_count: {n}
6. [S3:COMPLETE-MULTIPART] ✅ SUCCESS - File assembled in S3
7. [USE-CASE:COMPLETE] ✅ S3 multipart upload completed successfully
8. [USE-CASE:COMPLETE] File is ARCHIVE - starting processing pipeline (if archive)
9. [USE-CASE:COMPLETE] Detected MIME type: {mime}
10. [REPO:UPDATE-STATUS] Updating status - new_status: PROCESSING
11. [REPO:UPDATE-STATUS] ✅ Status updated
12. [USE-CASE:COMPLETE] ✅ Celery task dispatched - task: process_archive_task
13. [USE-CASE:COMPLETE] ✅ COMPLETE - final_status: PROCESSING
14. [MULTIPART-COMPLETE] ✅ SUCCESS - status: PROCESSING
15. [MULTIPART-COMPLETE] Archive detected - Celery task triggered
```

**Success Response:** HTTP 200 with upload entity

**Common Errors to Look For:**
- `❌ S3 completion failed` → Most common! See troubleshooting below
- `❌ Invalid archive MIME type` → File corruption or wrong file type
- `❌ Failed to initiate archive processing` → Celery task dispatch issue

## Troubleshooting Common Issues

### Issue 1: Init Returns 200, But No Sign-Part Calls
**Symptoms:**
- `[MULTIPART-INIT] ✅ SUCCESS` logged
- No `[MULTIPART-SIGN]` logs after that
- Frontend shows "stuck" or no progress

**Check:**
1. Frontend received upload_id:
   ```bash
   # Check backend response
   grep -A 5 "MULTIPART-INIT.*SUCCESS" /path/to/logs
   ```

2. Frontend is calling sign-part:
   ```bash
   # Should see multiple sign-part requests
   grep "MULTIPART-SIGN.*Received" /path/to/logs | wc -l
   ```

3. Frontend error logs for CORS/network issues

**Common Causes:**
- Frontend not extracting upload_id from response
- Frontend CORS issue (check browser console)
- Frontend timeout on init (didn't wait for 200)
- Frontend bug in chunking logic

### Issue 2: S3 Completion Fails
**Symptoms:**
- `[S3:COMPLETE-MULTIPART] ❌ FAILED` logged
- Error: "InvalidPart", "NoSuchUpload", or "EntityTooSmall"

**Check:**
```bash
# Check if parts were signed
grep "S3:PRESIGNED-PART.*SUCCESS" /path/to/logs | tail -20

# Check parts in complete request
grep "USE-CASE:COMPLETE.*Parts:" /path/to/logs
```

**Common Causes & Solutions:**

1. **Parts not uploaded (InvalidPart)**
   - Frontend got presigned URLs but didn't PUT chunks to S3
   - Check: Did frontend actually upload chunks?
   - Look for: Missing part numbers in logs

2. **Invalid ETags**
   - Frontend sent wrong ETags in complete request
   - ETags must match what S3 returned after PUT
   - Check: Frontend saved ETags from PUT responses?

3. **Upload expired (NoSuchUpload)**
   - Upload took too long (>24h by default)
   - Solution: Retry with new init

4. **Part too small (EntityTooSmall)**
   - Parts must be ≥5MB except last part
   - Check: Frontend chunk size

### Issue 3: No Logs at All
**Symptoms:**
- Request to init endpoint, but no `[MULTIPART-INIT]` logs

**Check:**
1. Logging configured:
   ```bash
   # Check if logger is imported
   grep "from config.logging_config import get_logger" backend/apps/uploads/presentation/views.py
   ```

2. Log level:
   ```python
   # In Django settings
   LOGGING['loggers']['apps.uploads']['level'] = 'DEBUG'
   ```

3. Django receiving request:
   ```bash
   # Check Django access logs
   tail -f /path/to/access.log
   ```

## Filtering Logs

### See Complete Upload Flow
```bash
# All upload-related logs for specific upload_id
grep "upload_id: abc123" /path/to/logs | grep -E "\[MULTIPART-|\[USE-CASE:|\[S3:|\[REPO:"
```

### Track Specific Upload
```bash
# Replace {upload_id} with actual ID
grep "{upload_id}" /path/to/logs
```

### See Only Errors
```bash
# All upload errors
grep -E "\[MULTIPART-.*❌|\[USE-CASE:.*❌|\[S3:.*❌|\[REPO:.*❌" /path/to/logs
```

### Count Sign-Part Calls
```bash
# How many parts were requested for an upload
grep "upload_id: {id}" /path/to/logs | grep "MULTIPART-SIGN.*part_number" | wc -l
```

### Check S3 Operations
```bash
# All S3 operations
grep -E "\[S3:" /path/to/logs
```

## Expected Behavior

### Single-File Upload (100MB, 10 chunks)
**Log Counts:**
- `[MULTIPART-INIT]`: 1 entry
- `[MULTIPART-SIGN]`: 10 entries (one per chunk)
- `[MULTIPART-COMPLETE]`: 1 entry
- `[S3:PRESIGNED-PART]`: 10 entries
- `[S3:COMPLETE-MULTIPART]`: 1 entry

### Archive Upload
**Additional:**
- `[USE-CASE:COMPLETE] Archive detected`
- `[REPO:UPDATE-STATUS] new_status: PROCESSING`
- `Celery task dispatched: process_archive_task`

### Non-Archive Upload
**Different:**
- `[USE-CASE:COMPLETE] File is not ARCHIVE`
- `[REPO:UPDATE-STATUS] new_status: COMPLETED`
- No Celery task

## Debug Checklist

When upload fails, check in order:

1. ✅ **Init succeeded?**
   ```bash
   grep "MULTIPART-INIT.*SUCCESS.*upload_id: {id}" logs
   ```

2. ✅ **S3 multipart created?**
   ```bash
   grep "S3:CREATE-MULTIPART.*SUCCESS.*UploadId" logs
   ```

3. ✅ **Database record created?**
   ```bash
   grep "REPO:CREATE.*Upload record created.*id: {id}" logs
   ```

4. ✅ **Sign-part called?**
   ```bash
   grep "MULTIPART-SIGN.*upload_id: {id}" logs | wc -l
   ```

5. ✅ **Presigned URLs generated?**
   ```bash
   grep "S3:PRESIGNED-PART.*SUCCESS.*part" logs | grep "{id}"
   ```

6. ✅ **Complete called?**
   ```bash
   grep "MULTIPART-COMPLETE.*upload_id: {id}" logs
   ```

7. ✅ **S3 completion succeeded?**
   ```bash
   grep "S3:COMPLETE-MULTIPART.*SUCCESS" logs | grep "{id}"
   ```

8. ✅ **Status updated?**
   ```bash
   grep "REPO:UPDATE-STATUS.*upload_id: {id}" logs
   ```

## Log Retention

**Production Recommendation:**
- Keep upload logs for at least 7 days
- Archive logs older than 30 days
- Set up alerts for:
  - `❌ Failed to create S3 multipart upload`
  - `❌ S3 completion failed`
  - High rate of `❌` errors

## Integration with Monitoring

**Metrics to Track:**
1. Init success rate: `[MULTIPART-INIT] ✅ SUCCESS` / total init requests
2. Sign-part success rate: `[MULTIPART-SIGN] ✅ SUCCESS` / total sign requests
3. Complete success rate: `[MULTIPART-COMPLETE] ✅ SUCCESS` / total complete requests
4. Average parts per upload: Count `[MULTIPART-SIGN]` per unique upload_id
5. S3 error rate: Count `[S3:.*❌]`

## Performance Benchmarks

**Typical Timings:**
- Init: < 1 second
- Sign-part (per call): < 100ms
- Complete (10 parts): 1-3 seconds
- Complete (100 parts): 5-10 seconds

**Red Flags:**
- Init taking > 5 seconds → Database slow
- Sign-part taking > 1 second → Database slow
- Complete taking > 30 seconds → Too many parts or S3 slow

## Example: Successful Upload

```log
2026-02-08 10:00:00 INFO [MULTIPART-INIT] Received init request from user 42
2026-02-08 10:00:00 INFO [MULTIPART-INIT] Starting upload - file: dataset.zip, size: 100.00 MB
2026-02-08 10:00:00 INFO [USE-CASE:INIT] Starting multipart upload initialization
2026-02-08 10:00:00 INFO [S3:CREATE-MULTIPART] Starting multipart upload creation
2026-02-08 10:00:01 INFO [S3:CREATE-MULTIPART] ✅ SUCCESS - UploadId: abc123xyz
2026-02-08 10:00:01 INFO [REPO:CREATE] ✅ Upload record created - id: uuid-123
2026-02-08 10:00:01 INFO [MULTIPART-INIT] ✅ SUCCESS - upload_id: uuid-123

2026-02-08 10:00:02 INFO [MULTIPART-SIGN] Received sign-part request - part_number: 1
2026-02-08 10:00:02 INFO [S3:PRESIGNED-PART] ✅ SUCCESS - Generated URL for part 1
...
2026-02-08 10:00:20 INFO [MULTIPART-SIGN] Received sign-part request - part_number: 10
2026-02-08 10:00:20 INFO [S3:PRESIGNED-PART] ✅ SUCCESS - Generated URL for part 10

2026-02-08 10:05:00 INFO [MULTIPART-COMPLETE] Received complete request - parts_count: 10
2026-02-08 10:05:00 INFO [S3:COMPLETE-MULTIPART] Starting completion - parts_count: 10
2026-02-08 10:05:03 INFO [S3:COMPLETE-MULTIPART] ✅ SUCCESS - File assembled in S3
2026-02-08 10:05:03 INFO [REPO:UPDATE-STATUS] ✅ Status updated - PENDING -> PROCESSING
2026-02-08 10:05:03 INFO [MULTIPART-COMPLETE] ✅ SUCCESS - status: PROCESSING
```

## Contact

For issues not covered in this guide:
1. Collect logs using commands above
2. Check error messages against common issues
3. Include full log context (before/after error)
