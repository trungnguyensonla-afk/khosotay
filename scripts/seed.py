"""Nạp dữ liệu danh mục ban đầu: lĩnh vực, đơn vị, tài khoản admin mặc định.
Chạy: python scripts/seed.py
An toàn để chạy lại nhiều lần (không tạo trùng dữ liệu đã có).
"""
import sys

if sys.stdout.encoding.lower() != "utf-8":
    # Console mặc định của Windows (cp1252/cp437) không hiển thị được tiếng Việt có dấu
    sys.stdout.reconfigure(encoding="utf-8")

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import LinhVuc, DonVi, NguoiDung

DANH_SACH_LINH_VUC = [
    "Đất đai", "Môi trường", "Khoáng sản", "Trồng trọt", "Chăn nuôi",
    "Thú y", "Lâm nghiệp", "Bảo vệ thực vật", "Thủy sản", "Thủy lợi",
    "Tài nguyên nước", "Phòng chống thiên tai", "OCOP", "Nông thôn mới",
    "Khuyến nông", "Phát triển nông thôn",
]

# Danh sách gợi ý ban đầu - admin có thể sửa/bổ sung sau cho đúng cơ cấu tổ chức thực tế
DANH_SACH_DON_VI = [
    "Văn phòng Sở",
    "Phòng Trồng trọt và Bảo vệ thực vật",
    "Phòng Chăn nuôi và Thú y",
    "Phòng Quản lý đất đai",
    "Phòng Tài nguyên nước và Khí tượng thủy văn",
    "Chi cục Kiểm lâm",
    "Chi cục Thủy lợi",
    "Chi cục Bảo vệ môi trường",
    "Trung tâm Khuyến nông và Chuyển đổi số",
]

TAI_KHOAN_ADMIN_MAC_DINH = {
    "ten_dang_nhap": "admin",
    "mat_khau": "admin@123",
    "ho_ten": "Quản trị hệ thống",
    "vai_tro": "admin",
}


def seed():
    app = create_app()
    with app.app_context():
        so_luong_moi = 0

        for ten in DANH_SACH_LINH_VUC:
            if not LinhVuc.query.filter_by(ten=ten).first():
                db.session.add(LinhVuc(ten=ten))
                so_luong_moi += 1

        for ten in DANH_SACH_DON_VI:
            if not DonVi.query.filter_by(ten=ten).first():
                db.session.add(DonVi(ten=ten))
                so_luong_moi += 1

        db.session.commit()

        if not NguoiDung.query.filter_by(ten_dang_nhap=TAI_KHOAN_ADMIN_MAC_DINH["ten_dang_nhap"]).first():
            admin = NguoiDung(
                ten_dang_nhap=TAI_KHOAN_ADMIN_MAC_DINH["ten_dang_nhap"],
                mat_khau_hash=generate_password_hash(TAI_KHOAN_ADMIN_MAC_DINH["mat_khau"]),
                ho_ten=TAI_KHOAN_ADMIN_MAC_DINH["ho_ten"],
                vai_tro=TAI_KHOAN_ADMIN_MAC_DINH["vai_tro"],
            )
            db.session.add(admin)
            db.session.commit()
            print(
                f"Đã tạo tài khoản admin mặc định: "
                f"{TAI_KHOAN_ADMIN_MAC_DINH['ten_dang_nhap']} / {TAI_KHOAN_ADMIN_MAC_DINH['mat_khau']}"
            )
            print("QUAN TRỌNG: đổi mật khẩu này ngay sau khi đăng nhập lần đầu.")

        print(f"Hoàn tất seed dữ liệu. Số bản ghi danh mục mới thêm: {so_luong_moi}")
        print(f"Tổng lĩnh vực: {LinhVuc.query.count()}, tổng đơn vị: {DonVi.query.count()}")


if __name__ == "__main__":
    seed()
