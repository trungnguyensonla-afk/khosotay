from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import NguoiDung, LinhVuc, DonVi, TaiLieu, ThongBao, VAI_TRO_HOP_LE
from app.sao_luu import thuc_hien_sao_luu, danh_sach_ban_sao_luu

admin_bp = Blueprint("admin", __name__, url_prefix="/quan-tri")

NHAN_VAI_TRO = {"admin": "Quản trị viên", "bien_tap": "Biên tập", "tra_cuu": "Tra cứu"}


@admin_bp.before_request
@login_required
def chi_cho_admin():
    if not current_user.la_admin():
        abort(403)


@admin_bp.route("/")
def tong_quan():
    tong_so_tai_lieu = TaiLieu.query.count()
    tong_so_nguoi_dung = NguoiDung.query.count()

    theo_linh_vuc = (
        db.session.query(LinhVuc.ten, func.count(TaiLieu.id))
        .outerjoin(TaiLieu, TaiLieu.linh_vuc_id == LinhVuc.id)
        .group_by(LinhVuc.ten)
        .order_by(LinhVuc.ten)
        .all()
    )
    theo_don_vi = (
        db.session.query(DonVi.ten, func.count(TaiLieu.id))
        .outerjoin(TaiLieu, TaiLieu.don_vi_id == DonVi.id)
        .group_by(DonVi.ten)
        .order_by(DonVi.ten)
        .all()
    )
    theo_tinh_trang = dict(
        db.session.query(TaiLieu.tinh_trang, func.count(TaiLieu.id)).group_by(TaiLieu.tinh_trang).all()
    )

    return render_template(
        "quan_tri/tong_quan.html",
        tong_so_tai_lieu=tong_so_tai_lieu,
        tong_so_nguoi_dung=tong_so_nguoi_dung,
        theo_linh_vuc=theo_linh_vuc,
        theo_don_vi=theo_don_vi,
        theo_tinh_trang=theo_tinh_trang,
    )


@admin_bp.route("/nguoi-dung")
def danh_sach_nguoi_dung():
    return render_template(
        "quan_tri/nguoi_dung.html",
        danh_sach=NguoiDung.query.order_by(NguoiDung.ten_dang_nhap.asc()).all(),
        danh_sach_don_vi=DonVi.query.order_by(DonVi.ten.asc()).all(),
        nhan_vai_tro=NHAN_VAI_TRO,
    )


@admin_bp.route("/nguoi-dung/them", methods=["POST"])
def them_nguoi_dung():
    ten_dang_nhap = request.form.get("ten_dang_nhap", "").strip()
    mat_khau = request.form.get("mat_khau", "")
    ho_ten = request.form.get("ho_ten", "").strip()
    vai_tro = request.form.get("vai_tro", "tra_cuu")
    don_vi_id = request.form.get("don_vi_id", type=int)

    loi = []
    if not ten_dang_nhap:
        loi.append("Vui lòng nhập tên đăng nhập.")
    elif NguoiDung.query.filter_by(ten_dang_nhap=ten_dang_nhap).first():
        loi.append(f'Tên đăng nhập "{ten_dang_nhap}" đã tồn tại.')
    if not ho_ten:
        loi.append("Vui lòng nhập họ tên.")
    if len(mat_khau) < 6:
        loi.append("Mật khẩu cần ít nhất 6 ký tự.")
    if vai_tro not in VAI_TRO_HOP_LE:
        loi.append("Vai trò không hợp lệ.")

    if loi:
        for thong_bao in loi:
            flash(thong_bao, "loi")
    else:
        nguoi_dung = NguoiDung(
            ten_dang_nhap=ten_dang_nhap,
            mat_khau_hash=generate_password_hash(mat_khau),
            ho_ten=ho_ten,
            vai_tro=vai_tro,
            don_vi_id=don_vi_id,
        )
        db.session.add(nguoi_dung)
        db.session.commit()
        flash(f'Đã tạo tài khoản "{ten_dang_nhap}".', "thanh_cong")

    return redirect(url_for("admin.danh_sach_nguoi_dung"))


