# HƯỚNG DẪN TRIỂN KHAI LÊN MÁY CHỦ (CHẠY CÔNG KHAI TRÊN INTERNET)

> Áp dụng cho máy chủ Windows Server (vật lý hoặc cloud) chưa có tên miền — truy cập tạm qua địa chỉ IP. Khi nào có tên miền, xem mục 9 để nâng cấp lên HTTPS.
> Tất cả lệnh chạy trong **PowerShell với quyền Administrator** trừ khi ghi chú khác.

---

## 1. Yêu cầu máy chủ

- Windows Server (2016 trở lên) hoặc Windows 10/11 Pro dùng làm máy chủ.
- Tối thiểu 4GB RAM, 20GB ổ trống còn trống (nhiều hơn nếu kho tài liệu lớn — file gốc + bản sao lưu chiếm dung lượng).
- Có địa chỉ IP mà máy tính khác trên Internet gọi tới được (IP công khai, hoặc máy chủ cloud đã có sẵn). Việc này do bộ phận IT/mạng của Sở xác nhận — nếu máy đứng sau NAT/router thì cần cấu hình port-forwarding ở router trỏ vào máy chủ trước khi làm mục 8.
- Quyền Administrator trên máy chủ.

---

## 2. Đưa mã nguồn lên máy chủ

Dự án hiện **chưa dùng Git**, nên cách đơn giản nhất là nén thư mục dự án rồi copy sang máy chủ.

Trên máy dev (`G:\Khosotay`), **loại trừ** các thư mục sau khi nén (không cần thiết / sẽ tạo lại trên máy chủ):
- `.venv\` (môi trường ảo Python — cài lại trên máy chủ, không copy qua)
- `__pycache__\`
- `backups\` (bản sao lưu của máy dev, không cần trên máy chủ)
- `.env` (chứa mật khẩu/API key của máy dev — **không copy trực tiếp**, sẽ tạo `.env` mới cho máy chủ ở mục 5)

Ví dụ nén bằng PowerShell trên máy dev:

```powershell
Compress-Archive -Path G:\Khosotay\* -DestinationPath C:\tam\khosotay_trien_khai.zip -Force
```

(Xoá `.venv`, `__pycache__`, `backups` trong file zip nếu `Compress-Archive` gộp hết — hoặc copy thủ công qua Explorer/RDP chỉ những gì cần.)

Copy file zip sang máy chủ (USB, RDP copy-paste, hoặc `scp`/`robocopy` qua mạng nội bộ nếu 2 máy nối được nhau), rồi giải nén vào ví dụ `C:\KhoSoTay\`.

> **Khuyến nghị cho lần sau:** nếu muốn cập nhật code dễ dàng hơn (không phải nén/copy thủ công mỗi lần sửa), có thể khởi tạo Git cho dự án và đẩy lên một kho lưu trữ riêng (GitHub private, hoặc Git server nội bộ của Sở), rồi trên máy chủ chỉ cần `git pull`. Đây là việc làm thêm, không bắt buộc — báo tôi nếu bạn muốn thiết lập.

---

## 3. Cài phần mềm nền trên máy chủ

Mở PowerShell (Administrator) và cài lần lượt (dùng `winget`, có sẵn trên Windows Server 2022+/Windows 11; nếu máy chủ cũ hơn không có `winget`, tải cài đặt thủ công từ trang chủ từng phần mềm):

```powershell
# Python 3.11+
winget install --id Python.Python.3.12 -e

# PostgreSQL 17
winget install --id PostgreSQL.PostgreSQL.17 -e

# Tesseract OCR (kèm gói tiếng Việt cần cài thêm - xem bên dưới)
winget install --id UB-Mannheim.TesseractOCR -e

# Poppler (cần cho đọc PDF scan)
winget install --id oschwartz10612.Poppler -e
```

Sau khi cài Tesseract, tải gói ngôn ngữ tiếng Việt `vie.traineddata` (nếu trình cài đặt chưa kèm sẵn) và đặt vào thư mục `tessdata` trong thư mục cài Tesseract (thường là `C:\Program Files\Tesseract-OCR\tessdata\`). Có thể tải từ kho `tessdata` chính thức của dự án Tesseract trên GitHub.

Ghi lại đường dẫn cài đặt thực tế của từng phần mềm (khác nhau tuỳ máy) — sẽ cần điền vào `.env` ở mục 5:
- `tesseract.exe` — thường `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Thư mục `bin` của Poppler — thường trong `C:\Users\<user>\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_...\poppler-*\Library\bin`
- `pg_dump.exe` — thường `C:\Program Files\PostgreSQL\17\bin\pg_dump.exe`

---

## 4. Tạo database PostgreSQL

