from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pycolmap
from PIL import Image
from PIL.ExifTags import GPSTAGS
from psygnal import Signal
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.logging import get_logger

logger = get_logger(__name__)

from .interfaces import IService

ProjectId = str
StepName = str


def _count_ply_vertices(ply_path: Path) -> int:
    """
    Read the vertex count from a PLY file header without loading the full file.

    Returns 0 if the file does not exist, is not a PLY file, or has no vertices.
    """
    if not ply_path.exists():
        return 0
    try:
        with open(ply_path, "rb") as fh:
            for _ in range(30):  # header is always within the first 30 lines
                line = fh.readline().decode("ascii", errors="ignore").strip()
                if line.startswith("element vertex"):
                    return int(line.split()[-1])
                if line == "end_header":
                    break
    except Exception:
        pass
    return 0


# COLMAP camera model_id → name (subset; see colmap/src/colmap/sensor/models.h).
_COLMAP_MODEL_NAMES: dict[int, str] = {
    0: "SIMPLE_PINHOLE",
    1: "PINHOLE",
    2: "SIMPLE_RADIAL",
    3: "RADIAL",
    4: "OPENCV",
    5: "OPENCV_FISHEYE",
    6: "FULL_OPENCV",
}


def _import_images_with_model(
    database_path: Path, image_path: Path, camera_model: str,
) -> None:
    """
    Run ``pycolmap.import_images`` with the camera model pinned to ``camera_model``.

    import_images pre-creates the camera rows; without pinning the model pycolmap
    defaults to SIMPLE_RADIAL, which under-models drone-lens distortion and domes
    the reconstruction.  pycolmap's API for passing reader options varies across
    builds (``options=`` vs ``reader_options=``; the model attribute may be
    ``camera_model`` and is set on an ``ImageReaderOptions`` instance), so this
    sets the model defensively with ``setattr`` and tries the known call shapes,
    finally falling back to a plain import (model is then corrected by the
    feature_extractor CLI and surfaced by ``_verify_camera_model``).

    Args:
        database_path: COLMAP SQLite database path
        image_path: Directory of input images
        camera_model: Camera model name to pin (e.g. "OPENCV")
    """
    reader_options = None
    try:
        reader_options = pycolmap.ImageReaderOptions()
        if hasattr(reader_options, "camera_model"):
            reader_options.camera_model = camera_model
        else:
            logger.warning(
                "pycolmap.ImageReaderOptions has no 'camera_model' attribute in "
                "this build; relying on feature_extractor to set the model.",
            )
    except Exception as exc:
        logger.warning(f"Could not build ImageReaderOptions: {exc}")
        reader_options = None

    base = dict(database_path=str(database_path), image_path=str(image_path),
                camera_mode=pycolmap.CameraMode.AUTO)

    # Try the call shapes that carry the reader options, then a plain import.
    # pycolmap 3.13 signature is
    #   import_images(database_path, image_path, camera_mode, image_names=[], options=…)
    # but older/newer builds have used image_list / reader_options, so try each.
    attempts = []
    if reader_options is not None:
        attempts.append({**base, "options": reader_options})
        attempts.append({**base, "image_names": [], "options": reader_options})
        attempts.append({**base, "image_list": [], "options": reader_options})
        attempts.append({**base, "reader_options": reader_options})
    attempts.append(base)

    last_err: Exception | None = None
    for kwargs in attempts:
        try:
            pycolmap.import_images(**kwargs)
            return
        except TypeError as exc:
            last_err = exc
            continue  # signature mismatch — try the next shape
    # Every shape failed on signature grounds; re-raise the last error.
    if last_err is not None:
        raise last_err


def _verify_camera_model(database_path: Path, expected_model: str) -> None:
    """
    Read back the camera model from the COLMAP database and warn on mismatch.

    The COLMAP database is a SQLite file; the ``cameras`` table stores a
    ``model`` integer id.  ``import_images`` pre-creates the cameras, and if the
    model is not pinned it defaults to SIMPLE_RADIAL — a single-k1 model too weak
    for drone lenses, which causes reconstruction doming.  This check surfaces
    that failure at extract time instead of leaving it to be discovered as a
    bowl-shaped DSM much later.

    Args:
        database_path: Path to the COLMAP SQLite database
        expected_model: Camera model name configured for this run (e.g. OPENCV)
    """
    import sqlite3

    try:
        con = sqlite3.connect(str(database_path))
        try:
            rows = con.execute("SELECT DISTINCT model FROM cameras").fetchall()
        finally:
            con.close()
    except Exception as exc:
        logger.debug(f"Could not read camera model from database: {exc}")
        return

    models = {_COLMAP_MODEL_NAMES.get(r[0], f"id={r[0]}") for r in rows}
    if not models:
        return
    if models == {expected_model}:
        logger.info(f"Camera model in database: {expected_model} (as configured)")
    else:
        logger.warning(
            f"Camera model mismatch: database has {sorted(models)} but "
            f"'{expected_model}' was configured.  A weak model (e.g. SIMPLE_RADIAL) "
            "under-models lens distortion and causes reconstruction doming.  "
            "Check that import_images pinned the model.",
        )


# COLMAP camera models that accept the OPENCV parameter block
# [fx, fy, cx, cy, k1, k2, p1, p2].  FULL_OPENCV extends with k3..k6 (zero-filled).
_OPENCV_PARAM_COUNT: dict[str, int] = {"OPENCV": 8, "FULL_OPENCV": 12}


def _parse_dji_dewarp_intrinsics(
    image_dir: Path,
) -> tuple[float, float, float, float, float, float, float, float, float] | None:
    """
    Parse DJI factory camera intrinsics from a sample image's ``DewarpData`` XMP.

    DJI embeds a per-camera factory calibration in the ``drone-dji:DewarpData``
    tag as ``date;fx,fy,cx,cy,k1,k2,p1,p2,k3``, where ``fx,fy`` are focal lengths
    in pixels and ``cx,cy`` are the principal-point offset **relative to the image
    centre**.  These are the manufacturer's known interior orientation; seeding and
    fixing them prevents COLMAP/GLOMAP from self-calibrating a wrong focal length
    under weak nadir-only geometry (which trades focal against flying height and
    domes the surface — see docs/architecture/adr/0002).

    Reads only the leading bytes of one image (XMP lives in the APP1 segment near
    the file start), so it is cheap.

    Args:
        image_dir: Directory of source images (the RGB images for SFM).

    Returns:
        ``(fx, fy, cx_off, cy_off, k1, k2, p1, p2, k3)`` or ``None`` if no image
        carries a parseable ``DewarpData`` tag.
    """
    candidates = sorted(
        p for p in image_dir.glob("*")
        if p.suffix.lower() in {".jpg", ".jpeg", ".tif", ".tiff"}
    )
    for img in candidates[:5]:
        try:
            with open(img, "rb") as fh:
                head = fh.read(524288).decode("latin-1", errors="ignore")
        except OSError:
            continue
        m = re.search(r'drone-dji:DewarpData="[^;"]*;([^"]+)"', head)
        if not m:
            continue
        try:
            vals = [float(x) for x in m.group(1).split(",")]
        except ValueError:
            continue
        if len(vals) >= 9:
            fx, fy, cx, cy, k1, k2, p1, p2, k3 = vals[:9]
            return (fx, fy, cx, cy, k1, k2, p1, p2, k3)
    return None


# COLMAP model id for FULL_OPENCV (see _COLMAP_MODEL_NAMES).  Seeding upgrades the
# camera to this model so the factory k3 radial term is carried: the plain OPENCV
# model has no k3 slot, and dropping it leaves ~20% of the edge radial distortion
# unmodelled — which (with intrinsics fixed) bends the bundle-adjustment geometry
# into a dome.  Empirically: OPENCV-no-k3 fixed → 5.6% sparse bowl; FULL_OPENCV+k3
# fixed → 0.5% (flatter than self-calibration).  See docs/architecture/adr/0002.
_FULL_OPENCV_MODEL_ID = 6


