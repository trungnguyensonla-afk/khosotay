import sys
from datetime import datetime

from flask import Flask

from app.config import Config
from app.extensions import db, migrate, login_manager


def create_app(config_class=Config):
    # Console Windows mặc định dùng bảng mã cp1252/850, không hiển thị được nhiều ký tự
    # tiếng Việt có dấu (VD: Đ, ư...) -> log lỗi/lệnh CLI in tiếng Việt sẽ crash UnicodeEncodeError.
    # Ép stdout/stderr sang UTF-8 ngay từ đầu để chạy ổn định trên máy chủ Windows.
    for luong in (sys.stdout, sys.stderr):
        try:
            luong.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app import models  # noqa: F401  (đảm bảo model được đăng ký với SQLAlchemy)

    from app.auth import auth_bp
    from app.main import main_bp
    from app.admin import admin_bp
    from app.chat import chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(chat_bp)

    from app.cli import dang_ky_cli
    dang_ky_cli(app)

    @app.context_processor
    def bien_dung_chung():
        return {"nam_hien_tai": datetime.now().year}

    return app
