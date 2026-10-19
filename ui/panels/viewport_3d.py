from __future__ import annotations

import numpy as np

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QWidget,
)

from ui.styles.theme import theme

try:
    import pyqtgraph.opengl as gl
    from pyqtgraph import Vector
except Exception:
    gl = None
    Vector = None


class Viewport3D(QFrame):
    """
    Viewport 3D cho hệ thống Scan-to-Path.

    Chức năng:
        - Hiển thị màn hình chờ khi chưa có dữ liệu.
        - Hiển thị point cloud.
        - Hiển thị vector pháp tuyến.
        - Hiển thị đường Zigzag / Contour.
        - Hiển thị mesh / surface map.
        - Normalize dữ liệu riêng cho mục đích hiển thị.

    Lưu ý:
        Dữ liệu gốc không bị thay đổi.
        Việc scale / đưa về tâm chỉ áp dụng cho viewport.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.point_item = None
        self.normal_item = None
        self.path_item = None
        self.mesh_item = None

        # View transform
        self._last_view_center = None
        self._last_view_scale = 1.0
        self._last_view_factor = 1.2

        # Cache point cloud
        self._cached_points = None
        self._cached_colors = None
        self._cached_point_size = 0.006

        # Cache normals
        self._cached_normal_lines = None
        self._cached_normal_width = 1.5

        # Cache path
        self._cached_path_points = None
        self._cached_path_width = 5.0
        self._cached_path_color = (1.0, 0.92, 0.0, 1.0)

        # Cache mesh
        self._cached_mesh_vertices = None
        self._cached_mesh_faces = None
        self._cached_mesh_color = (0.55, 0.60, 0.62, 0.18)
        self._cached_mesh_draw_edges = True
        self._cached_mesh_edge_color = (0.90, 0.90, 0.90, 0.20)

        # Cache text
        self._cached_title = "POINT CLOUD 3D"
        self._cached_mode = "3D VIEW"
        self._cached_status = "ĐÃ HIỂN THỊ POINT CLOUD"

        self._build_ui()
        self._build_layout()
        self.show_ready_state()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("viewport_3d")
        self.setProperty("role", "card")

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.lbl_title = QLabel("KHUNG HIỂN THỊ 3D")
        self.lbl_title.setStyleSheet(
            f"""
            font-size: {theme.fonts.SIZE_LG}px;
            font-weight: 700;
            """
        )

        self.lbl_mode = QLabel("CHẾ ĐỘ: SẴN SÀNG")
        self.lbl_mode.setProperty("role", "muted")

        self.lbl_footer = QLabel("CHỜ DỮ LIỆU QUÉT 3D")
        self.lbl_footer.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.lbl_footer.setProperty("role", "dim")

        self._build_placeholder()
        self._build_gl_viewer()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.placeholder_widget)

        if self.gl_view is not None:
            self.stack.addWidget(self.gl_view)

    def _build_placeholder(self):
        self.placeholder_widget = QWidget()

        layout = QVBoxLayout(self.placeholder_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.lbl_content = QLabel("")
        self.lbl_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_content.setWordWrap(True)
        self.lbl_content.setStyleSheet(
            f"""
            font-size: {theme.fonts.SIZE_XL}px;
            font-weight: 600;
            """
        )

        layout.addStretch()
        layout.addWidget(self.lbl_content)
        layout.addStretch()

    def _build_gl_viewer(self):
        if gl is None:
            self.gl_view = None
            return

        self.gl_view = gl.GLViewWidget()
        self.gl_view.setBackgroundColor("#111214")

        self.gl_view.setCameraPosition(
            distance=2.2,
            elevation=20,
            azimuth=45,
        )

        self.grid_item = gl.GLGridItem()
        self.grid_item.setSize(x=1.4, y=1.4, z=1.4)
        self.grid_item.setSpacing(x=0.05, y=0.05, z=0.05)
        self.grid_item.translate(0, 0, -0.65)
        self.gl_view.addItem(self.grid_item)

        self.axis_item = gl.GLAxisItem()
        self.axis_item.setSize(x=0.35, y=0.35, z=0.35)
        self.gl_view.addItem(self.axis_item)

    def _build_layout(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            theme.spacing.MD,
            theme.spacing.MD,
            theme.spacing.MD,
            theme.spacing.MD,
        )
        root.setSpacing(theme.spacing.SM)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_mode)

        root.addLayout(header)
        root.addWidget(self.stack, 1)
        root.addWidget(self.lbl_footer)

    # -------------------------------------------------
    # Basic setters
    # -------------------------------------------------
    def set_title(self, text: str):
        self.lbl_title.setText(text)

    def set_mode(self, text: str):
        self.lbl_mode.setText(f"CHẾ ĐỘ: {text}")

    def set_status(self, text: str):
        self.lbl_footer.setText(text)

    def set_content(self, text: str):
        self.lbl_content.setText(text)

    def set_viewport_status(self, message: str):
        self.show_placeholder(message)

    def set_message(self, message: str):
        self.show_placeholder(message)

    def show_message(self, message: str):
        self.show_placeholder(message)

    def show_placeholder(self, message: str):
        if self.stack is not None:
            self.stack.setCurrentWidget(self.placeholder_widget)

        self.set_title("KHUNG HIỂN THỊ 3D")
        self.set_mode("THÔNG TIN")
        self.set_content(message)
        self.set_status("UI MESSAGE")

    # -------------------------------------------------
    # Main render APIs
    # -------------------------------------------------
    def show_point_cloud(
        self,
        point_cloud,
        title: str = "POINT CLOUD 3D",
        status: str = "ĐÃ HIỂN THỊ POINT CLOUD",
        max_points: int = 120_000,
        point_size: float = 0.006,
        clear_overlays: bool = True,
    ):
        """
        Hiển thị point cloud Open3D trong viewport.
        """

        if point_cloud is None or len(point_cloud.points) == 0:
            self.show_placeholder("Không có dữ liệu point cloud để hiển thị.")
            return

        if self.gl_view is None or gl is None:
            self.show_placeholder(
                "Không thể mở viewer 3D.\n\n"
                "Hãy kiểm tra thư viện pyqtgraph và PyOpenGL."
            )
            return

        points = np.asarray(point_cloud.points, dtype=np.float32)

        if points.ndim != 2 or points.shape[1] != 3:
            self.show_placeholder("Dữ liệu point cloud không hợp lệ.")
            return

        valid_mask = np.isfinite(points).all(axis=1)
        points = points[valid_mask]

        if len(points) == 0:
            self.show_placeholder("Point cloud không có điểm hợp lệ để hiển thị.")
            return

        original_count = len(points)

        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)

        center = (bounds_min + bounds_max) / 2.0
        size = bounds_max - bounds_min

        max_size = float(np.max(size))
        if max_size <= 0:
            max_size = 1.0

        self._last_view_center = center.astype(np.float32)
        self._last_view_scale = float(max_size)
        self._last_view_factor = 1.2

        points_view = self._to_view_points(points)

        if original_count > max_points:
            rng = np.random.default_rng(42)
            indices = rng.choice(
                original_count,
                size=max_points,
                replace=False,
            )
            points_display = points_view[indices]
        else:
            points_display = points_view

        points_display = np.ascontiguousarray(points_display, dtype=np.float32)
        colors_display = self._build_visible_colors(points_display)

        self._cached_points = points_display.copy()
        self._cached_colors = colors_display.copy()
        self._cached_point_size = float(point_size)

        if clear_overlays:
            self._cached_normal_lines = None
            self._cached_path_points = None
            self._cached_mesh_vertices = None
            self._cached_mesh_faces = None

        self._cached_title = title
        self._cached_mode = "3D VIEW"
        self._cached_status = (
            f"{status} | Hiển thị {len(points_display):,}/{original_count:,} điểm"
            .replace(",", ".")
        )

        self._render_cached_scene()
        self._fit_camera_normalized()

        self.stack.setCurrentWidget(self.gl_view)

        self.set_title(self._cached_title)
        self.set_mode(self._cached_mode)
        self.set_status(self._cached_status)

        print("[VIEWPORT] Point cloud rendered")
        print("[VIEWPORT] Original points:", original_count)
        print("[VIEWPORT] Display points:", len(points_display))
        print("[VIEWPORT] Bounds min:", bounds_min)
        print("[VIEWPORT] Bounds max:", bounds_max)
        print("[VIEWPORT] View min:", points_display.min(axis=0))
        print("[VIEWPORT] View max:", points_display.max(axis=0))

    def show_normals(
        self,
        point_cloud,
        max_normals: int = 1500,
        length: float = 0.04,
        width: float = 1.5,
    ):
        """
        Hiển thị vector pháp tuyến dưới dạng đoạn thẳng.
        """

        if self.gl_view is None or gl is None:
            return

        if point_cloud is None:
            return

        if not point_cloud.has_normals():
            self.set_status("Point cloud chưa có pháp tuyến để hiển thị.")
            return

        points = np.asarray(point_cloud.points, dtype=np.float32)
        normals = np.asarray(point_cloud.normals, dtype=np.float32)

        if len(points) == 0 or len(normals) == 0:
            return

        valid_mask = (
            np.isfinite(points).all(axis=1)
            & np.isfinite(normals).all(axis=1)
        )

        points = points[valid_mask]
        normals = normals[valid_mask]

        if len(points) == 0:
            return

        points_view = self._to_view_points(points)

        normal_norm = np.linalg.norm(normals, axis=1, keepdims=True)
        normal_norm[normal_norm == 0] = 1.0
        normals = normals / normal_norm

        count = len(points_view)

        if count > max_normals:
            rng = np.random.default_rng(7)
            indices = rng.choice(
                count,
                size=max_normals,
                replace=False,
            )
            points_view = points_view[indices]
            normals = normals[indices]

        starts = points_view
        ends = points_view + normals * length

        line_points = np.empty(
            (len(starts) * 2, 3),
            dtype=np.float32,
        )
        line_points[0::2] = starts
        line_points[1::2] = ends

        self._cached_normal_lines = np.ascontiguousarray(line_points, dtype=np.float32)
        self._cached_normal_width = float(width)

        self._render_cached_scene()

        self.set_title("POINT CLOUD CÓ PHÁP TUYẾN")
        self.set_mode("NORMAL VIEW")
        self.set_status(
            f"Đã hiển thị {len(starts):,} vector pháp tuyến".replace(",", ".")
        )

    def show_mesh(
        self,
        mesh,
        title: str = "BẢN ĐỒ BỀ MẶT 3D",
        status: str = "ĐÃ HIỂN THỊ SURFACE MESH",
        color=(0.55, 0.60, 0.62, 0.18),
        draw_edges: bool = True,
        edge_color=(0.90, 0.90, 0.90, 0.20),
    ):
        """
        Hiển thị TriangleMesh Open3D trong viewport.

        Quan trọng:
            Khi chuyển sang surface mesh, phải xóa point cloud,
            normal vector và path cũ để viewport không bị rối.
        """

        if self.gl_view is None or gl is None:
            return

        if mesh is None or len(mesh.vertices) == 0 or len(mesh.triangles) == 0:
            self.set_status("Mesh không hợp lệ hoặc rỗng.")
            return

        vertices = np.asarray(mesh.vertices, dtype=np.float32)
        faces = np.asarray(mesh.triangles, dtype=np.int32)

        valid_mask = np.isfinite(vertices).all(axis=1)
        if not valid_mask.all():
            self.set_status("Mesh có vertex lỗi NaN/Inf.")
            return

        bounds_min = vertices.min(axis=0)
        bounds_max = vertices.max(axis=0)

        center = (bounds_min + bounds_max) / 2.0
        size = bounds_max - bounds_min

        max_size = float(np.max(size))
        if max_size <= 0:
            max_size = 1.0

        self._last_view_center = center.astype(np.float32)
        self._last_view_scale = float(max_size)
        self._last_view_factor = 1.2

        vertices_view = self._to_view_points(vertices)

        # -----------------------------
        # XÓA TẤT CẢ OVERLAY CŨ
        # -----------------------------
        self._cached_points = None
        self._cached_colors = None
        self._cached_normal_lines = None
        self._cached_path_points = None

        # -----------------------------
        # CACHE MESH MỚI
        # -----------------------------
        self._cached_mesh_vertices = np.ascontiguousarray(
            vertices_view,
            dtype=np.float32,
        )
        self._cached_mesh_faces = np.ascontiguousarray(
            faces,
            dtype=np.int32,
        )
        self._cached_mesh_color = color
        self._cached_mesh_draw_edges = draw_edges
        self._cached_mesh_edge_color = edge_color

        self._cached_title = title
        self._cached_mode = "SURFACE VIEW"
        self._cached_status = status

        self._render_cached_scene()
        self._fit_camera_normalized()

        self.stack.setCurrentWidget(self.gl_view)

        self.set_title(title)
        self.set_mode("SURFACE VIEW")
        self.set_status(status)

    def show_mesh_with_path(
        self,
        mesh,
        path_segments,
        path_normals=None,
        title: str = "BẢN ĐỒ BỀ MẶT 3D + ĐƯỜNG DẪN",
        status: str = "ĐÃ HIỂN THỊ MESH + PATH",
        mesh_color=(0.45, 0.48, 0.50, 0.12),
        path_color=(1.0, 0.92, 0.0, 1.0),
        path_width: float = 6.0,
        lift_offset_ratio: float = 0.018,
    ):
        """
        Chế độ trình chiếu:
            - Xóa point cloud và normal vector cũ.
            - Hiển thị mesh mờ.
            - Hiển thị đường path nổi trên bề mặt.
        """

        if mesh is None:
            self.set_status("Không có mesh để hiển thị.")
            return

        # Hiển thị mesh trước, hàm show_mesh đã tự clear point cloud/normal/path cũ.
        self.show_mesh(
            mesh,
            title=title,
            status="Đã hiển thị surface mesh",
            color=mesh_color,
            draw_edges=True,
            edge_color=(0.90, 0.90, 0.90, 0.16),
        )

        # Sau đó vẽ path lên mesh.
        self.show_path(
            path_segments,
            path_normals=path_normals,
            title=title,
            status=status,
            width=path_width,
            color=path_color,
            lift_offset_ratio=lift_offset_ratio,
            path_only=False,
        )

    def show_path_only(
        self,
        path_segments,
        path_normals=None,
        title: str = "ĐƯỜNG DẪN ZIGZAG",
        status: str = "CHỈ HIỂN THỊ ĐƯỜNG DẪN",
        path_color=(1.0, 0.92, 0.0, 1.0),
        path_width: float = 6.0,
    ):
        """
        Chỉ hiển thị đường dẫn, không hiển thị mesh/point cloud/normal.
        Dùng để thuyết trình cho rõ ý nghĩa path.
        """

        self.show_path(
            path_segments,
            path_normals=path_normals,
            title=title,
            status=status,
            width=path_width,
            color=path_color,
            lift_offset_ratio=0.0,
            path_only=True,
        )

    def show_path(
        self,
        path_points,
        path_normals=None,
        title: str = "ĐƯỜNG DẪN ZIGZAG",
        status: str = "ĐÃ HIỂN THỊ ĐƯỜNG DẪN",
        width: float = 5.0,
        color=(1.0, 0.92, 0.0, 1.0),
        lift_offset: float = 0.0,
        lift_offset_ratio: float = 0.015,
        path_only: bool = False,
    ):
        """
        Hiển thị đường dẫn 3D.

        path_points:
            - np.ndarray shape (N, 3)
            - hoặc list[np.ndarray], mỗi phần tử là một segment.

        path_normals:
            - None
            - hoặc list[np.ndarray] tương ứng với path_segments.

        lift_offset_ratio:
            Tỷ lệ nâng path khỏi bề mặt theo normal.
            Ví dụ 0.015 nghĩa là nâng lên khoảng 1.5% kích thước lớn nhất của vật.
        """

        if self.gl_view is None or gl is None:
            return

        if path_points is None:
            self.set_status("Không có dữ liệu đường dẫn để hiển thị.")
            return

        if lift_offset <= 0:
            lift_offset = float(self._last_view_scale) * float(lift_offset_ratio)

        display_segments = []

        # -------------------------------------------------
        # Case 1: path_points là list segment
        # -------------------------------------------------
        if isinstance(path_points, list):
            normals_list = path_normals if isinstance(path_normals, list) else None

            for idx, segment in enumerate(path_points):
                seg = np.asarray(segment, dtype=np.float32)

                if seg.ndim != 2 or seg.shape[1] != 3:
                    continue

                valid_mask = np.isfinite(seg).all(axis=1)
                seg = seg[valid_mask]

                if len(seg) < 2:
                    continue

                # Nếu có normal thì nâng path theo normal gốc
                if normals_list is not None and idx < len(normals_list):
                    nrm = np.asarray(normals_list[idx], dtype=np.float32)

                    if nrm.ndim == 2 and nrm.shape[1] == 3 and len(nrm) == len(segment):
                        nrm = nrm[valid_mask]

                        if len(nrm) == len(seg):
                            nrm = self._normalize_vectors(nrm)
                            seg = seg + nrm * lift_offset

                seg_view = self._to_view_points(seg)

                # Nếu không có normal, nâng nhẹ theo Z của viewport để path vẫn nổi
                if normals_list is None:
                    seg_view[:, 2] += float(lift_offset_ratio)

                display_segments.append(
                    np.ascontiguousarray(seg_view, dtype=np.float32)
                )

        # -------------------------------------------------
        # Case 2: path_points là một mảng Nx3
        # -------------------------------------------------
        else:
            seg = np.asarray(path_points, dtype=np.float32)

            if seg.ndim != 2 or seg.shape[1] != 3:
                self.set_status("Dữ liệu path không hợp lệ.")
                return

            valid_mask = np.isfinite(seg).all(axis=1)
            seg = seg[valid_mask]

            if len(seg) < 2:
                self.set_status("Không đủ điểm path để hiển thị.")
                return

            if path_normals is not None:
                nrm = np.asarray(path_normals, dtype=np.float32)

                if nrm.ndim == 2 and nrm.shape[1] == 3 and len(nrm) == len(valid_mask):
                    nrm = nrm[valid_mask]

                    if len(nrm) == len(seg):
                        nrm = self._normalize_vectors(nrm)
                        seg = seg + nrm * lift_offset

            seg_view = self._to_view_points(seg)

            if path_normals is None:
                seg_view[:, 2] += float(lift_offset_ratio)

            display_segments.append(
                np.ascontiguousarray(seg_view, dtype=np.float32)
            )

        if not display_segments:
            self.set_status("Không có segment path hợp lệ.")
            return

        # Nếu muốn trình chiếu path riêng, tắt mesh/point cloud
        if path_only:
            self._cached_points = None
            self._cached_colors = None
            self._cached_mesh_vertices = None
            self._cached_mesh_faces = None
            self._cached_normal_lines = None

        self._cached_path_points = display_segments
        self._cached_path_width = float(width)
        self._cached_path_color = color

        self._cached_title = title
        self._cached_status = status

        self._render_cached_scene()

        self.stack.setCurrentWidget(self.gl_view)

        self.set_title(title)
        self.set_mode("PATH VIEW")
        self.set_status(status)

    # -------------------------------------------------
    # Cached render
    # -------------------------------------------------
    def _render_cached_scene(self):
        """
        Render toàn bộ scene:
            mesh -> point cloud -> normals -> path

        Path render cuối cùng để nổi lên trên.
        """

        if self.gl_view is None or gl is None:
            return

        self._clear_render_items()

        # -----------------------------
        # Mesh mờ
        # -----------------------------
        if self._cached_mesh_vertices is not None and self._cached_mesh_faces is not None:
            self.mesh_item = gl.GLMeshItem(
                vertexes=self._cached_mesh_vertices,
                faces=self._cached_mesh_faces,
                faceColor=self._cached_mesh_color,
                edgeColor=self._cached_mesh_edge_color,
                drawEdges=self._cached_mesh_draw_edges,
                smooth=False,
                shader="shaded",
            )

            try:
                self.mesh_item.setGLOptions("translucent")
            except Exception:
                pass

            self.gl_view.addItem(self.mesh_item)

        # -----------------------------
        # Point cloud nếu có
        # -----------------------------
        if self._cached_points is not None and self._cached_colors is not None:
            self.point_item = gl.GLScatterPlotItem(
                pos=self._cached_points,
                color=self._cached_colors,
                size=self._cached_point_size,
                pxMode=False,
            )

            try:
                self.point_item.setGLOptions("opaque")
            except Exception:
                pass

            self.gl_view.addItem(self.point_item)

        # -----------------------------
        # Normals nếu có
        # -----------------------------
        if getattr(self, "_cached_normal_lines", None) is not None:
            self.normal_item = gl.GLLinePlotItem(
                pos=self._cached_normal_lines,
                color=(1.0, 0.85, 0.05, 1.0),
                width=getattr(self, "_cached_normal_width", 1.5),
                antialias=True,
                mode="lines",
            )

            try:
                self.normal_item.setGLOptions("opaque")
            except Exception:
                pass

            self.gl_view.addItem(self.normal_item)

        # -----------------------------
        # Path nổi bật
        # -----------------------------
        if self._cached_path_points is not None:
            self.path_item = []

            for segment in self._cached_path_points:
                if segment is None or len(segment) < 2:
                    continue

                item = gl.GLLinePlotItem(
                    pos=segment,
                    color=self._cached_path_color,
                    width=self._cached_path_width,
                    antialias=True,
                    mode="line_strip",
                )

                # additive giúp line nổi hơn trên nền tối/mesh
                try:
                    item.setGLOptions("additive")
                except Exception:
                    try:
                        item.setGLOptions("translucent")
                    except Exception:
                        pass

                self.gl_view.addItem(item)
                self.path_item.append(item)

        self.gl_view.update()

    def refresh_point_cloud(self):
        """
        Vẽ lại scene từ cache nếu OpenGL redraw bị mất buffer.
        """

        if self.stack is None or self.gl_view is None:
            return

        has_any_cache = any(
            item is not None
            for item in (
                self._cached_points,
                self._cached_mesh_vertices,
                self._cached_normal_lines,
                self._cached_path_points,
            )
        )

        if not has_any_cache:
            return

        self._render_cached_scene()
        self._fit_camera_normalized()

        self.stack.setCurrentWidget(self.gl_view)

        self.set_title(self._cached_title)
        self.set_mode(self._cached_mode)
        self.set_status(self._cached_status)

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _build_visible_colors(self, points_display: np.ndarray):
        """
        Tạo màu sáng theo chiều cao Z.
        Không dùng màu gốc để tránh bị chìm trên nền đen.
        """

        count = len(points_display)
        rgba = np.zeros((count, 4), dtype=np.float32)

        z = points_display[:, 2]
        z_min = float(z.min())
        z_max = float(z.max())
        z_range = max(z_max - z_min, 1e-6)

        z_norm = (z - z_min) / z_range

        rgba[:, 0] = 0.10 + 0.85 * z_norm
        rgba[:, 1] = 0.80
        rgba[:, 2] = 1.00 - 0.35 * z_norm
        rgba[:, 3] = 1.00

        return rgba

    def _fit_camera_normalized(self):
        """
        Fit camera cho dữ liệu đã normalize quanh gốc.
        """

        if self.gl_view is None:
            return

        if Vector is not None:
            self.gl_view.opts["center"] = Vector(0.0, 0.0, 0.0)

        self.gl_view.setCameraPosition(
            distance=2.2,
            elevation=20,
            azimuth=45,
        )

        if self.grid_item is not None:
            try:
                self.grid_item.resetTransform()
            except Exception:
                pass

            self.grid_item.setSize(x=1.4, y=1.4, z=1.4)
            self.grid_item.setSpacing(x=0.05, y=0.05, z=0.05)

            try:
                self.grid_item.translate(0, 0, -0.65)
            except Exception:
                pass

    def _to_view_points(self, points: np.ndarray) -> np.ndarray:
        """
        Chuyển tọa độ gốc sang tọa độ hiển thị đã normalize.
        """

        points = np.asarray(points, dtype=np.float32)

        if self._last_view_center is None:
            bounds_min = points.min(axis=0)
            bounds_max = points.max(axis=0)

            center = (bounds_min + bounds_max) / 2.0
            size = bounds_max - bounds_min

            max_size = float(np.max(size))
            if max_size <= 0:
                max_size = 1.0

            self._last_view_center = center.astype(np.float32)
            self._last_view_scale = max_size
            self._last_view_factor = 1.2

        view_points = (points - self._last_view_center) / self._last_view_scale
        view_points = view_points * self._last_view_factor

        return np.ascontiguousarray(view_points, dtype=np.float32)

    def _clear_render_items(self):
        """
        Xóa item render khỏi OpenGL scene nhưng không xóa cache.
        Hỗ trợ path_item dạng list.
        """

        if self.gl_view is None:
            return

        for attr_name in (
            "mesh_item",
            "point_item",
            "normal_item",
            "path_item",
        ):
            item = getattr(self, attr_name, None)

            if isinstance(item, list):
                for sub_item in item:
                    try:
                        self.gl_view.removeItem(sub_item)
                    except Exception:
                        pass

            elif item is not None:
                try:
                    self.gl_view.removeItem(item)
                except Exception:
                    pass

            setattr(self, attr_name, None)

    def _clear_scene_cache(self):
        """
        Xóa toàn bộ cache scene.
        """

        self._cached_points = None
        self._cached_colors = None
        self._cached_normal_lines = None
        self._cached_path_points = None
        self._cached_mesh_vertices = None
        self._cached_mesh_faces = None

    def _clear_point_cloud(self):
        """
        Giữ tên cũ để tương thích.
        Xóa toàn bộ item render và cache scene.
        """

        if self.gl_view is None:
            return

        self._clear_render_items()

        self._cached_points = None
        self._cached_colors = None
        self._cached_normal_lines = None
        self._cached_mesh_vertices = None
        self._cached_mesh_faces = None
        self._cached_path_points = None

        self.gl_view.update()

    def _clear_normals(self):
        """
        Tên hàm cũ giữ lại để tương thích.
        Chỉ xóa normal item/cache.
        """

        if self.gl_view is not None and self.normal_item is not None:
            try:
                self.gl_view.removeItem(self.normal_item)
            except Exception:
                pass

        self.normal_item = None
        self._cached_normal_lines = None

    def _clear_path(self):
        """
        Chỉ xóa path item/cache.
        Hỗ trợ path_item dạng list.
        """

        if self.gl_view is not None and self.path_item is not None:
            if isinstance(self.path_item, list):
                for item in self.path_item:
                    try:
                        self.gl_view.removeItem(item)
                    except Exception:
                        pass
            else:
                try:
                    self.gl_view.removeItem(self.path_item)
                except Exception:
                    pass

        self.path_item = None
        self._cached_path_points = None

        if self.gl_view is not None:
            self.gl_view.update()

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        vectors = np.asarray(vectors, dtype=np.float32)

        if len(vectors) == 0:
            return vectors

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0

        return vectors / norms

    # -------------------------------------------------
    # Qt events
    # -------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)

        if self.stack is not None and self.gl_view is not None:
            if self.stack.currentWidget() == self.gl_view:
                QTimer.singleShot(80, self.refresh_point_cloud)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.stack is not None and self.gl_view is not None:
            if self.stack.currentWidget() == self.gl_view:
                QTimer.singleShot(80, self.refresh_point_cloud)

    # -------------------------------------------------
    # View states
    # -------------------------------------------------
    def show_ready_state(self):
        self.show_placeholder(
            "XEM TRƯỚC QUY TRÌNH SCAN-TO-PATH\n\n"
            "Dữ liệu quét | Point Cloud | Bản đồ bề mặt | Pháp tuyến | Zigzag | Contour"
        )
        self.set_status("CHỜ DỮ LIỆU QUÉT 3D")

    def show_scan_mode(self):
        self.set_title("DỮ LIỆU QUÉT 3D")
        self.set_mode("SCAN INPUT")
        self.set_status("DỮ LIỆU QUÉT ĐÃ NẠP")

    def show_clean_pointcloud_mode(self):
        self.set_title("POINT CLOUD SAU LỌC")
        self.set_mode("FILTERED")
        self.set_status("POINT CLOUD ĐÃ LỌC")

    def show_surface_map_mode(self):
        self.set_title("BẢN ĐỒ BỀ MẶT 3D")
        self.set_mode("SURFACE")
        self.set_status("BẢN ĐỒ BỀ MẶT SẴN SÀNG")

    def show_normal_mode(self):
        self.set_title("TRƯỜNG PHÁP TUYẾN")
        self.set_mode("NORMALS")
        self.set_status("PHÁP TUYẾN ĐÃ TÍNH")

    def show_zigzag_path_mode(self):
        self.set_title("ĐƯỜNG ZIGZAG")
        self.set_mode("SURFACE PATH")
        self.set_status("ZIGZAG ĐÃ SINH")

    def show_contour_path_mode(self):
        self.set_title("ĐƯỜNG CONTOUR")
        self.set_mode("SURFACE PATH")
        self.set_status("CONTOUR ĐÃ SINH")

    def show_export_mode(self):
        self.show_placeholder(
            "ĐÃ XUẤT KẾT QUẢ\n\n"
            "surface_map.ply\n"
            "normal_field.ply\n"
            "zigzag_path.csv\n"
            "contour_path.csv"
        )
        self.set_status("KẾT QUẢ ĐÃ XUẤT")

    # -------------------------------------------------
    # Backward-compatible methods
    # -------------------------------------------------
    def show_camera_mode(self):
        self.show_scan_mode()

    def show_mesh_mode(self):
        self.show_surface_map_mode()

    def show_path_mode(self):
        self.show_zigzag_path_mode()

    def show_simulation_mode(self):
        self.show_zigzag_path_mode()

    def clear_view(self):
        self._clear_render_items()
        self._clear_scene_cache()
        self.show_ready_state()