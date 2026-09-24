"""
Visualize camera poses from PhotoGear SfM pipeline
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_camera_poses(poses_file):
    """Load camera poses from camera_poses.txt"""
    cameras = []
    image_ids = []

    if poses_file.exists():
        with open(poses_file) as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.strip().split()
                if len(parts) >= 8:
                    image_id = int(parts[0])
                    # Extract quaternion and translation
                    qw, qx, qy, qz = (
                        float(parts[2]),
                        float(parts[3]),
                        float(parts[4]),
                        float(parts[5]),
                    )
                    tx, ty, tz = float(parts[6]), float(parts[7]), float(parts[8])

                    cameras.append(
                        {
                            "position": [tx, ty, tz],
                            "quaternion": [qw, qx, qy, qz],
                            "image_id": image_id,
                        },
                    )
                    image_ids.append(image_id)

    return cameras, image_ids


def quaternion_to_rotation_matrix(q):
    """Convert quaternion to rotation matrix"""
    qw, qx, qy, qz = q
    return np.array(
        [
            [1 - 2 * (qy**2 + qz**2), 2 * (qx * qy - qw * qz), 2 * (qx * qz + qw * qy)],
            [2 * (qx * qy + qw * qz), 1 - 2 * (qx**2 + qz**2), 2 * (qy * qz - qw * qx)],
            [2 * (qx * qz - qw * qy), 2 * (qy * qz + qw * qx), 1 - 2 * (qx**2 + qy**2)],
        ],
    )


def visualize_camera_poses(dataset_path, show_trajectory=True, show_orientations=True):
    """Visualize camera poses in 3D"""
    dataset_path = Path(dataset_path)
    poses_file = dataset_path / "sparse" / "camera_poses.txt"

    if not poses_file.exists():
        print(f"Error: Camera poses file not found: {poses_file}")
        print("Make sure to run the SfM pipeline first!")
        return

    cameras, image_ids = load_camera_poses(poses_file)

    if len(cameras) == 0:
        print("No camera poses found!")
        return

    print(f"Loaded {len(cameras)} camera poses")

    # Extract positions
    positions = np.array([cam["position"] for cam in cameras])

    # Create 3D plot
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")

    # Plot camera positions
    ax.scatter(
        positions[:, 0],
        positions[:, 1],
        positions[:, 2],
        c=range(len(positions)),
        cmap="viridis",
        s=50,
        alpha=0.8,
    )

    # Show trajectory if requested
    if show_trajectory and len(positions) > 1:
        ax.plot(
            positions[:, 0],
            positions[:, 1],
            positions[:, 2],
            "r-",
            alpha=0.5,
            linewidth=1,
            label="Camera trajectory",
        )

    # Show camera orientations if requested
    if show_orientations:
        scale = np.std(positions) * 0.1  # Scale arrows based on scene size

        for i, camera in enumerate(cameras):
            pos = camera["position"]
            R = quaternion_to_rotation_matrix(camera["quaternion"])

            # Camera forward direction (negative Z in camera coordinates)
            forward = -R[:, 2] * scale

            # Draw arrow showing camera direction
            ax.quiver(
                pos[0],
                pos[1],
                pos[2],
                forward[0],
                forward[1],
                forward[2],
                color="red",
                alpha=0.6,
                arrow_length_ratio=0.1,
            )

    # Add labels for first and last camera
    if len(positions) > 1:
        ax.text(
            positions[0, 0],
            positions[0, 1],
            positions[0, 2],
            "Start",
            fontsize=10,
            color="green",
        )
        ax.text(
            positions[-1, 0],
            positions[-1, 1],
            positions[-1, 2],
            "End",
            fontsize=10,
            color="red",
        )

    # Set labels and title
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title(f"Camera Poses - {len(cameras)} cameras")

    # Equal aspect ratio
    max_range = np.array([positions.max() - positions.min()]).max() / 2.0
    mid_x = (positions[:, 0].max() + positions[:, 0].min()) * 0.5
    mid_y = (positions[:, 1].max() + positions[:, 1].min()) * 0.5
    mid_z = (positions[:, 2].max() + positions[:, 2].min()) * 0.5

    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)

    if show_trajectory:
        ax.legend()

    plt.tight_layout()
    plt.show()

    # Print statistics
    print("\nCamera Trajectory Statistics:")
    print(f"Number of cameras: {len(cameras)}")
    print(f"Scene center: ({mid_x:.2f}, {mid_y:.2f}, {mid_z:.2f})")
    print(f"Scene extent: {max_range * 2:.2f}")

    if len(positions) > 1:
        distances = np.linalg.norm(np.diff(positions, axis=0), axis=1)
        print(f"Average distance between consecutive cameras: {np.mean(distances):.2f}")
        print(f"Total trajectory length: {np.sum(distances):.2f}")


def main():
    parser = argparse.ArgumentParser(description="Visualize camera poses from SfM")
    parser.add_argument("dataset", help="Path to dataset directory")
    parser.add_argument(
        "--no-trajectory",
        action="store_true",
        help="Don't show camera trajectory",
    )
    parser.add_argument(
        "--no-orientations",
        action="store_true",
        help="Don't show camera orientations",
    )

    args = parser.parse_args()

    visualize_camera_poses(
        args.dataset,
        show_trajectory=not args.no_trajectory,
        show_orientations=not args.no_orientations,
    )


if __name__ == "__main__":
    main()
