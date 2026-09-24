#!/usr/bin/env bash
# =============================================================================
# PhotoGear - Robust Zenodo Dataset Downloader
# =============================================================================
# Downloads the Zenodo record 7749239 (Pistachio Orchard UAV RGB dataset)
# with resume support, automatic retries, and connection keep-alive.
#
# Usage:
#   chmod +x download_zenodo.sh
#   ./download_zenodo.sh
#
# The script will:
#   1. Query the Zenodo API for the file list
#   2. Download each file individually with resume support
#   3. Skip already-completed files on re-run
#   4. Retry with exponential backoff on failure
# =============================================================================

set -euo pipefail

# --- Configuration -----------------------------------------------------------
RECORD_ID="7749239"
API_URL="https://zenodo.org/api/records/${RECORD_ID}"
OUTPUT_DIR="./zenodo_${RECORD_ID}"
LOG_FILE="./download_zenodo_${RECORD_ID}.log"

MAX_RETRIES=50
RETRY_DELAY=10
MAX_RETRY_DELAY=300
CONNECT_TIMEOUT=30
SPEED_LIMIT=1024            # Abort if below 1 KB/s ...
SPEED_TIME=60               # ... for 60 seconds straight
# -----------------------------------------------------------------------------

mkdir -p "$OUTPUT_DIR"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

# --- Step 1: Fetch record metadata -------------------------------------------
log "================================================================"
log "  Fetching file list from Zenodo record ${RECORD_ID}..."
log "================================================================"

metadata=$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --retry 5 --retry-delay 5 "$API_URL")

if [[ -z "$metadata" ]] || echo "$metadata" | grep -q '"status": 4'; then
    log "ERROR: Could not fetch record metadata."
    echo "$metadata" | python3 -m json.tool 2>/dev/null || echo "$metadata"
    exit 1
fi

