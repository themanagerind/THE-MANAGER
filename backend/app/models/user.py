from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid

class UserBase(BaseModel):
    mobile: str
    name: str
    email: Optional[str] = None

class UserCreate(BaseModel):
    mobile: str
    name: str
    password: str
    email: Optional[str] = None
    society_id: Optional[str] = None
    wing_id: Optional[str] = None
    flat_id: Optional[str] = None

class UserLogin(BaseModel):
    mobile: str
    password: str
    role: Optional[str] = None  # For role switching

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mobile: str
    name: str
    email: Optional[str] = None
    role: Literal["platform_owner", "admin", "sub_admin", "resident"] = "resident"
    society_id: Optional[str] = None
    wing_id: Optional[str] = None
    flat_id: Optional[str] = None
    status: Literal["pending", "active", "blocked"] = "pending"
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserResponse(BaseModel):
    id: str
    mobile: str
    name: str
    email: Optional[str] = None
    role: str
    society_id: Optional[str] = None
    wing_id: Optional[str] = None
    flat_id: Optional[str] = None
    status: str
    created_at: datetime
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class SwitchRoleRequest(BaseModel):
    target_role: str
