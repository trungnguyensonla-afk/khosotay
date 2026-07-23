"""Trích xuất nội dung văn bản từ file PDF (có sẵn lớp chữ) và file Word.
PDF dạng scan (ảnh, không có lớp chữ) sẽ được đánh dấu cần OCR - xử lý ở bước sau (mục 4.2).
"""
import pdfplumber
from docx import Document as TaiLieuWord

# Dưới ngưỡng số ký tự này coi như PDF không có lớp chữ (bản scan ảnh), cần OCR
NGUONG_KY_TU_TOI_THIEU = 50

# Các ký tự KHÔNG tồn tại trong tiếng Việt (ü, ç, ñ, ö...) nhưng lại nằm trong cùng
# vùng mã Latin-1 với chữ có dấu tiếng Việt. Nếu xuất hiện trong văn bản, gần như chắc chắn
# lớp chữ có sẵn bị lỗi font (thường do máy scan/photocopy cũ dùng font TCVN3/VNI không
# có bảng ánh xạ Unicode đúng) -> không tin lớp chữ này, cần chạy OCR lại.
_KY_TU_BAO_HIEU_LOI_MA_HOA = set("üöäëïÿåøæçñßþðÜÖÄËÏŸÅØÆÇÑÞÐ")
_SO_KY_TU_LOI_TOI_DA_CHO_PHEP = 2  # cho phép vài ký tự lạc (VD: tên nước ngoài trích dẫn)


def _co_dau_hieu_loi_ma_hoa(text):
    so_ky_tu_loi = sum(1 for c in text if c in _KY_TU_BAO_HIEU_LOI_MA_HOA)
    return so_ky_tu_loi > _SO_KY_TU_LOI_TOI_DA_CHO_PHEP


def _lam_sach_text(text):
    """Bỏ ký tự NUL (\\x00) - PostgreSQL không cho phép ký tự này trong cột text.
    Một số PDF (font/encoding đặc biệt) trích xuất ra text có lẫn ký tự này."""
    return text.replace("\x00", "") if text else text


def _trich_xuat_pdf(duong_dan_tuyet_doi):
    doan_van = []
    with pdfplumber.open(duong_dan_tuyet_doi) as pdf:
        for trang in pdf.pages:
            chu = trang.extract_text()
            if chu:
                doan_van.append(chu)
    return _lam_sach_text("\n".join(doan_van).strip())


def _trich_xuat_docx(duong_dan_tuyet_doi):
    tai_lieu = TaiLieuWord(duong_dan_tuyet_doi)
    doan_van = [p.text for p in tai_lieu.paragraphs if p.text.strip()]
    for bang in tai_lieu.tables:
        for hang in bang.rows:
            for o in hang.cells:
                if o.text.strip():
                    doan_van.append(o.text)
    return _lam_sach_text("\n".join(doan_van).strip())


def trich_xuat_noi_dung(duong_dan_tuong_doi, duong_dan_tuyet_doi):
    """Trả về dict: noi_dung_text (str|None), can_ocr (bool), loi (str|None)."""
    duoi = duong_dan_tuong_doi.rsplit(".", 1)[-1].lower()

    try:
        if duoi == "pdf":
            text = _trich_xuat_pdf(duong_dan_tuyet_doi)
            if len(text) < NGUONG_KY_TU_TOI_THIEU:
                return {"noi_dung_text": None, "can_ocr": True, "loi": None}
            if _co_dau_hieu_loi_ma_hoa(text):
                # Lớp chữ có sẵn nhưng có vẻ bị lỗi mã hóa (mất dấu tiếng Việt) - chạy OCR lại cho chắc
                return {"noi_dung_text": None, "can_ocr": True, "loi": None}
            return {"noi_dung_text": text, "can_ocr": False, "loi": None}

        if duoi == "docx":
            text = _trich_xuat_docx(duong_dan_tuyet_doi)
            return {"noi_dung_text": text or None, "can_ocr": False, "loi": None}

        if duoi == "doc":
            return {
                "noi_dung_text": None,
                "can_ocr": False,
                "loi": "File .doc (định dạng Word cũ) chưa hỗ trợ tự động trích xuất nội dung. "
                       "Vui lòng mở file và lưu lại dưới dạng .docx rồi nạp lại.",
            }
    except Exception as loi_ngoai_le:
        return {"noi_dung_text": None, "can_ocr": False, "loi": f"Lỗi khi trích xuất nội dung: {loi_ngoai_le}"}

    return {"noi_dung_text": None, "can_ocr": False, "loi": "Định dạng file không được hỗ trợ."}
