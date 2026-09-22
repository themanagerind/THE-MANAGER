"""Notice service — Section 19."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import Notice


async def create_notice(db: AsyncSession, society_id: uuid.UUID, created_by: uuid.UUID, title: str, content: str) -> Notice:
    notice = Notice(society_id=society_id, title=title, content=content, created_by=created_by)
    db.add(notice)
    await db.commit()
    await db.refresh(notice)
    return notice


async def list_notices(db: AsyncSession, society_id: uuid.UUID, skip: int = 0, limit: int = 20) -> tuple[list[Notice], int]:
    """Section 49.7 RESOLVED — every role sees the same society-wide list;
    no wing/row audience targeting exists."""
    from sqlalchemy import func
    total = (await db.execute(select(func.count()).select_from(Notice).where(Notice.society_id == society_id))).scalar_one()
    rows = (
        await db.execute(
            select(Notice).where(Notice.society_id == society_id)
            .order_by(Notice.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return rows, total