Mở `psql` (hoặc pgAdmin nếu quen dùng giao diện) bằng tài khoản `postgres` vừa cài, rồi chạy:

```sql
CREATE DATABASE khosotay_db;
CREATE USER khosotay_app WITH PASSWORD 'đặt-mật-khẩu-mạnh-ở-đây';
GRANT ALL PRIVILEGES ON DATABASE khosotay_db TO khosotay_app;
\c khosotay_db
GRANT ALL ON SCHEMA public TO khosotay_app;
```

> Đặt mật khẩu mạnh, khác với mật khẩu dùng ở máy dev — đây là máy chủ công khai trên Internet.

---

## 5. Cài thư viện Python + cấu hình `.env`

Trong thư mục dự án trên máy chủ (`C:\KhoSoTay`):

```powershell
cd C:\KhoSoTay
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Tạo file `.env` mới (KHÔNG copy nguyên `.env` từ máy dev) với nội dung:

```
DATABASE_URL=postgresql+psycopg2://khosotay_app:mật-khẩu-đã-đặt-ở-mục-4@localhost:5432/khosotay_db
SECRET_KEY=<tạo-chuỗi-ngẫu-nhiên-mới-ở-dưới>
UPLOAD_DIR=data/files
POPPLER_PATH=<đường-dẫn-bin-poppler-trên-máy-chủ>
TESSERACT_CMD=<đường-dẫn-tesseract.exe-trên-máy-chủ>
PG_DUMP_CMD=<đường-dẫn-pg_dump.exe-trên-máy-chủ>
ANTHROPIC_API_KEY=<key-thật-lấy-tại-console.anthropic.com>
ANTHROPIC_MODEL=claude-haiku-4-5
PORT=80
```

Tạo `SECRET_KEY` mới (không dùng lại giá trị của máy dev):

```powershell
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
```

Dán kết quả vào `SECRET_KEY=` trong `.env`.

> `PORT=80` để truy cập trực tiếp `http://<IP-máy-chủ>` không cần gõ thêm cổng. Có thể để cổng khác (VD 5000) nếu cổng 80 đã bị chiếm bởi IIS/dịch vụ khác trên máy — khi đó người dùng phải gõ `http://<IP>:5000`.

---

## 6. Khởi tạo cấu trúc database

```powershell
cd C:\KhoSoTay
$env:FLASK_APP = "run.py"
.venv\Scripts\flask db upgrade
```

Lệnh này tạo toàn bộ bảng theo đúng cấu trúc hiện tại (kể cả các thay đổi gần đây: bảng `tep_tai_lieu`, cột tìm kiếm toàn văn...).

---

## 7. Tạo tài khoản quản trị đầu tiên

Database mới hoàn toàn trống, chưa có tài khoản nào — dùng lệnh sau (đã thêm riêng cho việc này):

```powershell
.venv\Scripts\flask tao-admin
```

Lệnh sẽ hỏi lần lượt: tên đăng nhập, họ tên, mật khẩu (gõ 2 lần để xác nhận). Tài khoản tạo ra có quyền admin — sau khi đăng nhập, có thể vào trang Quản trị để tạo thêm tài khoản khác cho cán bộ.

---

## 8. Chạy thử thủ công (kiểm tra trước khi cài làm dịch vụ)

```powershell
.venv\Scripts\python serve.py
```

Nếu thấy dòng `Đang chạy Kho Sổ Tay Hướng Dẫn Điện Tử tại cổng 80 ...` là đã chạy được. Từ máy khác trong cùng mạng, thử mở `http://<IP-nội-bộ-máy-chủ>` xem có vào được không. Bấm `Ctrl+C` để dừng thử nghiệm trước khi làm bước tiếp theo.

**Mở Windows Firewall cho cổng đã chọn** (ví dụ cổng 80):

```powershell
New-NetFirewallRule -DisplayName "Kho So Tay - HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
```

Nếu máy chủ là máy cloud (AWS/Azure/VNPT Cloud/Viettel Cloud...), **còn phải mở thêm ở Security Group / firewall của nhà cung cấp cloud** — phần này làm ở trang quản trị cloud, không phải trên Windows. Nếu máy chủ đứng sau router/NAT của Sở, cần nhờ bộ phận mạng mở port-forward TCP 80 (và 443 sau này) trỏ vào máy chủ.

Sau khi mở firewall, thử truy cập `http://<IP-công-khai-máy-chủ>` **từ mạng ngoài** (VD dùng 4G thay vì wifi cơ quan) để chắc chắn Internet gọi vào được, không chỉ mạng nội bộ.

---

## 9. Chạy như dịch vụ Windows (để tự khởi động cùng máy, không cần mở sẵn cửa sổ console)

