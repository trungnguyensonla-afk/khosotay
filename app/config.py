import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "chuoi-bi-mat-mac-dinh-chi-dung-khi-dev")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://khosotay_app:khosotay_app@localhost:5432/khosotay_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "data", "files"))
    POPPLER_PATH = os.environ.get("POPPLER_PATH") or None
    TESSERACT_CMD = os.environ.get("TESSERACT_CMD") or None
    PG_DUMP_CMD = os.environ.get("PG_DUMP_CMD", "pg_dump")
    BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(BASE_DIR, "backups"))
    # Chatbox AI hỏi-đáp trên nội dung tài liệu (Giai đoạn 3 SPEC) - dùng Anthropic Claude API
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
    # Giới hạn dung lượng file nạp - đủ cho tài liệu vài trăm trang, tránh treo máy chủ vì file quá lớn
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024
