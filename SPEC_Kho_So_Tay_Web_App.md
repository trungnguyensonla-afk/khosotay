# ĐẶC TẢ YÊU CẦU — WEB APP "KHO SỔ TAY HƯỚNG DẪN ĐIỆN TỬ"

> Tài liệu đề bài để phát triển bằng Claude Code.
> Đơn vị: Trung tâm Khuyến nông và Chuyển đổi số — Sở Nông nghiệp và Môi trường tỉnh Sơn La.

---

## 1. MỤC TIÊU

Xây dựng một web app để lưu trữ, số hóa (OCR tiếng Việt), phân loại và **tra cứu toàn văn** các văn bản, quy trình, sổ tay hướng dẫn nghiệp vụ của ngành nông nghiệp và môi trường. Chạy trên máy chủ Windows Server do Sở quản lý, **công khai trên Internet** — ai cũng truy cập và tra cứu được, không cần tài khoản. Đăng nhập chỉ dành cho cán bộ biên tập/quản trị để nạp và quản lý tài liệu.

> **Cập nhật 2026-07-22:** ban đầu đặc tả ghi "nội bộ, không mở ra Internet" — đã điều chỉnh lại theo đúng mục tiêu thực tế của đơn vị: hệ thống chạy công khai trên máy chủ của Sở, phục vụ cả cán bộ lẫn người dân/doanh nghiệp tra cứu. Xem lại mục 4.1 và mục 6 (Bảo mật) đã cập nhật theo hướng này.

**Nguyên tắc thiết kế:** đơn giản, dễ dùng cho cán bộ không chuyên IT; giao diện tiếng Việt hoàn toàn; ưu tiên tốc độ tra cứu.

---

## 2. CÔNG NGHỆ (TECH STACK) — BẮT BUỘC

- **Ngôn ngữ:** Python 3.11+
- **Khung web:** Flask (nhẹ, dễ bảo trì). Dùng Jinja2 template cho giao diện server-side.
- **Cơ sở dữ liệu:** PostgreSQL 16 (dùng full-text search sẵn có cho tiếng Việt). Giai đoạn dev có thể dùng SQLite, nhưng thiết kế phải sẵn sàng chuyển sang PostgreSQL.
- **OCR:** Tesseract OCR (engine) + thư viện `pytesseract`, dùng gói ngôn ngữ tiếng Việt `vie`. OCR chạy tại chỗ trên máy chủ, KHÔNG gửi tài liệu ra dịch vụ ngoài.
- **Đọc file:** `PyPDF2`/`pdfplumber` cho PDF có sẵn text; `pdf2image` + Tesseract cho PDF scan; `python-docx` cho file Word.
- **Giao diện:** HTML + CSS + JavaScript thuần (hoặc Bootstrap 5 cho nhanh). KHÔNG dùng framework phức tạp. Ưu tiên tải nhanh, đơn giản.
- **Máy chủ chạy:** Windows Server. Dùng `waitress` làm WSGI server (chạy tốt trên Windows, không cần Linux).

**Lưu ý cho Claude Code:** toàn bộ phải chạy được trên Windows Server không cần Docker. Không phụ thuộc dịch vụ đám mây. Tất cả thư viện đều mã nguồn mở, miễn phí.

---

## 3. MÔ HÌNH DỮ LIỆU

### Bảng `tai_lieu` (tài liệu)
| Trường | Kiểu | Mô tả |
|---|---|---|
| id | Khóa chính tự tăng | |
| tieu_de | Văn bản | Tiêu đề tài liệu |
| so_hieu | Văn bản | Số hiệu văn bản (VD: 1693/SKHCN-CĐS) |
| linh_vuc_id | Khóa ngoại | Liên kết bảng lĩnh vực |
| don_vi_id | Khóa ngoại | Liên kết bảng đơn vị quản lý |
| loai_van_ban | Văn bản | Sổ tay / Quy trình / Hướng dẫn / Mẫu biểu / QPPL / Quyết định / Quy định |
| tinh_trang | Văn bản | Còn hiệu lực / Hết hiệu lực / Đang rà soát |
| ngay_ban_hanh | Ngày | |
| ngay_het_hieu_luc | Ngày | Có thể trống |
| phien_ban | Văn bản | VD: 1.0, 2.1 |
| noi_dung_text | Văn bản dài | Nội dung tổng hợp từ tất cả file đính kèm (bảng `tep_tai_lieu`) — phục vụ tìm kiếm toàn văn |
| ngay_nap | Ngày giờ | Tự động khi nạp |
| nguoi_nap_id | Khóa ngoại | Liên kết bảng người dùng |

