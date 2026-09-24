#!/usr/bin/env bash
# =============================================================================
# PhotoGear - Robust Dataverse Dataset Downloader
# =============================================================================
# Downloads the WUR Multispectral & Thermal dataset from Harvard Dataverse
# with resume support, automatic retries, and connection keep-alive.
#
# Usage:
#   chmod +x download_dataset.sh
#   ./download_dataset.sh
#
# Optional: set your API token if the dataset requires authentication
#   export DATAVERSE_API_TOKEN=your_token_here
#   ./download_dataset.sh
# =============================================================================

set -euo pipefail

# --- Configuration -----------------------------------------------------------
SERVER_URL="https://dataverse.harvard.edu"
PERSISTENT_ID="doi:10.7910/DVN/RYA2ZQ"
OUTPUT_DIR="./wur_dataset"
LOG_FILE="./download.log"
DATAVERSE_API_TOKEN=${1}

MAX_RETRIES=50              # Max retry attempts per file
RETRY_DELAY=10              # Initial wait between retries (seconds)
MAX_RETRY_DELAY=300         # Max wait between retries (caps exponential backoff)
CONNECT_TIMEOUT=30          # Connection timeout (seconds)
SPEED_LIMIT=1024            # Abort if speed drops below this (bytes/sec)
SPEED_TIME=60               # ... for this many seconds consecutively
# -----------------------------------------------------------------------------

mkdir -p "$OUTPUT_DIR"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

# --- Build auth header if token is set ----------------------------------------
AUTH_ARGS=()
if [[ -n "${DATAVERSE_API_TOKEN:-}" ]]; then
    AUTH_ARGS=(-H "X-Dataverse-key:${DATAVERSE_API_TOKEN}")
    log "Using API token for authentication."
else
    log "No API token set. Downloading as public (set DATAVERSE_API_TOKEN if needed)."
fi

# --- Step 1: Fetch dataset metadata and file list ----------------------------
log "================================================================"
log "  Fetching dataset file list from Harvard Dataverse..."
log "================================================================"

METADATA_URL="${SERVER_URL}/api/datasets/:persistentId/?persistentId=${PERSISTENT_ID}"

metadata=$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --retry 5 --retry-delay 5 \
    "${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"}" "$METADATA_URL")

if [[ -z "$metadata" ]] || echo "$metadata" | grep -q '"status":"ERROR"'; then
    log "ERROR: Could not fetch dataset metadata. Check connection and persistent ID."
    echo "$metadata" | python3 -m json.tool 2>/dev/null || echo "$metadata"
    exit 1
fi

