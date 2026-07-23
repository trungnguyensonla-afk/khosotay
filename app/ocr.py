"""Chạy OCR tiếng Việt cho PDF dạng scan (ảnh) - dùng pdf2image + Tesseract.
Hàm ở đây được gọi từ một luồng nền (threading), không chạy trong request chính,
để tránh treo giao diện khi tài liệu có nhiều trang.
"""
import logging

import pytesseract
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)


def chay_ocr_pdf(duong_dan_tuyet_doi, poppler_path=None, tesseract_cmd=None, ngon_ngu="vie"):
    """Chuyển từng trang PDF thành ảnh rồi chạy Tesseract, ghép nội dung các trang lại."""
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    hinh_anh_cac_trang = convert_from_path(duong_dan_tuyet_doi, poppler_path=poppler_path)

    doan_van = []
    for so_trang, hinh in enumerate(hinh_anh_cac_trang, start=1):
        try:
            chu = pytesseract.image_to_string(hinh, lang=ngon_ngu)
        except Exception:
            logger.exception("Loi OCR trang %s cua file %s", so_trang, duong_dan_tuyet_doi)
            chu = ""
        if chu and chu.strip():
            doan_van.append(chu.strip())

    ket_qua = "\n".join(doan_van).strip()
    return ket_qua.replace("\x00", "")
