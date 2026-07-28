import os
import re
import threading
import uuid
from datetime import datetime

from flask import Blueprint, render_template, request, abort, flash, redirect, url_for, current_app, send_file
from flask_login import login_required, current_user
from markupsafe import Markup, escape
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename

from app.config import BASE_DIR
from app.extensions import db
from app.models import TaiLieu, LinhVuc, DonVi, TepTaiLieu, ThongBao
from app.trich_xuat import trich_xuat_noi_dung
from app.ocr import chay_ocr_pdf
from app.goi_y_linh_vuc import goi_y_linh_vuc

main_bp = Blueprint("main", __name__)

DANH_SACH_TINH_TRANG = ["Còn hiệu lực", "Hết hiệu lực", "Đang rà soát"]
NHAN_TRANG_THAI_SANG_CSS = {
    "Còn hiệu lực": "valid",
    "Hết hiệu lực": "expired",
    "Đang rà soát": "review",
}
TU_KHOA_GOI_Y = ["chuyển mục đích", "quan trắc môi trường", "OCOP", "tiêm phòng", "phòng cháy rừng"]
LOAI_VAN_BAN_LUA_CHON = ["Sổ tay", "Quy trình", "Hướng dẫn", "Mẫu biểu", "QPPL", "Quyết định", "Quy định", "Tài liệu khác"]
DUOI_FILE_HOP_LE = {"pdf", "doc", "docx"}


def _loai_file(duong_dan_file):
    if not duong_dan_file:
        return "doc"
    phan_mo_rong = duong_dan_file.rsplit(".", 1)[-1].lower()
    return "pdf" if phan_mo_rong == "pdf" else "doc"


def _loai_file_tai_lieu(tai_lieu):
    """Icon loại file đại diện cho cả tài liệu (có thể gồm nhiều file) ở danh sách kết quả tìm kiếm."""
    if any(_loai_file(t.duong_dan_file) == "pdf" for t in tai_lieu.tep_dinh_kem):
        return "pdf"
    return "doc"


def _parse_ngay(chuoi_ngay):
    if not chuoi_ngay:
        return None
    try:
        return datetime.strptime(chuoi_ngay, "%Y-%m-%d").date()
    except ValueError:
        return None


def _trich_doan(noi_dung, tu_khoa, tom_tat=None, do_dai=160):
    """Cắt một đoạn quanh từ khóa tìm thấy trong nội dung, escape an toàn rồi mới highlight.
    Không tìm kiếm (tu_khoa rỗng): ưu tiên tóm tắt do biên tập tự viết (đọc mạch lạc hơn
    cắt thô đoạn đầu tài liệu, vốn có thể là mục lục/số hiệu/tiêu đề lộn xộn)."""
    if not tu_khoa and tom_tat:
        doan = tom_tat[:do_dai] + ("…" if len(tom_tat) > do_dai else "")
        return Markup(escape(doan))

    if not noi_dung:
        return ""

    if not tu_khoa:
        doan = noi_dung[:do_dai] + ("…" if len(noi_dung) > do_dai else "")
        return Markup(escape(doan))

    vi_tri = noi_dung.lower().find(tu_khoa.lower())
    if vi_tri == -1:
        doan = noi_dung[:do_dai] + ("…" if len(noi_dung) > do_dai else "")
        return Markup(escape(doan))

    bat_dau = max(0, vi_tri - 60)
    ket_thuc = min(len(noi_dung), vi_tri + len(tu_khoa) + 100)
    truoc = noi_dung[bat_dau:vi_tri]
    khop = noi_dung[vi_tri:vi_tri + len(tu_khoa)]
    sau = noi_dung[vi_tri + len(tu_khoa):ket_thuc]

    return Markup(
        escape(("…" if bat_dau > 0 else "") + truoc)
        + "<mark>" + escape(khop) + "</mark>"
        + escape(sau + ("…" if ket_thuc < len(noi_dung) else ""))
    )


