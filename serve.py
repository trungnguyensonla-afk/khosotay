"""Chạy ứng dụng ở chế độ THẬT (production) bằng waitress - dùng file này trên máy chủ.
Khác với run.py (chỉ dùng khi phát triển/debug trên máy dev).

Chạy: python serve.py
Mặc định lắng nghe ở cổng 5000 trên mọi địa chỉ mạng của máy (0.0.0.0) - truy cập được cả
từ mạng nội bộ lẫn Internet (nếu máy chủ có IP công khai và đã mở cổng tương ứng).
Xem HUONG_DAN_TRIEN_KHAI.md để biết cách đưa lên Internet đầy đủ (firewall, HTTPS...).
"""
import os

from waitress import serve

from app import create_app

app = create_app()

if __name__ == "__main__":
    cong = int(os.environ.get("PORT", 5000))
    print(f"Đang chạy Kho Sổ Tay Hướng Dẫn Điện Tử tại cổng {cong} ...")
    print("Truy cập qua: http://<địa-chỉ-IP-máy-chủ>:" + str(cong))
    serve(app, host="0.0.0.0", port=cong, threads=8)
