"""them cot co_quan_ban_hanh vao tai_lieu

Revision ID: dd20213a4db2
Revises: 5d79e0a61825
Create Date: 2026-07-23 07:57:06.227830

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd20213a4db2'
down_revision = '5d79e0a61825'
branch_labels = None
depends_on = None


def upgrade():
    # Cột co_quan_ban_hanh phải có trước khi noi_dung_tsv (generated column) tham chiếu tới nó.
    op.add_column('tai_lieu', sa.Column('co_quan_ban_hanh', sa.String(length=255), nullable=True))

    # Alembic autogenerate không phát hiện thay đổi công thức của cột GENERATED ALWAYS AS -
    # phải tự drop index + cột cũ rồi tạo lại với công thức mới (Postgres không cho ALTER công thức generated column).
    op.drop_index('ix_tai_lieu_noi_dung_tsv', table_name='tai_lieu')
    op.drop_column('tai_lieu', 'noi_dung_tsv')
    op.execute(
        """
        ALTER TABLE tai_lieu ADD COLUMN noi_dung_tsv tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(tieu_de, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(so_hieu, '')), 'B') ||
            setweight(to_tsvector('simple', coalesce(co_quan_ban_hanh, '')), 'B') ||
            setweight(to_tsvector('simple', coalesce(noi_dung_text, '')), 'C')
        ) STORED
        """
    )
    op.create_index('ix_tai_lieu_noi_dung_tsv', 'tai_lieu', ['noi_dung_tsv'], postgresql_using='gin')


def downgrade():
    op.drop_index('ix_tai_lieu_noi_dung_tsv', table_name='tai_lieu')
    op.drop_column('tai_lieu', 'noi_dung_tsv')
    op.execute(
        """
        ALTER TABLE tai_lieu ADD COLUMN noi_dung_tsv tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(tieu_de, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(so_hieu, '')), 'B') ||
            setweight(to_tsvector('simple', coalesce(noi_dung_text, '')), 'C')
        ) STORED
        """
    )
    op.create_index('ix_tai_lieu_noi_dung_tsv', 'tai_lieu', ['noi_dung_tsv'], postgresql_using='gin')
    op.drop_column('tai_lieu', 'co_quan_ban_hanh')