@admin_bp.route("/nguoi-dung/<int:nguoi_dung_id>/sua", methods=["POST"])
def sua_nguoi_dung(nguoi_dung_id):
    nguoi_dung = db.session.get(NguoiDung, nguoi_dung_id) or abort(404)

    ho_ten = request.form.get("ho_ten", "").strip()
    vai_tro = request.form.get("vai_tro", "tra_cuu")
    don_vi_id = request.form.get("don_vi_id", type=int)
    mat_khau_moi = request.form.get("mat_khau_moi", "")

    if nguoi_dung.id == current_user.id and vai_tro != "admin":
        flash("Không thể tự hạ quyền admin của chính mình.", "loi")
        return redirect(url_for("admin.danh_sach_nguoi_dung"))

    if not ho_ten:
        flash("Họ tên không được để trống.", "loi")
        return redirect(url_for("admin.danh_sach_nguoi_dung"))

    if vai_tro not in VAI_TRO_HOP_LE:
        flash("Vai trò không hợp lệ.", "loi")
        return redirect(url_for("admin.danh_sach_nguoi_dung"))

    nguoi_dung.ho_ten = ho_ten
    nguoi_dung.vai_tro = vai_tro
    nguoi_dung.don_vi_id = don_vi_id

    if mat_khau_moi:
        if len(mat_khau_moi) < 6:
            flash("Mật khẩu mới cần ít nhất 6 ký tự - các thay đổi khác vẫn được lưu.", "loi")
        else:
            nguoi_dung.mat_khau_hash = generate_password_hash(mat_khau_moi)
            flash(f'Đã đặt lại mật khẩu cho "{nguoi_dung.ten_dang_nhap}".', "thanh_cong")

    db.session.commit()
    flash(f'Đã cập nhật tài khoản "{nguoi_dung.ten_dang_nhap}".', "thanh_cong")
    return redirect(url_for("admin.danh_sach_nguoi_dung"))


@admin_bp.route("/nguoi-dung/<int:nguoi_dung_id>/khoa", methods=["POST"])
def khoa_mo_nguoi_dung(nguoi_dung_id):
    nguoi_dung = db.session.get(NguoiDung, nguoi_dung_id) or abort(404)

    if nguoi_dung.id == current_user.id:
        flash("Không thể tự khóa tài khoản của chính mình.", "loi")
        return redirect(url_for("admin.danh_sach_nguoi_dung"))

    nguoi_dung.dang_hoat_dong = not nguoi_dung.dang_hoat_dong
    db.session.commit()
    trang_thai = "mở khóa" if nguoi_dung.dang_hoat_dong else "khóa"
    flash(f'Đã {trang_thai} tài khoản "{nguoi_dung.ten_dang_nhap}".', "thanh_cong")
    return redirect(url_for("admin.danh_sach_nguoi_dung"))


@admin_bp.route("/sao-luu")
def sao_luu():
    return render_template(
        "quan_tri/sao_luu.html",
        danh_sach=danh_sach_ban_sao_luu(current_app.config["BACKUP_DIR"]),
    )


@admin_bp.route("/sao-luu/chay", methods=["POST"])
def chay_sao_luu():
    ket_qua = thuc_hien_sao_luu(
        database_uri=current_app.config["SQLALCHEMY_DATABASE_URI"],
        upload_dir=current_app.config["UPLOAD_DIR"],
        backup_dir=current_app.config["BACKUP_DIR"],
        pg_dump_cmd=current_app.config["PG_DUMP_CMD"],
    )
    if ket_qua["thanh_cong"]:
        flash(f'Đã sao lưu thành công vào "{ket_qua["duong_dan"]}".', "thanh_cong")
    else:
        flash(ket_qua["loi"], "loi")
    return redirect(url_for("admin.sao_luu"))


@admin_bp.route("/danh-muc")
def danh_muc():
    return render_template(
        "quan_tri/danh_muc.html",
        danh_sach_linh_vuc=LinhVuc.query.order_by(LinhVuc.ten.asc()).all(),
        danh_sach_don_vi=DonVi.query.order_by(DonVi.ten.asc()).all(),
    )


