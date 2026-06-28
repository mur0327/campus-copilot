import sqlalchemy as sa

from alembic import op

revision = "20260625_01"
down_revision = "20260506_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("source_scope", sa.Text(), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "documents",
        sa.Column("page_kind", sa.Text(), nullable=False, server_default="unknown"),
    )
    op.alter_column("documents", "source_scope", server_default=None)
    op.alter_column("documents", "page_kind", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "page_kind")
    op.drop_column("documents", "source_scope")