@main_bp.route("/")
def trang_chu():
    tu_khoa = request.args.get("q", "").strip()
    linh_vuc_id = request.args.get("linh_vuc", type=int)
    don_vi_id = request.args.get("don_vi", type=int)
    tinh_trang = request.args.get("tinh_trang", "").strip()
    loai_van_ban = request.args.get("loai_van_ban", "").strip()
    tu_ngay = request.args.get("tu_ngay", "").strip()
    den_ngay = request.args.get("den_ngay", "").strip()
    sap_xep = request.args.get("sort", "new")

    truy_van = TaiLieu.query
    truy_van_tsv = None

    if tu_khoa:
        # Tìm toàn văn bằng cột tsvector đã tính sẵn (noi_dung_tsv) - nhanh hơn ILIKE
        # nhiều với hàng nghìn tài liệu, có xếp hạng độ liên quan (mục 4.3 SPEC).
        # OR thêm ILIKE trên so_hieu vì số hiệu văn bản (VD "1693/SKHCN-CĐS") tách từ
        # theo tsvector có thể mất khớp chính xác dấu gạch/số.
        truy_van_tsv = func.websearch_to_tsquery("simple", tu_khoa)
        truy_van = truy_van.filter(
            or_(
                TaiLieu.noi_dung_tsv.op("@@")(truy_van_tsv),
                TaiLieu.so_hieu.ilike(f"%{tu_khoa}%"),
            )
        )
    if linh_vuc_id:
        truy_van = truy_van.filter(TaiLieu.linh_vuc_id == linh_vuc_id)
    if don_vi_id:
        truy_van = truy_van.filter(TaiLieu.don_vi_id == don_vi_id)
    if tinh_trang:
        truy_van = truy_van.filter(TaiLieu.tinh_trang == tinh_trang)
    if loai_van_ban:
        truy_van = truy_van.filter(TaiLieu.loai_van_ban == loai_van_ban)
    ngay_tu = _parse_ngay(tu_ngay)
    if ngay_tu:
        truy_van = truy_van.filter(TaiLieu.ngay_ban_hanh >= ngay_tu)
    ngay_den = _parse_ngay(den_ngay)
    if ngay_den:
        truy_van = truy_van.filter(TaiLieu.ngay_ban_hanh <= ngay_den)

    if sap_xep == "az":
        truy_van = truy_van.order_by(TaiLieu.tieu_de.asc())
    elif sap_xep == "unit":
        truy_van = truy_van.outerjoin(DonVi, TaiLieu.don_vi_id == DonVi.id).order_by(DonVi.ten.asc())
    elif tu_khoa:
        # Có từ khóa: ưu tiên độ liên quan (ts_rank) trước, tài liệu mới hơn xếp trên khi hòa điểm
        truy_van = truy_van.order_by(
            func.ts_rank(TaiLieu.noi_dung_tsv, truy_van_tsv).desc(),
            TaiLieu.ngay_ban_hanh.desc(),
        )
    else:
        truy_van = truy_van.order_by(TaiLieu.ngay_ban_hanh.desc())

    ket_qua = truy_van.all()

    ket_qua_hien_thi = [
        {
            "tai_lieu": tl,
            "loai_file": _loai_file_tai_lieu(tl),
            "trich_doan": _trich_doan(tl.noi_dung_text, tu_khoa, tl.tom_tat),
            "status_class": NHAN_TRANG_THAI_SANG_CSS.get(tl.tinh_trang, "review"),
            # Nút tải nhanh ở danh sách kết quả trỏ vào file đầu tiên (tài liệu có thể có nhiều file)
            "tep_dau_id": min(tl.tep_dinh_kem, key=lambda t: t.thu_tu).id if tl.tep_dinh_kem else None,
        }
        for tl in ket_qua
    ]

    tong_so_tai_lieu = TaiLieu.query.count()
    dem_linh_vuc = dict(db.session.query(TaiLieu.linh_vuc_id, func.count(TaiLieu.id)).group_by(TaiLieu.linh_vuc_id).all())
    dem_don_vi = dict(db.session.query(TaiLieu.don_vi_id, func.count(TaiLieu.id)).group_by(TaiLieu.don_vi_id).all())
    dem_tinh_trang = dict(db.session.query(TaiLieu.tinh_trang, func.count(TaiLieu.id)).group_by(TaiLieu.tinh_trang).all())
    dem_loai_van_ban = dict(db.session.query(TaiLieu.loai_van_ban, func.count(TaiLieu.id)).group_by(TaiLieu.loai_van_ban).all())

    thong_bao_moi_nhat = ThongBao.query.order_by(ThongBao.ngay_dang.desc()).limit(3).all()
    tai_lieu_xem_nhieu = (
        TaiLieu.query.filter(TaiLieu.luot_xem > 0).order_by(TaiLieu.luot_xem.desc()).limit(3).all()
    )

    return render_template(
        "trang_chu.html",
        ket_qua=ket_qua_hien_thi,
        tong_so_ket_qua=len(ket_qua_hien_thi),
        tong_so_tai_lieu=tong_so_tai_lieu,
        danh_sach_linh_vuc=LinhVuc.query.order_by(LinhVuc.ten.asc()).all(),
        danh_sach_don_vi=DonVi.query.order_by(DonVi.ten.asc()).all(),
        danh_sach_tinh_trang=DANH_SACH_TINH_TRANG,
        loai_van_ban_lua_chon=LOAI_VAN_BAN_LUA_CHON,
        tu_khoa_goi_y=TU_KHOA_GOI_Y,
        dem_linh_vuc=dem_linh_vuc,
        dem_don_vi=dem_don_vi,
        dem_tinh_trang=dem_tinh_trang,
        dem_loai_van_ban=dem_loai_van_ban,
        thong_bao_moi_nhat=thong_bao_moi_nhat,
        tai_lieu_xem_nhieu=tai_lieu_xem_nhieu,
        bo_loc={
            "q": tu_khoa,
            "linh_vuc": linh_vuc_id,
            "don_vi": don_vi_id,
            "tinh_trang": tinh_trang,
            "loai_van_ban": loai_van_ban,
            "tu_ngay": tu_ngay,
            "den_ngay": den_ngay,
            "sort": sap_xep,
        },
    )


