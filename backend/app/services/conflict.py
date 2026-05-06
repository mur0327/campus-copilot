from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import ConflictPair
from app.schemas.chat import ConflictWarning

DEFAULT_CONFLICT_DESCRIPTION = "관련 문서 간 내용 차이가 있어 담당 부서 확인이 필요합니다."


async def load_conflict_warning(session: AsyncSession, chunk_ids: list[UUID]) -> ConflictWarning:
    if not chunk_ids:
        return ConflictWarning(exists=False)
    result = await session.execute(
        select(ConflictPair).where(
            ConflictPair.is_resolved.is_(False),
            or_(
                ConflictPair.chunk_a_id.in_(chunk_ids),
                ConflictPair.chunk_b_id.in_(chunk_ids),
            ),
        )
    )
    conflict = result.scalars().first()
    if conflict is None:
        return ConflictWarning(exists=False)
    return ConflictWarning(
        exists=True,
        description=build_conflict_description(conflict),
    )


def build_conflict_description(conflict: ConflictPair) -> str:
    if conflict.description:
        return conflict.description
    if conflict.conflict_type:
        return f"{conflict.conflict_type} 항목에서 문서 간 내용 차이가 있습니다."
    return DEFAULT_CONFLICT_DESCRIPTION
