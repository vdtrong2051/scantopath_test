from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import open3d as o3d


@dataclass
class RGBDToPLYParams:
    """
    Thông số chuyển RGB-D sang point cloud.

    Quy ước:
        - depth input thường là uint16, đơn vị millimeter từ OpenNI2.
        - depth_scale = 0.001 nghĩa là mm -> meter.
        - RGB input mặc định là RGB.
        - Nếu frame màu là BGR từ OpenCV thì đặt color_order="BGR".
    """

    fx: float = 580.0
    fy: float = 580.0
    cx: float = 320.0
    cy: float = 240.0

    depth_scale: float = 0.001

    min_depth_m: float = 0.10
    max_depth_m: float = 2.50

    color_order: str = "RGB"

    # Lấy mẫu thưa để giảm file nếu cần.
    # stride=1 nghĩa là giữ toàn bộ pixel hợp lệ.
    stride: int = 1

    # Giữ hệ tọa độ camera kiểu ảnh:
    # x sang phải, y xuống dưới, z đi ra trước camera.
    # Nếu muốn nhìn trong Open3D tự nhiên hơn thì có thể set flip_y=True.
    flip_y: bool = False

    # Lọc bớt điểm depth bằng 0 / NaN / Inf.
    remove_invalid: bool = True

    # Ghi binary PLY để nhanh hơn ASCII.
    write_ascii: bool = False


@dataclass
class RGBDToPLYResult:
    output_path: Path

    point_cloud: o3d.geometry.PointCloud

    point_count: int
    has_colors: bool

    bounds_min: np.ndarray
    bounds_max: np.ndarray
    center: np.ndarray
    size: np.ndarray

    message: str


def rgbd_to_point_cloud(
    rgb_frame: Optional[np.ndarray],
    depth_frame: np.ndarray,
    params: Optional[RGBDToPLYParams] = None,
) -> o3d.geometry.PointCloud:
    """
    Chuyển RGB-D frame thành Open3D PointCloud.

    Args:
        rgb_frame:
            Ảnh màu H x W x 3.
            Có thể là RGB hoặc BGR tùy params.color_order.

        depth_frame:
            Ảnh depth H x W.
            Thường là uint16 millimeter từ OpenNI2.

        params:
            Thông số camera và lọc depth.

    Returns:
        open3d.geometry.PointCloud
    """

    params = params or RGBDToPLYParams()

    depth = _prepare_depth(depth_frame, params)
    rgb = _prepare_rgb(rgb_frame, depth.shape, params)

    points, colors = rgbd_to_numpy_points(
        rgb_frame=rgb,
        depth_frame_m=depth,
        params=params,
    )

    cloud = o3d.geometry.PointCloud()

    if len(points) > 0:
        cloud.points = o3d.utility.Vector3dVector(points)

    if colors is not None and len(colors) == len(points):
        cloud.colors = o3d.utility.Vector3dVector(colors)

    return cloud