@main_bp.route("/thong-bao")
def danh_sach_thong_bao():
    return render_template(
        "thong_bao.html",
        danh_sach=ThongBao.query.order_by(ThongBao.ngay_dang.desc()).all(),
    )


def _duoi_file_hop_le(ten_file):
    return "." in ten_file and ten_file.rsplit(".", 1)[-1].lower() in DUOI_FILE_HOP_LE


def _luu_file_goc(file_storage):
    """Lưu file gốc vào data/files/<năm>/<tháng>/.

    Trả về (đường_dẫn_tương_đối để lưu DB, đường_dẫn_tuyệt_đối để xử lý ngay).
    """
    hom_nay = datetime.now()
    thu_muc_con = os.path.join(str(hom_nay.year), f"{hom_nay.month:02d}")
    thu_muc_day_du = os.path.join(current_app.config["UPLOAD_DIR"], thu_muc_con)
    os.makedirs(thu_muc_day_du, exist_ok=True)

    ten_goc = secure_filename(file_storage.filename)
    ten_luu = f"{uuid.uuid4().hex[:8]}_{ten_goc}"
    duong_dan_tuyet_doi = os.path.join(thu_muc_day_du, ten_luu)
    file_storage.save(duong_dan_tuyet_doi)

    duong_dan_tuong_doi = os.path.join("data", "files", thu_muc_con, ten_luu).replace("\\", "/")
    return duong_dan_tuong_doi, duong_dan_tuyet_doi


def _tu_goi_y_linh_vuc(tai_lieu, noi_dung_text):
    """Nếu chưa chọn lĩnh vực, thử tự gán theo từ khóa trong nội dung. Trả về tên lĩnh vực đã gán (hoặc None)."""
    if tai_lieu.linh_vuc_id or not noi_dung_text:
        return None

    ten_goi_y = goi_y_linh_vuc(noi_dung_text)
    if not ten_goi_y:
        return None

    lv = LinhVuc.query.filter_by(ten=ten_goi_y).first()
    if not lv:
        return None

    tai_lieu.linh_vuc_id = lv.id
    return ten_goi_y