### Bảng `tep_tai_lieu` (file đính kèm — bổ sung 2026-07-22)
Một tài liệu (sổ tay) có thể gồm nhiều file (VD: Phần 1, Phần 2, Phụ lục) — trước đây thiết kế 1 tài liệu = 1 file (`tai_lieu.duong_dan_file`), nay tách thành bảng riêng để 1 tài liệu chứa nhiều file.

| Trường | Kiểu | Mô tả |
|---|---|---|
| id | Khóa chính | |
| tai_lieu_id | Khóa ngoại | Liên kết bảng `tai_lieu` |
| duong_dan_file | Văn bản | Đường dẫn file gốc trên ổ đĩa |
| thu_tu | Số nguyên | Thứ tự hiển thị (Phần 1, Phần 2...) |
| noi_dung_text | Văn bản dài | Nội dung trích xuất/OCR riêng của file này |
| trang_thai_xu_ly | Văn bản | Trạng thái xử lý riêng file này: hoan_thanh / dang_xu_ly / loi |
| ngay_them | Ngày giờ | |

Nội dung + trạng thái của `tai_lieu` là **tổng hợp** từ các file con (ghép `noi_dung_text` theo `thu_tu`, trạng thái ưu tiên "đang xử lý" nếu còn file nào đang OCR).

### Bảng `linh_vuc` (lĩnh vực)
Danh mục cố định, quản trị viên thêm/sửa. Giá trị khởi tạo: Đất đai, Môi trường, Khoáng sản, Trồng trọt, Chăn nuôi, Thú y, Lâm nghiệp, Bảo vệ thực vật, Thủy sản, Thủy lợi, Tài nguyên nước, Phòng chống thiên tai, OCOP, Nông thôn mới, Khuyến nông, Phát triển nông thôn. Bổ sung 2026-07-22: Lĩnh vực chung, Thủ tục hành chính (dùng cho tài liệu không thuộc riêng một lĩnh vực chuyên môn nào, hoặc là hướng dẫn thủ tục hành chính chung), Chuyển đổi số.

### Bảng `don_vi` (đơn vị quản lý)
Danh mục các phòng/chi cục/đơn vị sự nghiệp thuộc Sở — **không phải "đơn vị ban hành" theo nghĩa văn bản hành chính** (đơn vị ban hành văn bản thường là UBND tỉnh, Bộ NN&MT chứ không phải các phòng ban nội bộ), nên nhãn trong giao diện gọi là "Đơn vị quản lý". Quản trị viên thêm/sửa qua trang Quản trị → Danh mục.

Danh sách hiện tại (cập nhật 2026-07-22 theo Điều 3, Quyết định số 552/QĐ-UBND ngày 24/02/2026 của UBND tỉnh Sơn La quy định cơ cấu tổ chức Sở Nông nghiệp và Môi trường — file gốc `552.pdf.pdf`):
- **7 phòng chuyên môn:** Văn phòng, Phòng Tổ chức cán bộ, Phòng Kế hoạch - Tài chính, Phòng Địa chất và Khoáng sản, Phòng Quản lý tài nguyên đất, Phòng Quản lý môi trường, Phòng Đo đạc, Bản đồ và Viễn thám.
- **5 chi cục:** Chi cục Trồng trọt và Bảo vệ thực vật, Chi cục Chăn nuôi, Thú y và Thủy sản, Chi cục Kiểm lâm, Chi cục Thủy lợi và Tài nguyên nước, Chi cục Phát triển nông thôn.
- **3 đơn vị sự nghiệp:** Văn phòng Đăng ký đất đai, Trung tâm Khuyến nông và Chuyển đổi số, Trung tâm Nước và Quan trắc môi trường.

