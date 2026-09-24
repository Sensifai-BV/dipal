"""
Visualize sparse reconstruction results from PhotoGear SfM pipeline
"""

import argparse
from pathlib import Path

import numpy as np
import open3d as o3d


def load_camera_poses(poses_file):
    """Load camera poses from camera_poses.txt"""
    cameras = []
    if poses_file.exists():
        with open(poses_file) as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.strip().split()
                if len(parts) >= 8:
                    # Extract translation (camera position)
                    tx, ty, tz = float(parts[5]), float(parts[6]), float(parts[7])
                    cameras.append([tx, ty, tz])
    return np.array(cameras)


def create_camera_frustums(cameras, scale=0.1):
    """Create simple camera frustum visualizations"""
    geometries = []

    for i, pos in enumerate(cameras):
        # Create a small coordinate frame for each camera
        frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=scale)
        frame.translate(pos)

        # Color cameras differently
        colors = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        frame.paint_uniform_color(colors[i % 3])
        geometries.append(frame)

    return geometries


def visualize_sparse_reconstruction(dataset_path, show_cameras=True):
    """Visualize sparse reconstruction with optional camera poses"""
    dataset_path = Path(dataset_path)

    # Load sparse point cloud
    sparse_ply = dataset_path / "sparse" / "sparse_points.ply"
    if not sparse_ply.exists():
        print(f"Error: Sparse point cloud not found at {sparse_ply}")
        print("Make sure to run the SfM pipeline first!")
        return

    print(f"Loading sparse point cloud from {sparse_ply}")
    point_cloud = o3d.io.read_point_cloud(str(sparse_ply))

    if len(point_cloud.points) == 0:
        print("Error: Point cloud is empty!")
        return

    print(f"Loaded {len(point_cloud.points)} points")

    # Prepare visualization
    geometries = [point_cloud]

    # Load and visualize camera poses if requested
    if show_cameras:
        poses_file = dataset_path / "sparse" / "camera_poses.txt"
        if poses_file.exists():
            cameras = load_camera_poses(poses_file)
            if len(cameras) > 0:
                print(f"Loaded {len(cameras)} camera poses")

                # Estimate appropriate scale for camera frustums
                pcd_scale = np.std(np.asarray(point_cloud.points))
                camera_scale = pcd_scale * 0.05  # 5% of point cloud scale

                camera_frustums = create_camera_frustums(cameras, camera_scale)
                geometries.extend(camera_frustums)
            else:
                print("No camera poses found in file")
        else:
            print(f"Camera poses file not found: {poses_file}")

    # Set up visualization
    print("\nVisualization Controls:")
    print("- Mouse: Rotate view")
    print("- Scroll: Zoom in/out")
    print("- Shift+Mouse: Pan")
    print("- 'R': Reset view")
    print("- 'Q' or ESC: Quit")

    # Visualize
    o3d.visualization.draw_geometries(
        geometries,
        window_name="PhotoGear - Sparse Reconstruction",
        width=1200,
        height=800,
        point_show_normal=False,
    )


def main():
    parser = argparse.ArgumentParser(description="Visualize sparse SfM reconstruction")
    parser.add_argument("dataset", help="Path to dataset directory")
    parser.add_argument(
        "--no-cameras",
        action="store_true",
        help="Don't show camera poses",
    )

    args = parser.parse_args()

    visualize_sparse_reconstruction(args.dataset, show_cameras=not args.no_cameras)


if __name__ == "__main__":
    main()
