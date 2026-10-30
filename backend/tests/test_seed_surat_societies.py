import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role, SocietyStatus, UserStatus
from app.models.identity import Society, User, UserRole
from scripts import seed_surat_societies as seed_mod


def test_seed_data_is_well_formed():
    names = [s[0] for s in seed_mod.SURAT_SOCIETIES]
    assert len(seed_mod.SURAT_SOCIETIES) == 20
    assert len(set(names)) == 20
    assert len(set(seed_mod.DEFAULT_MOBILES)) == 20
    assert all(len(m) == 10 and m.isdigit() for m in seed_mod.DEFAULT_MOBILES)
    assert all(len(s[2]) == 6 and s[2].isdigit() for s in seed_mod.SURAT_SOCIETIES)


async def test_seed_creates_active_societies_with_one_admin_each(db_session: AsyncSession):
    # Distinct from the placeholder range so the test can't collide with other fixtures.
    mobiles = [str(9100000101 + i) for i in range(20)]
    rows = await seed_mod.seed(db_session, mobiles)
<<<<<<< HEAD
    assert len(rows) == 20 and all(r["created"] for r in rows)
=======
    assert len(rows) == 20
>>>>>>> 191853d0b99367296d07aeb3fd7615459bc0b889

    surat = (
        await db_session.execute(select(Society).where(Society.city == "Surat"))
    ).scalars().all()
    assert len(surat) >= 20
    assert all(s.status == SocietyStatus.ACTIVE and s.state == "Gujarat" for s in surat)

    for r in rows:
        admin = (
            await db_session.execute(select(User).where(User.mobile == r["mobile"]))
        ).scalar_one()
        assert admin.status == UserStatus.ACTIVE
        roles = (
            await db_session.execute(select(UserRole).where(UserRole.user_id == admin.id))
        ).scalars().all()
        assert [Role(x.role) for x in roles] == [Role.ADMIN]


async def test_seed_is_idempotent(db_session: AsyncSession):
    mobiles = [str(9200000101 + i) for i in range(20)]
    await seed_mod.seed(db_session, mobiles)
    again = await seed_mod.seed(db_session, mobiles)
    assert not any(r["created"] for r in again)


async def test_seed_rejects_bad_mobile_lists(db_session: AsyncSession):
    with pytest.raises(ValueError):
        await seed_mod.seed(db_session, ["9000000001"])
    with pytest.raises(ValueError):
        await seed_mod.seed(db_session, ["9000000001"] * 20)