Dùng công cụ miễn phí **NSSM** (Non-Sucking Service Manager) để biến `serve.py` thành dịch vụ Windows chạy nền:

```powershell
winget install --id NSSM.NSSM -e
nssm install KhoSoTay "C:\KhoSoTay\.venv\Scripts\python.exe" "C:\KhoSoTay\serve.py"
nssm set KhoSoTay AppDirectory "C:\KhoSoTay"
nssm set KhoSoTay AppEnvironmentExtra PYTHONUTF8=1
nssm start KhoSoTay
```

Kiểm tra dịch vụ đã chạy: `Get-Service KhoSoTay`. Từ giờ mỗi khi máy chủ khởi động lại, hệ thống tự chạy theo, không cần đăng nhập RDP mở console tay.

Xem log dịch vụ (nếu lỗi): `nssm` mặc định không ghi log ra file — có thể cấu hình thêm bằng `nssm set KhoSoTay AppStdout C:\KhoSoTay\logs\out.log` và `AppStderr` tương tự nếu cần debug sau này.

---

## 10. (Khuyến nghị, làm sau khi có tên miền) Nâng cấp lên HTTPS

Hiện tại trang chạy HTTP thuần — **trình duyệt sẽ báo "Không an toàn"**, và mật khẩu đăng nhập cán bộ gửi đi không được mã hoá trên đường truyền. Chấp nhận được để chạy thử/ra mắt sớm, nhưng nên nâng cấp HTTPS sớm nhất có thể, đặc biệt trước khi cán bộ dùng thật để đăng nhập nạp tài liệu.

Khi Sở có tên miền trỏ vào máy chủ (VD `sotay.sonla.gov.vn`), cách đơn giản nhất trên Windows là dùng **Caddy** làm reverse proxy — tự động xin và gia hạn chứng chỉ HTTPS miễn phí (Let's Encrypt), không cần thao tác thủ công:

```powershell
winget install --id CaddyServer.Caddy -e
```

Tạo file `Caddyfile` (VD `C:\Caddy\Caddyfile`):

```
sotay.sonla.gov.vn {
    reverse_proxy localhost:80
}
```

Đổi cổng ứng dụng Flask (`PORT` trong `.env`) sang cổng khác (VD 5000) để nhường cổng 80/443 cho Caddy, sau đó chạy Caddy như dịch vụ (`caddy run --config C:\Caddy\Caddyfile`, hoặc cài làm Windows Service tương tự NSSM). Khi đó người dùng vào `https://sotay.sonla.gov.vn` là có HTTPS đầy đủ, Caddy tự lo chứng chỉ.

*(Nếu Sở đã dùng IIS sẵn cho các hệ thống khác, có thể dùng IIS + module Application Request Routing (ARR) làm reverse proxy thay Caddy — phức tạp hơn, báo tôi nếu cần hướng dẫn riêng theo hướng IIS.)*

---

## 11. Kiểm tra sau khi triển khai (checklist)

- [ ] Vào `http://<IP-hoặc-domain>` từ máy ngoài mạng Sở (VD 4G) — trang chủ hiện ra, không cần đăng nhập.
- [ ] Tìm kiếm thử 1 từ khóa — ra kết quả.
- [ ] Đăng nhập bằng tài khoản admin vừa tạo — vào được trang Quản trị.
- [ ] Nạp thử 1 tài liệu PDF — trích xuất nội dung thành công.
- [ ] Hỏi thử chatbox AI — trả lời được, có trích nguồn tài liệu (xác nhận `ANTHROPIC_API_KEY` hoạt động).
- [ ] Khởi động lại máy chủ (hoặc `Restart-Service KhoSoTay`) — dịch vụ tự chạy lại, không cần thao tác tay.
- [ ] Vào Quản trị → Sao lưu, bấm chạy thử sao lưu — kiểm tra thư mục `backups\` có file mới.

---

## 12. Cập nhật phiên bản sau này

Khi có thay đổi code (tính năng mới, sửa lỗi):

1. Nén/copy code mới sang máy chủ (đè lên `C:\KhoSoTay`, **giữ nguyên** `.env`, `data\`, `backups\`, `.venv\` — chỉ đè code).
2. `Stop-Service KhoSoTay`
3. `.venv\Scripts\pip install -r requirements.txt` (nếu có thư viện mới)
4. `$env:FLASK_APP="run.py"; .venv\Scripts\flask db upgrade` (nếu có thay đổi cấu trúc database — luôn chạy lệnh này để chắc chắn, không tốn gì nếu không có gì mới)
5. `Start-Service KhoSoTay`
6. Kiểm tra lại vài mục trong checklist ở mục 11.
