"""Sao lưu toàn bộ dữ liệu (database + file gốc tài liệu) ra thư mục có ngày giờ.
Xem mục 4.8 của spec. Có thể gọi từ trang quản trị hoặc từ scripts/sao_luu_cli.py
(để lên lịch chạy tự động bằng Windows Task Scheduler).
"""
import os
import shutil
import subprocess
from datetime import datetime

HUONG_DAN_KHOI_PHUC = """HƯỚNG DẪN KHÔI PHỤC DỮ LIỆU
============================

Thư mục này chứa 1 bản sao lưu của Kho Sổ Tay Hướng Dẫn Điện Tử, gồm:
  - database.sql   : toàn bộ dữ liệu database (PostgreSQL)
  - files/          : toàn bộ file gốc tài liệu đã nạp

CÁCH KHÔI PHỤC:

1. Dừng ứng dụng web (đóng cửa sổ đang chạy waitress/flask).

2. Khôi phục database:
   - Nếu database "khosotay_db" đã tồn tại và muốn ghi đè, xóa và tạo lại:
       "C:\\Program Files\\PostgreSQL\\17\\bin\\psql.exe" -U postgres -c "DROP DATABASE khosotay_db;"
       "C:\\Program Files\\PostgreSQL\\17\\bin\\psql.exe" -U postgres -c "CREATE DATABASE khosotay_db OWNER khosotay_app;"
   - Nạp lại dữ liệu từ file database.sql:
       "C:\\Program Files\\PostgreSQL\\17\\bin\\psql.exe" -U khosotay_app -d khosotay_db -f database.sql

3. Khôi phục file gốc tài liệu:
   - Copy toàn bộ nội dung thư mục "files" trong bản sao lưu này vào thư mục
     "data/files" của ứng dụng (ghi đè nếu được hỏi).

4. Khởi động lại ứng dụng web, kiểm tra đăng nhập và tra cứu vài tài liệu để chắc chắn dữ liệu đã đúng.
"""


def thuc_hien_sao_luu(database_uri, upload_dir, backup_dir, pg_dump_cmd):
    """Tạo 1 bản sao lưu mới. Trả về dict {thanh_cong, duong_dan, loi}."""
    nhan_thoi_gian = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    thu_muc_sao_luu = os.path.join(backup_dir, nhan_thoi_gian)
    os.makedirs(thu_muc_sao_luu, exist_ok=True)

    uri_chuan = database_uri.replace("postgresql+psycopg2://", "postgresql://")
    duong_dan_sql = os.path.join(thu_muc_sao_luu, "database.sql")

    try:
        subprocess.run(
            [pg_dump_cmd, uri_chuan, "-f", duong_dan_sql, "--no-owner", "--no-privileges"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as loi:
        chi_tiet = loi.stderr if isinstance(loi, subprocess.CalledProcessError) else str(loi)
        return {"thanh_cong": False, "duong_dan": thu_muc_sao_luu, "loi": f"Lỗi sao lưu database: {chi_tiet}"}

    if os.path.isdir(upload_dir):
        shutil.copytree(upload_dir, os.path.join(thu_muc_sao_luu, "files"), dirs_exist_ok=True)

    with open(os.path.join(thu_muc_sao_luu, "HUONG_DAN_KHOI_PHUC.txt"), "w", encoding="utf-8") as f:
        f.write(HUONG_DAN_KHOI_PHUC)

    return {"thanh_cong": True, "duong_dan": thu_muc_sao_luu, "loi": None}


def danh_sach_ban_sao_luu(backup_dir):
    """Liệt kê các bản sao lưu đã có, mới nhất trước, kèm dung lượng."""
    if not os.path.isdir(backup_dir):
        return []

    ket_qua = []
    for ten in sorted(os.listdir(backup_dir), reverse=True):
        duong_dan = os.path.join(backup_dir, ten)
        if not os.path.isdir(duong_dan):
            continue
        dung_luong = sum(
            os.path.getsize(os.path.join(goc, f))
            for goc, _, files in os.walk(duong_dan)
            for f in files
        )
        ket_qua.append({"ten": ten, "dung_luong_mb": round(dung_luong / (1024 * 1024), 1)})
    return ket_qua
