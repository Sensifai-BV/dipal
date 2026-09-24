"""
DSM Visualizer
--------------
Usage:
    python visualize_dsm.py /path/to/dsm.tif
    python visualize_dsm.py /path/to/dsm.tif --mode all
    python visualize_dsm.py /path/to/dsm.tif --mode hillshade
    python visualize_dsm.py /path/to/dsm.tif --mode elevation
    python visualize_dsm.py /path/to/dsm.tif --mode slope

Modes:
    all        — 2x2 grid: elevation, hillshade, slope, histogram  (default)
    elevation  — elevation map with terrain colormap
    hillshade  — greyscale hillshade
    slope      — slope map
    histogram  — elevation histogram
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LightSource
from matplotlib.ticker import MaxNLocator

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_dsm(path: str) -> tuple[np.ndarray, dict]:
    """
    Load DSM from GeoTIFF.  Returns (data_float32, meta).
    Tries rasterio first, falls back to GDAL bindings.
    """
    try:
        import rasterio
        with rasterio.open(path) as src:
            data = src.read(1).astype(np.float32)
            nodata = src.nodata
            transform = src.transform
            meta = {
                "crs": str(src.crs),
                "resolution_m": abs(src.res[0]),
                "width": src.width,
                "height": src.height,
                "nodata": nodata,
                "origin_x": transform.c,   # UTM easting of top-left
                "origin_y": transform.f,   # UTM northing of top-left
            }
        if nodata is not None:
            data[data == nodata] = np.nan
        data[~np.isfinite(data)] = np.nan
        return data, meta

    except ImportError:
        pass

    # GDAL fallback
    try:
        from osgeo import gdal
        gdal.UseExceptions()
        ds = gdal.Open(path, gdal.GA_ReadOnly)
        if ds is None:
            raise RuntimeError(f"GDAL cannot open {path}")
        band = ds.GetRasterBand(1)
        data = band.ReadAsArray().astype(np.float32)
        nodata = band.GetNoDataValue()
        gt = ds.GetGeoTransform()
        meta = {
            "crs": ds.GetProjection()[:60] + "...",
            "resolution_m": abs(gt[1]),
            "width": ds.RasterXSize,
            "height": ds.RasterYSize,
            "nodata": nodata,
            "origin_x": gt[0],   # UTM easting of top-left
            "origin_y": gt[3],   # UTM northing of top-left
        }
        ds = None
        if nodata is not None:
            data[data == nodata] = np.nan
        data[~np.isfinite(data)] = np.nan
        return data, meta
    except ImportError:
        raise RuntimeError(
            "Neither rasterio nor GDAL Python bindings are available.\n"
            "Install one:  pip install rasterio   or   pip install gdal"
        )


# ---------------------------------------------------------------------------
# Processing helpers
# ---------------------------------------------------------------------------

def normalise_u8(arr: np.ndarray) -> np.ndarray:
    """Stretch valid pixels to 0-255 uint8 for cv2 operations."""
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return np.zeros_like(arr, dtype=np.uint8)
    lo, hi = np.percentile(valid, 2), np.percentile(valid, 98)
    if hi == lo:
        return np.zeros_like(arr, dtype=np.uint8)
    scaled = np.clip((arr - lo) / (hi - lo) * 255, 0, 255)
    scaled[~np.isfinite(arr)] = 0
    return scaled.astype(np.uint8)


def _fill_nodata_nearest(dem: np.ndarray) -> np.ndarray:
    """
    Fill NaN holes with the nearest valid elevation (edge replication).

    Filling with a single global value (e.g. the median) creates an artificial
    flat plateau, so every valid/nodata boundary becomes a vertical "cliff".
    That injects spurious ~80-90° slopes and hard shadow lines into the slope
    and hillshade panels at the footprint edge — i.e. it visualises an artifact,
    not the terrain.  Nearest-valid fill makes the boundary gradient ~0, so the
    edges stay quiet; the filled pixels are re-masked to NaN by the callers.

    Uses ``cv2.inpaint`` over the nodata mask when available, falling back to a
    distance-transform nearest-neighbour fill.
    """
    mask = ~np.isfinite(dem)
    if not mask.any():
        return dem.astype(np.float32)

    valid = dem[~mask]
    fill_value = float(np.median(valid)) if valid.size else 0.0
    filled = np.where(mask, fill_value, dem).astype(np.float32)

    try:
        # Distance-transform indices of the nearest valid pixel for each hole.
        _, labels = cv2.distanceTransformWithLabels(
            mask.astype(np.uint8),
            cv2.DIST_L2,
            5,
            labelType=cv2.DIST_LABEL_PIXEL,
        )
        # Label 0 is background; labels enumerate the valid (zero-distance) pixels
        # in raster order, so map each hole's label to that valid pixel's value.
        valid_coords = np.flatnonzero(~mask.ravel())
        # Build a lookup: distanceTransformWithLabels numbers valid pixels 1..N
        # in row-major order of the zero-mask; reconstruct that ordering.
        order = np.argsort(np.flatnonzero(~mask.ravel()))
        lut = np.empty(valid_coords.size + 1, dtype=np.float32)
        lut[0] = fill_value
        lut[1:] = dem.ravel()[valid_coords[order]]
        filled = lut[labels].astype(np.float32)
    except Exception:
        pass  # keep the constant fill; callers re-mask the holes anyway

    return filled


def compute_hillshade(dem: np.ndarray, res: float = 1.0,
                      azimuth: float = 315, altitude: float = 45) -> np.ndarray:
    """
    Compute hillshade using matplotlib's LightSource (same math as gdaldem).
    Returns float array 0-1, NaN where DEM is NaN.
    """
    filled = _fill_nodata_nearest(dem)
    ls = LightSource(azdeg=azimuth, altdeg=altitude)
    hs = ls.hillshade(filled, vert_exag=1.5, dx=res, dy=res)
    hs[~np.isfinite(dem)] = np.nan
    return hs


def compute_slope(dem: np.ndarray, res: float = 1.0) -> np.ndarray:
    """Slope in degrees using Sobel gradients (same as gdaldem slope)."""
    filled = _fill_nodata_nearest(dem)
    # cv2 Sobel for robust gradient estimation
    gx = cv2.Sobel(filled, cv2.CV_64F, 1, 0, ksize=3) / (8 * res)
    gy = cv2.Sobel(filled, cv2.CV_64F, 0, 1, ksize=3) / (8 * res)
    slope = np.degrees(np.arctan(np.sqrt(gx**2 + gy**2)))
    slope[~np.isfinite(dem)] = np.nan
    return slope.astype(np.float32)


def build_mask_overlay(dem: np.ndarray) -> np.ndarray:
    """RGBA mask: transparent where valid, dark navy where nodata."""
    mask = np.zeros((*dem.shape, 4), dtype=np.float32)
    nodata_px = ~np.isfinite(dem)
    mask[nodata_px] = [0.05, 0.07, 0.12, 1.0]
    return mask


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------

STYLE = {
    "bg":      "#0d1117",
    "panel":   "#161b22",
    "text":    "#e6edf3",
    "subtext": "#8b949e",
    "accent":  "#58a6ff",
    "border":  "#30363d",
}


def _apply_global_style():
    plt.rcParams.update({
        "figure.facecolor":  STYLE["bg"],
        "axes.facecolor":    STYLE["panel"],
        "axes.edgecolor":    STYLE["border"],
        "axes.labelcolor":   STYLE["text"],
        "xtick.color":       STYLE["subtext"],
        "ytick.color":       STYLE["subtext"],
        "text.color":        STYLE["text"],
        "font.family":       "monospace",
        "grid.color":        STYLE["border"],
        "grid.linewidth":    0.5,
    })


def _label_ax(ax, title: str):
    ax.set_title(title, color=STYLE["accent"], fontsize=10,
                 fontweight="bold", pad=8, loc="left")
    ax.tick_params(labelsize=7)


def _stats_text(dem: np.ndarray, meta: dict) -> str:
    valid = dem[np.isfinite(dem)]
    if valid.size == 0:
        return "no valid data"
    return (
        f"min {valid.min():.2f} m   max {valid.max():.2f} m   "
        f"mean {valid.mean():.2f} m   σ {valid.std():.2f} m\n"
        f"resolution {meta['resolution_m']:.4f} m/px   "
        f"size {meta['width']}×{meta['height']} px   "
        f"valid {100*valid.size/(dem.size):.1f}%"
    )


# ---------------------------------------------------------------------------
# Individual panels
# ---------------------------------------------------------------------------

def plot_elevation(ax, dem: np.ndarray, meta: dict):
    valid = dem[np.isfinite(dem)]
    vmin, vmax = (np.percentile(valid, 2), np.percentile(valid, 98)) if valid.size else (0, 1)

    im = ax.imshow(dem, cmap="terrain", vmin=vmin, vmax=vmax,
                   interpolation="bilinear", origin="upper")
    ax.imshow(build_mask_overlay(dem), interpolation="nearest", origin="upper")

    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Elevation (m)", color=STYLE["subtext"], fontsize=7)
    cbar.ax.yaxis.set_tick_params(color=STYLE["subtext"], labelsize=7)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=STYLE["subtext"])

    _label_ax(ax, "Elevation")
    ax.axis("off")


def plot_hillshade(ax, dem: np.ndarray, meta: dict):
    hs = compute_hillshade(dem, res=meta["resolution_m"])
    ax.imshow(hs, cmap="gray", vmin=0, vmax=1,
              interpolation="bilinear", origin="upper")
    ax.imshow(build_mask_overlay(dem), interpolation="nearest", origin="upper")
    _label_ax(ax, "Hillshade  (az=315°  alt=45°  vert_exag=1.5×)")
    ax.axis("off")


def plot_slope(ax, dem: np.ndarray, meta: dict):
    slope = compute_slope(dem, res=meta["resolution_m"])
    valid = slope[np.isfinite(slope)]
    vmax = np.percentile(valid, 98) if valid.size else 45

    im = ax.imshow(slope, cmap="hot_r", vmin=0, vmax=vmax,
                   interpolation="bilinear", origin="upper")
    ax.imshow(build_mask_overlay(dem), interpolation="nearest", origin="upper")

    cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Slope (°)", color=STYLE["subtext"], fontsize=7)
    cbar.ax.yaxis.set_tick_params(color=STYLE["subtext"], labelsize=7)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=STYLE["subtext"])

    _label_ax(ax, "Slope")
    ax.axis("off")


def plot_histogram(ax, dem: np.ndarray, meta: dict):
    valid = dem[np.isfinite(dem)]
    if valid.size == 0:
        ax.text(0.5, 0.5, "no valid data", ha="center", va="center",
                transform=ax.transAxes, color=STYLE["subtext"])
        return

    lo, hi = np.percentile(valid, 1), np.percentile(valid, 99)
    n, bins, patches = ax.hist(valid, bins=120, range=(lo, hi),
                                color=STYLE["accent"], alpha=0.85, linewidth=0)

    # Colour bars by height for a gradient effect
    norm_h = n / n.max() if n.max() > 0 else n
    cmap_h = plt.get_cmap("cool")
    for patch, nh in zip(patches, norm_h):
        patch.set_facecolor(cmap_h(nh))

    ax.axvline(valid.mean(), color="#f78166", linewidth=1.2,
               label=f"mean {valid.mean():.2f} m")
    ax.axvline(np.median(valid), color="#ffa657", linewidth=1.2, linestyle="--",
               label=f"median {np.median(valid):.2f} m")

    ax.set_xlabel("Elevation (m)", fontsize=8)
    ax.set_ylabel("Pixel count", fontsize=8)
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.xaxis.set_major_locator(MaxNLocator(6))
    ax.legend(fontsize=7, facecolor=STYLE["panel"],
              edgecolor=STYLE["border"], labelcolor=STYLE["text"])
    ax.grid(True, axis="y", alpha=0.3)
    _label_ax(ax, "Elevation histogram")


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

def show_all(dem: np.ndarray, meta: dict, title: str):
    _apply_global_style()
    fig = plt.figure(figsize=(16, 12), facecolor=STYLE["bg"])
    fig.suptitle(
        title, color=STYLE["text"], fontsize=13,
        fontweight="bold", y=0.97, fontfamily="monospace"
    )

    # Stats bar below title
    fig.text(0.5, 0.935, _stats_text(dem, meta),
             ha="center", va="top", fontsize=8,
             color=STYLE["subtext"], fontfamily="monospace")

    gs = gridspec.GridSpec(2, 2, figure=fig,
                           left=0.04, right=0.96,
                           top=0.91, bottom=0.04,
                           hspace=0.12, wspace=0.08)

    plot_elevation(fig.add_subplot(gs[0, 0]), dem, meta)
    plot_hillshade(fig.add_subplot(gs[0, 1]), dem, meta)
    plot_slope(fig.add_subplot(gs[1, 0]), dem, meta)
    plot_histogram(fig.add_subplot(gs[1, 1]), dem, meta)

    plt.savefig("dsm_visualization.png", dpi=150, bbox_inches="tight",
                facecolor=STYLE["bg"])
    print("Saved: dsm_visualization.png")
    plt.show()


def show_single(dem: np.ndarray, meta: dict, mode: str, title: str):
    _apply_global_style()
    fig, ax = plt.subplots(figsize=(10, 8), facecolor=STYLE["bg"])
    fig.suptitle(title, color=STYLE["text"], fontsize=11,
                 fontweight="bold", fontfamily="monospace")
    fig.text(0.5, 0.91, _stats_text(dem, meta),
             ha="center", va="top", fontsize=7.5,
             color=STYLE["subtext"], fontfamily="monospace")

    dispatch = {
        "elevation": plot_elevation,
        "hillshade": plot_hillshade,
        "slope":     plot_slope,
        "histogram": plot_histogram,
    }
    dispatch[mode](ax, dem, meta)

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    out = f"dsm_{mode}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=STYLE["bg"])
    print(f"Saved: {out}")
    plt.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Visualize a DSM GeoTIFF with elevation, hillshade, slope, and histogram."
    )
    parser.add_argument("path", help="Path to DSM GeoTIFF (e.g. dsm_filled.tif)")
    parser.add_argument(
        "--mode",
        choices=["all", "elevation", "hillshade", "slope", "histogram"],
        default="all",
        help="Which visualization to show (default: all)",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {path} ...")
    dem, meta = load_dsm(str(path))
    print(f"Loaded: {meta['width']}×{meta['height']} px, "
          f"res={meta['resolution_m']:.4f} m, "
          f"CRS={meta['crs'][:40]}")

    title = path.name

    if args.mode == "all":
        show_all(dem, meta, title)
    else:
        show_single(dem, meta, args.mode, title)


if __name__ == "__main__":
    main()