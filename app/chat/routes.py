import re
import threading
import time
import unicodedata
from collections import defaultdict

from flask import Blueprint, current_app, jsonify, request, url_for
from sqlalchemy import func

from app.models import TaiLieu

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

SO_TAI_LIEU_TOI_DA = 5
DO_DAI_DOAN_TRICH = 700
DO_DAI_CAU_HOI_TOI_DA = 500
SO_LUOT_TRAO_DOI_GIU_LAI = 3  # số lượt hỏi-đáp trước đó gửi kèm làm ngữ cảnh hội thoại
DO_DAI_TIN_NHAN_CU_TOI_DA = 800

# Giới hạn tốc độ đơn giản theo IP (hệ thống công khai, gọi API trả phí) -
# không cần chính xác tuyệt đối nên dùng bộ nhớ trong tiến trình, không cần Redis.
GIOI_HAN_SO_LUOT = 15
GIOI_HAN_CUA_SO_GIAY = 300
_lich_su_yeu_cau = defaultdict(list)
_khoa_lich_su = threading.Lock()

# Danh sách các từ (đã bỏ dấu) không mang nhiều ý nghĩa tìm kiếm trong câu hỏi tự nhiên -
# tách theo từng từ đơn (câu hỏi được regex tách token trước khi so với danh sách này).
TU_DUNG = {
    "la", "va", "co", "cho", "cua", "trong", "nhung", "khong", "the", "voi", "nao",
    "gi", "duoc", "de", "khi", "nhu", "theo", "tai", "sao", "vay", "thi", "ban", "toi",
    "muon", "can", "hoi", "biet", "lam", "hay", "neu", "roi", "moi", "mot", "nay",
    "do", "day", "kia", "minh", "chung", "anh", "chi", "xin", "giup", "hien",
    "dang", "se", "phai", "tu", "den", "ve", "qua", "bang", "sau", "truoc", "tren",
    "duoi", "giua", "ngoai", "nhieu", "it", "rat",
}


def _bo_dau(chuoi):
    return "".join(
        c for c in unicodedata.normalize("NFD", chuoi) if unicodedata.category(c) != "Mn"
    ).lower()


def _tach_tu_khoa(cau_hoi):
    tu = re.findall(r"[\wÀ-ỹ]+", cau_hoi.lower())
    return [t for t in tu if len(t) >= 3 and _bo_dau(t) not in TU_DUNG]


SO_LAN_KHOP_TOI_DA_MOI_TU = 15
CUA_SO_DEM_MAT_DO_TU_KHOA = 400


def _lay_doan_lien_quan(noi_dung, tu_khoa_list, do_dai=DO_DAI_DOAN_TRICH):
    """Cắt đoạn quanh vị trí có mật độ từ khóa dày nhất trong tài liệu để làm ngữ cảnh cho AI.

    Chỉ lấy vị trí khớp đầu tiên của từ khóa dễ rơi vào phần mục lục ở đầu các sổ tay dài
    (mục lục cũng liệt kê đủ từ khóa nhưng không phải nội dung trả lời) - nên quét nhiều vị
    trí khớp rồi chọn nơi có nhiều từ khóa khác nhau xuất hiện gần nhau nhất.
    """
    if not noi_dung:
        return ""
    if not tu_khoa_list:
        doan = noi_dung[:do_dai]
        return doan + ("…" if len(noi_dung) > do_dai else "")

    noi_dung_thuong = noi_dung.lower()
    ung_vien = []
    for tu in tu_khoa_list:
        vi_tri, so_lan = 0, 0
        while so_lan < SO_LAN_KHOP_TOI_DA_MOI_TU:
            idx = noi_dung_thuong.find(tu, vi_tri)
            if idx == -1:
                break
            ung_vien.append(idx)
            vi_tri = idx + len(tu)
            so_lan += 1

    if not ung_vien:
        doan = noi_dung[:do_dai]
        return doan + ("…" if len(noi_dung) > do_dai else "")

    # Các sổ tay dài thường có mục lục chi tiết ở đầu, liệt kê lại gần hết tiêu đề mục -
    # dày đặc từ khóa hơn cả nội dung thật. Nhận diện mục lục qua dấu chấm dẫn dòng kiểu
    # "................. 39" rồi loại các vị trí khớp rơi vào đó ra trước, nếu còn ứng
    # viên nào ngoài mục lục thì ưu tiên chọn trong số đó.
    mau_dan_dong_muc_luc = re.compile(r"\.{5,}\s*\d{1,4}")
    khong_phai_muc_luc = [
        vt for vt in ung_vien
        if not mau_dan_dong_muc_luc.search(noi_dung[max(0, vt - 200):vt + 200])
    ]
    ung_vien_can_xet = khong_phai_muc_luc or ung_vien

    vi_tri_tot_nhat, diem_tot_nhat = ung_vien_can_xet[0], -1.0
    for vt in ung_vien_can_xet:
        vung_lan_can = noi_dung_thuong[max(0, vt - CUA_SO_DEM_MAT_DO_TU_KHOA):vt + CUA_SO_DEM_MAT_DO_TU_KHOA]
        diem = sum(1 for tu in tu_khoa_list if tu in vung_lan_can)
        # Ưu tiên nhẹ vị trí nằm sâu hơn trong tài liệu để tránh phần đầu hay là mục lục/lời mở đầu
        diem += (vt / len(noi_dung)) * 2
        if diem > diem_tot_nhat:
            diem_tot_nhat, vi_tri_tot_nhat = diem, vt

    bat_dau = max(0, vi_tri_tot_nhat - 150)
    ket_thuc = min(len(noi_dung), vi_tri_tot_nhat + do_dai)
    return ("…" if bat_dau > 0 else "") + noi_dung[bat_dau:ket_thuc] + ("…" if ket_thuc < len(noi_dung) else "")


