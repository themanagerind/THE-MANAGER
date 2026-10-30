"""Showcase signup prefill — Resident "Shop Now" (user-requested, design
reviewed with the Showcase team). showcase_prefill_service.
generate_prefill_token / redeem_prefill_token, and the API endpoints
around them. The token is deliberately opaque (no embedded data — see
ShowcasePrefillToken's docstring); Showcase's backend fetches the actual
profile data server-to-server via /redeem."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HouseType, LocationType, RelationshipType, Role, UserStatus
from app.models.identity import Property, PropertyResident, SocietyLocation, User, UserRole
from app.models.showcase_prefill import ShowcasePrefillToken
from app.services import showcase_prefill_service
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _seed_property(db_session: AsyncSession, society_id, house_number="A-1") -> Property:
    loc = SocietyLocation(society_id=society_id, name=f"Wing {uuid.uuid4().hex[:6]}", location_type=LocationType.WING)
    db_session.add(loc)
    await db_session.flush()
    prop = Property(
        society_id=society_id, location_id=loc.id, house_number=house_number,
        house_type=HouseType.FLAT, floor_number=4, status="ACTIVE",
    )
    db_session.add(prop)
    await db_session.commit()
    await db_session.refresh(prop)
    return prop


async def _seed_resident(
    db_session: AsyncSession, society_id, property_id, mobile: str,
    relationship_type: RelationshipType = RelationshipType.OWNER,
    email: str | None = None,
) -> User:
    resident = User(
        society_id=society_id, full_name="Ravi Verma", mobile=mobile, email=email, status=UserStatus.ACTIVE,
    )
    db_session.add(resident)
    await db_session.flush()
    db_session.add(UserRole(user_id=resident.id, role=Role.RESIDENT, assigned_at=datetime.now(timezone.utc)))
    if property_id is not None:
        db_session.add(
            PropertyResident(
                society_id=society_id, property_id=property_id, resident_id=resident.id,
                relationship_type=relationship_type, is_active=True, start_date=date.today(),
                created_at=datetime.now(timezone.utc),
            )
        )
    await db_session.commit()
    await db_session.refresh(resident)
    return resident


async def _set_society_address(db_session: AsyncSession, society_id) -> None:
    from app.models.identity import Society

    society = (await db_session.execute(select(Society).where(Society.id == society_id))).scalar_one()
    society.address = "AB Road"
    society.city = "Indore"
    society.state = "Madhya Pradesh"
    society.pincode = "452010"
    await db_session.commit()


async def test_generate_token_is_opaque_and_expires_in_5_minutes(
    db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9870000001")

    row = await showcase_prefill_service.generate_prefill_token(db_session, resident.id)

    assert len(row.token) >= 32  # base64url(32 random bytes) — opaque, no embedded data
    assert row.resident_id == resident.id
    assert row.is_used is False
    delta = row.expires_at - datetime.now(timezone.utc)
    assert timedelta(minutes=4, seconds=50) < delta <= timedelta(minutes=5, seconds=5)


async def test_redeem_returns_name_mobile_address_flat(db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    await _set_society_address(db_session, society_id)
    prop = await _seed_property(db_session, society_id, house_number="B-402")
    resident = await _seed_resident(db_session, society_id, prop.id, "9870000002", email="ravi@example.com")

    token_row = await showcase_prefill_service.generate_prefill_token(db_session, resident.id)
    data = await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token)

    assert data["name"] == "Ravi Verma"
    assert data["mobile"] == "9870000002"
    assert data["email"] == "ravi@example.com"
    assert data["address"]["city"] == "Indore"
    assert data["address"]["pincode"] == "452010"
    assert data["flat"]["number"] == "B-402"
    assert data["flat"]["floor"] == "4"


async def test_redeem_resident_with_no_active_property_returns_null_address_flat(
    db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    resident = await _seed_resident(db_session, society_id, None, "9870000003")

    token_row = await showcase_prefill_service.generate_prefill_token(db_session, resident.id)
    data = await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token)

    assert data["name"] == "Ravi Verma"
    assert data["address"] is None
    assert data["flat"] is None


async def test_redeem_marks_used_second_call_without_matching_request_id_is_410(
    db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9870000004")
    token_row = await showcase_prefill_service.generate_prefill_token(db_session, resident.id)

    await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token)

    with pytest.raises(HTTPException) as exc:
        await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token)
    assert exc.value.status_code == 410


async def test_redeem_retry_with_same_request_id_replays_success(
    db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9870000005")
    token_row = await showcase_prefill_service.generate_prefill_token(db_session, resident.id)

    first = await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token, request_id="sc-req-1")
    replay = await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token, request_id="sc-req-1")
    assert replay == first

    with pytest.raises(HTTPException) as exc:
        await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token, request_id="different")
    assert exc.value.status_code == 410


async def test_redeem_empty_string_request_id_never_replays(
    db_session: AsyncSession, two_societies_with_admins
):
    """Same audit finding as wallet-redemption verify: some client
    serializers send "" for an unset field instead of omitting it — this
    must behave identically to never sending a request_id at all."""
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9870000006")
    token_row = await showcase_prefill_service.generate_prefill_token(db_session, resident.id)

    await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token, request_id="")

    row = (
        await db_session.execute(select(ShowcasePrefillToken).where(ShowcasePrefillToken.id == token_row.id))
    ).scalar_one()
    assert row.consumed_request_id is None

    with pytest.raises(HTTPException) as exc:
        await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token, request_id="")
    assert exc.value.status_code == 410


async def test_redeem_expired_token_is_410(db_session: AsyncSession, two_societies_with_admins):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9870000007")
    token_row = await showcase_prefill_service.generate_prefill_token(db_session, resident.id)
    token_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await showcase_prefill_service.redeem_prefill_token(db_session, token_row.token)
    assert exc.value.status_code == 410


async def test_redeem_unknown_token_404(db_session: AsyncSession, two_societies_with_admins):
    with pytest.raises(HTTPException) as exc:
        await showcase_prefill_service.redeem_prefill_token(db_session, "not-a-real-token")
    assert exc.value.status_code == 404


# --- API endpoints -----------------------------------------------------------


async def test_resident_can_create_prefill_token_via_api(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9870000008")
    headers = auth_headers(resident.id, society_id, Role.RESIDENT, [Role.RESIDENT])

    resp = await client.post("/api/v1/showcase-prefill", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["token"]) >= 32
    assert "expires_at" in body


async def test_non_resident_cannot_create_prefill_token(client: AsyncClient, two_societies_with_admins):
    admin_id = two_societies_with_admins["a"]["admin_id"]
    society_id = two_societies_with_admins["a"]["society_id"]
    headers = auth_headers(admin_id, society_id, Role.ADMIN, [Role.ADMIN])

    resp = await client.post("/api/v1/showcase-prefill", headers=headers)
    assert resp.status_code == 403


async def test_redeem_endpoint_requires_store_api_key_and_retry_replays(
    client: AsyncClient, db_session: AsyncSession, two_societies_with_admins
):
    society_id = two_societies_with_admins["a"]["society_id"]
    prop = await _seed_property(db_session, society_id)
    resident = await _seed_resident(db_session, society_id, prop.id, "9870000009")
    token_row = await showcase_prefill_service.generate_prefill_token(db_session, resident.id)

    # No key at all.
    resp = await client.post("/api/v1/showcase-prefill/redeem", json={"token": token_row.token})
    assert resp.status_code == 401

    # Wrong key.
    resp = await client.post(
        "/api/v1/showcase-prefill/redeem", json={"token": token_row.token},
        headers={"X-Store-Api-Key": "totally-wrong"},
    )
    assert resp.status_code == 401

    # Correct key (matches ECOM_STORE_API_KEY seeded in conftest).
    headers = {"X-Store-Api-Key": "test-store-api-key-for-pytest-only"}
    resp = await client.post(
        "/api/v1/showcase-prefill/redeem", json={"token": token_row.token, "request_id": "sc-api-1"}, headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["mobile"] == "9870000009"

    # Same request_id again — safe retry, same 200.
    resp = await client.post(
        "/api/v1/showcase-prefill/redeem", json={"token": token_row.token, "request_id": "sc-api-1"}, headers=headers,
    )
    assert resp.status_code == 200

    # A different request_id against the now-used token is a clean 410.
    resp = await client.post(
        "/api/v1/showcase-prefill/redeem", json={"token": token_row.token, "request_id": "sc-api-2"}, headers=headers,
    )
    assert resp.status_code == 410
