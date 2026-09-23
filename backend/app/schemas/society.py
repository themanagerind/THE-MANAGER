"""Society request/response schemas — Section 5/6/25."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import SocietyStatus
from app.schemas.property import SocietyLocationCreateIn


class SocietySignupIn(BaseModel):
    """Admin self-signup for a new society (Section 26: Admin approval flow).
    Creates the Society (PENDING) and the Admin user (PENDING) together —
    both wait for Platform Owner approval before either becomes usable."""

    society_name: str
    society_code: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

    admin_full_name: str
    admin_mobile: str
    admin_email: str | None = None


class SocietySignupOut(BaseModel):
    society_id: uuid.UUID
    admin_user_id: uuid.UUID
    message: str = "Submitted — awaiting Platform Owner approval"


class SocietyCreateIn(BaseModel):
    """Platform Owner creates a society directly from their dashboard —
    the only way a society comes into existence now (SocietySignupIn's
    bundled self-service flow above stays for API compatibility but isn't
    linked from the signup page anymore). Goes straight to ACTIVE: the
    Platform Owner creating it IS the approval.

    `code` is never client-supplied — society_service.create_society
    auto-generates one and guarantees uniqueness, so two societies can
    never collide. Every field here is required EXCEPT `locations` and
    `latitude`/`longitude`: a society's identity/address should always be
    captured properly, but Wings/Rows are a genuine convenience — they
    can always be added later (either the Admin from their own
    Properties page, or the Platform Owner from the society's Edit view
    — see list_society_locations/add_society_location), so forcing them
    at creation time would just get in the way for a Platform Owner who
    doesn't have that detail yet. Same for the GPS pin — a Platform Owner
    may not have it handy at creation and can add it later via
    SocietyUpdateIn."""

    name: str
    address: str
    city: str
    state: str
    pincode: str
    locations: list[SocietyLocationCreateIn] = []
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _gps_both_or_neither(self) -> "SocietyCreateIn":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or neither")
        return self


class SocietyUpdateIn(BaseModel):
    """Platform Owner edits a society's profile after creation. `code` is
    deliberately not editable here — it's already shared with the
    society's Admin/Residents as their signup key; changing it would
    break their ability to find the society again. Locations aren't part
    of this request body either — they're listed/added via the separate
    GET/POST /societies/{id}/locations endpoints instead. `latitude`/
    `longitude` are optional here too, same as SocietyCreateIn — sending
    neither clears any GPS pin already on record."""

    name: str
    address: str
    city: str
    state: str
    pincode: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _gps_both_or_neither(self) -> "SocietyUpdateIn":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or neither")
        return self


class SocietyLookupOut(BaseModel):
    """Public, minimal — used by the Admin/Resident signup forms to find
    their society by its code without needing its internal UUID, and
    without exposing the full society list (that stays Platform-Owner-only)."""

    id: uuid.UUID
    name: str


class SocietySearchResultOut(BaseModel):
    """Public, minimal — powers a name-search picker as an alternative to
    typing the exact code. Deliberately excludes `code` (would let a
    stranger sign up as that society's Admin without ever asking the
    Platform Owner for the code) and address/pincode. Search is
    rate-limited and capped at a small result count (see
    society_service.search_societies_by_name) so it can't be used to
    enumerate the platform's full society list."""

    id: uuid.UUID
    name: str
    city: str | None


class SocietyOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    status: SocietyStatus
    address: str | None
    city: str | None
    state: str | None
    pincode: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SocietyStatusUpdateIn(BaseModel):
    status: SocietyStatus
