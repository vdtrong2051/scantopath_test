from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox


class PipelinePresenter:
    """
    Presenter chuyên hiển thị UI cho pipeline Scan-to-Path.

    Vai trò:
        - Cập nhật TopStatusBar.
        - Cập nhật ProgressRuntimeBar.
        - Cập nhật Viewport3D.
        - Hiển thị QMessageBox.
        - Format text hiển thị.

    Không làm:
        - Không xử lý dữ liệu.
        - Không gọi trực tiếp service.
        - Không quyết định pipeline stage.
    """

    def __init__(self, window):
        self.window = window

    # -------------------------------------------------
    # Input source / Load scan
    # -------------------------------------------------
    def show_source_selection_cancelled(self):
        self.set_viewport_status(
            "Đã hủy thao tác chọn nguồn dữ liệu 3D."
        )

    def show_load_scan_cancelled(self):
        self.set_viewport_status(
            "Đã hủy thao tác nạp dữ liệu quét 3D."
        )

    def show_load_scan_result(self, result):
        point_count_text = self._format_int(result.point_count)

        self.set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("DỮ LIỆU QUÉT: ĐÃ NẠP", "success"),
            path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
        )

        self.runtime("set_progress", 10)
        self.runtime("set_eta", "Nạp dữ liệu quét")
        self.runtime("set_mode", "CHỜ XỬ LÝ")
        self.runtime("set_points", point_count_text)
        self.runtime("set_method", "IMPORT")
        self.runtime("set_output", "POINT CLOUD THÔ")

        viewport = self.viewport()

        if viewport is not None and hasattr(viewport, "show_point_cloud"):
            viewport.show_point_cloud(
                result.point_cloud,
                title="POINT CLOUD THÔ",
                status=(
                    f"Đã nạp {result.file_name} | "
                    f"{point_count_text} điểm"
                ),
                max_points=120_000,
                point_size=0.006,
            )
        else:
            self.set_viewport_status(
                "Viewport hiện tại chưa hỗ trợ hiển thị 3D.\n\n"
                "Cần cập nhật ui/panels/viewport_3d.py để có hàm show_point_cloud()."
            )

    def show_load_scan_error(self, exc: Exception):
        self.set_top_status(
            system=("HỆ THỐNG: LỖI", "danger"),
            scan=("DỮ LIỆU QUÉT: LỖI", "danger"),
            path=("ĐƯỜNG DẪN: CHỜ", "muted"),
        )

        self.runtime("set_progress", 0)
        self.runtime("set_eta", "Lỗi nạp dữ liệu")
        self.runtime("set_mode", "LỖI")
        self.runtime("set_output", "THẤT BẠI")

        self.set_viewport_status(
            "Không thể nạp dữ liệu quét 3D.\n\n"
            f"Lỗi: {exc}"
        )

        QMessageBox.critical(
            self.window,
            "Lỗi nạp dữ liệu quét",
            f"Không thể nạp file quét 3D:\n\n{exc}",
        )

    # -------------------------------------------------
    # Camera mock
    # -------------------------------------------------
    def show_handheld_camera_mock(self, result):
        self.set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("CAMERA: HANDHELD MOCK", "warning"),
            path=("ĐƯỜNG DẪN: CHỜ DỮ LIỆU", "muted"),
        )

        self.runtime("set_progress", 5)
        self.runtime("set_eta", "Camera cầm tay mock")
        self.runtime("set_mode", "HANDHELD MOCK")
        self.runtime("set_points", "--")
        self.runtime("set_method", "RGB-D HANDHELD")
        self.runtime("set_output", "CHƯA CÓ POINT CLOUD")

        self.set_viewport_status(
            "CHẾ ĐỘ CAMERA CẦM TAY ĐÃ SẴN SÀNG\n\n"
            "Mục tiêu của mode này:\n"
            "- Người dùng cầm camera quét quanh vật thể hoặc người.\n"
            "- Hệ thống thu nhiều frame RGB-D.\n"
            "- Sau này các frame sẽ được ghép thành point cloud hoàn chỉnh.\n\n"
            "Trạng thái hiện tại:\n"
            f"- {result.message}\n\n"
            "Pipeline xử lý 3D hiện tại vẫn dùng nguồn FILE point cloud."
        )

        QMessageBox.information(
            self.window,
            "Camera cầm tay",
            (
                "Mode camera cầm tay đã sẵn sàng.\n\n"
                "Hiện tại đây là mock workflow, chưa tạo point cloud thật.\n"
                "Pipeline 3D vẫn cần nạp file point cloud để xử lý."
            ),
        )

    def show_handheld_camera_error(self, exc: Exception):
        self.set_top_status(
            system=("HỆ THỐNG: LỖI", "danger"),
            scan=("CAMERA HANDHELD: LỖI", "danger"),
            path=("ĐƯỜNG DẪN: CHỜ", "muted"),
        )

        self.runtime("set_mode", "LỖI")
        self.runtime("set_output", "THẤT BẠI")

        QMessageBox.critical(
            self.window,
            "Lỗi camera cầm tay",
            f"Không thể chạy mock camera cầm tay:\n\n{exc}",
        )

    def show_turntable_camera_mock(self, result):
        self.set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("CAMERA: TURNTABLE MOCK", "warning"),
            path=("ĐƯỜNG DẪN: CHỜ DỮ LIỆU", "muted"),
        )

        self.runtime("set_progress", 5)
        self.runtime("set_eta", "Bàn xoay Stop-and-Go mock")
        self.runtime("set_mode", "TURNTABLE MOCK")
        self.runtime("set_points", "--")
        self.runtime("set_method", "STOP-AND-GO")
        self.runtime("set_output", "CHƯA CÓ POINT CLOUD")

        self.set_viewport_status(
            "CHẾ ĐỘ BÀN XOAY STOP-AND-GO ĐÃ SẴN SÀNG\n\n"
            "Mục tiêu của mode này:\n"
            "- Camera được đặt cố định.\n"
            "- Arduino điều khiển bàn xoay từng góc.\n"
            "- Sau khi bàn xoay dừng, camera chụp RGB-D.\n"
            "- Các frame nhiều góc sẽ được ghép thành point cloud.\n\n"
            "Trạng thái hiện tại:\n"
            f"- {result.message}\n\n"
            "Pipeline xử lý 3D hiện tại vẫn dùng nguồn FILE point cloud."
        )

        QMessageBox.information(
            self.window,
            "Bàn xoay Stop-and-Go",
            (
                "Mode bàn xoay Stop-and-Go đã sẵn sàng.\n\n"
                "Hiện tại đây là mock workflow, chưa nối Arduino/camera thật.\n"
                "Pipeline 3D vẫn cần nạp file point cloud để xử lý."
            ),
        )

    def show_turntable_camera_error(self, exc: Exception):
        self.set_top_status(
            system=("HỆ THỐNG: LỖI", "danger"),
            scan=("TURNTABLE: LỖI", "danger"),
            path=("ĐƯỜNG DẪN: CHỜ", "muted"),
        )

        self.runtime("set_mode", "LỖI")
        self.runtime("set_output", "THẤT BẠI")

        QMessageBox.critical(
            self.window,
            "Lỗi bàn xoay Stop-and-Go",
            f"Không thể chạy mock bàn xoay:\n\n{exc}",
        )

    # -------------------------------------------------
    # Placeholder
    # -------------------------------------------------
    def show_edge_ai_placeholder(self):
        self.set_top_status(
            system=("HỆ THỐNG: ĐANG XỬ LÝ", "warning"),
            scan=("EDGE AI: ĐANG TÁCH VẬT THỂ", "warning"),
            path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
        )

        self.runtime("set_progress", 20)
        self.runtime("set_eta", "Tách vật thể bằng Edge AI")
        self.runtime("set_mode", "ĐANG XỬ LÝ")
        self.runtime("set_method", "EDGE AI / ROI")
        self.runtime("set_output", "MASK")

        self.set_viewport_status(
            "Đang tách vật thể khỏi nền bằng Edge AI / ROI mask.\n\n"
            "Kết quả mong muốn: vùng vật thể được giữ lại, nền và bàn xoay được loại bỏ."
        )

    def show_build_pointcloud_placeholder(self):
        self.set_top_status(
            system=("HỆ THỐNG: ĐANG XỬ LÝ", "warning"),
            scan=("POINT CLOUD: ĐANG TẠO", "warning"),
            path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
        )

        self.runtime("set_progress", 30)
        self.runtime("set_eta", "Tạo đám mây điểm")
        self.runtime("set_mode", "ĐANG XỬ LÝ")
        self.runtime("set_method", "RGB-D → POINT CLOUD")
        self.runtime("set_output", "POINT CLOUD THÔ")

        self.set_viewport_status(
            "Đang tạo đám mây điểm 3D của riêng vật thể.\n\n"
            "Dữ liệu đầu ra gồm các điểm không gian X, Y, Z."
        )

    def show_contour_placeholder(self):
        self.set_top_status(
            system=("HỆ THỐNG: ĐANG XỬ LÝ", "warning"),
            scan=("BỀ MẶT 3D: SẴN SÀNG", "success"),
            path=("CONTOUR: CHƯA BUILD", "warning"),
        )

        self.runtime("set_progress", 92)
        self.runtime("set_eta", "Sinh đường Contour")
        self.runtime("set_mode", "CHƯA BUILD")
        self.runtime("set_method", "CONTOUR")
        self.runtime("set_output", "CHƯA HỖ TRỢ")

        self.set_viewport_status(
            "CHỨC NĂNG CONTOUR PATH CHƯA ĐƯỢC BUILD\n\n"
            "Nút này được giữ lại trong pipeline để phát triển sau.\n\n"
            "Hiện tại chức năng đã hoàn thiện là:\n"
            "- Surface Mesh\n"
            "- Zigzag Path\n"
            "- Export kết quả"
        )

        QMessageBox.information(
            self.window,
            "Contour Path",
            "Chức năng Contour Path đang để dành cho giai đoạn build sau.",
        )

    # -------------------------------------------------
    # Filter
    # -------------------------------------------------
    def show_filter_result(self, result):
        input_text = self._format_int(result.input_point_count)
        output_text = self._format_int(result.output_point_count)
        removed_text = self._format_int(result.removed_point_count)

        self.set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("POINT CLOUD: ĐÃ LỌC NHIỄU", "success"),
            path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
        )

        self.runtime("set_progress", 45)
        self.runtime("set_eta", "Lọc nhiễu đám mây điểm")
        self.runtime("set_mode", "ĐÃ XỬ LÝ")
        self.runtime("set_points", output_text)
        self.runtime("set_method", "VOXEL / OUTLIER")
        self.runtime("set_output", "POINT CLOUD SẠCH")

        viewport = self.viewport()

        if viewport is not None and hasattr(viewport, "show_point_cloud"):
            viewport.show_point_cloud(
                result.output_cloud,
                title="POINT CLOUD SAU LỌC",
                status=(
                    f"Đã lọc point cloud | "
                    f"{input_text} → {output_text} điểm | "
                    f"Loại bỏ {removed_text} điểm"
                ),
                max_points=120_000,
                point_size=0.006,
            )
        else:
            self.set_viewport_status(
                "Viewport hiện tại chưa hỗ trợ hiển thị 3D."
            )

    def show_filter_error(self, exc: Exception):
        self.set_top_status(
            system=("HỆ THỐNG: LỖI", "danger"),
            scan=("POINT CLOUD: LỖI LỌC", "danger"),
            path=("ĐƯỜNG DẪN: CHỜ", "muted"),
        )

        self.runtime("set_progress", 30)
        self.runtime("set_eta", "Lỗi lọc point cloud")
        self.runtime("set_mode", "LỖI")
        self.runtime("set_output", "THẤT BẠI")

        self.set_viewport_status(
            "Không thể lọc nhiễu point cloud.\n\n"
            f"Lỗi: {exc}"
        )

        QMessageBox.critical(
            self.window,
            "Lỗi lọc point cloud",
            f"Không thể lọc nhiễu point cloud:\n\n{exc}",
        )

    # -------------------------------------------------
    # Normals
    # -------------------------------------------------
    def show_normal_result(self, result, source_name: str):
        point_text = self._format_int(result.point_count)
        radius_text = f"{result.search_radius:.4f}"

        self.set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("PHÁP TUYẾN: ĐÃ TÍNH", "success"),
            path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
        )

        self.runtime("set_progress", 72)
        self.runtime("set_eta", "Tính pháp tuyến bề mặt")
        self.runtime("set_mode", "ĐÃ XỬ LÝ")
        self.runtime("set_points", point_text)
        self.runtime("set_method", "KD-TREE / PCA")
        self.runtime("set_output", "NORMAL FIELD")

        viewport = self.viewport()

        if viewport is not None and hasattr(viewport, "show_point_cloud"):
            viewport.show_point_cloud(
                result.output_cloud,
                title="POINT CLOUD CÓ PHÁP TUYẾN",
                status=(
                    f"Đã tính pháp tuyến | "
                    f"{point_text} điểm | "
                    f"R = {radius_text}"
                ),
                max_points=120_000,
                point_size=0.006,
            )

        if viewport is not None and hasattr(viewport, "show_normals"):
            viewport.show_normals(
                result.output_cloud,
                max_normals=1500,
                length=0.02,
            )

        QMessageBox.information(
            self.window,
            "Tính pháp tuyến hoàn tất",
            (
                "Đã tính pháp tuyến bề mặt thành công.\n\n"
                f"Nguồn dữ liệu: {source_name}\n"
                f"Số điểm: {point_text}\n"
                f"Bán kính tìm kiếm: {radius_text}\n"
                f"Max NN: {result.max_nn}\n\n"
                "Bước tiếp theo: tạo bản đồ bề mặt 3D."
            ),
        )

    def show_normal_error(self, exc: Exception):
        self.set_top_status(
            system=("HỆ THỐNG: LỖI", "danger"),
            scan=("PHÁP TUYẾN: LỖI", "danger"),
            path=("ĐƯỜNG DẪN: CHỜ", "muted"),
        )

        self.runtime("set_progress", 60)
        self.runtime("set_eta", "Lỗi tính pháp tuyến")
        self.runtime("set_mode", "LỖI")
        self.runtime("set_output", "THẤT BẠI")

        self.set_viewport_status(
            "Không thể tính pháp tuyến bề mặt.\n\n"
            f"Lỗi: {exc}"
        )

        QMessageBox.critical(
            self.window,
            "Lỗi tính pháp tuyến",
            f"Không thể tính pháp tuyến bề mặt:\n\n{exc}",
        )

    # -------------------------------------------------
    # Surface
    # -------------------------------------------------
    def show_surface_building(self):
        self.set_top_status(
            system=("HỆ THỐNG: ĐANG XỬ LÝ", "warning"),
            scan=("BỀ MẶT 3D: ĐANG TẠO", "warning"),
            path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
        )

        self.runtime("set_progress", 60)
        self.runtime("set_eta", "Tạo bản đồ bề mặt 3D")
        self.runtime("set_mode", "ĐANG XỬ LÝ")
        self.runtime("set_method", "SURFACE RECON")
        self.runtime("set_output", "ĐANG TẠO MESH")

    def show_surface_result(self, result, normal_cloud=None):
        vertex_text = self._format_int(result.vertex_count)
        triangle_text = self._format_int(result.triangle_count)

        self.set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("BỀ MẶT 3D: SẴN SÀNG", "success"),
            path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
        )

        self.runtime("set_progress", 80)
        self.runtime("set_eta", "Đã tạo bản đồ bề mặt 3D")
        self.runtime("set_mode", "ĐÃ XỬ LÝ")
        self.runtime("set_points", vertex_text)
        self.runtime("set_method", result.method.upper())
        self.runtime("set_output", "SURFACE MESH")

        viewport = self.viewport()

        if viewport is not None and hasattr(viewport, "show_mesh"):
            viewport.show_mesh(
                result.mesh,
                title="BẢN ĐỒ BỀ MẶT 3D",
                status=(
                    f"Đã tạo surface mesh | "
                    f"{vertex_text} đỉnh | "
                    f"{triangle_text} mặt tam giác"
                ),
                color=(0.55, 0.60, 0.62, 0.16),
                draw_edges=True,
            )

        elif (
            normal_cloud is not None
            and viewport is not None
            and hasattr(viewport, "show_point_cloud")
        ):
            viewport.show_point_cloud(
                normal_cloud,
                title="BẢN ĐỒ BỀ MẶT 3D",
                status=(
                    f"Đã tạo surface map | "
                    f"{vertex_text} đỉnh | "
                    f"{triangle_text} mặt tam giác"
                ),
                max_points=120_000,
                point_size=0.006,
            )

        QMessageBox.information(
            self.window,
            "Tạo bản đồ bề mặt 3D hoàn tất",
            (
                "Đã tạo bản đồ bề mặt 3D thành công.\n\n"
                f"Phương pháp: {result.method}\n"
                f"Số đỉnh: {vertex_text}\n"
                f"Số mặt tam giác: {triangle_text}\n\n"
                "Bước tiếp theo: sinh đường Zigzag."
            ),
        )

    def show_surface_error(self, exc: Exception):
        self.set_top_status(
            system=("HỆ THỐNG: LỖI", "danger"),
            scan=("BỀ MẶT 3D: LỖI", "danger"),
            path=("ĐƯỜNG DẪN: CHỜ", "muted"),
        )

        self.runtime("set_progress", 60)
        self.runtime("set_eta", "Lỗi tạo bản đồ bề mặt")
        self.runtime("set_mode", "LỖI")
        self.runtime("set_output", "THẤT BẠI")

        self.set_viewport_status(
            "Không thể tạo bản đồ bề mặt 3D.\n\n"
            f"Lỗi: {exc}"
        )

        QMessageBox.critical(
            self.window,
            "Lỗi tạo bản đồ bề mặt 3D",
            f"Không thể tạo bản đồ bề mặt 3D:\n\n{exc}",
        )

    # -------------------------------------------------
    # Zigzag
    # -------------------------------------------------
    def show_zigzag_result(self, result):
        path_count_text = self._format_int(result.path_count)
        line_count_text = self._format_int(result.line_count)
        segment_count_text = self._format_int(result.segment_count)
        length_text = f"{result.path_length:.3f}"

        self.set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("BỀ MẶT 3D: SẴN SÀNG", "success"),
            path=("ZIGZAG: ĐÃ SINH", "success"),
        )

        self.runtime("set_progress", 85)
        self.runtime("set_eta", "Sinh đường Zigzag")
        self.runtime("set_mode", "ĐÃ XỬ LÝ")
        self.runtime("set_points", path_count_text)
        self.runtime("set_method", result.method.upper())
        self.runtime("set_output", "ZIGZAG PATH")

        path_segments_for_display = (
            result.display_path_segments
            if hasattr(result, "display_path_segments")
            else result.path_segments
        )

        path_normals_for_display = (
            None
            if hasattr(result, "display_path_segments")
            else result.normal_segments
        )

        zigzag_status = (
            f"Zigzag: {path_count_text} điểm | "
            f"{line_count_text} dải quét | "
            f"{segment_count_text} đoạn | "
            f"L = {length_text}"
        )

        viewport = self.viewport()

        if viewport is not None and hasattr(viewport, "show_mesh_with_path"):
            viewport.show_mesh_with_path(
                result.source_mesh,
                path_segments_for_display,
                path_normals=path_normals_for_display,
                title="BẢN ĐỒ BỀ MẶT 3D + ZIGZAG",
                status=zigzag_status,
                mesh_color=(0.45, 0.48, 0.50, 0.12),
                path_color=(1.0, 0.92, 0.0, 1.0),
                path_width=6.0,
                lift_offset_ratio=0.018,
            )

        else:
            if viewport is not None and hasattr(viewport, "show_mesh"):
                viewport.show_mesh(
                    result.source_mesh,
                    title="BẢN ĐỒ BỀ MẶT 3D + ZIGZAG",
                    status="Đã hiển thị surface mesh dùng để sinh Zigzag",
                    color=(0.45, 0.48, 0.50, 0.12),
                    draw_edges=True,
                )

            if viewport is not None and hasattr(viewport, "show_path"):
                viewport.show_path(
                    path_segments_for_display,
                    path_normals=path_normals_for_display,
                    title="ĐƯỜNG DẪN ZIGZAG",
                    status=zigzag_status,
                    width=6.0,
                    color=(1.0, 0.92, 0.0, 1.0),
                    lift_offset_ratio=0.0
                    if hasattr(result, "display_path_segments")
                    else 0.018,
                    path_only=False,
                )

        QMessageBox.information(
            self.window,
            "Sinh đường Zigzag hoàn tất",
            (
                "Đã sinh đường Zigzag từ surface mesh thành công.\n\n"
                f"Số điểm path: {path_count_text}\n"
                f"Số dải quét: {line_count_text}\n"
                f"Số đoạn path: {segment_count_text}\n"
                f"Chiều dài xấp xỉ: {length_text}\n"
                f"Khoảng cách dải quét: {result.path_spacing:.4f}\n"
                f"Khoảng cách lấy mẫu: {result.point_step:.4f}\n\n"
                "Mỗi điểm path gồm: x, y, z, nx, ny, nz."
            ),
        )

    def show_zigzag_error(self, exc: Exception):
        self.set_top_status(
            system=("HỆ THỐNG: LỖI", "danger"),
            scan=("BỀ MẶT 3D: SẴN SÀNG", "warning"),
            path=("ZIGZAG: LỖI", "danger"),
        )

        self.runtime("set_progress", 72)
        self.runtime("set_eta", "Lỗi sinh Zigzag")
        self.runtime("set_mode", "LỖI")
        self.runtime("set_output", "THẤT BẠI")

        self.set_viewport_status(
            "Không thể sinh đường Zigzag.\n\n"
            f"Lỗi: {exc}"
        )

        QMessageBox.critical(
            self.window,
            "Lỗi sinh đường Zigzag",
            f"Không thể sinh đường Zigzag:\n\n{exc}",
        )

    # -------------------------------------------------
    # Export
    # -------------------------------------------------
    def show_export_result(self, export_result):
        self.set_top_status(
            system=("HỆ THỐNG: HOÀN TẤT", "success"),
            scan=("BẢN ĐỒ 3D: ĐÃ XUẤT", "success"),
            path=("ZIGZAG: ĐÃ XUẤT", "success"),
        )

        self.runtime("set_progress", 100)
        self.runtime("set_eta", "Đã xuất kết quả")
        self.runtime("set_mode", "HOÀN TẤT")
        self.runtime("set_output", "ĐÃ XUẤT")

        self.set_viewport_status(
            "ĐÃ XUẤT KẾT QUẢ THÀNH CÔNG\n\n"
            f"Mã export:\n{export_result.export_id}\n\n"
            f"Thư mục:\n{export_result.export_dir}\n\n"
            "Danh sách file:\n"
            "- 00_summary.txt\n"
            "- 00_summary.json\n"
            "- 01_surface_mesh.ply\n"
            "- 02_zigzag_path.csv"
        )

        QMessageBox.information(
            self.window,
            "Xuất kết quả hoàn tất",
            (
                "Đã xuất kết quả pipeline thành công.\n\n"
                f"Mã export:\n{export_result.export_id}\n\n"
                f"Thư mục:\n{export_result.export_dir}\n\n"
                "Bao gồm:\n"
                "- 00_summary.txt\n"
                "- 00_summary.json\n"
                "- 01_surface_mesh.ply\n"
                "- 02_zigzag_path.csv"
            ),
        )

    def show_export_error(self, exc: Exception):
        self.set_top_status(
            system=("HỆ THỐNG: LỖI", "danger"),
            scan=("XUẤT FILE: LỖI", "danger"),
            path=("ZIGZAG: CHƯA XUẤT", "warning"),
        )

        self.runtime("set_eta", "Lỗi xuất kết quả")
        self.runtime("set_mode", "LỖI")
        self.runtime("set_output", "THẤT BẠI")

        QMessageBox.critical(
            self.window,
            "Lỗi xuất kết quả",
            f"Không thể xuất kết quả:\n\n{exc}",
        )

    # -------------------------------------------------
    # General
    # -------------------------------------------------
    def show_unknown_action(self, action: str):
        print(f"[UI WARNING] Unknown action: {action}")
        self.set_viewport_status(
            f"Không nhận diện được thao tác: {action}"
        )

    # -------------------------------------------------
    # UI helpers
    # -------------------------------------------------
    def viewport(self):
        return getattr(self.window, "viewport", None)

    def runtime_bar(self):
        return getattr(self.window, "runtime_bar", None)

    def top_bar(self):
        return getattr(self.window, "top_bar", None)

    def runtime(self, method_name: str, *args, **kwargs):
        runtime_bar = self.runtime_bar()

        if runtime_bar is None:
            return None

        method = getattr(runtime_bar, method_name, None)

        if callable(method):
            return method(*args, **kwargs)

        return None

    def set_top_status(self, system=None, scan=None, path=None):
        top_bar = self.top_bar()

        if top_bar is None:
            return

        if system:
            method = getattr(top_bar, "set_machine_status", None)
            if callable(method):
                method(system[0], system[1])

        if scan:
            method = getattr(top_bar, "set_camera_status", None)
            if callable(method):
                method(scan[0], scan[1])

        if path:
            method = getattr(top_bar, "set_robot_status", None)
            if callable(method):
                method(path[0], path[1])

    def set_viewport_status(self, message: str):
        viewport = self.viewport()

        if viewport is None:
            print(message)
            return

        possible_methods = [
            "set_viewport_status",
            "set_status",
            "set_message",
            "show_message",
            "show_placeholder",
        ]

        for method_name in possible_methods:
            method = getattr(viewport, method_name, None)

            if callable(method):
                method(message)
                return

        print(f"[VIEWPORT] {message}")

    def _format_int(self, value) -> str:
        try:
            return f"{int(value):,}".replace(",", ".")
        except Exception:
            return str(value)