### Bảng `nguoi_dung` (người dùng)
| Trường | Kiểu | Mô tả |
|---|---|---|
| id | Khóa chính | |
| ten_dang_nhap | Văn bản | |
| mat_khau_hash | Văn bản | Mật khẩu mã hóa (dùng bcrypt/werkzeug) |
| ho_ten | Văn bản | |
| don_vi_id | Khóa ngoại | Đơn vị công tác |
| vai_tro | Văn bản | admin / bien_tap / tra_cuu |

---

## 4. CHỨC NĂNG CHI TIẾT

### 4.1. Đăng nhập / Phân quyền
- **Tra cứu (tìm kiếm, xem chi tiết, xem trước/tải file, hỏi chatbox AI) là công khai — không cần đăng nhập.** Bất kỳ ai vào trang cũng dùng được.
- Đăng nhập bằng tài khoản + mật khẩu chỉ áp dụng cho việc **nạp/sửa tài liệu và trang quản trị**. Mật khẩu lưu dạng mã hóa (KHÔNG lưu văn bản thô).
- Ba vai trò (chỉ liên quan tới phần cần đăng nhập):
  - **admin:** toàn quyền — quản lý người dùng, danh mục, tài liệu.
  - **bien_tap:** nạp, sửa, gán nhãn tài liệu.
  - **tra_cuu:** vai trò tài khoản nội bộ mức thấp nhất (không có quyền biên tập) — không phải điều kiện để xem tài liệu công khai, vì phần tra cứu đã mở cho tất cả kể cả người chưa đăng nhập.
- Phân quyền theo đơn vị: cân nhắc cho phép giới hạn tài liệu nhạy cảm chỉ hiển thị cho đơn vị liên quan (giai đoạn 2, chưa bắt buộc ở bản đầu).

### 4.2. Nạp tài liệu (chức năng cốt lõi)
- **Một tài liệu có thể gồm nhiều file** (VD: sổ tay chia thành Phần 1, Phần 2, Phụ lục) — form nạp cho chọn nhiều file cùng lúc, gộp chung vào 1 bản ghi tài liệu. Có thể thêm/xoá file cho tài liệu đã có ở trang sửa tài liệu (phải còn tối thiểu 1 file).

Luồng xử lý khi người dùng tải file lên:
1. Nhận file (PDF hoặc Word, có thể nhiều file cùng lúc). Lưu từng file gốc vào thư mục có cấu trúc trên ổ đĩa (VD: `data/files/2026/07/`).
2. Trích xuất nội dung văn bản:
   - Nếu **PDF có sẵn text** hoặc **file Word** → trích trực tiếp (nhanh).
   - Nếu **PDF scan (ảnh)** → chuyển từng trang thành ảnh, chạy Tesseract OCR ngôn ngữ `vie`, ghép văn bản.
3. Lưu văn bản trích xuất vào trường `noi_dung_text` để phục vụ tìm kiếm.
4. Cho phép người nạp điền/sửa thông tin: tiêu đề, số hiệu, lĩnh vực, đơn vị, loại, tình trạng hiệu lực, ngày.
5. (Nâng cao) Tự động gợi ý lĩnh vực dựa trên từ khóa trong nội dung — xem mục 4.6.

**Yêu cầu OCR:**
- Ngôn ngữ tiếng Việt (`vie`), giữ đúng dấu.
- Xử lý được tài liệu nhiều trang (hàng trăm trang) — chạy nền, không treo giao diện.
- Hiển thị trạng thái xử lý (đang OCR / hoàn thành / lỗi).

### 4.3. Tìm kiếm toàn văn (chức năng cốt lõi)
- Ô tìm kiếm chính: gõ từ khóa, tìm trong **cả tiêu đề và nội dung** (`noi_dung_text`).
- Dùng full-text search của PostgreSQL, hỗ trợ tiếng Việt có dấu.
- Kết quả hiển thị: tiêu đề, số hiệu, đơn vị, lĩnh vực, đoạn trích chứa từ khóa (highlight từ khóa).
- Tốc độ mục tiêu: dưới 2 giây với vài nghìn tài liệu.

