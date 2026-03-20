from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid

class Notice(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    society_id: str
    title: str
    content: str
    created_by: str
    created_by_name: str
    is_pinned: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class NoticeCreate(BaseModel):
    title: str
    content: str
    is_pinned: bool = False

class Complaint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    society_id: str
    flat_id: str
    wing_id: str
    title: str
    category: Literal["plumbing", "electrical", "sanitation", "parking", "security", "general"]
    priority: Literal["low", "medium", "high", "urgent"]
    status: Literal["open", "in_progress", "resolved", "closed"] = "open"
    description: str
    created_by: str
    created_by_name: str
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ComplaintCreate(BaseModel):
    title: str
    category: str
    priority: str
    description: str

class ComplaintStatusUpdate(BaseModel):
    status: str
    assigned_to: Optional[str] = None

class PlatformSettings(BaseModel):
    id: str = "platform_settings"
    shopping_link: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ShoppingLinkUpdate(BaseModel):
    shopping_link: str
