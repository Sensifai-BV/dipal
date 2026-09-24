#!/usr/bin/env python3
"""
Visualize vegetation index GeoTIFFs (NDVI, NDRE, GNDVI) as
red → yellow → green heatmaps.

Usage:
    python visualize_vegetation_index.py <path_to_geotiff> [--output out.png]
    python visualize_vegetation_index.py ndvi.tif
    python visualize_vegetation_index.py ndvi.tif --output ndvi_heatmap.png
    python visualize_vegetation_index.py ndvi.tif ndre.tif gndvi.tif
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

try:
    from osgeo import gdal

    gdal.UseExceptions()
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False


# ---------------------------------------------------------------------------
# Red → Yellow → Green colormap (matches RdYlGn diverging scheme)
# ---------------------------------------------------------------------------
RDYLGN_COLORS = [
    (0.0, "#a50026"),   # dark red
    (0.1, "#d73027"),   # red
    (0.2, "#f46d43"),   # orange-red
    (0.3, "#fdae61"),   # orange
    (0.4, "#fee08b"),   # yellow-orange
    (0.5, "#ffffbf"),   # pale yellow
    (0.6, "#d9ef8b"),   # yellow-green
    (0.7, "#a6d96a"),   # light green
    (0.8, "#66bd63"),   # green
    (0.9, "#1a9850"),   # dark green
    (1.0, "#006837"),   # deep green
]

VEGETATION_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "vegetation_rdylgn",
    [(pos, c) for pos, c in RDYLGN_COLORS],
    N=256,
)


def load_band(path: str) -> np.ndarray:
    """Load a single-band GeoTIFF as a float32 numpy array."""
    if HAS_GDAL:
        ds = gdal.Open(path, gdal.GA_ReadOnly)
        if ds is None:
            raise FileNotFoundError(f"Cannot open: {path}")
        band = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
        nodata = ds.GetRasterBand(1).GetNoDataValue()
        ds = None
        if nodata is not None:
            band[band == nodata] = np.nan
        return band

    # Fallback: use rasterio
    try:
        import rasterio
    except ImportError:
        raise RuntimeError(
            "Either GDAL or rasterio is required. "
            "Install with: pip install rasterio"
        )
    with rasterio.open(path) as src:
        band = src.read(1).astype(np.float32)
        if src.nodata is not None:
            band[band == src.nodata] = np.nan
    return band


def detect_index_name(filepath: str) -> str:
    """Guess the index name from the filename."""
    name = Path(filepath).stem.lower()
    for idx in ("ndvi", "ndre", "gndvi"):
        if idx in name:
            return idx.upper()
    return "Vegetation Index"


def visualize_single(
    filepath: str,
    output: str | None = None,
    vmin: float = -1.0,
    vmax: float = 1.0,
) -> None:
    """Render a single vegetation index GeoTIFF as a heatmap."""
    band = load_band(filepath)
    index_name = detect_index_name(filepath)

    valid = band[np.isfinite(band)]
    avg = float(np.mean(valid)) if valid.size > 0 else 0.0

    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    im = ax.imshow(band, cmap=VEGETATION_CMAP, vmin=vmin, vmax=vmax)

    # Color bar
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label(f"{index_name} Value", fontsize=11)

    # Average value badge
    ax.text(
        0.98,
        0.97,
        f"Avg {index_name}\n{avg:.2f}",
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        va="top",
        ha="right",
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor="#3b82f6",
            edgecolor="none",
            alpha=0.9,
        ),
        color="white",
    )

    ax.set_title(f"{index_name} Heatmap", fontsize=14, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        print(f"Saved: {output}")
    else:
        plt.show()

    plt.close(fig)


def visualize_multi(
    filepaths: list[str],
    output: str | None = None,
    vmin: float = -1.0,
    vmax: float = 1.0,
) -> None:
    """Render multiple vegetation index GeoTIFFs side by side."""
    n = len(filepaths)
    fig, axes = plt.subplots(1, n, figsize=(7 * n, 7))
    if n == 1:
        axes = [axes]

    for ax, fp in zip(axes, filepaths):
        band = load_band(fp)
        index_name = detect_index_name(fp)

        valid = band[np.isfinite(band)]
        avg = float(np.mean(valid)) if valid.size > 0 else 0.0

        im = ax.imshow(band, cmap=VEGETATION_CMAP, vmin=vmin, vmax=vmax)
        ax.set_title(f"{index_name}  (avg: {avg:.2f})", fontsize=13, fontweight="bold")
        ax.axis("off")
        fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)

    fig.suptitle("Vegetation Index Heatmaps", fontsize=16, fontweight="bold", y=1.02)
    fig.tight_layout()

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        print(f"Saved: {output}")
    else:
        plt.show()

    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize vegetation index GeoTIFFs as red→yellow→green heatmaps."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Path(s) to vegetation index GeoTIFF(s) (NDVI, NDRE, GNDVI).",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Save output image to file instead of displaying.",
    )
    parser.add_argument(
        "--vmin", type=float, default=-1.0,
        help="Minimum value for colormap (default: -1.0).",
    )
    parser.add_argument(
        "--vmax", type=float, default=1.0,
        help="Maximum value for colormap (default: 1.0).",
    )
    args = parser.parse_args()

    for f in args.files:
        if not Path(f).exists():
            print(f"Error: file not found: {f}", file=sys.stderr)
            sys.exit(1)

    if len(args.files) == 1:
        visualize_single(args.files[0], args.output, args.vmin, args.vmax)
    else:
        visualize_multi(args.files, args.output, args.vmin, args.vmax)


if __name__ == "__main__":
    main()
