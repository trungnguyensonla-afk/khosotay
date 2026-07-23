-- Chạy script này bằng psql với quyền superuser "postgres" để tạo database và user riêng cho app.
-- Cách chạy: psql -U postgres -f scripts/init_database.sql

CREATE DATABASE khosotay_db;

-- Đổi 'doi_mat_khau_nay' thành mật khẩu bạn muốn dùng cho app,
-- rồi cập nhật đúng mật khẩu này vào file .env (DATABASE_URL)
CREATE USER khosotay_app WITH PASSWORD 'doi_mat_khau_nay';

GRANT ALL PRIVILEGES ON DATABASE khosotay_db TO khosotay_app;

\c khosotay_db

GRANT ALL ON SCHEMA public TO khosotay_app;