def _cap_nhat_tong_hop(tai_lieu):
    """Gộp nội dung + trạng thái xử lý từ tất cả file con thành nội dung/trạng thái tổng hợp
    của tài liệu - vì 1 tài liệu (sổ tay) có thể gồm nhiều file (Phần 1, Phần 2, Phụ lục...)."""
    danh_sach_tep = sorted(tai_lieu.tep_dinh_kem, key=lambda t: t.thu_tu)
    cac_doan = [t.noi_dung_text for t in danh_sach_tep if t.noi_dung_text]
    tai_lieu.noi_dung_text = "\n\n".join(cac_doan) if cac_doan else None

    if any(t.trang_thai_xu_ly == "dang_xu_ly" for t in danh_sach_tep):
        tai_lieu.trang_thai_xu_ly = "dang_xu_ly"
    elif cac_doan:
        tai_lieu.trang_thai_xu_ly = "hoan_thanh"
    elif any(t.trang_thai_xu_ly == "loi" for t in danh_sach_tep):
        tai_lieu.trang_thai_xu_ly = "loi"
    else:
        tai_lieu.trang_thai_xu_ly = "hoan_thanh"


def _chay_ocr_nen_tep(app, tep_id, tai_lieu_id, duong_dan_tuyet_doi):
    """Chạy trong luồng nền: OCR 1 file scan rồi cập nhật file đó + nội dung tổng hợp của tài liệu."""
    with app.app_context():
        try:
            noi_dung = chay_ocr_pdf(
                duong_dan_tuyet_doi,
                poppler_path=app.config.get("POPPLER_PATH"),
                tesseract_cmd=app.config.get("TESSERACT_CMD"),
            )
        except Exception:
            current_app.logger.exception("Loi OCR nen cho file id=%s", tep_id)
            noi_dung = None

        tep = db.session.get(TepTaiLieu, tep_id)
        if tep is None:
            return

        if noi_dung:
            tep.noi_dung_text = noi_dung
            tep.trang_thai_xu_ly = "hoan_thanh"
        else:
            tep.trang_thai_xu_ly = "loi"

        tai_lieu = db.session.get(TaiLieu, tai_lieu_id)
        if tai_lieu is not None:
            _cap_nhat_tong_hop(tai_lieu)
            if noi_dung:
                _tu_goi_y_linh_vuc(tai_lieu, tai_lieu.noi_dung_text)
        db.session.commit()