def _seed_camera_intrinsics(
    database_path: Path,
    camera_model: str,
    intrinsics: tuple[float, float, float, float, float, float, float, float, float],
) -> bool:
    """
    Overwrite the COLMAP database camera with DJI factory intrinsics (FULL_OPENCV).

    Runs after ``import_images`` (which pre-creates the camera with a guessed focal
    length) and before reconstruction.  Reads the image dimensions back from the
    camera row, converts the ``DewarpData`` centre-relative principal point to
    absolute pixels, and writes the **FULL_OPENCV** parameter block
    ``[fx, fy, cx, cy, k1, k2, p1, p2, k3, 0, 0, 0]`` — upgrading the camera model
    so the factory **k3** radial term is included (the plain OPENCV model has no k3
    slot).  Combined with disabling intrinsic refinement in GLOMAP and the bundle
    adjuster, this pins the complete interior orientation to the manufacturer
    calibration and removes the free parameters that cause doming.

    Only runs when the configured model is an OPENCV-family model; other models are
    left to self-calibration (returns False).

    Args:
        database_path: COLMAP SQLite database path.
        camera_model: Configured camera model name (e.g. "OPENCV"); used only as a
            gate — the seeded camera is always written as FULL_OPENCV.
        intrinsics: ``(fx, fy, cx_off, cy_off, k1, k2, p1, p2, k3)`` from
            :func:`_parse_dji_dewarp_intrinsics`.

    Returns:
        True if factory intrinsics were written to every camera, else False.
    """
    import sqlite3
    import struct

    if camera_model not in _OPENCV_PARAM_COUNT:
        logger.info(
            f"Factory-intrinsic seeding supports OPENCV/FULL_OPENCV only; "
            f"camera_model={camera_model} left to self-calibration.",
        )
        return False

    fx, fy, cx_off, cy_off, k1, k2, p1, p2, k3 = intrinsics

    try:
        con = sqlite3.connect(str(database_path))
        try:
            rows = con.execute(
                "SELECT camera_id, width, height FROM cameras",
            ).fetchall()
            if not rows:
                return False
            for camera_id, width, height in rows:
                cx = width / 2.0 + cx_off
                cy = height / 2.0 + cy_off
                # FULL_OPENCV: [fx, fy, cx, cy, k1, k2, p1, p2, k3, k4, k5, k6]
                params = [fx, fy, cx, cy, k1, k2, p1, p2, k3, 0.0, 0.0, 0.0]
                blob = struct.pack(f"<{len(params)}d", *params)
                con.execute(
                    "UPDATE cameras SET model=?, params=?, prior_focal_length=1 "
                    "WHERE camera_id=?",
                    (_FULL_OPENCV_MODEL_ID, blob, camera_id),
                )
            con.commit()
        finally:
            con.close()
    except Exception as exc:
        logger.warning(f"Could not seed factory intrinsics: {exc}")
        return False

    logger.info(
        f"Seeded factory intrinsics into {len(rows)} camera(s) as FULL_OPENCV: "
        f"fx={fx:.2f} fy={fy:.2f} cx_off={cx_off:+.2f} cy_off={cy_off:+.2f} "
        f"k1={k1:.5f} k2={k2:.5f} k3={k3:.5f} (upgraded from {camera_model} to "
        "carry k3); intrinsic refinement will be disabled to prevent doming.",
    )
    return True


def _intrinsics_are_seeded(database_path: Path) -> bool:
    """
    Return True if the database cameras were seeded with fixed factory intrinsics.

    Seeding sets ``prior_focal_length=1`` on every camera (see
    :func:`_seed_camera_intrinsics`).  This persistent DB flag lets the
    reconstruction and bundle-adjustment steps decide whether to disable intrinsic
    refinement, independently of in-process state — so a resumed run reads the same
    answer it wrote.  Returns False on any read error or if no camera is flagged.

    Args:
        database_path: COLMAP SQLite database path.
    """
    import sqlite3

    if not database_path.exists():
        return False
    try:
        con = sqlite3.connect(str(database_path))
        try:
            rows = con.execute(
                "SELECT prior_focal_length FROM cameras",
            ).fetchall()
        finally:
            con.close()
    except Exception:
        return False
    return bool(rows) and all(r[0] == 1 for r in rows)


def _extract_gps_from_images(image_dir: Path) -> list[tuple[str, float, float, float]]:
    """
    Extract GPS (filename, lat, lon, alt) from EXIF of all images in a directory.

    Uses PIL's modern ``getexif()`` API (Pillow ≥ 6.0) which works for both
    JPEG and TIFF files.  Falls back to the legacy ``_getexif()`` (JPEG only)
    if ``getexif()`` is unavailable.

    Args:
        image_dir: Directory containing drone images with GPS EXIF

    Returns:
        List of (filename, latitude, longitude, altitude_m) tuples.
        altitude defaults to 0.0 when the GPSAltitude tag is absent.
    """
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}
    results: list[tuple[str, float, float, float]] = []

    for image_path in image_dir.iterdir():
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            with Image.open(image_path) as img:
                # getexif() works for JPEG and TIFF (Pillow >= 6.0).
                # get_ifd(0x8825) returns the GPS sub-IFD as {tag_id: value}.
                exif = img.getexif()
                raw_gps = exif.get_ifd(0x8825)  # 0x8825 = GPSInfo IFD tag

            if not raw_gps:
                continue

            gps = {GPSTAGS.get(k, k): v for k, v in raw_gps.items()}

            if "GPSLatitude" not in gps or "GPSLongitude" not in gps:
                continue

            def _dms_to_decimal(dms: tuple, ref: str) -> float:
                deg, minutes, seconds = dms
                decimal = float(deg) + float(minutes) / 60.0 + float(seconds) / 3600.0
                if ref in ("S", "W"):
                    decimal = -decimal
                return decimal

            lat = _dms_to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
            lon = _dms_to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])

            alt = 0.0
            if "GPSAltitude" in gps:
                alt = float(gps["GPSAltitude"])
                if gps.get("GPSAltitudeRef") == 1:  # below sea level
                    alt = -alt

            results.append((image_path.name, lat, lon, alt))
        except Exception:
            continue

    return results


def _parse_mrk_file(mrk_path: Path) -> dict[str, tuple[float, float, float]]:
    """
    Parse a DJI PPK Timestamp Mark (.MRK) file.

    Extracts a per-image GPS position at RTK/PPK accuracy.  Each line of the MRK
    file records one image capture event.  The index in column 0 maps to the
    4-digit sequence number embedded in DJI image filenames
    (e.g. index 1 → ``DJI_..._0001_D.JPG``).

    DJI M3M RTK format (tab/space separated, tagged coordinate tokens)::

        <n>  <GPS_sec>  [<sats>]  <dN>,N  <dE>,E  <dV>,V  <lat>,Lat  <lon>,Lon  <alt>,Ellh  ...

    Example::

        1  454400.746373  [2323]  -40,N  -15,E  83,V  41.13015180,Lat  23.42749964,Lon  94.597,Ellh  ...

    The comma-tagged tokens ``<value>,Lat``, ``<value>,Lon``, ``<value>,Ellh``
    are the definitive coordinate fields regardless of column position.

    Args:
        mrk_path: Path to the ``.MRK`` file

    Returns:
        Mapping of zero-padded 4-digit image index (str) to ``(lat, lon, alt_m)``
        tuples.  Empty dict when the file cannot be parsed.
    """
    _LAT_RE = re.compile(r"([\d.]+),Lat")
    _LON_RE = re.compile(r"([\d.]+),Lon")
    _ELLH_RE = re.compile(r"([\d.]+),Ellh")

    result: dict[str, tuple[float, float, float]] = {}
    try:
        text = mrk_path.read_text(errors="replace")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue

            parts = line.split()
            if not parts:
                continue
            try:
                idx = int(parts[0])
            except ValueError:
                continue

            lat_m = _LAT_RE.search(line)
            lon_m = _LON_RE.search(line)
            alt_m = _ELLH_RE.search(line)

            if lat_m and lon_m and alt_m:
                result[f"{idx:04d}"] = (
                    float(lat_m.group(1)),
                    float(lon_m.group(1)),
                    float(alt_m.group(1)),
                )
                continue

            # Fallback: plain-float format (no comma tags) used by older firmware.
            # "2024/07/19"  (date only token) → time is next token → coord_start=3
            # "2024/07/19T08:43:15.123" (combined) → coord_start=2
            if len(parts) > 1 and re.match(r"\d{4}[/-]\d{2}[/-]\d{2}$", parts[1]):
                coord_start = 3
            else:
                coord_start = 2

            if len(parts) < coord_start + 3:
                continue
            try:
                lat = float(parts[coord_start])
                lon = float(parts[coord_start + 1])
                alt = float(parts[coord_start + 2])
                result[f"{idx:04d}"] = (lat, lon, alt)
            except ValueError:
                continue

    except Exception as exc:
        logger.warning(f"Failed to parse MRK file {mrk_path.name}: {exc}")

    return result


def _upgrade_gps_with_ppk(
    exif_entries: list[tuple[str, float, float, float]],
    mrk_gps: dict[str, tuple[float, float, float]],
) -> tuple[list[tuple[str, float, float, float]], int]:
    """
    Replace EXIF GPS with higher-accuracy PPK positions where available.

    Matches each image filename against the MRK index by extracting the
    4-digit sequence number embedded in DJI filenames
    (``DJI_YYYYMMDDHHMMSS_NNNN_X.JPG`` → ``NNNN``).

    Args:
        exif_entries: List of ``(filename, lat, lon, alt)`` from EXIF
        mrk_gps: Index → ``(lat, lon, alt)`` from ``_parse_mrk_file``

    Returns:
        Tuple of (upgraded_entries, num_upgraded)
    """
    upgraded_entries: list[tuple[str, float, float, float]] = []
    num_upgraded = 0
    for name, lat, lon, alt in exif_entries:
        m = re.search(r"_(\d{4})_[A-Za-z]\.", name)
        if m:
            key = m.group(1)
            if key in mrk_gps:
                lat, lon, alt = mrk_gps[key]
                num_upgraded += 1
        upgraded_entries.append((name, lat, lon, alt))
    return upgraded_entries, num_upgraded


