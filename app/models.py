from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import Computed
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.extensions import db, login_manager

VAI_TRO_HOP_LE = ("admin", "bien_tap", "tra_cuu")


class LinhVuc(db.Model):
    """Danh mục lĩnh vực (VD: Đất đai, Môi trường, Trồng trọt...)."""

    __tablename__ = "linh_vuc"

    id = db.Column(db.Integer, primary_key=True)
    ten = db.Column(db.String(255), nullable=False, unique=True)

    tai_lieu = db.relationship("TaiLieu", back_populates="linh_vuc")

    def __repr__(self):
        return f"<LinhVuc {self.ten}>"


class DonVi(db.Model):
    """Danh mục đơn vị quản lý tài liệu (phòng/chi cục/đơn vị sự nghiệp thuộc Sở) / đơn vị công tác của
    người dùng. Không phải "đơn vị ban hành" theo nghĩa văn bản hành chính (thường là UBND tỉnh, Bộ NN&MT)."""

    __tablename__ = "don_vi"

    id = db.Column(db.Integer, primary_key=True)
    ten = db.Column(db.String(255), nullable=False, unique=True)

    tai_lieu = db.relationship("TaiLieu", back_populates="don_vi")
    nguoi_dung = db.relationship("NguoiDung", back_populates="don_vi")

    def __repr__(self):
        return f"<DonVi {self.ten}>"


class NguoiDung(UserMixin, db.Model):
    """Tài khoản người dùng hệ thống."""

    __tablename__ = "nguoi_dung"

    id = db.Column(db.Integer, primary_key=True)
    ten_dang_nhap = db.Column(db.String(100), nullable=False, unique=True)
    mat_khau_hash = db.Column(db.String(255), nullable=False)
    ho_ten = db.Column(db.String(255), nullable=False)
    don_vi_id = db.Column(db.Integer, db.ForeignKey("don_vi.id"), nullable=True)
    vai_tro = db.Column(db.String(20), nullable=False, default="tra_cuu")
    # Phục vụ chức năng khóa tài khoản ở mục 4.7 (Giai đoạn 2)
    dang_hoat_dong = db.Column(db.Boolean, nullable=False, default=True)

    don_vi = db.relationship("DonVi", back_populates="nguoi_dung")
    tai_lieu_da_nap = db.relationship("TaiLieu", back_populates="nguoi_nap")

    __table_args__ = (
        db.CheckConstraint(f"vai_tro IN {VAI_TRO_HOP_LE}", name="ck_nguoi_dung_vai_tro"),
    )

    # Flask-Login dùng thuộc tính is_active để chặn tài khoản bị khóa đăng nhập
    @property
    def is_active(self):
        return self.dang_hoat_dong

    def la_admin(self):
        return self.vai_tro == "admin"

    def la_bien_tap(self):
        return self.vai_tro in ("admin", "bien_tap")

    def __repr__(self):
        return f"<NguoiDung {self.ten_dang_nhap}>"