### 4.4. Bộ lọc và duyệt
- Lọc theo: lĩnh vực, đơn vị quản lý, loại văn bản, tình trạng hiệu lực, khoảng thời gian ban hành.
- Cho phép lọc kết hợp nhiều tiêu chí cùng lúc.
- Sắp xếp: mới nhất, tên A-Z, theo đơn vị.

### 4.5. Xem và tải tài liệu
- Xem thông tin chi tiết tài liệu + nội dung văn bản đã trích.
- Xem trước file gốc (PDF) trong trình duyệt.
- Tải file gốc về.

### 4.6. Tự động gợi ý lĩnh vực (nâng cao, có thể làm giai đoạn 2)
- Khi nạp tài liệu, hệ thống quét `noi_dung_text` theo bộ từ khóa của từng lĩnh vực, tự gợi ý lĩnh vực phù hợp để người nạp xác nhận.
- Bộ từ khóa lưu trong file cấu hình, admin sửa được. (Xem Phụ lục A.)

### 4.7. Quản trị (chỉ admin)
- Quản lý người dùng (thêm/sửa/khóa tài khoản, đặt lại mật khẩu).
- Quản lý danh mục lĩnh vực, đơn vị, loại văn bản.
- Xem thống kê: tổng số tài liệu, số tài liệu theo lĩnh vực/đơn vị, tỷ lệ còn/hết hiệu lực.

### 4.8. Sao lưu
- Chức năng xuất toàn bộ dữ liệu (database + file gốc) ra thư mục sao lưu có ngày tháng.
- Hướng dẫn khôi phục.

### 4.9. Thông báo + Tài liệu xem nhiều ở trang chủ (đã triển khai 2026-07-22)
- Cột phải trang chủ gồm 2 khung: **Thông báo** (admin tự soạn đăng ở Quản trị → Thông báo, có thể gắn kèm 1 tài liệu liên quan để bấm vào xem thẳng; trang `/thong-bao` xem toàn bộ) và **Tài liệu xem nhiều** (tự động xếp theo số lượt xem thật, tăng mỗi khi có người mở trang chi tiết tài liệu — cột `tai_lieu.luot_xem`).
- Bố cục theo mẫu do người dùng cung cấp (`Giaodien.png`).

### 4.10. Chatbox trợ lý AI hỏi-đáp trên tài liệu (đã triển khai 2026-07-22)
- Khung chat nổi ở góc màn hình, có ở mọi trang công khai, không cần đăng nhập.
- Trả lời dựa trên nội dung tài liệu đã có trong kho (RAG đơn giản): mỗi câu hỏi được tìm tài liệu liên quan bằng full-text search PostgreSQL (OR các từ khóa nội dung, không AND cả câu để tránh trượt hết vì từ nối kiểu "như thế nào"), cắt đoạn trích quanh vị trí có mật độ từ khóa dày nhất (có tránh phần mục lục), rồi gửi kèm câu hỏi cho model AI trả lời — không dùng kiến thức ngoài tài liệu, luôn nêu tên tài liệu nguồn.
- Dùng **Anthropic Claude API** (model mặc định `claude-haiku-4-5`, cấu hình qua biến môi trường `ANTHROPIC_MODEL`) — nghĩa là nội dung câu hỏi + đoạn trích tài liệu liên quan **được gửi ra ngoài tới Anthropic** để xử lý (khác với OCR/tìm kiếm chạy hoàn toàn tại chỗ). Đây là đánh đổi có chủ đích để có chất lượng trả lời tốt hơn, đã được xác nhận khi quyết định chuyển hệ thống sang chạy công khai trên Internet.
- Cần điền `ANTHROPIC_API_KEY` vào `.env` (lấy tại console.anthropic.com) — nếu chưa điền, chatbox báo "chưa được cấu hình" thay vì lỗi.
- Có giới hạn tốc độ đơn giản theo IP (mặc định 15 lượt / 5 phút) để chặn spam vì gọi API tốn phí — không phải cơ chế bảo mật chặt, xem thêm mục 6.
- Có giữ ngữ cảnh hội thoại nhiều lượt (client gửi kèm lịch sử vài lượt gần nhất).