def _tim_tai_lieu_lien_quan(cau_hoi, tu_khoa_list):
    # Câu hỏi tự nhiên có nhiều từ nối (vd "như thế nào", "cần gì") - nếu AND hết cả câu
    # (như websearch_to_tsquery làm mặc định) thì gần như không tài liệu nào khớp đủ.
    # Ở đây OR các từ khóa nội dung đã lọc bớt từ nối, xếp hạng theo ts_rank để tài liệu
    # khớp nhiều từ hơn lên trên - phù hợp truy hồi (recall) cho chatbox hơn là tìm chính xác.
    chuoi_truy_van = " OR ".join(tu_khoa_list) if tu_khoa_list else cau_hoi
    truy_van_tsv = func.websearch_to_tsquery("simple", chuoi_truy_van)
    ket_qua = (
        TaiLieu.query.filter(
            TaiLieu.noi_dung_tsv.op("@@")(truy_van_tsv),
            TaiLieu.noi_dung_text.isnot(None),
        )
        .order_by(func.ts_rank(TaiLieu.noi_dung_tsv, truy_van_tsv).desc())
        .limit(SO_TAI_LIEU_TOI_DA)
        .all()
    )
    return ket_qua


def _kiem_tra_gioi_han_toc_do(ip):
    bay_gio = time.monotonic()
    with _khoa_lich_su:
        lan_goi = _lich_su_yeu_cau[ip]
        lan_goi[:] = [t for t in lan_goi if bay_gio - t < GIOI_HAN_CUA_SO_GIAY]
        if len(lan_goi) >= GIOI_HAN_SO_LUOT:
            return False
        lan_goi.append(bay_gio)
        return True


def _xay_noi_dung_nguoi_dung(cau_hoi, tai_lieu_lien_quan, tu_khoa_list):
    if not tai_lieu_lien_quan:
        phan_ngu_canh = "(Không tìm thấy tài liệu nào trong kho khớp với câu hỏi này.)"
    else:
        khoi = []
        for i, tl in enumerate(tai_lieu_lien_quan, start=1):
            doan = _lay_doan_lien_quan(tl.noi_dung_text, tu_khoa_list)
            thong_tin = f"{i}. \"{tl.tieu_de}\""
            if tl.so_hieu:
                thong_tin += f" (Số hiệu: {tl.so_hieu})"
            if tl.loai_van_ban:
                thong_tin += f" - {tl.loai_van_ban}"
            if tl.tinh_trang:
                thong_tin += f" - {tl.tinh_trang}"
            khoi.append(f"{thong_tin}\nTrích đoạn: {doan}")
        phan_ngu_canh = "\n\n".join(khoi)

    return (
        f"[Trích đoạn tài liệu liên quan tìm được trong kho]\n{phan_ngu_canh}\n\n"
        f"[Câu hỏi của người dùng]\n{cau_hoi}"
    )


