"""
Pose-driven multispectral orthorectification (collinearity projection through SFM).

Replaces the GPS + nadir direct-georeferencing path (``_warp_reflectance_image``)
with a photogrammetrically rigorous projection: each multispectral band is sampled
by projecting every DSM cell into the **RGB camera's SFM pose**, then mapping the
RGB image coordinate into the band's sensor frame via the DJI factory geometry
(``DewarpHMatrix`` + ``RelativeOpticalCenter``).  Because every band of a capture
shares the RGB pose and the same DSM, the bands co-register by construction —
eliminating the "puzzle-piece" misplacement of the GPS path.

Coordinate chain (validated: camera positions reconstruct to ~0.1 m vs PPK):
    DSM cell (E, N, Z)_UTM  --osr-->  ECEF  --Sim3^-1-->  local SFM
    local SFM  --RGB pose (R, t) + FULL_OPENCV intrinsics-->  RGB pixel
    RGB pixel  --DewarpHMatrix^-1-->  MS plane (NIR frame)
    + RelativeOpticalCenter[band]  -->  band sensor pixel  -->  bilinear sample

The blend across overlapping captures is **band-coherent**: a single per-capture,
per-cell weight (a rectangular edge-feather — distance of the projected point to the
nearest RGB image border) is computed once and applied to every band, so RED and NIR
at any cell are the same weighted combination of the same captures.

See docs/architecture/adr/0002-multispectral-orthorectification-through-sfm.md §3.5.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from services.orthomosaic_generation.logger import logger

try:
    from osgeo import gdal, osr

    gdal.UseExceptions()
except ImportError:
    gdal = None
    osr = None

try:
    from shared.colmap.model_reader import read_cameras_binary, read_images_binary
except ImportError:
    read_cameras_binary = None
    read_images_binary = None

_ECEF_EPSG = 4978
_NODATA = 0.0
# Width of the rectangular edge-feather, as a fraction of the half-frame: the outer
# ``_FEATHER_FRAC`` of each RGB footprint ramps the blend weight 0→1, while the whole
# interior carries uniform weight 1.  Iso-weight contours follow the rectangular sensor
# footprint (not a circle), so overlapping captures cross-fade only at their shared
# seams and average equally elsewhere — this both removes the circular "scallop" seams
# a radial weight produces AND averages out each capture's center-bright vignette/BRDF
# texture (a peaked weight would re-light those center hotspots as circular disks).
_FEATHER_FRAC = 0.30
# Trim this many pixels off the real point-cloud coverage before painting, removing
# the noisy single-capture perimeter (matches the DSM mask erosion in the GPS path).
_COVERAGE_EROSION_PX = 12
_OSR_CHUNK = 1_000_000


@dataclass
class SfmGeometry:
    """RGB camera intrinsics, per-capture poses, and the local→ECEF Sim3."""

    fx: float
    fy: float
    cx: float
    cy: float
    rgb_w: int
    rgb_h: int
    dist: np.ndarray  # FULL_OPENCV extra params [k1,k2,p1,p2,k3,k4,k5,k6]
    pose_by_capture: dict[str, tuple[np.ndarray, np.ndarray]]  # seq → (R, t) local
    sim_scale: float
    sim_rot: np.ndarray  # 3×3, local→ECEF rotation
    sim_t: np.ndarray  # ECEF translation
    utm_epsg: int


def _capture_seq(name: str) -> str | None:
    """Return the DJI 4-digit capture sequence embedded in a filename, else None."""
    m = re.search(r"_(\d{4})_", name)
    return m.group(1) if m else None


def _quat_to_rot(q: np.ndarray) -> np.ndarray:
    """Convert a (w, x, y, z) unit quaternion to a 3×3 rotation matrix."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * w * z, 2 * x * z + 2 * w * y],
        [2 * x * y + 2 * w * z, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * w * x],
        [2 * x * z - 2 * w * y, 2 * y * z + 2 * w * x, 1 - 2 * x * x - 2 * y * y],
    ])


