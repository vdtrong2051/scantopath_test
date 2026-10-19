import os

def generate_tree(dir_path, exclude_dirs=None, prefix=""):
    """
    Hàm đệ quy in ra cây thư mục.
    
    :param dir_path: Đường dẫn tới thư mục cần in.
    :param exclude_dirs: Tập hợp (set) hoặc danh sách các thư mục cần bỏ qua.
    :param prefix: Tiền tố dùng để vẽ các nhánh của cây (dùng trong đệ quy).
    """
    # Các thư mục mặc định cần bỏ qua nếu không được truyền vào
    if exclude_dirs is None:
        exclude_dirs = {'.venv', 'venv', 'env', '.git', '__pycache__', '.idea', '.vscode'}

    try:
        # Lấy danh sách tất cả các file và thư mục con
        items = os.listdir(dir_path)
    except PermissionError:
        # Bỏ qua nếu không có quyền truy cập
        return

    # Lọc bỏ các file/thư mục nằm trong danh sách exclude_dirs
    items = [item for item in items if item not in exclude_dirs]
    
    # Sắp xếp theo thứ tự alphabet để dễ nhìn hơn
    items.sort()

    for i, item in enumerate(items):
        path = os.path.join(dir_path, item)
        is_last = (i == len(items) - 1)
        
        # Chọn ký tự nhánh cây phù hợp
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{item}")

        # Nếu là thư mục, tiếp tục gọi đệ quy
        if os.path.isdir(path):
            extension = "    " if is_last else "│   "
            generate_tree(path, exclude_dirs, prefix + extension)

if __name__ == "__main__":
    # Thay "." bằng đường dẫn project của bạn nếu cần
    project_path = "."
    
    # Lấy tên thư mục gốc để làm tên root của cây
    root_name = os.path.basename(os.path.abspath(project_path))
    print(f"📁 {root_name}/")
    
    # Chạy hàm tạo cây
    generate_tree(project_path)