def _gps_to_ecef(lat: float, lon: float, alt: float) -> tuple[float, float, float]:
    """
    Convert GPS coordinates (WGS84) to ECEF (Earth-Centered Earth-Fixed) metres.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        alt: Altitude above WGS84 ellipsoid in metres

    Returns:
        (X, Y, Z) in ECEF metres
    """
    a = 6378137.0          # WGS84 semi-major axis (m)
    e2 = 0.00669437999014  # WGS84 first eccentricity squared
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    sin_lat = math.sin(lat_r)
    cos_lat = math.cos(lat_r)
    N = a / math.sqrt(1.0 - e2 * sin_lat * sin_lat)
    X = (N + alt) * cos_lat * math.cos(lon_r)
    Y = (N + alt) * cos_lat * math.sin(lon_r)
    Z = ((1.0 - e2) * N + alt) * sin_lat
    return X, Y, Z


def _utm_epsg_from_latlon(lat: float, lon: float) -> int:
    """
    Compute the WGS84 UTM EPSG code for a given geographic position.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees

    Returns:
        EPSG code for the UTM zone (e.g. 32636 for zone 36N)
    """
    zone = math.floor((lon + 180.0) / 6.0) + 1
    if lat >= 0:
        return 32600 + zone
    return 32700 + zone


def _filter_misaligned_cameras(
    sparse_path: Path,
    ref_images_txt: Path,
    max_error_m: float,
) -> tuple[int, int]:
    """
    Remove cameras whose ECEF position (after model_aligner) deviates from
    their GPS reference by more than *max_error_m* metres.

    GLOMAP sometimes produces a bimodal error distribution: the majority of
    cameras align well (< 1 m), but a tail of outliers can be tens or hundreds
    of metres away.  Keeping those outliers in the sparse model causes
    patch_match_stereo to produce incoherent depth maps, which stereo_fusion
    then rejects almost entirely (fused.ply ends up with only a handful of
    points).

    Args:
        sparse_path:    Path to the COLMAP sparse model directory (``sparse/0/``).
        ref_images_txt: Path to the reference-images text file written by
                        ``geo_register`` (``image_name lat lon alt`` per line).
        max_error_m:    Discard cameras farther than this many metres from GPS.

    Returns:
        (num_removed, num_kept) — count of frames removed / kept.
    """
    # Parse GPS reference positions → ECEF
    gps_ecef: dict[str, tuple[float, float, float]] = {}
    with open(ref_images_txt) as fh:
        for line in fh:
            parts = line.strip().split()
            if len(parts) >= 4:
                name = parts[0]
                lat, lon, alt = float(parts[1]), float(parts[2]), float(parts[3])
                gps_ecef[name] = _gps_to_ecef(lat, lon, alt)

    reconstruction = pycolmap.Reconstruction(str(sparse_path))

    frames_to_remove: set[int] = set()
    for image in reconstruction.images.values():
        if not image.has_pose:
            continue
        ref = gps_ecef.get(image.name)
        if ref is None:
            continue
        center = image.projection_center()  # numpy array [X, Y, Z] in ECEF
        error = math.sqrt(
            (center[0] - ref[0]) ** 2
            + (center[1] - ref[1]) ** 2
            + (center[2] - ref[2]) ** 2
        )
        if error > max_error_m:
            frames_to_remove.add(image.frame_id)

    num_kept = reconstruction.num_reg_frames() - len(frames_to_remove)
    if frames_to_remove:
        for frame_id in frames_to_remove:
            reconstruction.deregister_frame(frame_id)
        reconstruction.write(str(sparse_path))

    return len(frames_to_remove), num_kept


class ColmapSettings(BaseSettings):
    """Settings for COLMAP service."""

    # ============================================
    # General Settings
    # ============================================
    run_path: Path = Path("run_1")

    feature_type: str = "sift"  # sift, superpoint, etc.
    matcher_type: str = "sequential"  # exhaustive, sequential, spatial, vocab_tree

    # ============================================
    # Feature Extraction Settings (STEP 1)
    # ============================================
    # Camera settings
    camera_model: str = (
        "OPENCV"  # SIMPLE_PINHOLE, PINHOLE, SIMPLE_RADIAL, RADIAL, OPENCV, etc.
    )
    # Seed the camera with the DJI factory DewarpData intrinsics and FIX them
    # (disable focal/principal/distortion refinement in GLOMAP + the bundle
    # adjuster).  Under single-altitude nadir grids the focal length is weakly
    # constrained and self-calibration drifts (measured 5146 px vs factory 3713 px
    # on JOB_11_JUN), trading against flying height and doming the DSM.  Pinning the
    # manufacturer calibration removes that free parameter.  Falls back to
    # self-calibration when no DewarpData is present (non-DJI drones).
    #
    # DEFAULT OFF: not yet validated on a full DSM (the cheap sparse-cloud proxy is
    # unreliable — doming manifests in the dense stage).  Enable per run via
    # COLMAP_SEED_FACTORY_INTRINSICS=true to validate the DSM doming reduction.
    # See docs/architecture/adr/0002.
    seed_factory_intrinsics: bool = False
    single_camera: bool = True  # SFM always reconstructs from RGB-only images — always True
    images_subdir: str = "images"  # Subdirectory within dataset_path where input images live; use "rgb" for multispectral datasets

    # SIFT feature extraction
    sift_max_num_features: int = 16384  # Maximum features per image
    sift_first_octave: int = 0  # First octave in scale-space pyramid (-1 doubles resolution, risky on T4)
    sift_estimate_affine_shape: bool = False  # DSP-SIFT: known CUDA issues on Turing (T4 CC 7.5)
    sift_domain_size_pooling: bool = (
        False  # DSP-SIFT: known CUDA issues on Turing (T4 CC 7.5)
    )
    sift_upright: bool = False  # Allow rotation invariance (False = not upright)

    # Performance settings for feature extraction
    feature_extraction_max_image_size: int = (
        5280  # Maximum image dimension for feature extraction
    )
    feature_extraction_num_threads: int = -1  # -1 = auto (all cores)
    feature_extraction_use_gpu: bool = True
    feature_extraction_gpu_index: str = "0"

    # ============================================
    # Feature Matching Settings (STEP 2)
    # ============================================
    # Sequential matching settings
    sequential_overlap: int = 25  # Number of sequential images to match
    sequential_quadratic_overlap: bool = True  # Check additional image pairs
    sequential_loop_detection: bool = True  # Detect loops in grid patterns
    sequential_loop_detection_num_images: int = 20
    sequential_vocab_tree_path: str = ""  # Path to vocabulary tree (empty = don't use)

    # Matching options
    matching_guided_matching: bool = True  # Use geometric verification
    matching_max_num_matches: int = 65536  # Maximum matches per image pair
    matching_max_ratio: float = 0.75  # Lowe's ratio test threshold
    matching_max_distance: float = 0.65  # Maximum descriptor distance
    matching_cross_check: bool = True  # Bidirectional matching
    # matching_max_error: float = 4.0  # Maximum epipolar error in pixels
    # matching_confidence: float = 0.999  # RANSAC confidence
    # matching_min_inlier_ratio: float = 0.20  # Minimum inlier ratio
    # matching_min_num_inliers: int = 20  # Minimum number of inliers

    # Performance settings for matching
    matching_use_gpu: bool = True
    matching_gpu_index: str = "0"

    # ============================================
    # Mapper Settings (STEP 3 - Sparse Reconstruction with glomap)
    # ============================================
    # Glomap output format
    glomap_output_format: str = "bin"  # Output format for glomap mapper

    # Bundle adjustment settings
    mapper_ba_refine_focal_length: bool = True
    mapper_ba_refine_principal_point: bool = True
    mapper_ba_refine_extra_params: bool = True
    mapper_ba_global_max_num_iterations: int = 100
    mapper_ba_global_frames_ratio: float = 1.2
    mapper_ba_global_points_ratio: float = 1.2
    mapper_ba_global_max_refinements: int = 5
    mapper_ba_local_max_num_iterations: int = 50
    mapper_ba_local_max_refinements: int = 3

    # Glomap bundle adjustment options
    glomap_ba_optimize_rotations: bool = True
    glomap_ba_optimize_translation: bool = True
    glomap_ba_optimize_points: bool = True

    # Mapper general settings
    mapper_min_num_matches: int = 20
    mapper_ignore_watermarks: bool = False
    mapper_multiple_models: bool = False
    mapper_extract_colors: bool = True
    mapper_num_threads: int = -1
    mapper_min_model_size: int = 10
    mapper_ba_local_num_images: int = 6
    mapper_use_prior_position: bool = True
    mapper_prior_position_loss_scale: float = 15.0
    # Glomap constraint type — controls the global positioning objective.
    # ONLY_POINTS           : visual-only (correct default; GPS alignment is done
    #                         separately by geo_register() via model_aligner after
    #                         reconstruction, so glomap must stay in local SFM space)
    # POINTS_AND_CAMERAS_BALANCED : includes GPS camera priors from the COLMAP
    #                         database.  Only use this if pycolmap.import_images
    #                         populates prior_t in a metric coordinate system (ECEF);
    #                         if prior_t is lat/lon/alt the constraints are degenerate
    #                         and glomap will triangulate 0 points.
    # ONLY_CAMERAS          : GPS-only (rarely useful for drone surveys)
    # POINTS_AND_CAMERAS    : visual + GPS, full weight (same caveat as BALANCED)
    glomap_constraint_type: str = "ONLY_POINTS"

    # Initialization settings
    mapper_init_min_num_inliers: int = 50
    mapper_init_max_error: float = 4.0
    mapper_init_max_forward_motion: float = 0.95
    mapper_init_min_tri_angle: float = 3.0

    # Triangulation settings
    mapper_min_angle: float = 1.5
    mapper_complete_max_reproj_error: float = 4.0
    mapper_create_max_angle_error: float = 3.0

    # Absolute pose estimation
    mapper_abs_pose_max_error: float = 12.0
    mapper_abs_pose_min_num_inliers: int = 30
    mapper_abs_pose_min_inlier_ratio: float = 0.25

    # Filtering settings
    mapper_filter_max_reproj_error: float = 4.0
    mapper_filter_min_tri_angle: float = 1.5

    # Registration settings
    mapper_max_reg_trials: int = 3
    mapper_fix_existing_frames: bool = False

    # GPU settings for mapper
    mapper_ba_use_gpu: bool = True
    mapper_ba_gpu_index: str = "0"

    # ============================================
    # Bundle Adjuster Settings (STEP 4)
    # ============================================
    ba_max_num_iterations: int = 100
    ba_refine_focal_length: bool = True
    ba_refine_principal_point: bool = True
    ba_refine_extra_params: bool = True
    ba_use_gpu: bool = True
    ba_gpu_index: str = "0"

    # ============================================
    # Image Undistortion Settings (STEP 5)
    # ============================================
    undistort_max_image_size: int = 5280
    undistort_output_type: str = "COLMAP"  # COLMAP, PMVS, CMP-MVS

    # ============================================
    # Dense Reconstruction Settings (STEP 6)
    # ============================================
    # Patch Match Stereo settings
    patch_match_max_image_size: int = 5280
    patch_match_window_radius: int = 5
    patch_match_window_step: int = 1
    patch_match_num_samples: int = 15
    patch_match_num_iterations: int = 5
    patch_match_geom_consistency: bool = True
    patch_match_geom_consistency_regularizer: float = 0.3
    patch_match_geom_consistency_max_cost: float = 3.0
    patch_match_filter: bool = True
    patch_match_filter_min_ncc: float = 0.1
    patch_match_filter_min_triangulation_angle: float = 1.0
    patch_match_filter_min_num_consistent: int = 2
    patch_match_filter_geom_consistency_max_cost: float = 1.0
    patch_match_cache_size: int = 24
    patch_match_allow_missing_files: bool = False
    patch_match_write_consistency_graph: bool = False
    patch_match_gpu_index: str = "0"

    # Stereo Fusion settings
    fusion_input_type: str = "photometric"  # Input type for stereo fusion
    fusion_mask_path: str = ""
    fusion_num_threads: int = -1
    fusion_max_image_size: int = 5280
    fusion_min_num_pixels: int = 5
    fusion_max_num_pixels: int = 10000
    fusion_max_traversal_depth: int = 100
    fusion_max_reproj_error: float = 2.0
    fusion_max_depth_error: float = 0.05
    fusion_max_normal_error: float = 10.0
    fusion_check_num_images: int = 50
    fusion_use_cache: bool = True
    fusion_cache_size: int = 24

    # Workspace format
    dense_workspace_format: str = "COLMAP"

    # ============================================
    # Geo-registration Settings
    # ============================================
    geo_registration_max_error: float = 3.0
    # After model_aligner, remove cameras farther than this many metres from
    # their GPS reference position.  Outlier cameras (GLOMAP drift artifacts)
    # produce incoherent depth maps that cause stereo_fusion to discard almost
    # all points.  Set to 0 to disable filtering.
    geo_registration_outlier_filter_m: float = 10.0

    # ============================================
    # Meshing Settings (Optional)
    # ============================================
    poisson_depth: int = 13
    poisson_trim: float = 7.0
    mesher_trim: float = 10.0
    # Minimum fused points required to attempt Poisson meshing.
    # poisson_mesher crashes (SIGSEGV) on an empty or near-empty point cloud.
    mesh_min_points: int = 100

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_prefix="COLMAP_",
        case_sensitive=False,
    )