@main_bp.route("/nap-tai-lieu", methods=["GET", "POST"])
@login_required
def nap_tai_lieu():
    if not current_user.la_bien_tap():
        abort(403)

    if request.method == "POST":
        tieu_de = request.form.get("tieu_de", "").strip()
        files = [f for f in request.files.getlist("file") if f and f.filename]

        loi = []
        if not tieu_de:
            loi.append("Vui lòng nhập tiêu đề tài liệu.")
        if not files:
            loi.append("Vui lòng chọn ít nhất 1 file để nạp.")
        else:
            for f in files:
                if not _duoi_file_hop_le(f.filename):
                    loi.append(f'File "{f.filename}" không đúng định dạng - chỉ chấp nhận PDF hoặc Word (.pdf, .doc, .docx).')

        if loi:
            for thong_bao in loi:
                flash(thong_bao, "loi")
        else:
            tai_lieu = TaiLieu(
                tieu_de=tieu_de,
                tom_tat=request.form.get("tom_tat", "").strip() or None,
                so_hieu=request.form.get("so_hieu", "").strip() or None,
                co_quan_ban_hanh=request.form.get("co_quan_ban_hanh", "").strip() or None,
                linh_vuc_id=request.form.get("linh_vuc_id", type=int),
                don_vi_id=request.form.get("don_vi_id", type=int),
                loai_van_ban=request.form.get("loai_van_ban") or None,
                tinh_trang=request.form.get("tinh_trang") or "Còn hiệu lực",
                ngay_ban_hanh=_parse_ngay(request.form.get("ngay_ban_hanh")),
                ngay_het_hieu_luc=_parse_ngay(request.form.get("ngay_het_hieu_luc")),
                phien_ban=request.form.get("phien_ban", "").strip() or None,
                nguoi_nap_id=current_user.id,
            )

            tep_can_ocr = []  # [(TepTaiLieu, duong_dan_tuyet_doi), ...] - xử lý OCR nền sau khi commit
            for thu_tu, f in enumerate(files):
                duong_dan_luu, duong_dan_tuyet_doi = _luu_file_goc(f)
                ket_qua_trich_xuat = trich_xuat_noi_dung(duong_dan_luu, duong_dan_tuyet_doi)

                tep = TepTaiLieu(duong_dan_file=duong_dan_luu, thu_tu=thu_tu)
                if ket_qua_trich_xuat["can_ocr"]:
                    tep.trang_thai_xu_ly = "dang_xu_ly"
                    tep_can_ocr.append((tep, duong_dan_tuyet_doi))
                elif ket_qua_trich_xuat["loi"]:
                    tep.trang_thai_xu_ly = "loi"
                else:
                    tep.noi_dung_text = ket_qua_trich_xuat["noi_dung_text"]
                    tep.trang_thai_xu_ly = "hoan_thanh"
                tai_lieu.tep_dinh_kem.append(tep)

            _cap_nhat_tong_hop(tai_lieu)
            ten_linh_vuc_goi_y = _tu_goi_y_linh_vuc(tai_lieu, tai_lieu.noi_dung_text)

            db.session.add(tai_lieu)
            db.session.commit()

            for tep, duong_dan_tuyet_doi in tep_can_ocr:
                app_obj = current_app._get_current_object()
                threading.Thread(
                    target=_chay_ocr_nen_tep,
                    args=(app_obj, tep.id, tai_lieu.id, duong_dan_tuyet_doi),
                    daemon=True,
                ).start()

            so_file = len(files)
            phan_so_file = f" ({so_file} file)" if so_file > 1 else ""
            if tep_can_ocr:
                flash(
                    f'Đã nạp tài liệu "{tieu_de}"{phan_so_file}. Có {len(tep_can_ocr)} file dạng scan (ảnh) - '
                    f'đang chạy OCR tiếng Việt ở chế độ nền, nội dung sẽ tìm kiếm được sau ít phút.',
                    "thanh_cong",
                )
            elif any(t.trang_thai_xu_ly == "loi" for t in tai_lieu.tep_dinh_kem):
                flash(f'Đã nạp tài liệu "{tieu_de}"{phan_so_file}, nhưng một số file chưa trích xuất được nội dung.', "loi")
            else:
                so_ky_tu = len(tai_lieu.noi_dung_text or "")
                thong_bao = f'Đã nạp tài liệu "{tieu_de}" thành công{phan_so_file}. Đã trích xuất {so_ky_tu} ký tự nội dung để tìm kiếm.'
                if ten_linh_vuc_goi_y:
                    thong_bao += f' Đã tự động gán lĩnh vực gợi ý "{ten_linh_vuc_goi_y}" - vào sửa tài liệu nếu chưa đúng.'
                flash(thong_bao, "thanh_cong")

            return redirect(url_for("main.trang_chu"))

    return render_template(
        "nap_tai_lieu.html",
        danh_sach_linh_vuc=LinhVuc.query.order_by(LinhVuc.ten.asc()).all(),
        danh_sach_don_vi=DonVi.query.order_by(DonVi.ten.asc()).all(),
        loai_van_ban_lua_chon=LOAI_VAN_BAN_LUA_CHON,
        tinh_trang_lua_chon=DANH_SACH_TINH_TRANG,
    )


def _duong_dan_tuyet_doi(duong_dan_tuong_doi):
    return os.path.join(BASE_DIR, duong_dan_tuong_doi)


def _ten_file_hien_thi(duong_dan_file):
    """Bỏ tiền tố mã ngẫu nhiên (uuid) khi hiển thị/tải về, trả lại tên file gốc dễ đọc."""
    ten = os.path.basename(duong_dan_file)
    return re.sub(r"^[0-9a-fA-F]{8}_", "", ten)


