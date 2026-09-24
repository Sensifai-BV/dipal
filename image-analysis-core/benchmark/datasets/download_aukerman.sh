#!/usr/bin/env bash
# =============================================================================
# PhotoGear - OpenDroneMap Aukerman Dataset Downloader
# =============================================================================
# Downloads the ODM Aukerman benchmark dataset from GitHub.
# 77 images, ~543 MB, GPS/EXIF georeferenced.
#
# Source: https://github.com/OpenDroneMap/odm_data_aukerman
# DroneDB: https://hub.dronedb.app/r/odm/aukerman
#
# Usage:
#   chmod +x download_aukerman.sh
#   ./download_aukerman.sh
# =============================================================================

set -euo pipefail

URL="https://github.com/OpenDroneMap/odm_data_aukerman/archive/refs/heads/master.zip"
OUTPUT_DIR="./odm_aukerman"
ZIP_FILE="${OUTPUT_DIR}/odm_data_aukerman.zip"
LOG_FILE="./download_aukerman.log"

MAX_RETRIES=50
RETRY_DELAY=10
MAX_RETRY_DELAY=300
SPEED_LIMIT=1024
SPEED_TIME=60

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

log "================================================================"
log "  OpenDroneMap Aukerman Dataset Downloader"
log "  77 images, ~543 MB"
log "================================================================"

mkdir -p "$OUTPUT_DIR"

# Check if already extracted
if [[ -d "${OUTPUT_DIR}/odm_data_aukerman-master/images" ]]; then
    img_count=$(find "${OUTPUT_DIR}/odm_data_aukerman-master/images" -type f \( -iname '*.jpg' -o -iname '*.JPG' -o -iname '*.tif' \) | wc -l)
    if [[ "$img_count" -ge 70 ]]; then
        log "Already downloaded and extracted (${img_count} images found)."
        log "Location: ${OUTPUT_DIR}/odm_data_aukerman-master/"
        exit 0
    fi
fi

# Download with resume and retries
attempt=0
delay=$RETRY_DELAY

while [[ $attempt -lt $MAX_RETRIES ]]; do
    attempt=$((attempt + 1))
    log "[ATTEMPT ${attempt}/${MAX_RETRIES}] Downloading..."

    set +e
    curl \
        -L \
        -C - \
        -o "$ZIP_FILE" \
        --globoff \
        --connect-timeout 30 \
        --speed-limit "$SPEED_LIMIT" \
        --speed-time "$SPEED_TIME" \
        --retry 3 \
        --retry-delay 5 \
        --retry-connrefused \
        --keepalive-time 60 \
        --tcp-nodelay \
        --progress-bar \
        "$URL" 2>>"$LOG_FILE"
    rc=$?
    set -e

    if [[ $rc -eq 0 ]] && [[ -f "$ZIP_FILE" ]]; then
        fsize=$(stat -c%s "$ZIP_FILE" 2>/dev/null || stat -f%z "$ZIP_FILE" 2>/dev/null || echo 0)
        if [[ $fsize -gt 1000000 ]]; then
            log "[DONE] Downloaded $(python3 -c "print(f'{$fsize/1048576:.1f} MB')")"
            break
        else
            log "[ERROR] File too small (${fsize} bytes). Retrying..."
            rm -f "$ZIP_FILE"
        fi
    else
        case $rc in
            6)  log "[ERROR] DNS resolution failed." ;;
            7)  log "[ERROR] Connection refused." ;;
            18) log "[ERROR] Partial transfer — will resume." ;;
            28) log "[ERROR] Timeout." ;;
            33) log "[ERROR] Resume not supported. Restarting..."
                rm -f "$ZIP_FILE" ;;
            56) log "[ERROR] Connection reset." ;;
            *)  log "[ERROR] curl exit code: ${rc}" ;;
        esac
    fi

    if [[ $attempt -ge $MAX_RETRIES ]]; then
        log "[FAILED] Could not download after ${MAX_RETRIES} attempts."
        exit 1
    fi

    jitter=$((RANDOM % 10))
    wait_time=$((delay + jitter))
    log "[WAIT] ${wait_time}s before retry..."
    sleep "$wait_time"

    delay=$((delay * 2))
    if [[ $delay -gt $MAX_RETRY_DELAY ]]; then
        delay=$MAX_RETRY_DELAY
    fi
done

# Extract
log ""
log "Extracting..."
if command -v unzip &> /dev/null; then
    unzip -o -q "$ZIP_FILE" -d "$OUTPUT_DIR" 2>>"$LOG_FILE"
else
    python3 -c "
import zipfile, sys
with zipfile.ZipFile('${ZIP_FILE}', 'r') as z:
    z.extractall('${OUTPUT_DIR}')
print('Extracted')
" 2>>"$LOG_FILE"
fi

# Verify
if [[ -d "${OUTPUT_DIR}/odm_data_aukerman-master" ]]; then
    img_count=$(find "${OUTPUT_DIR}/odm_data_aukerman-master" -type f \( -iname '*.jpg' -o -iname '*.JPG' -o -iname '*.tif' \) | wc -l)
    total_size=$(du -sh "${OUTPUT_DIR}/odm_data_aukerman-master" 2>/dev/null | cut -f1)

    log "[OK] Extracted: ${img_count} images, ${total_size}"
    log ""
    log "Dataset location: ${OUTPUT_DIR}/odm_data_aukerman-master/"
    log "Images:           ${OUTPUT_DIR}/odm_data_aukerman-master/images/"

    # Clean up zip
    log ""
    read -rp "Delete zip file to save space? [y/N]: " delete_zip
    if [[ "${delete_zip,,}" == "y" ]]; then
        rm -f "$ZIP_FILE"
        log "Zip deleted."
    fi
else
    log "[ERROR] Extraction failed — expected directory not found."
    exit 1
fi

log ""
log "Done. Re-run anytime — skips if already extracted."