from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid

class SocietyCreate(BaseModel):
    name: str
    address: str

class Society(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    address: str
    admin_id: Optional[str] = None
    status: Literal["active", "blocked"] = "active"
    shopping_link: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SocietyResponse(BaseModel):
    id: str
    name: str
    address: str
    admin_id: Optional[str] = None
    status: str
    shopping_link: Optional[str] = None
    created_at: datetime

class WingCreate(BaseModel):
    name: str
    society_id: str

class Wing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    society_id: str
    name: str
    sub_admin_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WingResponse(BaseModel):
    id: str
    society_id: str
    name: str
    sub_admin_id: Optional[str] = None
    sub_admin_name: Optional[str] = None
    created_at: datetime

class FlatCreate(BaseModel):
    wing_id: str
    number: str
    floor: int

class Flat(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wing_id: str
    society_id: str
    number: str
    floor: int
    is_active: bool = True
    resident_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FlatResponse(BaseModel):
    id: str
    wing_id: str
    society_id: str
    number: str
    floor: int
    is_active: bool
    resident_id: Optional[str] = None
    resident_name: Optional[str] = None
    wing_name: Optional[str] = None
    created_at: datetime

class FlatToggle(BaseModel):
    is_active: bool
