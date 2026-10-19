from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import csv
import json
import re
import unicodedata

import numpy as np
import open3d as o3d

from modules.surface_map.surface_map_builder import SurfaceMapResult
from modules.path_generation.zigzag_generator import ZigzagPathResult
from services.measurement_service import GeometryMeasurementResult

@dataclass
class ExportResult:
    export_id: str
    export_dir: Path

    summary_txt_path: Path
    summary_json_path: Path

    surface_mesh_path: Optional[Path] = None
    zigzag_csv_path: Optional[Path] = None
    clean_cloud_path: Optional[Path] = None
    normal_cloud_path: Optional[Path] = None

    message: str = "Đã xuất kết quả."


class ExportService:
    """
    Service xuất kết quả cuối pipeline Scan-to-Path.

    Quy ước folder export:

        data/exports/
        └── PJ1_YYYYMMDD_NNN_MODE_OBJECT_STATUS/

    Ví dụ:

        PJ1_20260515_001_FILE_RING_OK
        PJ1_20260515_002_FILE_SAMPLE_OK
        PJ1_20260515_003_TURNTABLE_WOODBLOCK_OK

    Bên trong folder:

        00_summary.txt
        00_summary.json
        01_surface_mesh.ply
        02_zigzag_path.csv
        03_clean_pointcloud.ply      optional
        04_normal_cloud.ply          optional

    Ghi chú:
        - File TXT dùng tiếng Việt để trình bày/demo.
        - File JSON dùng để sau này làm SQLite/job manager.
        - Không lưu dữ liệu lớn vào SQLite.
    """

    def __init__(
        self,
        export_root: str | Path = "data/exports",
        project_code: str = "PJ1",
    ):
        self.export_root = Path(export_root)
        self.project_code = self._sanitize_token(project_code or "PJ1")

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def export_pipeline_result(
        self,
        surface_result: SurfaceMapResult,
        zigzag_result: ZigzagPathResult,
        clean_cloud: Optional[o3d.geometry.PointCloud] = None,
        normal_cloud: Optional[o3d.geometry.PointCloud] = None,
        input_mode: str = "FILE",
        object_name: str = "SAMPLE",
        status: str = "OK",
        include_clean_cloud: bool = False,
        include_normal_cloud: bool = False,
        measurement_result: Optional[GeometryMeasurementResult] = None,
    ) -> ExportResult:
        """
        Xuất kết quả pipeline hiện tại.

        Args:
            surface_result:
                Kết quả tạo bản đồ bề mặt 3D.

            zigzag_result:
                Kết quả sinh đường Zigzag.

            clean_cloud:
                Point cloud sau lọc, optional.

            normal_cloud:
                Point cloud có normal, optional.

            input_mode:
                FILE / HANDHELD / TURNTABLE

            object_name:
                Tên mẫu vật, ví dụ RING / WOODBLOCK / PERSON / SAMPLE.

            status:
                OK / FAIL / TEST

            include_clean_cloud:
                True nếu muốn xuất thêm point cloud sạch.

            include_normal_cloud:
                True nếu muốn xuất thêm point cloud có normal.

        Returns:
            ExportResult
        """

        self._validate_surface_result(surface_result)
        self._validate_zigzag_result(zigzag_result)

        export_dir, export_id = self._create_export_dir(
            input_mode=input_mode,
            object_name=object_name,
            status=status,
        )

        # -------------------------------------------------
        # 01. Surface mesh
        # -------------------------------------------------
        surface_mesh_path = export_dir / "01_surface_mesh.ply"

        # Ưu tiên mesh thật sự đã dùng để sinh path.
        mesh_to_export = (
            zigzag_result.source_mesh
            if zigzag_result.source_mesh is not None
            else surface_result.mesh
        )

        ok = o3d.io.write_triangle_mesh(
            str(surface_mesh_path),
            mesh_to_export,
            write_ascii=False,
        )

        if not ok:
            raise RuntimeError(
                f"Không thể lưu surface mesh: {surface_mesh_path}"
            )

        # -------------------------------------------------
        # 02. Zigzag path CSV
        # -------------------------------------------------
        zigzag_csv_path = export_dir / "02_zigzag_path.csv"

        self._write_zigzag_csv(
            zigzag_result=zigzag_result,
            output_path=zigzag_csv_path,
        )

        # -------------------------------------------------
        # Optional point clouds
        # -------------------------------------------------
        clean_cloud_path = None
        normal_cloud_path = None

        if include_clean_cloud and clean_cloud is not None:
            clean_cloud_path = export_dir / "03_clean_pointcloud.ply"
            ok = o3d.io.write_point_cloud(
                str(clean_cloud_path),
                clean_cloud,
                write_ascii=False,
            )

            if not ok:
                raise RuntimeError(
                    f"Không thể lưu point cloud sạch: {clean_cloud_path}"
                )

        if include_normal_cloud and normal_cloud is not None:
            normal_cloud_path = export_dir / "04_normal_cloud.ply"
            ok = o3d.io.write_point_cloud(
                str(normal_cloud_path),
                normal_cloud,
                write_ascii=False,
            )

            if not ok:
                raise RuntimeError(
                    f"Không thể lưu normal cloud: {normal_cloud_path}"
                )

        # -------------------------------------------------
        # Summary TXT + JSON
        # -------------------------------------------------
        summary_txt_path = export_dir / "00_summary.txt"
        summary_json_path = export_dir / "00_summary.json"

        metadata = self._build_metadata(
            export_id=export_id,
            export_dir=export_dir,
            surface_result=surface_result,
            zigzag_result=zigzag_result,
            input_mode=input_mode,
            object_name=object_name,
            status=status,
            surface_mesh_path=surface_mesh_path,
            zigzag_csv_path=zigzag_csv_path,
            clean_cloud_path=clean_cloud_path,
            normal_cloud_path=normal_cloud_path,
            measurement_result=measurement_result,
        )

        summary_txt = self._build_summary_txt(
            metadata=metadata,
            measurement_result=measurement_result,
        )
        summary_txt_path.write_text(summary_txt, encoding="utf-8")

        summary_json_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )

        return ExportResult(
            export_id=export_id,
            export_dir=export_dir,
            surface_mesh_path=surface_mesh_path,
            zigzag_csv_path=zigzag_csv_path,
            clean_cloud_path=clean_cloud_path,
            normal_cloud_path=normal_cloud_path,
            summary_txt_path=summary_txt_path,
            summary_json_path=summary_json_path,
            message=(
                "Đã xuất kết quả pipeline thành công: "
                f"{export_dir}"
            ),
        )

    # -------------------------------------------------
    # Folder naming
    # -------------------------------------------------
    def _create_export_dir(
        self,
        input_mode: str,
        object_name: str,
        status: str,
    ) -> tuple[Path, str]:
        self.export_root.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y%m%d")

        mode_token = self._sanitize_token(input_mode or "FILE")
        object_token = self._sanitize_token(object_name or "SAMPLE")
        status_token = self._sanitize_token(status or "OK")

        next_index = self._get_next_daily_index(
            date_token=today,
        )

        export_id = (
            f"{self.project_code}_"
            f"{today}_"
            f"{next_index:03d}_"
            f"{mode_token}_"
            f"{object_token}_"
            f"{status_token}"
        )

        export_dir = self.export_root / export_id
        export_dir.mkdir(parents=True, exist_ok=False)

        return export_dir, export_id

    def _get_next_daily_index(self, date_token: str) -> int:
        """
        Tìm số thứ tự tiếp theo trong ngày.

        Ví dụ đang có:
            PJ1_20260515_001_FILE_SAMPLE_OK
            PJ1_20260515_002_FILE_SAMPLE_OK

        Thì lần tiếp theo là:
            003
        """

        pattern = re.compile(
            rf"^{re.escape(self.project_code)}_"
            rf"{re.escape(date_token)}_"
            r"(\d{3})_"
        )

        max_index = 0

        for item in self.export_root.iterdir():
            if not item.is_dir():
                continue

            match = pattern.match(item.name)

            if not match:
                continue

            try:
                idx = int(match.group(1))
                max_index = max(max_index, idx)
            except ValueError:
                continue

        return max_index + 1

    def _sanitize_token(self, text: str) -> str:
        """
        Chuẩn hóa token folder:
            - Bỏ dấu tiếng Việt.
            - Chuyển thành chữ hoa.
            - Thay ký tự lạ bằng dấu gạch dưới.
        """

        text = str(text).strip()

        if not text:
            return "UNKNOWN"

        normalized = unicodedata.normalize("NFKD", text)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

        ascii_text = ascii_text.upper()
        ascii_text = re.sub(r"[^A-Z0-9]+", "_", ascii_text)
        ascii_text = ascii_text.strip("_")

        return ascii_text or "UNKNOWN"

    # -------------------------------------------------
    # Writers
    # -------------------------------------------------
    def _write_zigzag_csv(
        self,
        zigzag_result: ZigzagPathResult,
        output_path: Path,
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow([
                "segment_id",
                "point_id",
                "x",
                "y",
                "z",
                "nx",
                "ny",
                "nz",
            ])

            for segment_id, (seg_points, seg_normals) in enumerate(
                zip(
                    zigzag_result.path_segments,
                    zigzag_result.normal_segments,
                )
            ):
                points = np.asarray(seg_points, dtype=float)
                normals = np.asarray(seg_normals, dtype=float)
                normals = self._normalize_vectors(normals)

                for point_id, (point, normal) in enumerate(
                    zip(points, normals)
                ):
                    writer.writerow([
                        segment_id,
                        point_id,
                        float(point[0]),
                        float(point[1]),
                        float(point[2]),
                        float(normal[0]),
                        float(normal[1]),
                        float(normal[2]),
                    ])

    def _build_metadata(
        self,
        export_id: str,
        export_dir: Path,
        surface_result: SurfaceMapResult,
        zigzag_result: ZigzagPathResult,
        input_mode: str,
        object_name: str,
        status: str,
        surface_mesh_path: Path,
        zigzag_csv_path: Path,
        clean_cloud_path: Optional[Path],
        normal_cloud_path: Optional[Path],
        measurement_result: Optional[GeometryMeasurementResult] = None,
    ) -> dict:
        export_time = datetime.now()

        return {
            "project": {
                "code": self.project_code,
                "name": "Scan-to-Path",
            },
            "export": {
                "id": export_id,
                "time": export_time.strftime("%Y-%m-%d %H:%M:%S"),
                "folder": str(export_dir),
                "input_mode": self._sanitize_token(input_mode),
                "object_name": self._sanitize_token(object_name),
                "status": self._sanitize_token(status),
            },
            "pipeline": [
                "Nạp / Quét mẫu 3D",
                "Lọc nhiễu đám mây điểm",
                "Tính pháp tuyến bề mặt",
                "Tạo bản đồ bề mặt 3D",
                "Sinh đường Zigzag",
                "Xuất kết quả",
            ],
            "surface_map": {
                "method": surface_result.method,
                "input_point_count": int(surface_result.input_point_count),
                "working_point_count": int(surface_result.working_point_count),
                "vertex_count": int(surface_result.vertex_count),
                "triangle_count": int(surface_result.triangle_count),
                "bounds_min": self._array_to_list(surface_result.bounds_min),
                "bounds_max": self._array_to_list(surface_result.bounds_max),
                "center": self._array_to_list(surface_result.center),
                "size": self._array_to_list(surface_result.size),
            },
            "zigzag_path": {
                "method": zigzag_result.method,
                "path_count": int(zigzag_result.path_count),
                "line_count": int(zigzag_result.line_count),
                "segment_count": int(zigzag_result.segment_count),
                "path_length": float(zigzag_result.path_length),
                "path_spacing": float(zigzag_result.path_spacing),
                "point_step": float(zigzag_result.point_step),
                "max_gap": float(zigzag_result.max_gap),
            },
            "measurement": (
                measurement_result.to_dict()
                if measurement_result is not None
                else None
            ),
            "files": {
                "summary_txt": "00_summary.txt",
                "summary_json": "00_summary.json",
                "surface_mesh": surface_mesh_path.name,
                "zigzag_path": zigzag_csv_path.name,
                "clean_cloud": (
                    clean_cloud_path.name
                    if clean_cloud_path is not None
                    else None
                ),
                "normal_cloud": (
                    normal_cloud_path.name
                    if normal_cloud_path is not None
                    else None
                ),
            },
        }

    def _build_summary_txt(self, metadata: dict, measurement_result: Optional[GeometryMeasurementResult] = None,) -> str:
        surface = metadata["surface_map"]
        zigzag = metadata["zigzag_path"]
        export = metadata["export"]
        files = metadata["files"]

        lines = [
            "BÁO CÁO XUẤT KẾT QUẢ SCAN-TO-PATH",
            "====================================",
            "",
            "[THÔNG TIN CHUNG]",
            f"Mã export      : {export['id']}",
            f"Thời gian xuất : {export['time']}",
            f"Thư mục        : {export['folder']}",
            f"Chế độ đầu vào : {export['input_mode']}",
            f"Tên mẫu vật    : {export['object_name']}",
            f"Trạng thái     : {export['status']}",
            "",
            "[QUY TRÌNH XỬ LÝ]",
            "1. Nạp / Quét mẫu 3D",
            "2. Lọc nhiễu đám mây điểm",
            "3. Tính pháp tuyến bề mặt",
            "4. Tạo bản đồ bề mặt 3D",
            "5. Sinh đường Zigzag",
            "6. Xuất kết quả",
            "",
            "[BẢN ĐỒ BỀ MẶT 3D]",
            f"Phương pháp tạo mesh      : {surface['method']}",
            f"Số điểm đầu vào           : {surface['input_point_count']}",
            f"Số điểm dùng để dựng mesh : {surface['working_point_count']}",
            f"Số đỉnh mesh              : {surface['vertex_count']}",
            f"Số mặt tam giác           : {surface['triangle_count']}",
            f"Tâm mô hình               : {surface['center']}",
            f"Kích thước mô hình        : {surface['size']}",
            "",
            "[ĐƯỜNG DẪN ZIGZAG]",
            f"Phương pháp sinh đường : {zigzag['method']}",
            f"Số điểm đường dẫn      : {zigzag['path_count']}",
            f"Số dải quét            : {zigzag['line_count']}",
            f"Số đoạn đường dẫn      : {zigzag['segment_count']}",
            f"Chiều dài xấp xỉ       : {zigzag['path_length']:.6f}",
            f"Khoảng cách dải quét   : {zigzag['path_spacing']:.6f}",
            f"Khoảng cách lấy mẫu    : {zigzag['point_step']:.6f}",
            f"Ngưỡng tách đoạn       : {zigzag['max_gap']:.6f}",
            "",
            "[DANH SÁCH FILE]",
            f"1. {files['summary_txt']}   - Báo cáo tóm tắt dạng TXT",
            f"2. {files['summary_json']}  - Metadata dạng JSON",
            f"3. {files['surface_mesh']}  - Mesh/bản đồ bề mặt 3D",
            f"4. {files['zigzag_path']}   - Đường dẫn Zigzag dạng CSV",
        ]

        if files.get("clean_cloud"):
            lines.append(
                f"5. {files['clean_cloud']} - Point cloud sau lọc nhiễu"
            )

        if files.get("normal_cloud"):
            lines.append(
                f"6. {files['normal_cloud']} - Point cloud có pháp tuyến"
            )

        lines.extend([
            "",
            "[GHI CHÚ]",
            "- File CSV chứa các cột: segment_id, point_id, x, y, z, nx, ny, nz.",
            "- x, y, z là tọa độ điểm đường dẫn.",
            "- nx, ny, nz là vector pháp tuyến tại điểm đường dẫn.",
            "- Dữ liệu này dùng cho bước mô phỏng hoặc phát triển điều khiển robot phun sơn sau này.",
            "",
        ])

        if measurement_result is not None:
            lines.append("")
            lines.append(measurement_result.to_text())

        return "\n".join(lines)

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _validate_surface_result(
        self,
        surface_result: SurfaceMapResult,
    ):
        if surface_result is None:
            raise ValueError("Chưa có kết quả surface map để xuất.")

        if surface_result.mesh is None:
            raise ValueError("Surface map không có mesh để xuất.")

        if len(surface_result.mesh.vertices) <= 0:
            raise ValueError("Surface mesh không có vertex.")

        if len(surface_result.mesh.triangles) <= 0:
            raise ValueError("Surface mesh không có triangle.")

    def _validate_zigzag_result(
        self,
        zigzag_result: ZigzagPathResult,
    ):
        if zigzag_result is None:
            raise ValueError("Chưa có kết quả Zigzag để xuất.")

        if zigzag_result.path_segments is None:
            raise ValueError("Zigzag chưa có path_segments.")

        if zigzag_result.normal_segments is None:
            raise ValueError("Zigzag chưa có normal_segments.")

        if len(zigzag_result.path_segments) <= 0:
            raise ValueError("Zigzag path rỗng.")

        if len(zigzag_result.path_points) <= 0:
            raise ValueError("Zigzag không có điểm đường dẫn.")

    def _array_to_list(self, value) -> list[float]:
        array = np.asarray(value, dtype=float).reshape(-1)

        return [float(x) for x in array]

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        vectors = np.asarray(vectors, dtype=float)

        if len(vectors) == 0:
            return vectors

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0

        return vectors / norms