class TaiLieu(db.Model):
    """Tài liệu / văn bản trong kho."""

    __tablename__ = "tai_lieu"

    id = db.Column(db.Integer, primary_key=True)
    tieu_de = db.Column(db.String(500), nullable=False)
    so_hieu = db.Column(db.String(100), nullable=True)
    # Cơ quan ban hành văn bản (VD: UBND tỉnh Sơn La, Bộ NN&MT) - khác với don_vi_id
    # (đơn vị nội bộ Sở quản lý tài liệu này), xem ghi chú ở model DonVi.
    co_quan_ban_hanh = db.Column(db.String(255), nullable=True)
    linh_vuc_id = db.Column(db.Integer, db.ForeignKey("linh_vuc.id"), nullable=True)
    don_vi_id = db.Column(db.Integer, db.ForeignKey("don_vi.id"), nullable=True)
    loai_van_ban = db.Column(db.String(50), nullable=True)
    tinh_trang = db.Column(db.String(50), nullable=True, default="Còn hiệu lực")
    ngay_ban_hanh = db.Column(db.Date, nullable=True)
    ngay_het_hieu_luc = db.Column(db.Date, nullable=True)
    phien_ban = db.Column(db.String(20), nullable=True)
    # Tóm tắt do biên tập tự viết (không bắt buộc) - hiển thị ở trang chủ thay cho việc
    # cắt thô đoạn đầu noi_dung_text, vì nội dung trích xuất/OCR thô đọc lôm côm.
    tom_tat = db.Column(db.Text, nullable=True)
    # Nội dung tổng hợp từ tất cả file đính kèm (bảng tep_tai_lieu) - ghép theo thu_tu,
    # phục vụ tìm kiếm toàn văn qua noi_dung_tsv bên dưới. Xem TepTaiLieu cho nội dung riêng từng file.
    noi_dung_text = db.Column(db.Text, nullable=True)
    ngay_nap = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    nguoi_nap_id = db.Column(db.Integer, db.ForeignKey("nguoi_dung.id"), nullable=True)
    # Trạng thái xử lý trích xuất/OCR: hoan_thanh / dang_xu_ly / loi (mục 4.2)
    trang_thai_xu_ly = db.Column(db.String(20), nullable=False, default="hoan_thanh")
    # Tăng mỗi khi có người mở trang chi tiết - phục vụ mục "Tài liệu xem nhiều" ở trang chủ
    luot_xem = db.Column(db.Integer, nullable=False, default=0)

    # Cột tìm kiếm toàn văn (mục 4.3) - PostgreSQL tự tính lại mỗi khi tieu_de/so_hieu/
    # noi_dung_text thay đổi, không cần code Python cập nhật. Dùng config 'simple' (không
    # stem/bỏ dấu) để giữ đúng dấu tiếng Việt theo lưu ý Phụ lục B điểm 2.
    noi_dung_tsv = db.Column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple', coalesce(tieu_de, '')), 'A') || "
            "setweight(to_tsvector('simple', coalesce(so_hieu, '')), 'B') || "
            "setweight(to_tsvector('simple', coalesce(co_quan_ban_hanh, '')), 'B') || "
            "setweight(to_tsvector('simple', coalesce(noi_dung_text, '')), 'C')",
            persisted=True,
        ),
    )

    linh_vuc = db.relationship("LinhVuc", back_populates="tai_lieu")
    don_vi = db.relationship("DonVi", back_populates="tai_lieu")
    nguoi_nap = db.relationship("NguoiDung", back_populates="tai_lieu_da_nap")
    tep_dinh_kem = db.relationship(
        "TepTaiLieu",
        back_populates="tai_lieu",
        order_by="TepTaiLieu.thu_tu",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index("ix_tai_lieu_noi_dung_tsv", "noi_dung_tsv", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<TaiLieu {self.tieu_de}>"


class TepTaiLieu(db.Model):
    """Một file vật lý đính kèm vào tài liệu - 1 tài liệu (sổ tay) có thể gồm nhiều file
    (VD: Phần 1, Phần 2, Phụ lục) ghép chung nội dung tìm kiếm về TaiLieu.noi_dung_text."""

    __tablename__ = "tep_tai_lieu"

    id = db.Column(db.Integer, primary_key=True)
    tai_lieu_id = db.Column(db.Integer, db.ForeignKey("tai_lieu.id"), nullable=False, index=True)
    duong_dan_file = db.Column(db.String(1000), nullable=False)
    thu_tu = db.Column(db.Integer, nullable=False, default=0)
    noi_dung_text = db.Column(db.Text, nullable=True)
    # Trạng thái xử lý riêng của file này: hoan_thanh / dang_xu_ly / loi
    trang_thai_xu_ly = db.Column(db.String(20), nullable=False, default="hoan_thanh")
    ngay_them = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    tai_lieu = db.relationship("TaiLieu", back_populates="tep_dinh_kem")

    def __repr__(self):
        return f"<TepTaiLieu {self.duong_dan_file}>"


class ThongBao(db.Model):
    """Tin thông báo do admin đăng ở trang chủ (VD: văn bản mới cập nhật, lịch tập huấn...).
    Có thể gắn kèm 1 tài liệu liên quan (không bắt buộc) để bấm vào xem thẳng tài liệu đó."""

    __tablename__ = "thong_bao"

    id = db.Column(db.Integer, primary_key=True)
    tieu_de = db.Column(db.String(500), nullable=False)
    tai_lieu_id = db.Column(db.Integer, db.ForeignKey("tai_lieu.id"), nullable=True)
    ngay_dang = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    nguoi_dang_id = db.Column(db.Integer, db.ForeignKey("nguoi_dung.id"), nullable=True)

    tai_lieu = db.relationship("TaiLieu")
    nguoi_dang = db.relationship("NguoiDung")

    def __repr__(self):
        return f"<ThongBao {self.tieu_de}>"


@login_manager.user_loader
def tai_nguoi_dung(user_id):
    return db.session.get(NguoiDung, int(user_id))
