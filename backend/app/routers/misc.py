from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime, timezone
from ..models.misc import Notice, NoticeCreate, Complaint, ComplaintCreate, ComplaintStatusUpdate
from ..core.database import (
    notices_collection, complaints_collection, users_collection,
    platform_settings_collection
)
from ..core.security import require_role, get_current_user

router = APIRouter(tags=["Misc"])

# ============ NOTICES ============
@router.post("/notices", response_model=dict)
async def create_notice(
    data: NoticeCreate,
    current_user: dict = Depends(require_role("admin"))
):
    """Create a new notice"""
    notice = Notice(
        society_id=current_user["society_id"],
        title=data.title,
        content=data.content,
        created_by=current_user["id"],
        created_by_name=current_user["name"],
        is_pinned=data.is_pinned
    )
    
    notice_dict = notice.model_dump()
    notice_dict['created_at'] = notice_dict['created_at'].isoformat()
    await notices_collection.insert_one(notice_dict)
    
    return {"message": "Notice created", "id": notice.id}

@router.get("/notices")
async def get_notices(current_user: dict = Depends(get_current_user)):
    """Get all notices for society"""
    society_id = current_user.get("society_id")
    if not society_id:
        return []
    
    notices = await notices_collection.find(
        {"society_id": society_id},
        {"_id": 0}
    ).sort([("is_pinned", -1), ("created_at", -1)]).to_list(100)
    
    for notice in notices:
        if isinstance(notice.get("created_at"), str):
            notice["created_at"] = datetime.fromisoformat(notice["created_at"].replace('Z', '+00:00'))
    
    return notices

@router.put("/notices/{notice_id}")
async def update_notice(
    notice_id: str,
    data: NoticeCreate,
    current_user: dict = Depends(require_role("admin"))
):
    """Update a notice"""
    notice = await notices_collection.find_one({"id": notice_id})
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    
    if notice["society_id"] != current_user["society_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await notices_collection.update_one(
        {"id": notice_id},
        {"$set": {
            "title": data.title,
            "content": data.content,
            "is_pinned": data.is_pinned
        }}
    )
    
    return {"message": "Notice updated"}

@router.delete("/notices/{notice_id}")
async def delete_notice(
    notice_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Delete a notice"""
    notice = await notices_collection.find_one({"id": notice_id})
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
    
    if notice["society_id"] != current_user["society_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await notices_collection.delete_one({"id": notice_id})
    return {"message": "Notice deleted"}

# ============ COMPLAINTS ============
@router.post("/complaints", response_model=dict)
async def create_complaint(
    data: ComplaintCreate,
    current_user: dict = Depends(require_role("resident", "sub_admin"))
):
    """Create a new complaint"""
    if not current_user.get("flat_id"):
        raise HTTPException(status_code=400, detail="You must be assigned to a flat to file complaints")
    
    complaint = Complaint(
        society_id=current_user["society_id"],
        flat_id=current_user["flat_id"],
        wing_id=current_user["wing_id"],
        title=data.title,
        category=data.category,
        priority=data.priority,
        description=data.description,
        created_by=current_user["id"],
        created_by_name=current_user["name"]
    )
    
    complaint_dict = complaint.model_dump()
    complaint_dict['created_at'] = complaint_dict['created_at'].isoformat()
    complaint_dict['updated_at'] = complaint_dict['updated_at'].isoformat()
    await complaints_collection.insert_one(complaint_dict)
    
    return {"message": "Complaint submitted", "id": complaint.id}

@router.get("/complaints")
async def get_complaints(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get complaints - filtered by role"""
    query = {"society_id": current_user.get("society_id")}
    
    # Filter by wing for sub-admin
    if current_user["role"] == "sub_admin":
        query["wing_id"] = current_user.get("wing_id")
    
    # Filter by flat for resident
    if current_user["role"] == "resident":
        query["flat_id"] = current_user.get("flat_id")
    
    if status:
        query["status"] = status
    
    complaints = await complaints_collection.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    for complaint in complaints:
        for date_field in ['created_at', 'updated_at']:
            if isinstance(complaint.get(date_field), str):
                complaint[date_field] = datetime.fromisoformat(complaint[date_field].replace('Z', '+00:00'))
    
    return complaints

@router.put("/complaints/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: str,
    data: ComplaintStatusUpdate,
    current_user: dict = Depends(require_role("admin", "sub_admin"))
):
    """Update complaint status"""
    complaint = await complaints_collection.find_one({"id": complaint_id})
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    # Sub-admin can only update their wing's complaints
    if current_user["role"] == "sub_admin":
        if complaint["wing_id"] != current_user.get("wing_id"):
            raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = {
        "status": data.status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if data.assigned_to:
        assignee = await users_collection.find_one({"id": data.assigned_to}, {"_id": 0, "name": 1})
        update_data["assigned_to"] = data.assigned_to
        update_data["assigned_to_name"] = assignee["name"] if assignee else None
    
    await complaints_collection.update_one(
        {"id": complaint_id},
        {"$set": update_data}
    )
    
    return {"message": "Complaint updated"}

# ============ BAZAAR / SHOPPING LINK ============
@router.get("/bazaar/link")
async def get_bazaar_link(current_user: dict = Depends(get_current_user)):
    """Get shopping/bazaar link for wallet redemption"""
    settings = await platform_settings_collection.find_one(
        {"id": "platform_settings"},
        {"_id": 0}
    )
    
    return {
        "shopping_link": settings.get("shopping_link") if settings else None,
        "available": bool(settings and settings.get("shopping_link"))
    }