@main_bp.route("/tai-lieu/<int:tai_lieu_id>")
def chi_tiet_tai_lieu(tai_lieu_id):
    tl = TaiLieu.query.get_or_404(tai_lieu_id)

    # Cập nhật kiểu SQL "luot_xem = luot_xem + 1" (không đọc-rồi-ghi bằng Python) để tránh
    # mất lượt đếm khi nhiều người xem cùng lúc ghi đè giá trị cũ lên nhau.
    tl.luot_xem = TaiLieu.luot_xem + 1
    db.session.commit()

    danh_sach_tep = sorted(tl.tep_dinh_kem, key=lambda t: t.thu_tu)
    tep_xem_truoc = next((t for t in danh_sach_tep if _loai_file(t.duong_dan_file) == "pdf"), None)
    return render_template(
        "chi_tiet_tai_lieu.html",
        tl=tl,
        danh_sach_tep=[
            {
                "tep": t,
                "loai_file": _loai_file(t.duong_dan_file),
                "ten_hien_thi": _ten_file_hien_thi(t.duong_dan_file),
            }
            for t in danh_sach_tep
        ],
        tep_xem_truoc_id=tep_xem_truoc.id if tep_xem_truoc else None,
        status_class=NHAN_TRANG_THAI_SANG_CSS.get(tl.tinh_trang, "review"),
    )


@main_bp.route("/tai-lieu/<int:tai_lieu_id>/file/<int:tep_id>")
def file_tai_lieu(tai_lieu_id, tep_id):
    tep = TepTaiLieu.query.filter_by(id=tep_id, tai_lieu_id=tai_lieu_id).first_or_404()

    duong_dan = _duong_dan_tuyet_doi(tep.duong_dan_file)
    if not os.path.exists(duong_dan):
        abort(404)

    tai_ve = request.args.get("tai_ve") == "1"
    return send_file(
        duong_dan,
        as_attachment=tai_ve,
        download_name=_ten_file_hien_thi(tep.duong_dan_file) if tai_ve else None,
    )


@main_bp.route("/tai-lieu/<int:tai_lieu_id>/sua", methods=["GET", "POST"])
@login_required
def sua_tai_lieu(tai_lieu_id):
    if not current_user.la_bien_tap():
        abort(403)

    tl = TaiLieu.query.get_or_404(tai_lieu_id)

    if request.method == "POST":
        tieu_de = request.form.get("tieu_de", "").strip()
        if not tieu_de:
            flash("Vui lòng nhập tiêu đề tài liệu.", "loi")
        else:
            tl.tieu_de = tieu_de
            tl.tom_tat = request.form.get("tom_tat", "").strip() or None
            tl.so_hieu = request.form.get("so_hieu", "").strip() or None
            tl.co_quan_ban_hanh = request.form.get("co_quan_ban_hanh", "").strip() or None
            tl.linh_vuc_id = request.form.get("linh_vuc_id", type=int)
            tl.don_vi_id = request.form.get("don_vi_id", type=int)
            tl.loai_van_ban = request.form.get("loai_van_ban") or None
            tl.tinh_trang = request.form.get("tinh_trang") or "Còn hiệu lực"
            tl.ngay_ban_hanh = _parse_ngay(request.form.get("ngay_ban_hanh"))
            tl.ngay_het_hieu_luc = _parse_ngay(request.form.get("ngay_het_hieu_luc"))
            tl.phien_ban = request.form.get("phien_ban", "").strip() or None
            db.session.commit()
            flash(f'Đã cập nhật tài liệu "{tieu_de}".', "thanh_cong")
            return redirect(url_for("main.chi_tiet_tai_lieu", tai_lieu_id=tl.id))

    danh_sach_tep = sorted(tl.tep_dinh_kem, key=lambda t: t.thu_tu)
    return render_template(
        "sua_tai_lieu.html",
        tl=tl,
        danh_sach_tep=[
            {"tep": t, "ten_hien_thi": _ten_file_hien_thi(t.duong_dan_file)}
            for t in danh_sach_tep
        ],
        danh_sach_linh_vuc=LinhVuc.query.order_by(LinhVuc.ten.asc()).all(),
        danh_sach_don_vi=DonVi.query.order_by(DonVi.ten.asc()).all(),
        loai_van_ban_lua_chon=LOAI_VAN_BAN_LUA_CHON,
        tinh_trang_lua_chon=DANH_SACH_TINH_TRANG,
    )