def rgbd_to_numpy_points(
    rgb_frame: Optional[np.ndarray],
    depth_frame_m: np.ndarray,
    params: Optional[RGBDToPLYParams] = None,
) -> tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Chuyển RGB-D thành mảng numpy points/colors.

    Returns:
        points:
            N x 3, float64, đơn vị meter.

        colors:
            N x 3, float64, range 0..1 hoặc None.
    """

    params = params or RGBDToPLYParams()

    depth = np.asarray(depth_frame_m, dtype=np.float32)

    if depth.ndim != 2:
        raise ValueError(
            "depth_frame_m phải là ảnh 2D dạng H x W."
        )

    h, w = depth.shape

    stride = max(1, int(params.stride))

    if stride > 1:
        depth = depth[::stride, ::stride]
        h, w = depth.shape

    jj, ii = np.meshgrid(
        np.arange(w, dtype=np.float32),
        np.arange(h, dtype=np.float32),
    )

    # Nếu stride > 1 thì pixel index thực tế phải nhân lại.
    if stride > 1:
        jj = jj * stride
        ii = ii * stride

    valid_mask = np.ones_like(depth, dtype=bool)

    if params.remove_invalid:
        valid_mask &= np.isfinite(depth)
        valid_mask &= depth > 0

    valid_mask &= depth >= float(params.min_depth_m)
    valid_mask &= depth <= float(params.max_depth_m)

    if not np.any(valid_mask):
        return (
            np.empty((0, 3), dtype=np.float64),
            None,
        )

    z = depth[valid_mask].astype(np.float64)

    x = (jj[valid_mask].astype(np.float64) - float(params.cx)) * z / float(params.fx)
    y = (ii[valid_mask].astype(np.float64) - float(params.cy)) * z / float(params.fy)

    if params.flip_y:
        y = -y

    points = np.stack((x, y, z), axis=1)

    colors = None

    if rgb_frame is not None:
        rgb = np.asarray(rgb_frame)

        if stride > 1:
            rgb = rgb[::stride, ::stride]

        if rgb.shape[:2] == depth.shape and rgb.ndim == 3 and rgb.shape[2] >= 3:
            color_values = rgb[:, :, :3][valid_mask]

            if params.color_order.strip().upper() == "BGR":
                color_values = color_values[:, [2, 1, 0]]

            color_values = color_values.astype(np.float64)

            if color_values.max(initial=0) > 1.0:
                color_values = color_values / 255.0

            colors = np.clip(color_values, 0.0, 1.0)

    return points, colors


def save_rgbd_as_ply(
    rgb_frame: Optional[np.ndarray],
    depth_frame: np.ndarray,
    output_path: str | Path,
    params: Optional[RGBDToPLYParams] = None,
) -> RGBDToPLYResult:
    """
    Chuyển RGB-D frame sang point cloud và lưu ra .ply.

    Đây là hàm chính mà openni_scan_worker.py sẽ gọi khi bấm:
        CHỤP 1 FRAME
    """

    params = params or RGBDToPLYParams()
    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cloud = rgbd_to_point_cloud(
        rgb_frame=rgb_frame,
        depth_frame=depth_frame,
        params=params,
    )

    point_count = len(cloud.points)

    if point_count <= 0:
        raise RuntimeError(
            "Không tạo được point cloud: không có điểm depth hợp lệ."
        )

    ok = o3d.io.write_point_cloud(
        str(output_path),
        cloud,
        write_ascii=params.write_ascii,
    )

    if not ok:
        raise RuntimeError(
            f"Không thể ghi point cloud ra file: {output_path}"
        )

    return _build_result(
        output_path=output_path,
        cloud=cloud,
    )


def save_rgbd_as_ascii_ply_manual(
    rgb_frame: Optional[np.ndarray],
    depth_frame: np.ndarray,
    output_path: str | Path,
    params: Optional[RGBDToPLYParams] = None,
) -> RGBDToPLYResult:
    """
    Ghi PLY thủ công dạng ASCII.

    Hàm này giữ lại tinh thần từ code SaveWorker cũ.
    Bình thường nên dùng save_rgbd_as_ply() vì Open3D ghi binary nhanh hơn.
    """

    params = params or RGBDToPLYParams()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    depth = _prepare_depth(depth_frame, params)
    rgb = _prepare_rgb(rgb_frame, depth.shape, params)

    points, colors = rgbd_to_numpy_points(
        rgb_frame=rgb,
        depth_frame_m=depth,
        params=params,
    )

    if len(points) <= 0:
        raise RuntimeError(
            "Không tạo được point cloud: không có điểm depth hợp lệ."
        )

    if colors is None:
        colors_uint8 = np.full(
            (len(points), 3),
            180,
            dtype=np.uint8,
        )
    else:
        colors_uint8 = np.clip(colors * 255.0, 0, 255).astype(np.uint8)

    header = [
        "ply",
        "format ascii 1.0",
        f"element vertex {len(points)}",
        "property float x",
        "property float y",
        "property float z",
        "property uchar red",
        "property uchar green",
        "property uchar blue",
        "end_header",
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n")

        data = np.hstack(
            [
                points.astype(np.float64),
                colors_uint8.astype(np.uint8),
            ]
        )

        np.savetxt(
            f,
            data,
            fmt="%.6f %.6f %.6f %d %d %d",
        )

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)

    if colors is not None:
        cloud.colors = o3d.utility.Vector3dVector(colors)

    return _build_result(
        output_path=output_path,
        cloud=cloud,
    )


# -------------------------------------------------
# Internal helpers
# -------------------------------------------------
def _prepare_depth(
    depth_frame: np.ndarray,
    params: RGBDToPLYParams,
) -> np.ndarray:
    if depth_frame is None:
        raise ValueError("depth_frame bị None.")

    depth = np.asarray(depth_frame)

    if depth.ndim != 2:
        raise ValueError(
            f"depth_frame phải là ảnh 2D H x W, nhận được shape={depth.shape}"
        )

    depth = depth.astype(np.float32)

    depth = np.nan_to_num(
        depth,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    # Nếu depth lớn hơn 20 thì gần như chắc là millimeter.
    # Nếu đã là meter rồi thì không nhân scale nữa.
    if depth.max(initial=0) > 20.0:
        depth = depth * float(params.depth_scale)

    return depth


def _prepare_rgb(
    rgb_frame: Optional[np.ndarray],
    target_shape: tuple[int, int],
    params: RGBDToPLYParams,
) -> Optional[np.ndarray]:
    if rgb_frame is None:
        return None

    rgb = np.asarray(rgb_frame)

    if rgb.ndim != 3 or rgb.shape[2] < 3:
        return None

    rgb = rgb[:, :, :3]

    if rgb.dtype != np.uint8:
        rgb = _normalize_to_uint8(rgb)

    target_h, target_w = target_shape

    if rgb.shape[0] != target_h or rgb.shape[1] != target_w:
        rgb = _resize_nearest(
            image=rgb,
            target_h=target_h,
            target_w=target_w,
        )

    return np.ascontiguousarray(rgb)


def _resize_nearest(
    image: np.ndarray,
    target_h: int,
    target_w: int,
) -> np.ndarray:
    src_h, src_w = image.shape[:2]

    y_idx = np.linspace(0, src_h - 1, target_h).astype(np.int32)
    x_idx = np.linspace(0, src_w - 1, target_w).astype(np.int32)

    return image[y_idx][:, x_idx]


def _normalize_to_uint8(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image, dtype=np.float32)

    arr = np.nan_to_num(
        arr,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    min_val = float(arr.min(initial=0))
    max_val = float(arr.max(initial=0))

    if max_val - min_val < 1e-9:
        return np.zeros(arr.shape, dtype=np.uint8)

    arr = (arr - min_val) / (max_val - min_val)
    arr = arr * 255.0

    return np.clip(arr, 0, 255).astype(np.uint8)


def _build_result(
    output_path: Path,
    cloud: o3d.geometry.PointCloud,
) -> RGBDToPLYResult:
    points = np.asarray(cloud.points)

    if len(points) <= 0:
        bounds_min = np.zeros(3)
        bounds_max = np.zeros(3)
        center = np.zeros(3)
        size = np.zeros(3)
    else:
        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)
        center = (bounds_min + bounds_max) / 2.0
        size = bounds_max - bounds_min

    return RGBDToPLYResult(
        output_path=Path(output_path),
        point_cloud=cloud,
        point_count=len(cloud.points),
        has_colors=cloud.has_colors(),
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        center=center,
        size=size,
        message=(
            f"Đã tạo point cloud từ RGB-D: {output_path} "
            f"({len(cloud.points)} điểm)"
        ),
    )