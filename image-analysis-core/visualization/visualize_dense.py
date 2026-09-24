"""
Visualize dense reconstruction results from PhotoGear SfM pipeline
"""

import argparse
from pathlib import Path

import open3d as o3d


def visualize_dense_reconstruction(dataset_path, downsample=True, voxel_size=0.01):
    """Visualize dense reconstruction with optional downsampling"""
    dataset_path = Path(dataset_path)

    # Load dense point cloud
    dense_ply = dataset_path / "dense" / "fused.ply"
    if not dense_ply.exists():
        print(f"Error: Dense point cloud not found at {dense_ply}")
        print("Make sure to run the SfM pipeline with dense reconstruction enabled!")
        return

    print(f"Loading dense point cloud from {dense_ply}")
    point_cloud = o3d.io.read_point_cloud(str(dense_ply))

    if len(point_cloud.points) == 0:
        print("Error: Point cloud is empty!")
        return

    print(f"Loaded {len(point_cloud.points)} points")

    # Downsample for better performance if requested
    if downsample and len(point_cloud.points) > 100000:
        print(f"Downsampling point cloud (voxel size: {voxel_size})")
        point_cloud = point_cloud.voxel_down_sample(voxel_size)
        print(f"After downsampling: {len(point_cloud.points)} points")

    # Compute normals for better visualization
    if not point_cloud.has_normals():
        print("Computing normals...")
        point_cloud.estimate_normals()

    # Set up visualization
    print("\nVisualization Controls:")
    print("- Mouse: Rotate view")
    print("- Scroll: Zoom in/out")
    print("- Shift+Mouse: Pan")
    print("- 'R': Reset view")
    print("- 'N': Toggle normals")
    print("- 'Q' or ESC: Quit")

    # Visualize
    o3d.visualization.draw_geometries(
        [point_cloud],
        window_name="PhotoGear - Dense Reconstruction",
        width=1200,
        height=800,
        point_show_normal=False,
    )


def main():
    parser = argparse.ArgumentParser(description="Visualize dense SfM reconstruction")
    parser.add_argument("dataset", help="Path to dataset directory")
    parser.add_argument(
        "--no-downsample",
        action="store_true",
        help="Don't downsample large point clouds",
    )
    parser.add_argument(
        "--voxel-size",
        type=float,
        default=0.01,
        help="Voxel size for downsampling (default: 0.01)",
    )

    args = parser.parse_args()

    visualize_dense_reconstruction(
        args.dataset,
        downsample=not args.no_downsample,
        voxel_size=args.voxel_size,
    )


if __name__ == "__main__":
    main()
