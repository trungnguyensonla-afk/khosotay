"""Tự động gợi ý lĩnh vực dựa trên từ khóa trong nội dung tài liệu (mục 4.6, Phụ lục A).
Bộ từ khóa đọc từ config/tu_khoa_linh_vuc.json mỗi lần gọi, để admin sửa file là có tác dụng ngay,
không cần khởi động lại ứng dụng.
"""
import json
import os

from app.config import BASE_DIR

DUONG_DAN_CONFIG = os.path.join(BASE_DIR, "config", "tu_khoa_linh_vuc.json")


def _doc_cau_hinh_tu_khoa():
    try:
        with open(DUONG_DAN_CONFIG, encoding="utf-8") as f:
            du_lieu = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {ten: tu_khoa for ten, tu_khoa in du_lieu.items() if not ten.startswith("_")}


def goi_y_linh_vuc(noi_dung_text):
    """Trả về tên lĩnh vực có nhiều từ khóa khớp nhất trong nội dung, hoặc None nếu không khớp gì."""
    if not noi_dung_text:
        return None

    noi_dung_thuong = noi_dung_text.lower()
    cau_hinh = _doc_cau_hinh_tu_khoa()

    diem_theo_linh_vuc = {}
    for ten_linh_vuc, danh_sach_tu_khoa in cau_hinh.items():
        diem = sum(1 for tu_khoa in danh_sach_tu_khoa if tu_khoa.lower() in noi_dung_thuong)
        if diem > 0:
            diem_theo_linh_vuc[ten_linh_vuc] = diem

    if not diem_theo_linh_vuc:
        return None

    return max(diem_theo_linh_vuc, key=diem_theo_linh_vuc.get)
