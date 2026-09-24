"""
Compare sparse and dense reconstruction results side by side
"""

import argparse
from pathlib import Path

import open3d as o3d


def load_point_clouds(dataset_path):
    """Load both sparse and dense point clouds"""
    dataset_path = Path(dataset_path)

    # Load sparse point cloud
    sparse_ply = dataset_path / "sparse" / "sparse_points.ply"
    dense_ply = dataset_path / "dense" / "fused.ply"

    sparse_pcd = None
    dense_pcd = None

    if sparse_ply.exists():
        sparse_pcd = o3d.io.read_point_cloud(str(sparse_ply))
        if len(sparse_pcd.points) > 0:
            # Color sparse points blue
            sparse_pcd.paint_uniform_color([0.2, 0.6, 1.0])
            print(f"Loaded sparse: {len(sparse_pcd.points)} points")
        else:
            sparse_pcd = None

    if dense_ply.exists():
        dense_pcd = o3d.io.read_point_cloud(str(dense_ply))
        if len(dense_pcd.points) > 0:
            # Downsample dense if too large
            if len(dense_pcd.points) > 500000:
                print(
                    f"Downsampling dense point cloud from {len(dense_pcd.points)} points...",
                )
                dense_pcd = dense_pcd.voxel_down_sample(0.01)
                print(f"After downsampling: {len(dense_pcd.points)} points")

            # Keep original colors if available, otherwise use red
            if not dense_pcd.has_colors():
                dense_pcd.paint_uniform_color([1.0, 0.3, 0.3])
            print(f"Loaded dense: {len(dense_pcd.points)} points")
        else:
            dense_pcd = None

    return sparse_pcd, dense_pcd


def compare_reconstructions(dataset_path, mode="both"):
    """Compare sparse and dense reconstructions"""
    sparse_pcd, dense_pcd = load_point_clouds(dataset_path)

    geometries = []

    if mode in ["sparse", "both"] and sparse_pcd is not None:
        geometries.append(sparse_pcd)

    if mode in ["dense", "both"] and dense_pcd is not None:
        geometries.append(dense_pcd)

    if not geometries:
        print("No point clouds found to visualize!")
        print("Make sure to run the SfM pipeline first.")
        return

    # Print comparison statistics
    print("\nReconstruction Comparison:")
    if sparse_pcd is not None:
        print(f"Sparse points: {len(sparse_pcd.points):,}")
    if dense_pcd is not None:
        print(f"Dense points: {len(dense_pcd.points):,}")

    if sparse_pcd is not None and dense_pcd is not None:
        ratio = len(dense_pcd.points) / len(sparse_pcd.points)
        print(f"Dense/Sparse ratio: {ratio:.1f}x")

    print("\nVisualization:")
    if mode == "both":
        print("- Blue points: Sparse reconstruction")
        print("- Red/Original colors: Dense reconstruction")

    print("\nControls:")
    print("- Mouse: Rotate view")
    print("- Scroll: Zoom in/out")
    print("- Shift+Mouse: Pan")
    print("- 'R': Reset view")
    print("- 'Q' or ESC: Quit")

    # Visualize
    o3d.visualization.draw_geometries(
        geometries,
        window_name=f"PhotoGear - {mode.title()} Reconstruction",
        width=1200,
        height=800,
        point_show_normal=False,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Compare sparse and dense reconstructions",
    )
    parser.add_argument("dataset", help="Path to dataset directory")
    parser.add_argument(
        "--mode",
        choices=["sparse", "dense", "both"],
        default="both",
        help="Which reconstruction to show (default: both)",
    )

    args = parser.parse_args()

    compare_reconstructions(args.dataset, args.mode)


if __name__ == "__main__":
    main()
