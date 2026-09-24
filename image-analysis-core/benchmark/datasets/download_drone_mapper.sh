#!/usr/bin/env bash
# =============================================================================
# PhotoGear - DroneMapper Agriculture Datasets Downloader
# =============================================================================
# Bucket: s3://DroneMapper_US/example/
# Requester Pays — your AWS account is charged for transfer (~$0.09/GB)
#
# PREREQUISITES:
#   1. AWS CLI installed
#   2. AWS credentials configured: aws configure
#
# Usage:
#   chmod +x download_dronemapper.sh
#   ./download_dronemapper.sh
#
# Datasets (raw + processed):
#   1. MicaSense Altum — 6-band multispectral orchard + calibration panel
#   2. Precision Ag R-G-NIR Switzerland — NDVI, management zones, orthomosaic
#   3. Precision Ag R-G-B Indianapolis — orthomosaic, DEM
#   4. Greg Reservoir with GCPs — for positional accuracy benchmarking
# =============================================================================

set -euo pipefail

BUCKET="DroneMapper_US"
OUTPUT_DIR="./dronemapper_agriculture"
LOG_FILE="./download_dronemapper.log"
MAX_RETRIES=10
RETRY_DELAY=15

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

log "================================================================"
log "  DroneMapper Agriculture Datasets Downloader"
log "  Bucket: s3://${BUCKET}/example/"
log "================================================================"

if ! command -v aws &> /dev/null; then
    log "ERROR: AWS CLI not installed."; exit 1
fi
if ! aws sts get-caller-identity &> /dev/null; then
    log "ERROR: AWS credentials not configured. Run: aws configure"; exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
log "AWS account: ${AWS_ACCOUNT}"
log ""
mkdir -p "$OUTPUT_DIR"

downloaded=0
failed=0

download_s3() {
    local s3_path="$1"
    local local_path="$2"
    local description="$3"

    local dir
    dir=$(dirname "$local_path")
    mkdir -p "$dir"

    if [[ -f "$local_path" ]]; then
        local fsize
        fsize=$(stat -c%s "$local_path" 2>/dev/null || stat -f%z "$local_path" 2>/dev/null || echo 0)
        if [[ "$fsize" -gt 1000 ]]; then
            log "  [SKIP] $(basename "$local_path")"
            downloaded=$((downloaded + 1))
            return 0
        fi
    fi

    local attempt=0
    while [[ $attempt -lt $MAX_RETRIES ]]; do
        attempt=$((attempt + 1))
        log "  [${attempt}/${MAX_RETRIES}] ${description}"

        set +e
        aws s3 cp "s3://${s3_path}" "$local_path" \
            --request-payer requester \
            2>>"$LOG_FILE"
        local rc=$?
        set -e

        if [[ $rc -eq 0 ]] && [[ -f "$local_path" ]]; then
            local sz
            sz=$(stat -c%s "$local_path" 2>/dev/null || echo 0)
            log "  [DONE] $(basename "$local_path") (${sz} bytes)"
            downloaded=$((downloaded + 1))
            return 0
        fi
        log "  [RETRY] waiting ${RETRY_DELAY}s..."
        sleep "$RETRY_DELAY"
    done

    log "  [FAILED] ${description}"
    failed=$((failed + 1))
    return 1
}

# =========================================================================
# 1. MicaSense Altum (Multispectral Orchard)
# =========================================================================
log "================================================================"
log "  1. MicaSense Altum — Multispectral Orchard"
log "     6 bands: R, G, B, NIR, RedEdge, Thermal + calibration panel"
log "================================================================"
DS1="${OUTPUT_DIR}/01_micasense_altum"

download_s3 \
    "DroneMapper_US/example/RGBNET-MicaSense.zip" \
    "${DS1}/processed/RGBNET-MicaSense.zip" \
    "Altum processed (ortho, DEM, point cloud)" || true

log ""
log "  Raw Altum data hosted by MicaSense (not S3 Requester Pays)."
log "  Downloading via curl..."
mkdir -p "${DS1}/raw"
if [[ -f "${DS1}/raw/altum-sample-data.zip" ]] && [[ $(stat -c%s "${DS1}/raw/altum-sample-data.zip" 2>/dev/null || echo 0) -gt 1000 ]]; then
    log "  [SKIP] altum-sample-data.zip"
else
    set +e
    curl -L -C - -o "${DS1}/raw/altum-sample-data.zip" \
        --connect-timeout 30 --speed-limit 1024 --speed-time 60 \
        --retry 10 --retry-delay 10 --keepalive-time 60 \
        --progress-bar \
        "https://www.micasense.com/altum-sample-data" 2>>"$LOG_FILE"
    rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
        ftype=$(file "${DS1}/raw/altum-sample-data.zip" 2>/dev/null || true)
        if echo "$ftype" | grep -qi "zip\|archive"; then
            log "  [DONE] altum-sample-data.zip"
            downloaded=$((downloaded + 1))
        else
            log "  [NOTE] URL returned HTML, not a zip. Download manually:"
            log "         https://www.micasense.com/altum-sample-data"
            rm -f "${DS1}/raw/altum-sample-data.zip"
            failed=$((failed + 1))
        fi
    else
        log "  [NOTE] curl failed. Download manually:"
        log "         https://www.micasense.com/altum-sample-data"
        failed=$((failed + 1))
    fi