@admin_bp.route("/danh-muc/linh-vuc/them", methods=["POST"])
def them_linh_vuc():
    ten = request.form.get("ten", "").strip()
    if not ten:
        flash("Vui lòng nhập tên lĩnh vực.", "loi")
    elif LinhVuc.query.filter_by(ten=ten).first():
        flash(f'Lĩnh vực "{ten}" đã tồn tại.', "loi")
    else:
        db.session.add(LinhVuc(ten=ten))
        db.session.commit()
        flash(f'Đã thêm lĩnh vực "{ten}".', "thanh_cong")
    return redirect(url_for("admin.danh_muc"))


@admin_bp.route("/danh-muc/linh-vuc/<int:linh_vuc_id>/sua", methods=["POST"])
def sua_linh_vuc(linh_vuc_id):
    lv = db.session.get(LinhVuc, linh_vuc_id) or abort(404)
    ten_moi = request.form.get("ten", "").strip()
    if not ten_moi:
        flash("Tên lĩnh vực không được để trống.", "loi")
    else:
        lv.ten = ten_moi
        db.session.commit()
        flash("Đã cập nhật lĩnh vực.", "thanh_cong")
    return redirect(url_for("admin.danh_muc"))


@admin_bp.route("/danh-muc/don-vi/them", methods=["POST"])
def them_don_vi():
    ten = request.form.get("ten", "").strip()
    if not ten:
        flash("Vui lòng nhập tên đơn vị.", "loi")
    elif DonVi.query.filter_by(ten=ten).first():
        flash(f'Đơn vị "{ten}" đã tồn tại.', "loi")
    else:
        db.session.add(DonVi(ten=ten))
        db.session.commit()
        flash(f'Đã thêm đơn vị "{ten}".', "thanh_cong")
    return redirect(url_for("admin.danh_muc"))


@admin_bp.route("/danh-muc/don-vi/<int:don_vi_id>/sua", methods=["POST"])
def sua_don_vi(don_vi_id):
    dv = db.session.get(DonVi, don_vi_id) or abort(404)
    ten_moi = request.form.get("ten", "").strip()
    if not ten_moi:
        flash("Tên đơn vị không được để trống.", "loi")
    else:
        dv.ten = ten_moi
        db.session.commit()
        flash("Đã cập nhật đơn vị.", "thanh_cong")
    return redirect(url_for("admin.danh_muc"))


@admin_bp.route("/thong-bao")
def thong_bao():
    return render_template(
        "quan_tri/thong_bao.html",
        danh_sach=ThongBao.query.order_by(ThongBao.ngay_dang.desc()).all(),
        danh_sach_tai_lieu=TaiLieu.query.order_by(TaiLieu.tieu_de.asc()).all(),
    )


@admin_bp.route("/thong-bao/them", methods=["POST"])
def them_thong_bao():
    tieu_de = request.form.get("tieu_de", "").strip()
    tai_lieu_id = request.form.get("tai_lieu_id", type=int)

    if not tieu_de:
        flash("Vui lòng nhập tiêu đề thông báo.", "loi")
    else:
        db.session.add(ThongBao(tieu_de=tieu_de, tai_lieu_id=tai_lieu_id, nguoi_dang_id=current_user.id))
        db.session.commit()
        flash("Đã đăng thông báo.", "thanh_cong")
    return redirect(url_for("admin.thong_bao"))


@admin_bp.route("/thong-bao/<int:thong_bao_id>/sua", methods=["POST"])
def sua_thong_bao(thong_bao_id):
    tb = db.session.get(ThongBao, thong_bao_id) or abort(404)
    tieu_de = request.form.get("tieu_de", "").strip()
    if not tieu_de:
        flash("Tiêu đề thông báo không được để trống.", "loi")
    else:
        tb.tieu_de = tieu_de
        tb.tai_lieu_id = request.form.get("tai_lieu_id", type=int)
        db.session.commit()
        flash("Đã cập nhật thông báo.", "thanh_cong")
    return redirect(url_for("admin.thong_bao"))


@admin_bp.route("/thong-bao/<int:thong_bao_id>/xoa", methods=["POST"])
def xoa_thong_bao(thong_bao_id):
    tb = db.session.get(ThongBao, thong_bao_id) or abort(404)
    db.session.delete(tb)
    db.session.commit()
    flash("Đã xoá thông báo.", "thanh_cong")
    return redirect(url_for("admin.thong_bao"))
