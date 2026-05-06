import sqlalchemy as sa

from alembic import op

revision = "20260506_01"
down_revision = "20260419_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crawl_jobs",
        sa.Column("total_pages", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "crawl_jobs",
        sa.Column("processed_pages", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("crawl_jobs", sa.Column("current_stage", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("crawl_jobs", "current_stage")
    op.drop_column("crawl_jobs", "processed_pages")
    op.drop_column("crawl_jobs", "total_pages")