---

## 5. GIAO DIỆN — YÊU CẦU

- **Tiếng Việt hoàn toàn**, thuật ngữ hành chính chuẩn (không dịch máy khó hiểu).
- Màu chủ đạo: xanh lá (tông chuyển đổi số ngành nông nghiệp), sạch, dễ đọc.
- Bố cục: thanh tìm kiếm nổi bật trên cùng; menu trái (danh mục lĩnh vực, đơn vị); vùng kết quả bên phải.
- Responsive cơ bản (dùng được trên máy tính bảng).
- Font dễ đọc trên màn hình.
- Tối giản: mỗi màn hình phục vụ một mục đích rõ ràng, tránh nhồi nhét.

**Các màn hình chính:**
1. Trang chủ / Tìm kiếm (ô tìm kiếm lớn + kết quả) — công khai, không cần đăng nhập.
2. Danh sách tài liệu (có bộ lọc bên trái) — công khai.
3. Chi tiết tài liệu (thông tin + xem trước + tải về) — công khai.
4. Chatbox trợ lý AI (khung nổi trên mọi trang công khai) — công khai.
5. Đăng nhập — chỉ cần cho cán bộ biên tập/quản trị.
6. Nạp tài liệu (form upload + điền thông tin) — cần đăng nhập (bien_tap/admin).
7. Quản trị (người dùng, danh mục, thống kê) — chỉ admin.

---

## 6. YÊU CẦU PHI CHỨC NĂNG

- **Bảo mật:** hệ thống chạy công khai trên Internet (không còn giới hạn trong mạng nội bộ) — cần HTTPS ở tầng triển khai (reverse proxy/IIS), mật khẩu mã hóa, không đặt dữ liệu nhạy cảm trên URL. Vì công khai, KHÔNG được nạp lên các tài liệu có nội dung mật/nhạy cảm không dành cho công chúng — việc kiểm soát nội dung nào được nạp là trách nhiệm của cán bộ biên tập khi upload, hệ thống không tự phân loại mật/không mật. Các thao tác ghi (nạp/sửa tài liệu, quản trị) vẫn yêu cầu đăng nhập như mục 4.1. Chatbox AI (mục 4.9) có giới hạn tốc độ theo IP để tránh bị lạm dụng gọi API tốn phí.
- **Hiệu năng:** tìm kiếm < 2 giây với ~5.000 tài liệu. OCR chạy nền.
- **Triển khai:** chạy trên Windows Server không cần Docker. Có tài liệu hướng dẫn cài đặt kèm theo.
- **Bảo trì:** code có chú thích tiếng Việt ở các phần quan trọng; cấu trúc rõ ràng để người khác tiếp quản được.
- **Mở rộng:** thiết kế có API (REST) để sau này tích hợp với hệ thống khác của tỉnh (LGSP, kho dữ liệu dùng chung).

---

## 7. PHÂN KỲ PHÁT TRIỂN (đề xuất cho Claude Code làm từng bước)

**Giai đoạn 1 — Lõi (ưu tiên):**
- Cơ sở dữ liệu + mô hình dữ liệu.
- Đăng nhập, phân quyền cơ bản.
- Nạp tài liệu + OCR tiếng Việt + trích xuất văn bản.
- Tìm kiếm toàn văn + bộ lọc.
- Xem/tải tài liệu.

**Giai đoạn 2 — Hoàn thiện:**
- Tự động gợi ý lĩnh vực theo từ khóa.
- Trang quản trị + thống kê.
- Sao lưu.
- Phân quyền theo đơn vị.

**Giai đoạn 3 — Nâng cao:**
- ✅ Trợ lý AI hỏi-đáp trên nội dung tài liệu (chatbox công khai, dùng Anthropic Claude API) — xem mục 4.9. Hoàn thành 2026-07-22.
- ⏳ API tích hợp hệ thống tỉnh (LGSP, kho dữ liệu dùng chung) — chưa làm.
- ⏳ Dashboard giám sát hiệu lực văn bản — chưa làm.