@main_bp.route("/tai-lieu/<int:tai_lieu_id>/them-file", methods=["POST"])
@login_required
def them_file_tai_lieu(tai_lieu_id):
    if not current_user.la_bien_tap():
        abort(403)

    tai_lieu = TaiLieu.query.get_or_404(tai_lieu_id)
    files = [f for f in request.files.getlist("file") if f and f.filename]

    if not files:
        flash("Vui lòng chọn ít nhất 1 file để thêm.", "loi")
        return redirect(url_for("main.sua_tai_lieu", tai_lieu_id=tai_lieu.id))

    loi_dinh_dang = [
        f'File "{f.filename}" không đúng định dạng - chỉ chấp nhận PDF hoặc Word (.pdf, .doc, .docx).'
        for f in files if not _duoi_file_hop_le(f.filename)
    ]
    if loi_dinh_dang:
        for thong_bao in loi_dinh_dang:
            flash(thong_bao, "loi")
        return redirect(url_for("main.sua_tai_lieu", tai_lieu_id=tai_lieu.id))

    thu_tu_bat_dau = max((t.thu_tu for t in tai_lieu.tep_dinh_kem), default=-1) + 1
    tep_can_ocr = []
    for i, f in enumerate(files):
        duong_dan_luu, duong_dan_tuyet_doi = _luu_file_goc(f)
        ket_qua_trich_xuat = trich_xuat_noi_dung(duong_dan_luu, duong_dan_tuyet_doi)

        tep = TepTaiLieu(duong_dan_file=duong_dan_luu, thu_tu=thu_tu_bat_dau + i)
        if ket_qua_trich_xuat["can_ocr"]:
            tep.trang_thai_xu_ly = "dang_xu_ly"
            tep_can_ocr.append((tep, duong_dan_tuyet_doi))
        elif ket_qua_trich_xuat["loi"]:
            tep.trang_thai_xu_ly = "loi"
        else:
            tep.noi_dung_text = ket_qua_trich_xuat["noi_dung_text"]
            tep.trang_thai_xu_ly = "hoan_thanh"
        tai_lieu.tep_dinh_kem.append(tep)

    _cap_nhat_tong_hop(tai_lieu)
    _tu_goi_y_linh_vuc(tai_lieu, tai_lieu.noi_dung_text)
    db.session.commit()

    for tep, duong_dan_tuyet_doi in tep_can_ocr:
        app_obj = current_app._get_current_object()
        threading.Thread(
            target=_chay_ocr_nen_tep,
            args=(app_obj, tep.id, tai_lieu.id, duong_dan_tuyet_doi),
            daemon=True,
        ).start()

    flash(f'Đã thêm {len(files)} file vào tài liệu "{tai_lieu.tieu_de}".', "thanh_cong")
    return redirect(url_for("main.sua_tai_lieu", tai_lieu_id=tai_lieu.id))


@main_bp.route("/tai-lieu/<int:tai_lieu_id>/tep/<int:tep_id>/xoa", methods=["POST"])
@login_required
def xoa_tep_tai_lieu(tai_lieu_id, tep_id):
    if not current_user.la_bien_tap():
        abort(403)

    tai_lieu = TaiLieu.query.get_or_404(tai_lieu_id)
    tep = next((t for t in tai_lieu.tep_dinh_kem if t.id == tep_id), None)
    if tep is None:
        abort(404)
    if len(tai_lieu.tep_dinh_kem) <= 1:
        flash("Tài liệu phải còn ít nhất 1 file - không thể xoá file cuối cùng.", "loi")
        return redirect(url_for("main.sua_tai_lieu", tai_lieu_id=tai_lieu.id))

    duong_dan_tuyet_doi = _duong_dan_tuyet_doi(tep.duong_dan_file)
    ten_hien_thi = _ten_file_hien_thi(tep.duong_dan_file)
    tai_lieu.tep_dinh_kem.remove(tep)
    _cap_nhat_tong_hop(tai_lieu)
    db.session.commit()

    if os.path.exists(duong_dan_tuyet_doi):
        try:
            os.remove(duong_dan_tuyet_doi)
        except OSError:
            current_app.logger.exception("Khong xoa duoc file vat ly %s", duong_dan_tuyet_doi)

    flash(f'Đã xoá file "{ten_hien_thi}" khỏi tài liệu.', "thanh_cong")
    return redirect(url_for("main.sua_tai_lieu", tai_lieu_id=tai_lieu.id))