def load_sfm_geometry(sfm_run_path: Path) -> SfmGeometry | None:
    """
    Load RGB camera intrinsics, per-capture poses, and the Sim3 geo-transform.

    Reads ``sparse/0/{cameras,images}.bin`` (via the shared COLMAP reader) and
    ``geo_transform.txt`` (COLMAP Sim3: ``scale qw qx qy qz tx ty tz``) plus
    ``geo_reference.json`` (``utm_epsg``).  Returns None — caller falls back to the
    GPS path — when any artifact is missing or the reader is unavailable.

    Args:
        sfm_run_path: SFM run directory containing sparse/0 + geo_transform.txt.

    Returns:
        Populated :class:`SfmGeometry`, or None if pose-based ortho is not possible.
    """
    if read_images_binary is None or osr is None:
        logger.info("COLMAP reader / GDAL osr unavailable — pose ortho disabled")
        return None

    import json

    sparse = sfm_run_path / "sparse" / "0"
    cameras_bin = sparse / "cameras.bin"
    images_bin = sparse / "images.bin"
    transform_txt = sfm_run_path / "geo_transform.txt"
    geo_json = sfm_run_path / "geo_reference.json"
    for required in (cameras_bin, images_bin, transform_txt, geo_json):
        if not required.exists():
            logger.info(f"Pose ortho: missing {required.name} — falling back to GPS path")
            return None

    try:
        cameras = read_cameras_binary(cameras_bin)
        images = read_images_binary(images_bin)
        cam = next(iter(cameras.values()))
        params = np.asarray(cam.params, dtype=np.float64)
        if params.size < 8:
            logger.warning(f"Pose ortho: camera model {cam.model_name} too small; disabling")
            return None
        dist = np.zeros(8, dtype=np.float64)
        dist[: params.size - 4] = params[4:]

        pose_by_capture: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for img in images.values():
            seq = _capture_seq(img.name)
            if seq is not None:
                pose_by_capture[seq] = (img.rotation_matrix(), np.asarray(img.tvec))

        vals = [float(x) for x in transform_txt.read_text().split()]
        if len(vals) < 8:
            logger.warning("Pose ortho: geo_transform.txt not a Sim3 (8 values); disabling")
            return None
        sim_scale = vals[0]
        sim_rot = _quat_to_rot(np.asarray(vals[1:5]))
        sim_t = np.asarray(vals[5:8])
        utm_epsg = int(json.loads(geo_json.read_text())["utm_epsg"])

        logger.info(
            f"Pose ortho geometry loaded: {len(pose_by_capture)} capture poses, "
            f"camera={cam.model_name} fx={params[0]:.1f}, Sim3 scale={sim_scale:.3f}, "
            f"UTM EPSG:{utm_epsg}"
        )
        return SfmGeometry(
            fx=float(params[0]), fy=float(params[1]), cx=float(params[2]),
            cy=float(params[3]), rgb_w=int(cam.width), rgb_h=int(cam.height),
            dist=dist, pose_by_capture=pose_by_capture,
            sim_scale=sim_scale, sim_rot=sim_rot, sim_t=sim_t, utm_epsg=utm_epsg,
        )
    except Exception as exc:  # noqa: BLE001 — any read/parse failure → safe fallback
        logger.warning(f"Pose ortho: failed to load SFM geometry ({exc}); GPS fallback")
        return None