# Parse file list: name, download link, size, checksum
file_list=$(echo "$metadata" | python3 -c "
import json, sys
from urllib.parse import quote

data = json.load(sys.stdin)
files = data.get('files', [])
if not files:
    print('NO_FILES')
    sys.exit(0)
total_size = 0
for f in files:
    fname = f.get('key', 'unknown')
    fsize = f.get('size', 0)
    checksum = f.get('checksum', '')
    # Build direct download link with proper URL encoding
    link = f.get('links', {}).get('self', '')
    if link:
        # Re-encode: split into base + filename, encode the filename part
        # Zenodo self links look like: https://zenodo.org/api/records/ID/files/FILENAME/content
        # They may contain spaces or special chars in FILENAME
        parts = link.rsplit('/files/', 1)
        if len(parts) == 2:
            link = parts[0] + '/files/' + quote(parts[1], safe='/')
    else:
        encoded_name = quote(fname)
        link = f'https://zenodo.org/records/${RECORD_ID}/files/{encoded_name}?download=1'
    total_size += fsize
    print(f'{fname}|{link}|{fsize}|{checksum}')
print(f'TOTAL_SIZE|{total_size}')
")

if [[ "$file_list" == "NO_FILES" ]]; then
    log "ERROR: No files found in record."
    exit 1
fi

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
echo "$file_entries" | while IFS='|' read -r fname link fsize checksum; do
    fsize_h=$(python3 -c "
s = $fsize
for u in ['B','KB','MB','GB']:
    if s < 1024: print(f'{s:.1f} {u}'); break
    s /= 1024
")
    echo "  $fname ($fsize_h)"
done | tee -a "$LOG_FILE"
echo ""

# --- Step 2: Download each file ----------------------------------------------
log "================================================================"
log "  Starting downloads with resume support..."
log "================================================================"

downloaded=0
failed=0
skipped=0
verified=0
failed_files=""

verify_checksum() {
    local filepath="$1"
    local expected="$2"

    # Zenodo checksums are in format "md5:abc123..."
    if [[ -z "$expected" ]] || [[ "$expected" == "null" ]]; then
        return 0  # No checksum to verify
    fi

    local algo="${expected%%:*}"
    local hash="${expected#*:}"

    if [[ "$algo" != "md5" ]]; then
        log "  [CHECKSUM] Unknown algorithm: ${algo}, skipping verification"
        return 0
    fi

    local actual
    actual=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1)

    if [[ "$actual" == "$hash" ]]; then
        log "  [CHECKSUM] MD5 verified OK"
        verified=$((verified + 1))
        return 0
    else
        log "  [CHECKSUM] MISMATCH: expected ${hash}, got ${actual}"
        return 1
    fi
}

download_file() {
    local fname="$1"
    local url="$2"
    local expected_size="$3"
    local checksum="$4"

    local output_path="${OUTPUT_DIR}/${fname}"

    # Skip if already fully downloaded and checksum matches
    if [[ -f "$output_path" ]]; then
        local current_size
        current_size=$(stat -c%s "$output_path" 2>/dev/null || stat -f%z "$output_path" 2>/dev/null || echo 0)
        if [[ "$current_size" -ge "$expected_size" ]] && [[ "$expected_size" -gt 0 ]]; then
            # Verify checksum before skipping
            if verify_checksum "$output_path" "$checksum"; then
                log "  [SKIP] Already complete and verified: ${fname}"
                skipped=$((skipped + 1))
                return 0
            else
                log "  [REDOWNLOAD] Checksum mismatch, deleting and re-downloading: ${fname}"
                rm -f "$output_path"
            fi
        else
            log "  [RESUME] Partial file: ${current_size}/${expected_size} bytes"
        fi
    fi

    local attempt=0
    local delay=$RETRY_DELAY

    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        log "  [ATTEMPT ${attempt}/${MAX_RETRIES}] ${fname}"

        set +e
        curl \
            -L \
            -C - \
            -o "$output_path" \
            --globoff \
            --connect-timeout "$CONNECT_TIMEOUT" \
            --speed-limit "$SPEED_LIMIT" \
            --speed-time "$SPEED_TIME" \
            --retry 3 \
            --retry-delay 5 \
            --retry-connrefused \
            --keepalive-time 60 \
            --tcp-nodelay \
            --progress-bar \
            "$url" 2>>"$LOG_FILE"
        local exit_code=$?
        set -e

        if [[ $exit_code -eq 0 ]]; then
            local actual_size
            actual_size=$(stat -c%s "$output_path" 2>/dev/null || stat -f%z "$output_path" 2>/dev/null || echo 0)

            if [[ "$expected_size" -gt 0 ]] && [[ "$actual_size" -lt "$expected_size" ]]; then
                log "  [INCOMPLETE] ${actual_size}/${expected_size} bytes. Retrying..."
            else
                # Verify checksum
                if verify_checksum "$output_path" "$checksum"; then
                    log "  [DONE] ${fname} (${actual_size} bytes)"
                    downloaded=$((downloaded + 1))
                    return 0
                else
                    log "  [CORRUPT] Checksum failed. Deleting and retrying..."
                    rm -f "$output_path"
                fi
            fi
        else
            case $exit_code in
                6)  log "  [ERROR] Could not resolve host." ;;
                7)  log "  [ERROR] Connection refused." ;;
                18) log "  [ERROR] Partial transfer — will resume." ;;
                28) log "  [ERROR] Timeout — stalled connection." ;;
                33) log "  [ERROR] Resume not supported. Restarting..."
                    rm -f "$output_path" ;;
                56) log "  [ERROR] Connection reset." ;;
                *)  log "  [ERROR] curl exit code: ${exit_code}" ;;
            esac
        fi

        local jitter=$((RANDOM % 10))
        local wait_time=$((delay + jitter))
        log "  [WAIT] ${wait_time}s before retry..."
        sleep "$wait_time"

        delay=$((delay * 2))
        if [[ $delay -gt $MAX_RETRY_DELAY ]]; then
            delay=$MAX_RETRY_DELAY
        fi
    done

    log "  [FAILED] Gave up after ${MAX_RETRIES} attempts: ${fname}"
    failed=$((failed + 1))
    failed_files="${failed_files}\n  - ${fname}"
    return 1
}

# Also offer the full archive download as an alternative
log ""
log "NOTE: You can also download the entire archive at once."
log "      The script will download individual files for better resume support."
log ""

file_index=0
while IFS='|' read -r fname link fsize checksum; do
    file_index=$((file_index + 1))
    echo ""
    log "[${file_index}/${file_count}] ${fname}"
    download_file "$fname" "$link" "$fsize" "$checksum" || true
done <<< "$file_entries"

# --- Step 3: Summary ---------------------------------------------------------
echo ""
log "================================================================"
log "  Download Summary — Zenodo Record ${RECORD_ID}"
log "================================================================"
log "  Output directory: $(cd "$OUTPUT_DIR" && pwd)"
log "  Log file:         ${LOG_FILE}"
log ""
log "  Downloaded:  ${downloaded}"
log "  Skipped:     ${skipped} (already complete)"
log "  Verified:    ${verified} (checksum OK)"
log "  Failed:      ${failed}"

if [[ -n "$failed_files" ]]; then
    log ""
    log "  Failed files:${failed_files}"
fi

actual_size=$(du -sh "$OUTPUT_DIR" 2>/dev/null | cut -f1)
actual_count=$(find "$OUTPUT_DIR" -type f | wc -l)
log ""
log "  Files on disk: ${actual_count}"
log "  Total size:    ${actual_size}"
log ""

if [[ $failed -gt 0 ]]; then
    log "  WARNING: Some files failed. Re-run to resume:"
    log "  ./download_zenodo.sh"
    exit 1
else
    log "  All ${file_count} files downloaded and verified!"
fi
