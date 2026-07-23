"""Lệnh dòng lệnh quản trị hệ thống - dùng khi triển khai, không qua giao diện web.
Chạy: flask --app run.py tao-admin (máy dev) hoặc flask --app serve.py tao-admin (máy chủ).
"""
import click
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import NguoiDung


def dang_ky_cli(app):
    @app.cli.command("tao-admin")
    @click.option("--ten-dang-nhap", prompt=True, help="Tên đăng nhập")
    @click.option("--ho-ten", prompt=True, help="Họ tên hiển thị")
    @click.option("--mat-khau", prompt=True, hide_input=True, confirmation_prompt=True, help="Mật khẩu (tối thiểu 6 ký tự)")
    def tao_admin(ten_dang_nhap, ho_ten, mat_khau):
        """Tạo tài khoản quản trị (admin) - dùng khi triển khai lần đầu, DB chưa có tài khoản nào."""
        ten_dang_nhap = ten_dang_nhap.strip()
        ho_ten = ho_ten.strip()

        if not ten_dang_nhap or not ho_ten:
            click.echo("Tên đăng nhập và họ tên không được để trống.")
            return
        if NguoiDung.query.filter_by(ten_dang_nhap=ten_dang_nhap).first():
            click.echo(f'Tài khoản "{ten_dang_nhap}" đã tồn tại.')
            return
        if len(mat_khau) < 6:
            click.echo("Mật khẩu cần ít nhất 6 ký tự.")
            return

        nguoi_dung = NguoiDung(
            ten_dang_nhap=ten_dang_nhap,
            mat_khau_hash=generate_password_hash(mat_khau),
            ho_ten=ho_ten,
            vai_tro="admin",
        )
        db.session.add(nguoi_dung)
        db.session.commit()
        click.echo(f'Đã tạo tài khoản quản trị "{ten_dang_nhap}".')