fi

# =========================================================================
# 2. Precision Ag R-G-NIR — Switzerland
# =========================================================================
log ""
log "================================================================"
log "  2. Precision Ag R-G-NIR — Switzerland"
log "     Canon S110 (R, G, NIR) — 3.7 cm GSD, 101 images"
log "     NDVI + management zones + orthomosaic"
log "================================================================"
DS2="${OUTPUT_DIR}/02_precision_ag_switzerland_rgnir"

download_s3 \
    "DroneMapper_US/example/Ag/DroneMapper_ManagementZoneAOI_ClassNDVI.zip" \
    "${DS2}/processed/ManagementZone_ClassNDVI.zip" \
    "Management zone shapefile" || true

download_s3 \
    "DroneMapper_US/example/Ag/Ortho-DroneMapper.kmz" \
    "${DS2}/processed/Ortho-DroneMapper.kmz" \
    "Orthomosaic KMZ" || true

download_s3 \
    "DroneMapper_US/example/Ag/NDVI-DroneMapper.kmz" \
    "${DS2}/processed/NDVI-DroneMapper.kmz" \
    "NDVI KMZ" || true

download_s3 \
    "DroneMapper_US/example/Ag/RdYlGn_NDVI-Legend.PNG" \
    "${DS2}/processed/NDVI-Legend.png" \
    "NDVI legend" || true

download_s3 \
    "DroneMapper_US/example/Ag/Ortho-DroneMapper.tif" \
    "${DS2}/processed/Ortho-DroneMapper.tif" \
    "Orthomosaic GeoTIFF" || true

download_s3 \
    "DroneMapper_US/example/Ag/NDVI-DroneMapper.tif" \
    "${DS2}/processed/NDVI-DroneMapper.tif" \
    "NDVI GeoTIFF" || true

log ""
log "  Raw R-G-NIR images hosted by Pix4D. Download manually:"
log "  https://support.pix4d.com/hc/en-us/articles/202561429"
log "  Save to: ${DS2}/raw/"

# =========================================================================
# 3. Precision Ag R-G-B — Indianapolis
# =========================================================================
log ""
log "================================================================"
log "  3. Precision Ag R-G-B — Indianapolis"
log "     Precision Hawk UAV, 644 images, 4 cm GSD"
log "================================================================"
DS3="${OUTPUT_DIR}/03_precision_ag_indianapolis_rgb"

download_s3 \
    "DroneMapper_US/example/PHawkAg/DroneMapper_PrecisionAg_RGB_Ortho.kmz" \
    "${DS3}/processed/PrecisionAg_RGB_Ortho.kmz" \
    "Indianapolis orthomosaic KMZ" || true

download_s3 \
    "DroneMapper_US/example/PHawkAg/DroneMapper_PrecisionAg_RGB_DEM.zip" \
    "${DS3}/processed/PrecisionAg_RGB_DEM.zip" \
    "Indianapolis DEM" || true

download_s3 \
    "DroneMapper_US/example/PHawkAg/DroneMapper_PrecisionAg_RGB_Ortho.zip" \
    "${DS3}/processed/PrecisionAg_RGB_Ortho.zip" \
    "Indianapolis orthomosaic GeoTIFF" || true

# =========================================================================
# 4. Greg Reservoir with GCPs (accuracy benchmarking)
# =========================================================================
log ""
log "================================================================"
log "  4. Greg Reservoir + GCPs — Grand Mesa, Colorado"
log "     189 images + Trimble 5800 surveyed GCPs"
log "================================================================"
DS4="${OUTPUT_DIR}/04_greg_reservoir_gcp"

download_s3 \
    "DroneMapper_US/example/DroneMapper_Gregg1_2.zip" \
    "${DS4}/DroneMapper_Gregg1_2.zip" \
    "Greg Reservoir raw JPGs + GCP data" || true

# =========================================================================
# Summary
# =========================================================================
echo ""
log "================================================================"
log "  Download Summary"
log "================================================================"
log ""
log "  Output: ${OUTPUT_DIR}/"
log "  Log:    ${LOG_FILE}"
log ""
log "  Downloaded: ${downloaded}"
log "  Failed:     ${failed}"
log ""

for d in "$OUTPUT_DIR"/*/; do
    [[ ! -d "$d" ]] && continue
    dname=$(basename "$d")
    dcount=$(find "$d" -type f | wc -l)
    dsize=$(du -sh "$d" 2>/dev/null | cut -f1)
    log "  ${dname}/ — ${dcount} files, ${dsize}"
done

log ""
log "  Manual downloads needed:"
log "    - Raw R-G-NIR (Switzerland): https://support.pix4d.com/hc/en-us/articles/202561429"
log "    - Raw Altum (if failed):     https://www.micasense.com/altum-sample-data"
log ""
log "  Re-run anytime — completed files are skipped."