# Parse file list: extract file ID, filename, and size
file_list=$(echo "$metadata" | python3 -c "
import json, sys
data = json.load(sys.stdin)
files = data.get('data', {}).get('latestVersion', {}).get('files', [])
if not files:
    print('NO_FILES')
    sys.exit(0)
total_size = 0
for f in files:
    df = f.get('dataFile', {})
    fid = df.get('id', '')
    fname = df.get('filename', 'unknown')
    fsize = df.get('filesize', 0)
    total_size += fsize
    dir_label = f.get('directoryLabel', '')
    if dir_label:
        full_path = f'{dir_label}/{fname}'
    else:
        full_path = fname
    print(f'{fid}|{full_path}|{fsize}')
print(f'TOTAL_SIZE|{total_size}')
")

if [[ "$file_list" == "NO_FILES" ]]; then
    log "ERROR: No files found in dataset."
    exit 1
fi

# Extract total size and file entries
total_bytes=$(echo "$file_list" | grep "^TOTAL_SIZE|" | cut -d'|' -f2)
file_entries=$(echo "$file_list" | grep -v "^TOTAL_SIZE|")
file_count=$(echo "$file_entries" | wc -l)

human_size=$(python3 -c "
s = $total_bytes
for u in ['B','KB','MB','GB','TB']:
    if s < 1024: print(f'{s:.1f} {u}'); break
    s /= 1024
")

log "Found ${file_count} files (${human_size} total)."
echo ""
log "Files to download:"
echo "$file_entries" | while IFS='|' read -r fid fpath fsize; do
    fsize_h=$(python3 -c "
s = $fsize
for u in ['B','KB','MB','GB']:
    if s < 1024: print(f'{s:.1f} {u}'); break
    s /= 1024
")
    echo "  $fpath ($fsize_h)"
done | tee -a "$LOG_FILE"
echo ""

# --- Step 2: Download each file with resume + retries ------------------------
log "================================================================"
log "  Starting downloads with resume support..."
log "================================================================"

downloaded=0
failed=0
skipped=0
failed_files=""

download_file() {
    local file_id="$1"
    local file_path="$2"
    local expected_size="$3"

    local output_path="${OUTPUT_DIR}/${file_path}"
    local output_dir
    output_dir=$(dirname "$output_path")
    mkdir -p "$output_dir"

    # Skip if already fully downloaded
    if [[ -f "$output_path" ]]; then
        local current_size
        current_size=$(stat -c%s "$output_path" 2>/dev/null || stat -f%z "$output_path" 2>/dev/null || echo 0)
        if [[ "$current_size" -ge "$expected_size" ]] && [[ "$expected_size" -gt 0 ]]; then
            log "  [SKIP] Already complete: ${file_path}"
            skipped=$((skipped + 1))
            return 0
        else
            log "  [RESUME] Partial file found: ${current_size}/${expected_size} bytes"
        fi
    fi

    local url="${SERVER_URL}/api/access/datafile/${file_id}"
    local attempt=0
    local delay=$RETRY_DELAY

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        log "  [ATTEMPT ${attempt}/${MAX_RETRIES}] Downloading: ${file_path}"

        # Build curl command with resume support and keep-alive
        set +e
        curl \
            -L \
            -C - \
            -o "$output_path" \
            --connect-timeout "$CONNECT_TIMEOUT" \
            --speed-limit "$SPEED_LIMIT" \
            --speed-time "$SPEED_TIME" \
            --retry 3 \
            --retry-delay 5 \
            --retry-connrefused \
            --keepalive-time 60 \
            --tcp-nodelay \
            --progress-bar \
            "${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"}" \
            "$url" 2>>"$LOG_FILE"
        local exit_code=$?
        set -e

        if [[ $exit_code -eq 0 ]]; then
            # Verify file size
            local actual_size
            actual_size=$(stat -c%s "$output_path" 2>/dev/null || stat -f%z "$output_path" 2>/dev/null || echo 0)

            if [[ "$expected_size" -gt 0 ]] && [[ "$actual_size" -lt "$expected_size" ]]; then
                log "  [INCOMPLETE] Got ${actual_size}/${expected_size} bytes. Retrying..."
            else
                log "  [DONE] ${file_path} (${actual_size} bytes)"
                downloaded=$((downloaded + 1))
                return 0
            fi
        else
            case $exit_code in
                6)  log "  [ERROR] Could not resolve host. Check DNS/internet." ;;
                7)  log "  [ERROR] Connection refused." ;;
                18) log "  [ERROR] Partial transfer — will resume on retry." ;;
                28) log "  [ERROR] Timeout — connection too slow or stalled." ;;
                33) log "  [ERROR] Range request not supported. Deleting partial and restarting..."
                    rm -f "$output_path" ;;
                56) log "  [ERROR] Connection reset — network interruption." ;;
                *)  log "  [ERROR] curl exit code: ${exit_code}" ;;
            esac
        fi

        # Exponential backoff with jitter
        local jitter=$((RANDOM % 10))
        local wait_time=$((delay + jitter))
        log "  [WAIT] Retrying in ${wait_time}s (backoff: ${delay}s + jitter: ${jitter}s)..."
        sleep "$wait_time"

        # Increase delay with cap
        delay=$((delay * 2))
        if [[ $delay -gt $MAX_RETRY_DELAY ]]; then
            delay=$MAX_RETRY_DELAY
        fi
    done

    log "  [FAILED] Gave up after ${MAX_RETRIES} attempts: ${file_path}"
    failed=$((failed + 1))
    failed_files="${failed_files}\n  - ${file_path}"
    return 1
}

# Download files one by one
file_index=0
while IFS='|' read -r fid fpath fsize; do
    file_index=$((file_index + 1))
    echo ""
    log "[${file_index}/${file_count}] ${fpath}"
    download_file "$fid" "$fpath" "$fsize" || true
done <<< "$file_entries"

# --- Step 3: Summary ---------------------------------------------------------
echo ""
log "================================================================"
log "  Download Summary"
log "================================================================"
log "  Output directory: $(cd "$OUTPUT_DIR" && pwd)"
log "  Log file:         ${LOG_FILE}"
log ""
log "  Downloaded: ${downloaded}"
log "  Skipped:    ${skipped} (already complete)"
log "  Failed:     ${failed}"

if [[ -n "$failed_files" ]]; then
    log ""
    log "  Failed files:${failed_files}"
fi

actual_size=$(du -sh "$OUTPUT_DIR" 2>/dev/null | cut -f1)
log ""
log "  Total on disk: ${actual_size}"
log ""

if [[ $failed -gt 0 ]]; then
    log "  WARNING: Some files failed. Re-run this script to resume."
    log "  The script will automatically skip completed files."
    log ""
    log "  Just run:  ./download_dataset.sh"
    exit 1
else
    log "  All ${file_count} files downloaded successfully!"
fi
