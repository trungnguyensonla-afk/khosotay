from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from app.models import NguoiDung

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/dang-nhap", methods=["GET", "POST"])
def dang_nhap():
    if current_user.is_authenticated:
        return redirect(url_for("main.trang_chu"))

    if request.method == "POST":
        ten_dang_nhap = request.form.get("ten_dang_nhap", "").strip()
        mat_khau = request.form.get("mat_khau", "")

        nguoi_dung = NguoiDung.query.filter_by(ten_dang_nhap=ten_dang_nhap).first()

        if nguoi_dung is None or not check_password_hash(nguoi_dung.mat_khau_hash, mat_khau):
            flash("Sai tên đăng nhập hoặc mật khẩu.", "loi")
        elif not nguoi_dung.dang_hoat_dong:
            flash("Tài khoản đã bị khóa. Liên hệ quản trị viên.", "loi")
        else:
            login_user(nguoi_dung)
            trang_tiep_theo = request.args.get("next")
            return redirect(trang_tiep_theo or url_for("main.trang_chu"))

    return render_template("dang_nhap.html")


@auth_bp.route("/dang-xuat")
@login_required
def dang_xuat():
    logout_user()
    flash("Đã đăng xuất.", "thanh_cong")
    return redirect(url_for("auth.dang_nhap"))