HE_THONG_PROMPT = (
    "Bạn là trợ lý tra cứu văn bản của Kho Sổ tay Hướng dẫn Điện tử - "
    "Sở Nông nghiệp và Môi trường tỉnh Sơn La. Nhiệm vụ của bạn là trả lời câu hỏi của "
    "cán bộ và người dân CHỈ dựa trên các trích đoạn tài liệu được cung cấp trong mỗi lượt hỏi.\n\n"
    "Quy tắc bắt buộc:\n"
    "- Chỉ trả lời dựa trên nội dung trích đoạn được cung cấp. Không tự suy diễn hay bịa thêm quy định.\n"
    "- Nếu trích đoạn không đủ thông tin để trả lời, nói rõ là chưa tìm thấy nội dung phù hợp trong kho tài liệu, "
    "gợi ý người dùng thử từ khóa khác hoặc liên hệ đơn vị chuyên môn - không được bịa câu trả lời.\n"
    "- Khi trả lời, luôn nêu rõ trả lời dựa trên tài liệu nào (tên tài liệu, số hiệu nếu có).\n"
    "- Trả lời ngắn gọn, rõ ràng, bằng tiếng Việt, đúng trọng tâm câu hỏi.\n"
    "- Đây là văn bản hành chính/kỹ thuật, không phải tư vấn pháp lý chính thức - nếu câu hỏi mang tính pháp lý phức tạp, "
    "nhắc người dùng đối chiếu lại với văn bản gốc hoặc hỏi trực tiếp đơn vị quản lý."
)


@chat_bp.route("/hoi", methods=["POST"])
def hoi():
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"loi": "Chatbox AI chưa được cấu hình trên máy chủ. Liên hệ quản trị viên."}), 503

    # Lưu ý: X-Forwarded-For có thể bị giả mạo nếu máy chủ không đứng sau reverse proxy
    # đáng tin cậy (nginx/IIS) loại bỏ header client tự gửi - chỉ dùng để hạn chế spam nhẹ,
    # không phải cơ chế bảo mật chặt.
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    if not _kiem_tra_gioi_han_toc_do(ip):
        return jsonify({"loi": "Bạn hỏi hơi nhanh, vui lòng thử lại sau vài phút."}), 429

    du_lieu = request.get_json(silent=True) or {}
    cau_hoi = str(du_lieu.get("cau_hoi", "")).strip()[:DO_DAI_CAU_HOI_TOI_DA]
    if not cau_hoi:
        return jsonify({"loi": "Vui lòng nhập câu hỏi."}), 400

    lich_su_tho = du_lieu.get("lich_su") or []
    tin_nhan = []
    for luot in lich_su_tho[-(SO_LUOT_TRAO_DOI_GIU_LAI * 2):]:
        vai_tro = luot.get("vai_tro")
        noi_dung = str(luot.get("noi_dung", "")).strip()[:DO_DAI_TIN_NHAN_CU_TOI_DA]
        if vai_tro in ("nguoi_dung", "tro_ly") and noi_dung:
            tin_nhan.append({"role": "user" if vai_tro == "nguoi_dung" else "assistant", "content": noi_dung})

    tu_khoa_list = _tach_tu_khoa(cau_hoi)
    try:
        tai_lieu_lien_quan = _tim_tai_lieu_lien_quan(cau_hoi, tu_khoa_list)
    except Exception:
        current_app.logger.exception("Loi tim tai lieu lien quan cho chatbox AI")
        tai_lieu_lien_quan = []

    tin_nhan.append({"role": "user", "content": _xay_noi_dung_nguoi_dung(cau_hoi, tai_lieu_lien_quan, tu_khoa_list)})

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        phan_hoi = client.messages.create(
            model=current_app.config.get("ANTHROPIC_MODEL", "claude-haiku-4-5"),
            max_tokens=800,
            temperature=0.3,
            system=HE_THONG_PROMPT,
            messages=tin_nhan,
        )
        tra_loi = "".join(khoi.text for khoi in phan_hoi.content if khoi.type == "text").strip()
    except Exception:
        current_app.logger.exception("Loi goi Anthropic API cho chatbox AI")
        return jsonify({"loi": "Không gọi được trợ lý AI lúc này, vui lòng thử lại sau."}), 502

    nguon = [
        {
            "id": tl.id,
            "tieu_de": tl.tieu_de,
            "so_hieu": tl.so_hieu,
            "url": url_for("main.chi_tiet_tai_lieu", tai_lieu_id=tl.id),
        }
        for tl in tai_lieu_lien_quan
    ]

    return jsonify({"tra_loi": tra_loi, "nguon": nguon})