---

## PHỤ LỤC A — BỘ TỪ KHÓA TỰ ĐỘNG PHÂN LOẠI THEO LĨNH VỰC

Dùng cho chức năng 4.6. Mỗi lĩnh vực gắn với danh sách từ khóa; nếu nội dung tài liệu chứa từ khóa, gợi ý lĩnh vực tương ứng.

- **Đất đai:** giấy chứng nhận quyền sử dụng đất, chuyển mục đích, thu hồi đất, giao đất, cho thuê đất, quy hoạch sử dụng đất
- **Môi trường:** đánh giá tác động môi trường, quan trắc, nước thải, khí thải, chất thải rắn, chất thải nguy hại, giấy phép môi trường
- **Khoáng sản:** khai thác khoáng sản, thăm dò, cấp phép khoáng sản, vật liệu xây dựng
- **Trồng trọt:** trồng trọt, canh tác, giống cây trồng, phân bón, cà phê, cây ăn quả
- **Chăn nuôi:** chăn nuôi, gia súc, gia cầm, thức ăn chăn nuôi
- **Thú y:** thú y, tiêm phòng, vắc xin, dịch bệnh động vật, kiểm dịch động vật
- **Lâm nghiệp:** lâm nghiệp, kiểm lâm, bảo vệ rừng, lâm sản, phòng cháy chữa cháy rừng, trồng rừng
- **Bảo vệ thực vật:** bảo vệ thực vật, kiểm dịch thực vật, thuốc bảo vệ thực vật, sâu bệnh
- **Thủy sản:** thủy sản, nuôi trồng thủy sản, khai thác thủy sản, giống thủy sản
- **Thủy lợi:** thủy lợi, công trình thủy lợi, hồ chứa, đập, kênh mương, tưới tiêu
- **Tài nguyên nước:** tài nguyên nước, nước ngầm, nước mặt, giấy phép khai thác nước, lưu vực sông
- **Phòng chống thiên tai:** phòng chống thiên tai, lũ lụt, sạt lở, hạn hán, ứng phó thiên tai, tìm kiếm cứu nạn
- **OCOP:** OCOP, sản phẩm nông thôn, phân hạng sản phẩm, mỗi xã một sản phẩm
- **Nông thôn mới:** nông thôn mới, xã đạt chuẩn, tiêu chí nông thôn
- **Khuyến nông:** khuyến nông, mô hình trình diễn, chuyển giao kỹ thuật, tập huấn
- **Phát triển nông thôn:** phát triển nông thôn, hợp tác xã, kinh tế hợp tác, giảm nghèo

---

## PHỤ LỤC B — LƯU Ý KỸ THUẬT QUAN TRỌNG CHO CLAUDE CODE

1. **OCR tiếng Việt là điểm khó nhất.** Cần cài Tesseract engine trên máy chủ Windows và gói ngôn ngữ `vie` (file `vie.traineddata`). Hướng dẫn cài đặt Tesseract trên Windows phải nằm trong tài liệu triển khai.
2. **Full-text search tiếng Việt:** PostgreSQL hỗ trợ full-text search; cần cấu hình đúng để xử lý dấu tiếng Việt. Nếu khó, phương án dự phòng: chuẩn hóa Unicode (NFC) trước khi index và tìm kiếm.
3. **Xử lý tài liệu lớn (hàng trăm trang):** OCR phải chạy ở tiến trình nền (background task), tránh làm treo giao diện web. Có thể dùng hàng đợi đơn giản (threading hoặc `RQ`/`Celery` nếu cần).
4. **File gốc lưu ngoài database**, chỉ lưu đường dẫn trong database — tránh phình database.
5. **Không cần Docker.** Toàn bộ chạy trực tiếp trên Windows Server bằng Python + waitress.
6. **Kèm file hướng dẫn cài đặt** (README tiếng Việt): cài Python, cài PostgreSQL, cài Tesseract + gói vie, chạy app.
