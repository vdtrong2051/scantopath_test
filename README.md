````md
# Scan-to-Path: 3D Surface Mapping and Path Generation System

## 1. Giới thiệu dự án

Dự án **Scan-to-Path** xây dựng một hệ thống phần mềm hỗ trợ số hóa sản phẩm thủ công mỹ nghệ không có bản vẽ CAD hoặc mô hình 3D sẵn có.

Hệ thống sử dụng dữ liệu quét 3D từ camera RGB-D, cụ thể là **Orbbec Astra Mini Pro**, để tạo đám mây điểm của vật thể. Sau đó phần mềm thực hiện các bước xử lý dữ liệu 3D gồm: lọc nhiễu, tái tạo/lập bản đồ bề mặt, ước lượng vector pháp tuyến và sinh đường dẫn bề mặt dạng **Zigzag** hoặc **Contour**.

Mục tiêu chính của hệ thống là:

```text
Vật thể thật
→ Quét 3D
→ Tạo point cloud
→ Lọc nhiễu
→ Tạo bản đồ bề mặt 3D
→ Tính pháp tuyến
→ Sinh đường dẫn Zigzag/Contour
→ Hiển thị và xuất kết quả
````

Dự án không tập trung vào điều khiển robot phun sơn thật, động học ngược hoàn chỉnh hoặc điều khiển lưu lượng sơn. Phần đường dẫn được xây dựng ở mức **mô phỏng hình học trên bề mặt 3D**, đóng vai trò dữ liệu đầu vào cho các bước robot hóa sau này.

---

## 2. Mục tiêu demo

Khi demo, hệ thống cần chứng minh được quy trình:

```text
Đặt vật mẫu / nạp dữ liệu quét
→ Tạo mô hình hoặc bản đồ bề mặt 3D của vật thể
→ Tính vector pháp tuyến bề mặt
→ Sinh đường dẫn Zigzag hoặc Contour phủ lên bề mặt
→ Hiển thị kết quả trên giao diện HMI
→ Xuất file kết quả
```

Kết quả đầu ra mong muốn:

```text
surface_model.ply
surface_map.ply
normal_field.ply
zigzag_path.csv
contour_path.csv
path_result.json
path_preview.png
```

---

## 3. Phạm vi hệ thống

### 3.1. Có thực hiện

* Nhập dữ liệu quét 3D từ file `.ply`, `.pcd`, `.xyz`.
* Hỗ trợ dữ liệu từ camera Orbbec Astra Mini Pro.
* Tạo và xử lý point cloud.
* Lọc nhiễu và giảm mật độ điểm.
* Tái tạo/lập bản đồ bề mặt 3D.
* Ước lượng vector pháp tuyến.
* Sinh đường dẫn Zigzag/Contour trên bề mặt.
* Gắn vector pháp tuyến vào từng điểm đường dẫn.
* Hiển thị dữ liệu 3D trên UI.
* Xuất kết quả ra file.

### 3.2. Chưa thực hiện trong phạm vi hiện tại

* Điều khiển robot phun sơn thật.
* Giải động học ngược đầy đủ cho robot 6 bậc tự do.
* Điều khiển van phun/lưu lượng sơn thật.
* Tối ưu va chạm robot công nghiệp.
* Tích hợp dây chuyền sản xuất hoàn chỉnh.

---

## 4. Công nghệ sử dụng

### 4.1. Ngôn ngữ

```text
Python 3.10.11 64-bit
```

### 4.2. Thư viện chính

```text
PyQt6          - Xây dựng giao diện HMI
Open3D         - Xử lý point cloud, mesh, normal, ICP
OpenCV         - Xử lý ảnh RGB/depth/mask
NumPy          - Tính toán ma trận, vector, tọa độ 3D
SciPy          - Nội suy, KD-Tree, xử lý hình học
Pandas         - Xuất dữ liệu đường dẫn CSV
ONNX Runtime   - Chạy mô hình Edge AI ở local
Trimesh        - Hỗ trợ xử lý mesh
Loguru         - Ghi log hệ thống
```

---

## 5. Phần cứng quét 3D

Camera chính:

```text
Orbbec Astra Mini Pro
```

Trong giai đoạn đầu, hệ thống ưu tiên cách làm ổn định:

```text
Orbbec Viewer / Orbbec SDK
→ Quét vật thể
→ Xuất file .ply hoặc .pcd
→ Phần mềm Scan-to-Path import file và xử lý
```

Sau khi pipeline xử lý 3D ổn định, có thể mở rộng sang chế độ capture trực tiếp từ camera bằng Orbbec SDK/Python wrapper.

---

## 6. Kiến trúc thư mục

```text
scan_to_path/
├── main.py
├── requirements.txt
├── README.md
│
├── app/
│   ├── config.py
│   ├── paths.py
│   └── logger.py
│
├── ui/
│   ├── main_window.py
│   ├── panels/
│   │   ├── viewport_3d.py
│   │   ├── right_action_panel.py
│   │   ├── top_status_bar.py
│   │   └── progress_runtime_bar.py
│   ├── dialogs/
│   ├── widgets/
│   └── styles/
│
├── modules/
│   ├── acquisition/
│   │   ├── scan_importer.py
│   │   ├── rgbd_capture.py
│   │   └── turntable_capture.py
│   │
│   ├── edge_ai/
│   │   ├── object_segmentation.py
│   │   ├── mask_refinement.py
│   │   └── depth_enhancement.py
│   │
│   ├── pointcloud/
│   │   ├── depth_to_pointcloud.py
│   │   ├── pointcloud_loader.py
│   │   ├── pointcloud_filter.py
│   │   ├── pointcloud_registration.py
│   │   └── pointcloud_writer.py
│   │
│   ├── surface_map/
│   │   ├── surface_reconstruction.py
│   │   ├── surface_map_builder.py
│   │   └── normal_estimation.py
│   │
│   ├── path_generation/
│   │   ├── slicing_path.py
│   │   ├── zigzag_generator.py
│   │   ├── contour_generator.py
│   │   ├── normal_sync.py
│   │   ├── path_smoothing.py
│   │   └── path_exporter.py
│   │
│   └── evaluation/
│       ├── scan_quality.py
│       ├── coverage_metric.py
│       ├── normal_quality.py
│       └── path_quality.py
│
├── services/
│   ├── project_service.py
│   ├── scan_service.py
│   ├── edge_ai_service.py
│   ├── pointcloud_service.py
│   ├── surface_map_service.py
│   ├── normal_service.py
│   ├── path_generation_service.py
│   └── export_service.py
│
├── workflows/
│   ├── full_scan_to_path_flow.py
│   ├── scan_to_surface_map_flow.py
│   └── generate_surface_path_flow.py
│
├── data/
│   ├── raw_rgb/
│   ├── raw_depth/
│   ├── masks/
│   ├── pointcloud_raw/
│   ├── pointcloud_clean/
│   ├── surface_maps/
│   ├── normal_maps/
│   ├── surface_paths/
│   └── exports/
│
└── tests/
```

---

## 7. Pipeline xử lý chính

### 7.1. Full Scan-to-Path Pipeline

```text
1. Load / Capture Scan
2. Run Edge AI Mask
3. Build Point Cloud
4. Filter Point Cloud
5. Build 3D Surface Map
6. Estimate Surface Normals
7. Generate Zigzag Path
8. Generate Contour Path
9. Synchronize Normals to Path
10. Display Result on UI
11. Export Results
```

### 7.2. Ý nghĩa từng bước

#### Bước 1: Load / Capture Scan

Nạp file point cloud hoặc dữ liệu RGB-D từ camera.

Định dạng hỗ trợ:

```text
.ply
.pcd
.xyz
```

#### Bước 2: Run Edge AI Mask

Edge AI được dùng để tách vật thể khỏi nền, bàn xoay hoặc vùng không cần xử lý.

Trong bản đầu tiên, nếu chưa có model AI hoàn chỉnh, hệ thống có thể dùng chế độ fallback:

```text
ROI Crop
Depth Threshold
Background Removal
```

#### Bước 3: Build Point Cloud

Chuyển dữ liệu depth/RGB-D hoặc file quét thành đám mây điểm 3D.

#### Bước 4: Filter Point Cloud

Lọc dữ liệu nhiễu bằng các phương pháp:

```text
Voxel Downsample
Statistical Outlier Removal
Radius Outlier Removal
ROI Crop
```

#### Bước 5: Build 3D Surface Map

Tạo bản đồ bề mặt 3D từ dữ liệu point cloud đã xử lý.

#### Bước 6: Estimate Surface Normals

Tính vector pháp tuyến tại từng vùng bề mặt bằng phương pháp lân cận cục bộ.

Dữ liệu pháp tuyến có dạng:

```text
Nx, Ny, Nz
```

#### Bước 7: Generate Zigzag Path

Sinh đường dẫn dạng Zigzag phủ trên vùng bề mặt.

#### Bước 8: Generate Contour Path

Sinh đường dẫn dạng Contour theo biên dạng hoặc lớp cắt bề mặt.

#### Bước 9: Synchronize Normals to Path

Mỗi điểm trên đường dẫn được gắn thêm vector pháp tuyến gần nhất.

Dữ liệu đường dẫn cuối cùng có dạng:

```text
x, y, z, nx, ny, nz
```

#### Bước 10: Display Result on UI

Hiển thị:

```text
Raw Point Cloud
Clean Point Cloud
Surface Map
Normal Vectors
Zigzag Path
Contour Path
```

#### Bước 11: Export Results

Xuất file phục vụ báo cáo, demo hoặc robot hóa ở giai đoạn sau.

---

## 8. Cấu trúc file đường dẫn

File `zigzag_path.csv` hoặc `contour_path.csv` có cấu trúc:

```csv
index,path_type,x,y,z,nx,ny,nz
0,zigzag,12.3,4.5,8.1,0.12,0.98,0.15
1,zigzag,12.8,4.5,8.3,0.14,0.97,0.16
2,zigzag,13.2,4.5,8.4,0.16,0.96,0.18
```

Ý nghĩa:

```text
index      - số thứ tự điểm
path_type  - loại đường dẫn: zigzag hoặc contour
x, y, z    - tọa độ điểm trong không gian 3D
nx, ny, nz - vector pháp tuyến tại điểm đó
```

---

## 9. Cài đặt môi trường

### 9.1. Tạo môi trường ảo

```bash
py -3.10 -m venv .venv
```

### 9.2. Kích hoạt môi trường

```bash
.venv\Scripts\activate
```

### 9.3. Cập nhật pip

```bash
python -m pip install --upgrade pip setuptools wheel
```

### 9.4. Cài thư viện

```bash
pip install -r requirements.txt
```

### 9.5. Kiểm tra thư viện

```bash
python -c "import open3d as o3d; import cv2; import numpy as np; import PyQt6; import onnxruntime; print('Environment OK')"
```

---

## 10. Chạy chương trình

```bash
python main.py
```

Sau khi mở giao diện, thao tác theo thứ tự:

```text
1. Load / Capture Scan
2. Run Edge AI Mask
3. Build Point Cloud
4. Filter Point Cloud
5. Build 3D Surface Map
6. Estimate Normals
7. Generate Zigzag Path
8. Generate Contour Path
9. Export Results
```

---

## 11. Giao diện HMI

### 11.1. Các nút chính

```text
Load / Capture Scan
Run Edge AI Mask
Build Point Cloud
Filter Point Cloud
Build 3D Surface Map
Estimate Normals
Generate Zigzag Path
Generate Contour Path
Export Results
```

### 11.2. Các chế độ hiển thị

```text
Show Raw Point Cloud
Show Clean Point Cloud
Show Surface Map
Show Normal Vectors
Show Zigzag Path
Show Contour Path
```

---

## 12. Edge AI trong hệ thống

Edge AI được tích hợp nhằm hỗ trợ tăng chất lượng dữ liệu quét.

Vai trò chính:

```text
Tách vật thể khỏi nền
Loại bỏ vùng bàn xoay
Làm sạch dữ liệu depth
Hỗ trợ tạo point cloud sạch hơn
```

Trong bản demo đầu tiên, Edge AI có thể hoạt động theo hai chế độ:

```text
Mode 1: AI Segmentation bằng mô hình ONNX
Mode 2: Fallback bằng ROI Crop hoặc Depth Threshold
```

Điều này giúp hệ thống vẫn chạy ổn định ngay cả khi chưa tích hợp xong model AI thật.

---

## 13. Quy ước phát triển

### 13.1. Không đưa vào bản lõi hiện tại

```text
Robot control
PLC control
Emergency stop flow
Spray valve control
Flow rate control
Full inverse kinematics
```

### 13.2. Chỉ tập trung vào

```text
3D Scan
Point Cloud Processing
Surface Map
Normal Estimation
Zigzag/Contour Path Generation
3D Visualization
Result Export
```

---

## 14. Đầu ra phục vụ báo cáo

Sau khi chạy pipeline, các file kết quả được lưu trong:

```text
data/exports/
```

Các file quan trọng:

```text
surface_model.ply
surface_map.ply
normal_field.ply
zigzag_path.csv
contour_path.csv
path_result.json
path_preview.png
```

Những file này dùng để chứng minh hệ thống đã thực hiện được:

```text
Scan → Surface Map → Normal Field → Surface Path
```

---

## 15. Hướng phát triển tiếp theo

Sau khi hoàn thành bản demo chính, hệ thống có thể mở rộng theo các hướng:

```text
Tích hợp capture trực tiếp từ Orbbec Astra Mini Pro
Tối ưu Edge AI segmentation
Tăng độ chính xác ghép nhiều góc quét
Tối ưu sinh đường dẫn trên bề mặt cong phức tạp
Thêm mô phỏng tư thế đầu phun
Kết nối với robot thật ở giai đoạn sau
```

---

## 16. Tóm tắt định hướng đề tài

Hệ thống không nhằm thay thế hoàn toàn dây chuyền robot phun sơn trong giai đoạn hiện tại. Trọng tâm của đề tài là giải quyết khâu nền tảng quan trọng nhất:

```text
Biến một sản phẩm thủ công mỹ nghệ không có CAD
thành mô hình/bản đồ bề mặt 3D
và đường dẫn bề mặt Zigzag/Contour có gắn vector pháp tuyến.
```

Đây là bước trung gian quan trọng để phục vụ định vị, lập trình hoặc huấn luyện robot sơn tự động trong các nghiên cứu và ứng dụng tiếp theo.

```
```