def _utm_to_local(
    e: np.ndarray, n: np.ndarray, z: np.ndarray, geom: SfmGeometry,
) -> np.ndarray:
    """
    Transform UTM (E, N, Z) cell coordinates to the local SFM frame.

    UTM → ECEF via GDAL osr (chunked to bound memory), then ECEF → local by
    inverting the Sim3: ``P_local = R^T (P_ecef − t) / s``.

    Returns:
        (K, 3) array of local-frame points.
    """
    utm = osr.SpatialReference()
    utm.ImportFromEPSG(geom.utm_epsg)
    utm.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ecef = osr.SpatialReference()
    ecef.ImportFromEPSG(_ECEF_EPSG)
    ecef.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(utm, ecef)

    coords = np.column_stack([e, n, z])
    p_ecef = np.empty_like(coords)
    for start in range(0, len(coords), _OSR_CHUNK):
        block = coords[start : start + _OSR_CHUNK]
        p_ecef[start : start + len(block)] = np.asarray(ct.TransformPoints(block.tolist()))
    return ((p_ecef - geom.sim_t) @ geom.sim_rot) / geom.sim_scale


def _project_to_rgb(
    p_local: np.ndarray, rot: np.ndarray, tvec: np.ndarray, geom: SfmGeometry,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Project local-frame points into the RGB camera (FULL_OPENCV intrinsics).

    Returns:
        (u_rgb, v_rgb, front) — pixel coordinates and a mask of points in front
        of the camera.
    """
    p_cam = p_local @ rot.T + tvec
    zc = p_cam[:, 2]
    front = zc > 1e-6
    zc = np.where(front, zc, 1.0)
    xn = p_cam[:, 0] / zc
    yn = p_cam[:, 1] / zc
    k1, k2, p1, p2, k3, k4, k5, k6 = geom.dist
    r2 = xn * xn + yn * yn
    radial = 1 + r2 * (k1 + r2 * (k2 + r2 * (k3 + r2 * (k4 + r2 * (k5 + r2 * k6)))))
    xd = xn * radial + 2 * p1 * xn * yn + p2 * (r2 + 2 * xn * xn)
    yd = yn * radial + p1 * (r2 + 2 * yn * yn) + 2 * p2 * xn * yn
    return geom.fx * xd + geom.cx, geom.fy * yd + geom.cy, front


def _bilinear_sample(arr: np.ndarray, u: np.ndarray, v: np.ndarray, ok: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Bilinearly sample ``arr`` at fractional (u, v) where ``ok``; 0 / False elsewhere.

    Returns:
        (values, valid_mask) over the full input length.
    """
    h, w = arr.shape
    out = np.zeros_like(u)
    valid = np.zeros_like(u, dtype=bool)
    uu = u[ok]
    vv = v[ok]
    x0 = np.floor(uu).astype(np.int64)
    y0 = np.floor(vv).astype(np.int64)
    inside = (x0 >= 0) & (x0 < w - 1) & (y0 >= 0) & (y0 < h - 1)
    xi = x0[inside]
    yi = y0[inside]
    fx = uu[inside] - xi
    fy = vv[inside] - yi
    s = (
        arr[yi, xi] * (1 - fx) * (1 - fy)
        + arr[yi, xi + 1] * fx * (1 - fy)
        + arr[yi + 1, xi] * (1 - fx) * fy
        + arr[yi + 1, xi + 1] * fx * fy
    )
    idx = np.where(ok)[0][inside]
    out[idx] = s
    valid[idx] = True
    return out, valid


def _read_band_geometry(orig_path: str) -> tuple[np.ndarray, tuple[float, float]] | None:
    """
    Read the inverse ``DewarpHMatrix`` and ``RelativeOpticalCenter`` from MS XMP.

    ``DewarpHMatrix`` maps MS-sensor pixels → RGB pixels (identical across the four
    bands of a capture); its inverse maps RGB → the MS/NIR plane.
    ``RelativeOpticalCenterX/Y`` is the band's pixel offset from the NIR baseline.

    Returns:
        (H_inverse 3×3, (offset_x, offset_y)) or None if the tags are absent.
    """
    try:
        head = Path(orig_path).read_bytes()[:262144].decode("latin-1", errors="ignore")
    except OSError:
        return None
    h_match = re.search(r'DewarpHMatrix="([^"]+)"', head)
    if not h_match:
        return None
    try:
        h_mat = np.asarray([float(x) for x in h_match.group(1).split(",")]).reshape(3, 3)
    except ValueError:
        return None
    rx = re.search(r'RelativeOpticalCenterX="([+-]?[\d.]+)"', head)
    ry = re.search(r'RelativeOpticalCenterY="([+-]?[\d.]+)"', head)
    off = (float(rx.group(1)) if rx else 0.0, float(ry.group(1)) if ry else 0.0)
    try:
        return np.linalg.inv(h_mat), off
    except np.linalg.LinAlgError:
        return None


def _group_captures_by_band(
    cal_root: Path,
    band_manifest: dict,
    bands: list[str],
    build_original_map,
) -> dict[str, dict[str, tuple[Path, str]]]:
    """
    Group reflectance images by capture sequence across bands.

    Args:
        cal_root: Root of calibrated images (band subfolders).
        band_manifest: Serialised band manifest (for original raw MS paths).
        bands: Spectral band names to include.
        build_original_map: ``_build_original_image_map`` from the caller (stem→path).

    Returns:
        ``{capture_seq: {band: (reflectance_tif, original_raw_path)}}``.
    """
    captures: dict[str, dict[str, tuple[Path, str]]] = {}
    for band in bands:
        band_dir = cal_root / band
        if not band_dir.is_dir():
            continue
        original_map = build_original_map(band_manifest, band)
        orig_by_seq = {
            s: path
            for stem, path in original_map.items()
            if (s := _capture_seq(Path(path).name))
        }
        for refl in sorted(band_dir.glob("*_reflectance.tif")):
            seq = _capture_seq(refl.name)
            raw_stem = refl.stem.removesuffix("_reflectance")
            orig = original_map.get(raw_stem) or orig_by_seq.get(seq)
            if seq and orig:
                captures.setdefault(seq, {})[band] = (refl, orig)
    return captures


def _erode_mask(mask: np.ndarray, iterations: int) -> np.ndarray:
    """
    4-connected binary erosion (scipy-free fallback).

    Args:
        mask: Boolean coverage mask.
        iterations: Number of erosion passes (each trims a one-pixel border).

    Returns:
        The eroded mask.
    """
    m = mask
    for _ in range(max(0, iterations)):
        e = np.zeros_like(m)
        e[1:-1, 1:-1] = (
            m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
        )
        m = e
    return m


def _real_coverage_mask(dsm_path: Path) -> np.ndarray | None:
    """
    Build the real (unfilled) point-cloud coverage mask for boundary clipping.

    Reads the sibling unfilled ``dsm.tif`` next to a ``dsm_filled.tif`` and erodes its
    valid-data mask by ``_COVERAGE_EROSION_PX``.  The filled DSM extends beyond the true
    cloud, so painting bands over it spills past the RGB orthomosaic boundary; clipping
    to the unfilled coverage keeps the band extent aligned with the RGB product.

    Args:
        dsm_path: Path to the (filled) DSM the bands are rasterised onto.

    Returns:
        The eroded boolean coverage mask, or None when no unfilled sibling exists.
    """
    if gdal is None:
        return None
    unfilled = dsm_path.with_name(dsm_path.name.replace("_filled", ""))
    if unfilled == dsm_path or not unfilled.is_file():
        return None
    ds = gdal.Open(str(unfilled), gdal.GA_ReadOnly)
    if ds is None:
        return None
    band = ds.GetRasterBand(1)
    nd = band.GetNoDataValue()
    arr = band.ReadAsArray()
    ds = None
    cov = (arr != nd) & np.isfinite(arr.astype(np.float32)) if nd is not None else np.isfinite(arr.astype(np.float32))
    return _erode_mask(cov, _COVERAGE_EROSION_PX)


def _write_band_geotiff(values: np.ndarray, dsm_info: dict, out_path: Path) -> None:
    """Write a single-band ortho array (DSM grid) to a DEFLATE GeoTIFF."""
    h = dsm_info["height"]
    w = dsm_info["width"]
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(out_path), w, h, 1, gdal.GDT_Float32, options=["COMPRESS=DEFLATE"])
    ds.SetGeoTransform(dsm_info["geotransform"])
    ds.SetProjection(dsm_info["projection"])
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(_NODATA)
    band.WriteArray(values.reshape(h, w))
    ds.FlushCache()
    ds = None


