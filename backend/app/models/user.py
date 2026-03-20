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

class ResidentSignupRequest(BaseModel):
    name: str
    mobile: str
    otp_token: str
    society_id: str
    wing_id: str
    flat_id: str

class SetPasswordRequest(BaseModel):
    mobile: str
    password: str

class SendOTPRequest(BaseModel):
    mobile: str
    purpose: Literal["signup", "forgot_password"] = "signup"

class VerifyOTPRequest(BaseModel):
    mobile: str
    otp: str
    purpose: Literal["signup", "forgot_password"] = "signup"

class ForgotPasswordResetRequest(BaseModel):
    mobile: str
    otp_token: str
    new_password: str

class UserLogin(BaseModel):
    mobile: str
    password: str
    role: Optional[str] = None

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mobile: str
    name: str
    email: Optional[str] = None
    role: Literal["platform_owner", "admin", "sub_admin", "resident"] = "resident"
    society_id: Optional[str] = None
    wing_id: Optional[str] = None
    flat_id: Optional[str] = None
    status: Literal["pending", "approved", "active", "blocked"] = "pending"
    password_hash: Optional[str] = None
    needs_password_setup: bool = False
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
    needs_password_setup: bool = False
    created_at: datetime
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class SwitchRoleRequest(BaseModel):
    target_role: str

class OTPRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mobile: str
    otp_hash: str
    purpose: Literal["signup", "forgot_password"]
    attempts: int = 0
    blocked_until: Optional[datetime] = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