class ColmapService(IService):
    """
    COLMAP service implementation using command-line interface.

    Runs COLMAP and GLOMAP commands directly on the host system.
    Uses glomap for the mapping stage.

    Note on interface compatibility:
    - Some methods use pycolmap when no CLI equivalent exists
    - create_tracks: Integrated into COLMAP's mapper (no separate step needed)
    - create_rig: COLMAP supports rigs but configuration differs
    - compute_statistics: Uses pycolmap to read reconstruction
    - export_report: Uses pycolmap or model_converter for format conversion
    """

    __service_name = "ColmapService"

    completion_steps_signal = Signal(ProjectId, StepName)

    def __init__(self, additional_settings: dict | None = None):
        if additional_settings is None:
            additional_settings = {}
        self.settings = ColmapSettings(**additional_settings)

        # Track active projects: {project_id: workspace_path}
        self._projects: dict[str, Path] = {}

    def _get_workspace(self, project_id: str) -> Path:
        """Get workspace path for a project."""
        if project_id not in self._projects:
            raise ValueError(f"Project '{project_id}' not found. Call start() first.")
        return self._projects[project_id]

    def _get_database_path(self, project_id: str) -> Path:
        """Get database path for a project."""
        workspace = self._get_workspace(project_id)
        return workspace / self.settings.run_path / "database.db"

    def _get_image_path(self, project_id: str) -> Path:
        """Get images directory path."""
        workspace = self._get_workspace(project_id)
        return workspace / self.settings.images_subdir

    def _get_sparse_path(self, project_id: str) -> Path:
        """Get sparse reconstruction output path."""
        workspace = self._get_workspace(project_id)
        return workspace / self.settings.run_path / "sparse"

    def _get_dense_path(self, project_id: str) -> Path:
        """Get dense reconstruction path."""
        workspace = self._get_workspace(project_id)
        return workspace / self.settings.run_path / "dense"

    def _run_command(
        self,
        command: list[str],
        cwd: Path,
        stream_output: bool = True,
    ) -> str:
        """Execute a command and return stdout, optionally streaming output in real-time.

        Args:
            command: Command and arguments to execute
            cwd: Working directory for the command
            stream_output: If True, stream output in real-time; if False, capture and log at end

        Returns:
            Combined stdout/stderr output as string
        """
        try:
            if stream_output:
                # Stream output in real-time
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=cwd,
                    bufsize=1,  # Line buffered
                )

                output_lines = []
                for line in iter(process.stdout.readline, ""):  # type: ignore
                    if line:
                        line = line.rstrip()
                        logger.info(f"[COMMAND] {line}")
                        output_lines.append(line)

                process.stdout.close()
                process.wait()

                if process.returncode != 0:
                    error_msg = f"Command failed with return code {process.returncode}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                return "\n".join(output_lines)
            else:
                # Original behavior - capture all output at once
                process = subprocess.run(  # type: ignore
                    command,
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=cwd,
                )
                if process.stdout:
                    logger.info(f"Command output: {process.stdout.strip()}")  # type: ignore
                if process.stderr:
                    logger.warning(f"Command stderr: {process.stderr.strip()}")  # type: ignore
                return process.stdout  # type: ignore

        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed with error: {e.stderr or e.stdout}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except FileNotFoundError:
            raise RuntimeError(
                f"Command not found: {command[0]}. Ensure COLMAP/GLOMAP is installed and in PATH.",
            )

    def _check_gpu_availability(self) -> bool:
        """
        Check if NVIDIA GPUs are available on the system.

        Returns:
            bool: True if NVIDIA GPUs are detected, False otherwise
        """
        try:
            # Check if nvidia-smi is available and can detect GPUs
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_names = result.stdout.strip().split("\n")
                logger.info(
                    f"Detected {len(gpu_names)} NVIDIA GPU(s): {', '.join(gpu_names)}",
                )
                return True
            else:
                logger.info("No NVIDIA GPUs detected via nvidia-smi")
                return False
        except FileNotFoundError:
            logger.info("nvidia-smi not found - NVIDIA GPU support not available")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("nvidia-smi timed out - assuming no GPU available")
            return False
        except Exception as e:
            logger.warning(f"Failed to check GPU availability: {e}")
            return False

    def create_processing_config(self):
        """
        Create processing configuration.
        Note: COLMAP uses command-line options.
        This is a placeholder for custom configuration if needed.
        """
        logger.info("COLMAP configuration managed through ColmapSettings")

    def extract_metadata(self, project_id: str):
        """
        Extract image metadata and create/populate COLMAP database.

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        database_path = workspace / self.settings.run_path / "database.db"
        image_path = self._get_image_path(project_id)

        # create database path
        database_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Extracting metadata for project {project_id}, images: {image_path}")

        try:
            # Create empty database using pycolmap (no CLI equivalent)
            if not database_path.exists():
                db = pycolmap.Database()
                db.open(str(database_path))
                # db.close()
                logger.info(f"Created database at {database_path}")

            # Import images into database using pycolmap.
            #
            # CRITICAL: import_images PRE-CREATES the camera rows in the database.
            # If we do not pin the camera model here, pycolmap defaults to
            # SIMPLE_RADIAL — a single-k1 distortion model too weak for drone
            # lenses.  feature_extractor's --ImageReader.camera_model OPENCV is
            # then silently ignored because the cameras already exist, and the
            # under-modelled distortion bends the reconstruction into a bowl
            # ("doming").  Pass the configured model (OPENCV) via ImageReaderOptions
            # so the database is created with the correct model from the start.
            # (single_camera is NOT an ImageReaderOptions field in pycolmap 3.13 —
            # camera sharing is governed by CameraMode and the feature_extractor
            # CLI flag — so only camera_model is set here.)
            _import_images_with_model(
                database_path, image_path, self.settings.camera_model,
            )

            _verify_camera_model(database_path, self.settings.camera_model)

            # Seed + fix the manufacturer interior orientation (anti-doming).
            # Self-calibration under nadir-only single-altitude geometry drifts the
            # focal length (trading against flying height) and bends the DSM into a
            # bowl; pinning the DJI factory DewarpData intrinsics removes that free
            # parameter.  No-op for non-DJI images (no DewarpData) → falls back to
            # self-calibration.  See docs/architecture/adr/0002.
            if self.settings.seed_factory_intrinsics:
                intrinsics = _parse_dji_dewarp_intrinsics(image_path)
                if intrinsics is None:
                    logger.info(
                        "No DJI DewarpData found in source images; keeping "
                        "self-calibrated intrinsics (factory seeding skipped).",
                    )
                else:
                    _seed_camera_intrinsics(
                        database_path, self.settings.camera_model, intrinsics,
                    )

            logger.info(f"Metadata extracted successfully for {project_id}")
            self.completion_steps_signal.emit(project_id, "extract_metadata")

        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            raise

    def extract_features(self, project_id: str):
        """
        Extract features from images using SIFT or other descriptors.

        Uses colmap feature_extractor command with all configured options.

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        database_path = self._get_database_path(project_id)
        image_path = self._get_image_path(project_id)

        logger.info(f"Extracting features for project {project_id}")
        logger.info(
            f"Using settings: max_features={self.settings.sift_max_num_features}, "
            f"max_image_size={self.settings.feature_extraction_max_image_size}, "
            f"num_threads={self.settings.feature_extraction_num_threads}, "
            f"use_gpu={self.settings.feature_extraction_use_gpu}",
        )

        try:
            # Build colmap feature_extractor command
            command = [
                "colmap",
                "feature_extractor",
                "--database_path",
                str(database_path),
                "--image_path",
                str(image_path),
                # ImageReader options
                "--ImageReader.camera_model",
                self.settings.camera_model,
                "--ImageReader.single_camera",
                str(int(self.settings.single_camera)),
                # SiftExtraction options
                "--SiftExtraction.max_image_size",
                str(self.settings.feature_extraction_max_image_size),
                "--SiftExtraction.max_num_features",
                str(self.settings.sift_max_num_features),
                "--SiftExtraction.first_octave",
                str(self.settings.sift_first_octave),
                "--SiftExtraction.estimate_affine_shape",
                str(int(self.settings.sift_estimate_affine_shape)),
                "--SiftExtraction.domain_size_pooling",
                str(int(self.settings.sift_domain_size_pooling)),
                "--SiftExtraction.upright",
                str(int(self.settings.sift_upright)),
                # FeatureExtraction options
                "--FeatureExtraction.num_threads",
                str(self.settings.feature_extraction_num_threads),
                "--FeatureExtraction.use_gpu",
                str(int(self.settings.feature_extraction_use_gpu)),
                "--FeatureExtraction.gpu_index",
                str(self.settings.feature_extraction_gpu_index),
            ]

            if self.settings.feature_extraction_use_gpu:
                logger.info(
                    f"GPU acceleration enabled (gpu_index={self.settings.feature_extraction_gpu_index})",
                )
            else:
                logger.info("Using CPU for feature extraction")

            self._run_command(command, cwd=workspace)

            logger.info(f"Features extracted successfully for {project_id}")
            self.completion_steps_signal.emit(project_id, "extract_features")

        except Exception as e:
            logger.error(f"Failed to extract features: {e}")
            logger.error("If you're experiencing OOM errors, try:")
            logger.error(
                f"  1. Reducing feature_extraction_max_image_size (current: {self.settings.feature_extraction_max_image_size})",
            )
            logger.error(
                f"  2. Reducing feature_extraction_num_threads (current: {self.settings.feature_extraction_num_threads})",
            )
            logger.error(
                f"  3. Reducing sift_max_num_features (current: {self.settings.sift_max_num_features})",
            )
            logger.error(
                f"  4. Enabling GPU acceleration if available (current: {self.settings.feature_extraction_use_gpu})",
            )
            raise

    def match_features(self, project_id: str):
        """
        Match features between images using different matcher types.

        Uses colmap sequential_matcher, exhaustive_matcher, spatial_matcher,
        or vocab_tree_matcher based on settings.

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        database_path = self._get_database_path(project_id)

        logger.info(
            f"Matching features for project {project_id} using {self.settings.matcher_type}",
        )

        try:
            # Base command parts
            base_command = [
                "colmap",
            ]

            # Common matching options
            common_options = [
                "--database_path",
                str(database_path),
                # FeatureMatching options
                "--FeatureMatching.use_gpu",
                str(int(self.settings.matching_use_gpu)),
                "--FeatureMatching.gpu_index",
                str(self.settings.matching_gpu_index),
                "--FeatureMatching.guided_matching",
                str(int(self.settings.matching_guided_matching)),
                "--FeatureMatching.max_num_matches",
                str(self.settings.matching_max_num_matches),
                # SiftMatching options
                "--SiftMatching.max_ratio",
                str(self.settings.matching_max_ratio),
                "--SiftMatching.max_distance",
                str(self.settings.matching_max_distance),
                "--SiftMatching.cross_check",
                str(int(self.settings.matching_cross_check)),
            ]

            if self.settings.matcher_type == "spatial":
                command = base_command + ["spatial_matcher"] + common_options
                logger.info("Using spatial matcher (requires GPS data in EXIF)")

            elif self.settings.matcher_type == "sequential":
                command = (
                    base_command
                    + [
                        "sequential_matcher",
                    ]
                    + common_options
                    + [
                        "--SequentialMatching.overlap",
                        str(self.settings.sequential_overlap),
                        "--SequentialMatching.quadratic_overlap",
                        str(int(self.settings.sequential_quadratic_overlap)),
                        "--SequentialMatching.loop_detection",
                        str(int(self.settings.sequential_loop_detection)),
                        "--SequentialMatching.loop_detection_num_images",
                        str(self.settings.sequential_loop_detection_num_images),
                    ]
                )
                if self.settings.sequential_vocab_tree_path:
                    command.extend(
                        [
                            "--SequentialMatching.vocab_tree_path",
                            self.settings.sequential_vocab_tree_path,
                        ],
                    )

            elif self.settings.matcher_type == "exhaustive":
                command = base_command + ["exhaustive_matcher"] + common_options

            elif self.settings.matcher_type == "vocab_tree":
                command = base_command + ["vocab_tree_matcher"] + common_options
                if self.settings.sequential_vocab_tree_path:
                    command.extend(
                        [
                            "--VocabTreeMatching.vocab_tree_path",
                            self.settings.sequential_vocab_tree_path,
                        ],
                    )

            else:
                logger.warning(
                    f"Unknown matcher type: {self.settings.matcher_type}, using sequential",
                )
                command = (
                    base_command
                    + [
                        "sequential_matcher",
                    ]
                    + common_options
                    + [
                        "--SequentialMatching.overlap",
                        str(self.settings.sequential_overlap),
                    ]
                )

            self._run_command(command, cwd=workspace)

            logger.info(f"Features matched successfully for {project_id}")
            self.completion_steps_signal.emit(project_id, "match_features")

        except Exception as e:
            logger.error(f"Failed to match features: {e}")
            raise

    def create_tracks(self, project_id: str):
        """
        Create feature tracks.

        Note: COLMAP integrates track creation into the mapper step.
        This method is a no-op for compatibility with IService interface.

        Args:
            project_id: Project identifier
        """
        logger.info(f"Track creation is integrated into COLMAP mapper for {project_id}")
        self.completion_steps_signal.emit(project_id, "create_tracks")

    def create_rig(self, project_id: str):
        """
        Create camera rig configuration.

        Note: COLMAP supports camera rigs but configuration is done differently
        than OpenSFM. This is a placeholder for rig-specific setup.

        Args:
            project_id: Project identifier
        """
        logger.info(
            f"Camera rig configuration for COLMAP should be done via database for {project_id}",
        )
        logger.info(
            "Refer to COLMAP documentation for rig setup if using multi-camera systems",
        )
        self.completion_steps_signal.emit(project_id, "create_rig")

    def compute_reconstruct(self, project_id: str):
        """
        Compute sparse reconstruction using glomap mapper.

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        database_path = self._get_database_path(project_id)
        image_path = self._get_image_path(project_id)
        sparse_path = self._get_sparse_path(project_id)

        logger.info(
            f"Computing sparse reconstruction for project {project_id} using glomap",
        )

        # When factory intrinsics were seeded (extract_metadata), keep GLOMAP from
        # re-estimating focal length / principal point — that self-calibration is
        # what domes the model under nadir-only geometry (ADR 0002, Phase 1).
        fix_intrinsics = _intrinsics_are_seeded(database_path)
        optimize_intrinsics = (
            0 if fix_intrinsics else int(self.settings.mapper_ba_refine_focal_length)
        )
        optimize_principal_point = (
            0 if fix_intrinsics else int(self.settings.mapper_ba_refine_principal_point)
        )
        if fix_intrinsics:
            logger.info(
                "Factory intrinsics fixed: GLOMAP intrinsic + principal-point "
                "optimisation disabled (anti-doming).",
            )

        try:
            # Build glomap mapper command
            command = [
                "glomap",
                "mapper",
                "--database_path",
                str(database_path),
                "--output_path",
                str(sparse_path),
                "--image_path",
                str(image_path),
                # Output options
                "--output_format",
                self.settings.glomap_output_format,
                # Bundle adjustment iterations
                "--ba_iteration_num",
                str(self.settings.mapper_ba_global_max_refinements),
                # Global positioning options
                "--GlobalPositioning.use_gpu",
                str(int(self.settings.mapper_ba_use_gpu)),
                "--GlobalPositioning.gpu_index",
                str(self.settings.mapper_ba_gpu_index),
                "--GlobalPositioning.max_num_iterations",
                str(self.settings.mapper_ba_global_max_num_iterations),
                # Bundle adjustment options
                "--BundleAdjustment.use_gpu",
                str(int(self.settings.mapper_ba_use_gpu)),
                "--BundleAdjustment.gpu_index",
                str(self.settings.mapper_ba_gpu_index),
                "--BundleAdjustment.optimize_rotations",
                str(int(self.settings.glomap_ba_optimize_rotations)),
                "--BundleAdjustment.optimize_translation",
                str(int(self.settings.glomap_ba_optimize_translation)),
                "--BundleAdjustment.optimize_intrinsics",
                str(optimize_intrinsics),
                "--BundleAdjustment.optimize_principal_point",
                str(optimize_principal_point),
                "--BundleAdjustment.optimize_points",
                str(int(self.settings.glomap_ba_optimize_points)),
                "--BundleAdjustment.max_num_iterations",
                str(self.settings.mapper_ba_global_max_num_iterations),
                # Triangulation options
                "--Triangulation.min_angle",
                str(self.settings.mapper_min_angle),
                "--Triangulation.min_num_matches",
                str(self.settings.mapper_min_num_matches),
            ]

            command += ["--constraint_type", self.settings.glomap_constraint_type]
            logger.info(f"glomap constraint_type={self.settings.glomap_constraint_type}")

            if self.settings.mapper_ba_use_gpu:
                logger.info(
                    f"GPU acceleration enabled for mapping (gpu_index={self.settings.mapper_ba_gpu_index})",
                )

            self._run_command(command, cwd=workspace)

            logger.info(f"Sparse reconstruction completed with glomap for {project_id}")
            self.completion_steps_signal.emit(project_id, "compute_reconstruct")

        except Exception as e:
            logger.error(f"Failed to compute reconstruction: {e}")
            raise

    def reconstruct_from_prior(self, project_id: str):
        """
        Reconstruct with prior information (e.g., GPS, known poses).

        Note: COLMAP supports reconstruction with priors through GPS data
        in EXIF or custom prior files. This requires specific setup.

        Args:
            project_id: Project identifier
        """
        logger.info(f"Reconstruction from prior for {project_id}")
        logger.info("COLMAP can use GPS priors from EXIF. Ensure images have GPS tags.")

        # This would require custom implementation based on available prior data
        # For now, it's a placeholder
        self.completion_steps_signal.emit(project_id, "reconstruct_from_prior")

    def bundle_reconstruction(self, project_id: str):
        """
        Perform bundle adjustment on reconstruction using colmap bundle_adjuster.

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        database_path = self._get_database_path(project_id)
        sparse_path = self._get_sparse_path(project_id)
        input_path = sparse_path / "0"
        output_path = sparse_path / "0"

        logger.info(f"Bundle adjustment for project {project_id}")

        # When factory intrinsics were seeded, do not let the final bundle adjuster
        # refine them back into a domed solution (ADR 0002, Phase 1).
        fix_intrinsics = _intrinsics_are_seeded(database_path)
        refine_focal = 0 if fix_intrinsics else int(self.settings.ba_refine_focal_length)
        refine_pp = 0 if fix_intrinsics else int(self.settings.ba_refine_principal_point)
        refine_extra = 0 if fix_intrinsics else int(self.settings.ba_refine_extra_params)
        if fix_intrinsics:
            logger.info(
                "Factory intrinsics fixed: bundle_adjuster focal/principal/extra "
                "refinement disabled (anti-doming).",
            )

        try:
            # Build colmap bundle_adjuster command
            command = [
                "colmap",
                "bundle_adjuster",
                "--input_path",
                str(input_path),
                "--output_path",
                str(output_path),
                # Bundle adjustment options
                "--BundleAdjustment.max_num_iterations",
                str(self.settings.ba_max_num_iterations),
                "--BundleAdjustment.refine_focal_length",
                str(refine_focal),
                "--BundleAdjustment.refine_principal_point",
                str(refine_pp),
                "--BundleAdjustment.refine_extra_params",
                str(refine_extra),
                "--BundleAdjustment.use_gpu",
                str(int(self.settings.ba_use_gpu)),
                "--BundleAdjustment.gpu_index",
                str(self.settings.ba_gpu_index),
            ]

            self._run_command(command, cwd=workspace)

            logger.info(f"Bundle adjustment completed for {project_id}")
            self.completion_steps_signal.emit(project_id, "bundle_reconstruction")

        except Exception as e:
            logger.error(f"Failed to perform bundle adjustment: {e}")
            raise

    def geo_register(self, project_id: str) -> None:
        """
        Compute the GPS alignment transform for the sparse model and write
        geo_reference.json.  Runs AFTER compute_depthmaps so that dense
        reconstruction (undistort → patch_match_stereo → stereo_fusion) always
        operates in local SFM space — which COLMAP handles correctly.

        sparse/0 is NOT replaced.  mesh() reads geo_transform.txt and applies
        it to fused.ply (local SFM) → fused_georef.ply (ECEF), which PDAL then
        reprojects to UTM to produce the georeferenced orthomosaic.
        """
        workspace = self._get_workspace(project_id)
        sparse_path = self._get_sparse_path(project_id) / "0"
        image_path = self._get_image_path(project_id)
        geo_ref_path = workspace / self.settings.run_path / "geo_reference.json"

        logger.info(f"Geo-registering model for project {project_id}")

        gps_entries = _extract_gps_from_images(image_path)
        if not gps_entries:
            logger.warning(
                "No GPS EXIF found in images — skipping geo-registration. "
                "Output will NOT be geotagged."
            )
            self.completion_steps_signal.emit(project_id, "geo_register")
            return

        # Attempt to upgrade EXIF GPS (±1–3 m) with PPK accuracy (±1–3 cm) from a
        # DJI Timestamp Mark file (.MRK) if one is present in the dataset directory.
        mrk_candidates = sorted(
            list(workspace.glob("*.MRK"))
            + list(workspace.glob("*.mrk"))
            + list(workspace.glob("**/*.MRK"))
        )
        if mrk_candidates:
            mrk_path = mrk_candidates[0]
            mrk_gps = _parse_mrk_file(mrk_path)
            if mrk_gps:
                gps_entries, n_upgraded = _upgrade_gps_with_ppk(gps_entries, mrk_gps)
                logger.info(
                    f"PPK upgrade: {n_upgraded}/{len(gps_entries)} images now use "
                    f"high-accuracy GPS from {mrk_path.name} "
                    f"(remaining {len(gps_entries) - n_upgraded} fall back to EXIF)"
                )
            else:
                logger.warning(
                    f"MRK file found ({mrk_path.name}) but could not be parsed — "
                    "falling back to EXIF GPS for geo-registration."
                )
        else:
            logger.debug(
                "No .MRK file found in dataset directory — using EXIF GPS for geo-registration."
            )

        centroid_lat = sum(lat for _, lat, _, _ in gps_entries) / len(gps_entries)
        centroid_lon = sum(lon for _, _, lon, _ in gps_entries) / len(gps_entries)
        utm_epsg = _utm_epsg_from_latlon(centroid_lat, centroid_lon)

        logger.info(
            f"GPS centroid: lat={centroid_lat:.6f}, lon={centroid_lon:.6f} "
            f"→ UTM EPSG:{utm_epsg}"
        )

        ref_images_txt = workspace / self.settings.run_path / "ref_images.txt"
        transform_path = workspace / self.settings.run_path / "geo_transform.txt"
        ref_images_txt.parent.mkdir(parents=True, exist_ok=True)

        ref_images_txt.write_text(
            "".join(f"{name} {lat} {lon} {alt}\n" for name, lat, lon, alt in gps_entries)
        )
        logger.info(f"Wrote {len(gps_entries)} GPS reference entries to {ref_images_txt}")

        # model_aligner output goes to a temporary directory — we only need
        # geo_transform.txt.  sparse/0 is left untouched so that fused.ply
        # (already written by stereo_fusion) is in local SFM space.
        # mesh() will apply geo_transform.txt to produce fused_georef.ply (ECEF).
        sparse_aligned_tmp = sparse_path.parent / "0_aligned_tmp"
        if sparse_aligned_tmp.exists():
            shutil.rmtree(sparse_aligned_tmp)
        sparse_aligned_tmp.mkdir(parents=True)

        try:
            command = [
                "colmap",
                "model_aligner",
                "--input_path",      str(sparse_path),
                "--output_path",     str(sparse_aligned_tmp),
                "--ref_images_path", str(ref_images_txt),
                "--ref_is_gps",      "1",
                "--alignment_type",  "ecef",
                "--alignment_max_error",
                str(self.settings.geo_registration_max_error),
                "--transform_path",  str(transform_path),
            ]
            output = self._run_command(command, cwd=workspace)

            # Discard the aligned model — we only needed geo_transform.txt.
            shutil.rmtree(sparse_aligned_tmp, ignore_errors=True)

            # Warn on bad alignment (scale far from 1.0 or large RMSE).
            scale_match = re.search(r"Scale[:\s]+([0-9.eE+\-]+)", output)
            if scale_match:
                scale = float(scale_match.group(1))
                if abs(scale - 1.0) > 0.10:
                    logger.warning(
                        f"model_aligner scale={scale:.4f} deviates >10 % from 1.0 — "
                        "possible unit mismatch. Geo-referencing may be inaccurate."
                    )
            rmse_match = re.search(r"RMSE[:\s]+([0-9.eE+\-]+)", output)
            if rmse_match:
                rmse = float(rmse_match.group(1))
                if rmse > 5.0 * self.settings.geo_registration_max_error:
                    logger.warning(
                        f"model_aligner RMSE={rmse:.2f} m exceeds 5× max_error threshold — "
                        "alignment may be unreliable."
                    )

            logger.info(
                f"model_aligner completed — geo_transform.txt written to {transform_path}. "
                "sparse/0 kept in local SFM space."
            )

            geo_ref_path.write_text(
                json.dumps(
                    {
                        "centroid_lat": centroid_lat,
                        "centroid_lon": centroid_lon,
                        "utm_epsg": utm_epsg,
                        "input_srs": "EPSG:4978",
                        "georef_pointcloud": "fused_georef.ply",
                    },
                    indent=2,
                )
            )
            logger.info(f"Geo-reference metadata saved to {geo_ref_path}")

        except Exception as e:
            shutil.rmtree(sparse_aligned_tmp, ignore_errors=True)
            logger.error(
                f"model_aligner failed: {e}. "
                "Outputs will not be geotagged."
            )

        self.completion_steps_signal.emit(project_id, "geo_register")

    def mesh(self, project_id: str):
        """
        Generate mesh from dense point cloud using Poisson meshing.

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        dense_path = self._get_dense_path(project_id)
        input_path = dense_path / "fused.ply"
        output_path = dense_path / "meshed-poisson.ply"

        logger.info(f"Generating mesh for project {project_id}")

        # Now that fused.ply exists, create fused_georef.ply (ECEF copy for PDAL).
        # fused.ply stays in local SFM coordinates for the 3D viewer.
        transform_path = workspace / self.settings.run_path / "geo_transform.txt"
        fused_georef_ply = dense_path / "fused_georef.ply"
        if input_path.exists() and transform_path.exists() and not fused_georef_ply.exists():
            fused_georef_tmp = dense_path / "fused_georef_tmp.ply"
            try:
                self._run_command(
                    [
                        "colmap",
                        "model_transformer",
                        "--input_path",     str(input_path),
                        "--output_path",    str(fused_georef_tmp),
                        "--transform_path", str(transform_path),
                    ],
                    cwd=workspace,
                )
                fused_georef_tmp.replace(fused_georef_ply)
                logger.info(
                    "ECEF geo-transform applied → fused_georef.ply "
                    "(fused.ply unchanged in local SFM coordinates)"
                )
            except Exception as tf_err:
                fused_georef_tmp.unlink(missing_ok=True)
                logger.warning(
                    f"model_transformer failed (non-fatal) — "
                    f"fused_georef.ply will not be created: {tf_err}"
                )

        # Also emit a UTM-projected cloud for human coordinate extraction.
        # fused_georef.ply is in ECEF (EPSG:4978) — geocentric XYZ in the
        # millions of metres, which is correct for the downstream PDAL pipeline
        # but unreadable in a viewer and not in the same CRS as the DSM/ortho
        # (UTM).  fused_utm.ply reprojects ECEF → UTM so testers can read sane
        # easting/northing/elevation and overlay it on the orthomosaic.
        self._write_utm_pointcloud(project_id, fused_georef_ply, dense_path)

        # Guard: poisson_mesher crashes with SIGSEGV on an empty or near-empty
        # point cloud.  Check the vertex count before invoking it.
        fused_count = _count_ply_vertices(input_path)
        if fused_count < self.settings.mesh_min_points:
            logger.warning(
                f"fused.ply has {fused_count} point(s) — below threshold of "
                f"{self.settings.mesh_min_points}. Skipping Poisson meshing."
            )
            self.completion_steps_signal.emit(project_id, "mesh")
            return

        try:
            # Build colmap poisson_mesher command
            command = [
                "colmap",
                "poisson_mesher",
                "--input_path",
                str(input_path),
                "--output_path",
                str(output_path),
                # Poisson meshing options
                "--PoissonMeshing.depth",
                str(self.settings.poisson_depth),
                "--PoissonMeshing.trim",
                str(self.settings.mesher_trim),
            ]

            self._run_command(command, cwd=workspace)

            logger.info(f"Mesh generated successfully at {output_path}")
            self.completion_steps_signal.emit(project_id, "mesh")

        except Exception as e:
            logger.error(f"Failed to generate mesh: {e}")
            logger.error(f"Ensure fused point cloud exists at {input_path}")
            raise

    def _write_utm_pointcloud(
        self, project_id: str, ecef_ply: Path, dense_path: Path,
    ) -> None:
        """
        Reproject the ECEF ``fused_georef.ply`` to UTM as ``fused_utm.ply``.

        The ECEF cloud (EPSG:4978) is correct but geocentric — coordinates are
        in the millions of metres and do not match the DSM/ortho CRS, so it is
        unusable for human coordinate extraction or overlay.  This produces a
        UTM cloud in the same CRS as the orthomosaic (from ``geo_reference.json``'s
        ``utm_epsg``) using the same PDAL ``filters.reprojection`` the ortho
        pipeline uses.  Non-fatal: a failure leaves the ECEF cloud in place.

        Args:
            project_id: Project identifier
            ecef_ply: Path to the ECEF ``fused_georef.ply``
            dense_path: Dense reconstruction directory (output location)
        """
        if not ecef_ply.exists():
            return

        geo_ref_path = (
            self._get_workspace(project_id)
            / self.settings.run_path
            / "geo_reference.json"
        )
        if not geo_ref_path.exists():
            logger.debug(
                "geo_reference.json missing — skipping UTM point cloud export.",
            )
            return

        try:
            geo_ref = json.loads(geo_ref_path.read_text())
            in_srs = geo_ref.get("input_srs", "EPSG:4978")
            utm_epsg = geo_ref["utm_epsg"]
        except Exception as exc:
            logger.warning(f"Could not read geo_reference.json for UTM export: {exc}")
            return

        utm_ply = dense_path / "fused_utm.ply"
        pipeline = dense_path / "pdal_fused_utm.json"
        pipeline.write_text(
            json.dumps(
                [
                    str(ecef_ply),
                    {
                        "type": "filters.reprojection",
                        "in_srs": in_srs,
                        "out_srs": f"EPSG:{utm_epsg}",
                    },
                    {
                        "type": "writers.ply",
                        "filename": str(utm_ply),
                        "storage_mode": "little endian",
                    },
                ],
            ),
        )
        try:
            self._run_command(["pdal", "pipeline", str(pipeline)], cwd=dense_path)
            logger.info(
                f"UTM point cloud written → fused_utm.ply (EPSG:{utm_epsg}). "
                "Open this file (not fused.ply or fused_georef.ply) to read "
                "easting/northing/elevation coordinates."
            )
            # Record the human-usable cloud in geo_reference.json for consumers.
            try:
                geo_ref["utm_pointcloud"] = "fused_utm.ply"
                geo_ref_path.write_text(json.dumps(geo_ref, indent=2))
            except Exception:
                pass
        except Exception as exc:
            logger.warning(
                f"PDAL reprojection to UTM failed (non-fatal) — fused_utm.ply "
                f"not created; fused_georef.ply (ECEF) remains available: {exc}",
            )

    def undistort(self, project_id: str):
        """
        Undistort images for dense reconstruction.

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        image_path = self._get_image_path(project_id)
        sparse_path = self._get_sparse_path(project_id) / "0"
        dense_path = self._get_dense_path(project_id)

        logger.info(f"Undistorting images for project {project_id}")

        try:
            # Build colmap image_undistorter command
            command = [
                "colmap",
                "image_undistorter",
                "--image_path",
                str(image_path),
                "--input_path",
                str(sparse_path),
                "--output_path",
                str(dense_path),
                # Undistortion options
                "--output_type",
                self.settings.undistort_output_type,
                "--max_image_size",
                str(self.settings.undistort_max_image_size),
            ]

            self._run_command(command, cwd=workspace)

            logger.info(f"Images undistorted successfully for {project_id}")
            self.completion_steps_signal.emit(project_id, "undistort")

        except Exception as e:
            logger.error(f"Failed to undistort images: {e}")
            raise

    def compute_depthmaps(self, project_id: str):
        """
        Compute dense depth maps and fuse into point cloud.

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        dense_path = self._get_dense_path(project_id)

        logger.info(f"Computing depth maps for project {project_id}")

        try:
            # Step 1: Run patch match stereo
            logger.info("Running patch match stereo...")
            patch_match_command = [
                "colmap",
                "patch_match_stereo",
                "--workspace_path",
                str(dense_path),
                "--workspace_format",
                self.settings.dense_workspace_format,
                # PatchMatchStereo options
                "--PatchMatchStereo.max_image_size",
                str(self.settings.patch_match_max_image_size),
                "--PatchMatchStereo.window_radius",
                str(self.settings.patch_match_window_radius),
                "--PatchMatchStereo.window_step",
                str(self.settings.patch_match_window_step),
                "--PatchMatchStereo.num_samples",
                str(self.settings.patch_match_num_samples),
                "--PatchMatchStereo.num_iterations",
                str(self.settings.patch_match_num_iterations),
                "--PatchMatchStereo.geom_consistency",
                str(int(self.settings.patch_match_geom_consistency)),
                "--PatchMatchStereo.geom_consistency_regularizer",
                str(self.settings.patch_match_geom_consistency_regularizer),
                "--PatchMatchStereo.geom_consistency_max_cost",
                str(self.settings.patch_match_geom_consistency_max_cost),
                "--PatchMatchStereo.filter",
                str(int(self.settings.patch_match_filter)),
                "--PatchMatchStereo.filter_min_ncc",
                str(self.settings.patch_match_filter_min_ncc),
                "--PatchMatchStereo.filter_min_triangulation_angle",
                str(self.settings.patch_match_filter_min_triangulation_angle),
                "--PatchMatchStereo.filter_min_num_consistent",
                str(self.settings.patch_match_filter_min_num_consistent),
                "--PatchMatchStereo.filter_geom_consistency_max_cost",
                str(self.settings.patch_match_filter_geom_consistency_max_cost),
                "--PatchMatchStereo.cache_size",
                str(self.settings.patch_match_cache_size),
                "--PatchMatchStereo.gpu_index",
                str(self.settings.patch_match_gpu_index),
            ]

            self._run_command(patch_match_command, cwd=workspace)

            # Step 2: Fuse depth maps into point cloud
            logger.info("Fusing depth maps into point cloud...")
            output_path = dense_path / "fused.ply"
            fusion_command = [
                "colmap",
                "stereo_fusion",
                "--workspace_path",
                str(dense_path),
                "--workspace_format",
                self.settings.dense_workspace_format,
                "--input_type",
                self.settings.fusion_input_type,
                "--output_path",
                str(output_path),
                # StereoFusion options
                "--StereoFusion.num_threads",
                str(self.settings.fusion_num_threads),
                "--StereoFusion.max_image_size",
                str(self.settings.fusion_max_image_size),
                "--StereoFusion.min_num_pixels",
                str(self.settings.fusion_min_num_pixels),
                "--StereoFusion.max_num_pixels",
                str(self.settings.fusion_max_num_pixels),
                "--StereoFusion.max_traversal_depth",
                str(self.settings.fusion_max_traversal_depth),
                "--StereoFusion.max_reproj_error",
                str(self.settings.fusion_max_reproj_error),
                "--StereoFusion.max_depth_error",
                str(self.settings.fusion_max_depth_error),
                "--StereoFusion.max_normal_error",
                str(self.settings.fusion_max_normal_error),
                "--StereoFusion.check_num_images",
                str(self.settings.fusion_check_num_images),
                "--StereoFusion.use_cache",
                str(int(self.settings.fusion_use_cache)),
                "--StereoFusion.cache_size",
                str(self.settings.fusion_cache_size),
            ]

            self._run_command(fusion_command, cwd=workspace)

            # Verify the fusion actually produced points before proceeding.
            # An empty fused.ply causes poisson_mesher to crash with SIGSEGV.
            fused_count = _count_ply_vertices(output_path)
            if fused_count == 0:
                raise RuntimeError(
                    "stereo_fusion produced 0 fused points. "
                    f"Current COLMAP_FUSION_MAX_DEPTH_ERROR={self.settings.fusion_max_depth_error}. "
                    "Dense reconstruction runs in local SFM space before geo-registration. "
                    "If this is 0, check that patch_match_stereo ran with filtering enabled "
                    "(COLMAP_PATCH_MATCH_FILTER=true) and that the sparse model has "
                    "enough registered images."
                )
            logger.info(f"Fused point cloud: {fused_count:,} points")

            logger.info(f"Depth maps computed and fused for {project_id}")
            self.completion_steps_signal.emit(project_id, "compute_depthmaps")

        except Exception as e:
            logger.error(f"Failed to compute depth maps: {e}")
            raise

    def compute_statistics(self, project_id: str):
        """
        Compute reconstruction statistics.

        Uses pycolmap to read reconstruction (no CLI equivalent).

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        sparse_path = workspace / self.settings.run_path / "sparse" / "0"

        logger.info(f"Computing statistics for project {project_id}")

        try:
            # Load reconstruction using pycolmap (no CLI equivalent)
            reconstruction = pycolmap.Reconstruction(str(sparse_path))

            # Gather statistics
            stats = {
                "num_cameras": len(reconstruction.cameras),
                "num_images": len(reconstruction.images),
                "num_reg_images": reconstruction.num_reg_images(),
                "num_points3D": len(reconstruction.points3D),
                "mean_track_length": reconstruction.compute_mean_track_length(),
                "mean_observations_per_image": reconstruction.compute_mean_observations_per_reg_image(),
                "mean_reprojection_error": reconstruction.compute_mean_reprojection_error(),
            }

            # Save statistics
            stats_file = workspace / "statistics.json"
            with open(stats_file, "w") as f:
                json.dump(stats, f, indent=2)

            logger.info(f"Statistics computed: {stats}")
            self.completion_steps_signal.emit(project_id, "compute_statistics")

        except Exception as e:
            logger.error(f"Failed to compute statistics: {e}")
            raise

    def export_report(self, project_id: str):
        """
        Export reconstruction report.

        Uses pycolmap for format conversion (no CLI equivalent for all formats).

        Args:
            project_id: Project identifier
        """
        workspace = self._get_workspace(project_id)
        sparse_path = workspace / self.settings.run_path / "sparse" / "0"

        logger.info(f"Exporting report for project {project_id}")

        try:
            # Load reconstruction using pycolmap
            reconstruction = pycolmap.Reconstruction(str(sparse_path))

            # Export reconstruction in various formats
            report_dir = workspace / "report"
            report_dir.mkdir(exist_ok=True)

            # Export as text format
            report_text_format_path = report_dir / "sparse_text"
            report_text_format_path.mkdir(exist_ok=True)
            reconstruction.write_text(str(report_text_format_path))

            # Export as binary format (default COLMAP format)
            report_binary_format_path = report_dir / "sparse_binary"
            report_binary_format_path.mkdir(exist_ok=True)
            reconstruction.write(str(report_binary_format_path))

            # Create summary report
            summary = {
                "project_id": project_id,
                "workspace": str(workspace),
                "num_cameras": len(reconstruction.cameras),
                "num_images": len(reconstruction.images),
                "num_registered_images": reconstruction.num_reg_images(),
                "num_points": len(reconstruction.points3D),
                "camera_models": [
                    cam.model.name for cam in reconstruction.cameras.values()
                ],
            }

            with open(report_dir / "summary.json", "w") as f:
                json.dump(summary, f, indent=2)

            logger.info(f"Report exported to {report_dir}")
            self.completion_steps_signal.emit(project_id, "export_report")

        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            raise

    def start(self, dataset_path: Path) -> str:
        """
        Initialize COLMAP workspace.

        Args:
            dataset_path: Path to dataset containing images

        Returns:
            project_id: Project identifier for this reconstruction project
        """
        if not dataset_path.is_absolute():
            raise ValueError("The dataset_path must be an absolute path.")

        if not dataset_path.exists():
            raise ValueError(f"The dataset_path '{dataset_path}' does not exist.")

        # Generate unique project ID
        project_id = f"{self.__service_name}_{uuid.uuid4().hex[:8]}"

        # Store project info
        self._projects[project_id] = dataset_path

        logger.info(f"COLMAP project initialized: {project_id}")
        logger.info(f"Workspace: {dataset_path}")
        logger.info(f"Project ID: {project_id}")

        return project_id

    def stop(self, project_id: str):
        """
        Stop project processing (no-op for direct execution).

        Args:
            project_id: Project identifier
        """
        logger.info(
            f"Stop called for project {project_id} (no action needed for direct execution)",
        )

    def clean(self, project_id: str):
        """
        Clean up project tracking.

        Args:
            project_id: Project identifier to remove from tracking
        """
        logger.info(f"Cleaning up project {project_id}")

        # Remove from tracking
        if project_id in self._projects:
            workspace = self._projects[project_id]
            logger.info(
                f"Project removed from tracking. Workspace preserved at: {workspace}",
            )
            del self._projects[project_id]
        else:
            logger.warning(f"Project {project_id} not found in project tracking")

        logger.info(f"Project {project_id} cleaned up")