def orthorectify_bands_pose(
    calibration_path: str,
    sfm_run_path: str,
    dsm_info: dict,
    band_manifest: dict,
    output_dir: str,
    bands: list[str],
    build_original_map,
) -> dict[str, str] | None:
    """
    Orthorectify all spectral bands by projecting the DSM through the SFM RGB poses.

    For every valid DSM cell and every capture, the cell is projected into the RGB
    camera (SFM pose + FULL_OPENCV intrinsics), mapped to the band's sensor frame
    (``DewarpHMatrix``⁻¹ + ``RelativeOpticalCenter``), and bilinearly sampled.
    Overlapping captures are blended with a per-capture nadir weight that is shared
    across all bands, so the bands stay co-registered.

    Args:
        calibration_path: Root of calibrated images (band subfolders).
        sfm_run_path: SFM run directory (sparse/0 + geo_transform.txt + geo_reference.json).
        dsm_info: DSM metadata (width, height, geotransform, projection, coverage_mask).
        band_manifest: Serialised band manifest (original raw MS paths for XMP).
        output_dir: Directory for the output band ortho GeoTIFFs.
        bands: Spectral band names to orthorectify.
        build_original_map: ``_build_original_image_map`` callable from the caller.

    Returns:
        ``{band_name: geotiff_path}``, or None if the SFM geometry is unavailable
        (caller should fall back to the GPS path).
    """
    if gdal is None or osr is None:
        return None
    geom = load_sfm_geometry(Path(sfm_run_path))
    if geom is None:
        return None

    cal_root = Path(calibration_path)
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    captures = _group_captures_by_band(cal_root, band_manifest, bands, build_original_map)
    if not captures:
        refl_count = sum(
            len(list((cal_root / b).glob("*_reflectance.tif"))) for b in bands if (cal_root / b).is_dir()
        )
        manifest_count = sum(
            len(build_original_map(band_manifest, b)) for b in bands
        )
        logger.warning(
            "Pose ortho: no captures grouped from manifest; GPS fallback "
            f"(found {refl_count} reflectance tifs, {manifest_count} manifest entries, "
            f"{len(geom.pose_by_capture)} poses — check reflectance/raw stem match)"
        )
        return None

    # Valid DSM cells → UTM (E, N, Z) → local SFM (precomputed once).
    gt = dsm_info["geotransform"]
    h = dsm_info["height"]
    w = dsm_info["width"]
    coverage = dsm_info.get("coverage_mask")
    dsm_path = dsm_info.get("path")
    if dsm_path is None:
        logger.warning("Pose ortho: dsm_info lacks 'path'; cannot read elevations")
        return None
    zds = gdal.Open(str(dsm_path), gdal.GA_ReadOnly)
    zband = zds.GetRasterBand(1)
    z_nodata = zband.GetNoDataValue()
    z = zband.ReadAsArray().astype(np.float64)
    zds = None

    rows = np.arange(h)
    cols = np.arange(w)
    cc, rr = np.meshgrid(cols, rows)
    valid = np.isfinite(z) & (z != z_nodata)
    if coverage is not None:
        valid &= coverage
    real = _real_coverage_mask(Path(dsm_path))
    if real is not None and real.shape == valid.shape:
        valid &= real
        logger.info(f"Pose ortho: clipped to unfilled cloud coverage ({valid.mean():.1%} of grid)")
    flat_valid = valid.ravel()
    cc_v = cc.ravel()[flat_valid]
    rr_v = rr.ravel()[flat_valid]
    z_v = z.ravel()[flat_valid]
    e_v = gt[0] + (cc_v + 0.5) * gt[1] + (rr_v + 0.5) * gt[2]
    n_v = gt[3] + (cc_v + 0.5) * gt[4] + (rr_v + 0.5) * gt[5]
    logger.info(f"Pose ortho: projecting {len(captures)} captures onto {flat_valid.sum()} DSM cells")
    p_local = _utm_to_local(e_v, n_v, z_v, geom)

    k = len(z_v)
    acc = {band: np.zeros(k) for band in bands}
    wsum = {band: np.zeros(k) for band in bands}

    used = 0
    for seq, bandmap in captures.items():
        pose = geom.pose_by_capture.get(seq)
        if pose is None:
            continue
        rot, tvec = pose
        u_rgb, v_rgb, front = _project_to_rgb(p_local, rot, tvec, geom)
        in_rgb = front & (u_rgb >= 0) & (u_rgb < geom.rgb_w) & (v_rgb >= 0) & (v_rgb < geom.rgb_h)
        if not in_rgb.any():
            continue
        used += 1
        # Band-coherent edge-feather weight (shared across bands): normalised distance
        # of the projected point to the nearest RGB image border (1 at centre, 0 at any
        # border).  Rectangular iso-contours follow the sensor footprint, so overlapping
        # captures cross-fade smoothly instead of leaving circular "scallop" seams.
        du = np.minimum(u_rgb, geom.rgb_w - 1.0 - u_rgb) / (0.5 * geom.rgb_w)
        dv = np.minimum(v_rgb, geom.rgb_h - 1.0 - v_rgb) / (0.5 * geom.rgb_h)
        edge = np.minimum(du, dv)
        feather = np.clip(edge / _FEATHER_FRAC, 0.0, 1.0)
        weight = np.where(in_rgb, np.maximum(feather, 1e-3), 0.0)

        h_inv = None
        for band, (_refl, orig) in bandmap.items():
            geo = _read_band_geometry(orig)
            if geo is None:
                continue
            h_inv, off = geo
            denom = h_inv[2, 0] * u_rgb + h_inv[2, 1] * v_rgb + h_inv[2, 2]
            u_ms = (h_inv[0, 0] * u_rgb + h_inv[0, 1] * v_rgb + h_inv[0, 2]) / denom - off[0]
            v_ms = (h_inv[1, 0] * u_rgb + h_inv[1, 1] * v_rgb + h_inv[1, 2]) / denom - off[1]
            _rds = gdal.Open(str(_refl), gdal.GA_ReadOnly)
            arr = _rds.GetRasterBand(1).ReadAsArray().astype(np.float32)
            _rds = None
            val, ok = _bilinear_sample(arr, u_ms, v_ms, in_rgb)
            ok &= val != _NODATA
            acc[band] += np.where(ok, val * weight, 0.0)
            wsum[band] += np.where(ok, weight, 0.0)

    logger.info(f"Pose ortho: {used}/{len(captures)} captures had a valid footprint")

    outputs: dict[str, str] = {}
    for band in bands:
        if wsum[band].max() <= 0:
            continue
        full = np.full(h * w, _NODATA, dtype=np.float64)
        m = wsum[band] > 0
        cell_val = np.zeros(k)
        cell_val[m] = acc[band][m] / wsum[band][m]
        flat_idx = np.where(flat_valid)[0]
        full[flat_idx[m]] = cell_val[m]
        out_path = out_root / f"{band}_ortho.tif"
        _write_band_geotiff(full, dsm_info, out_path)
        outputs[band] = str(out_path)
        logger.info(f"Pose ortho: wrote {band} → {out_path.name}")

    return outputs or None
