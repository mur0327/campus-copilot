import sqlalchemy as sa

from alembic import op

revision = "20260704_01"
down_revision = "20260625_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 문서 단위 검색 키워드(어휘 갭 보완용 문서 확장). 색인 시 LLM이 생성해 BM25 입력에만 얹는다.
    op.add_column("documents", sa.Column("search_keywords", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "search_keywords")
