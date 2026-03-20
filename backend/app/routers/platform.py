from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime, timezone
from ..models.user import UserResponse
from ..models.misc import ShoppingLinkUpdate, PlatformSettings, BazaarSettingsUpdate
from ..core.database import users_collection, societies_collection, platform_settings_collection
from ..core.security import require_role

router = APIRouter(prefix="/platform", tags=["Platform Owner"])

@router.get("/admins", response_model=List[dict])
async def get_all_admins(current_user: dict = Depends(require_role("platform_owner"))):
    """Get all admins with their society info"""
    admins = await users_collection.find(
        {"role": "admin"},
        {"_id": 0, "password_hash": 0}
    ).to_list(1000)
    
    # Enrich with society data
    result = []
    for admin in admins:
        society = None
        if admin.get("society_id"):
            society = await societies_collection.find_one(
                {"id": admin["society_id"]},
                {"_id": 0}
            )
        
        created_at = admin.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        result.append({
            "id": admin["id"],
            "mobile": admin["mobile"],
            "name": admin["name"],
            "email": admin.get("email"),
            "status": admin["status"],
            "created_at": created_at,
            "society": society
        })
    
    return result

@router.post("/admins/{admin_id}/approve")
async def approve_admin(admin_id: str, current_user: dict = Depends(require_role("platform_owner"))):
    """Approve a pending admin"""
    admin = await users_collection.find_one({"id": admin_id, "role": "admin"})
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    if admin["status"] != "pending":
        raise HTTPException(status_code=400, detail="Admin is not in pending status")
    
    await users_collection.update_one(
        {"id": admin_id},
        {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Also activate the society
    if admin.get("society_id"):
        await societies_collection.update_one(
            {"id": admin["society_id"]},
            {"$set": {"status": "active"}}
        )
    
    return {"message": "Admin approved successfully"}

@router.post("/admins/{admin_id}/block")
async def block_admin(admin_id: str, current_user: dict = Depends(require_role("platform_owner"))):
    """Block an admin - cascades to block the entire society"""
    admin = await users_collection.find_one({"id": admin_id, "role": "admin"})
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # Block the admin
    await users_collection.update_one(
        {"id": admin_id},
        {"$set": {"status": "blocked", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Block the society
    if admin.get("society_id"):
        await societies_collection.update_one(
            {"id": admin["society_id"]},
            {"$set": {"status": "blocked"}}
        )
    
    return {"message": "Admin and society blocked successfully"}

@router.post("/admins/{admin_id}/unblock")
async def unblock_admin(admin_id: str, current_user: dict = Depends(require_role("platform_owner"))):
    """Unblock an admin and their society"""
    admin = await users_collection.find_one({"id": admin_id, "role": "admin"})
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    await users_collection.update_one(
        {"id": admin_id},
        {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if admin.get("society_id"):
        await societies_collection.update_one(
            {"id": admin["society_id"]},
            {"$set": {"status": "active"}}
        )
    
    return {"message": "Admin and society unblocked successfully"}

@router.get("/shopping-link")
async def get_shopping_link(current_user: dict = Depends(require_role("platform_owner"))):
    """Get current shopping/bazaar link"""
    settings = await platform_settings_collection.find_one({"id": "platform_settings"}, {"_id": 0})
    return {"shopping_link": settings.get("shopping_link") if settings else None}

@router.put("/shopping-link")
async def set_shopping_link(
    data: ShoppingLinkUpdate,
    current_user: dict = Depends(require_role("platform_owner"))
):
    """Set the shopping/bazaar link for wallet redemption"""
    await platform_settings_collection.update_one(
        {"id": "platform_settings"},
        {
            "$set": {
                "shopping_link": data.shopping_link,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    return {"message": "Shopping link updated successfully", "shopping_link": data.shopping_link}

@router.get("/stats")
async def get_platform_stats(current_user: dict = Depends(require_role("platform_owner"))):
    """Get platform-wide statistics"""
    total_societies = await societies_collection.count_documents({})
    active_societies = await societies_collection.count_documents({"status": "active"})
    total_admins = await users_collection.count_documents({"role": "admin"})
    pending_admins = await users_collection.count_documents({"role": "admin", "status": "pending"})
    total_residents = await users_collection.count_documents({"role": "resident"})
    
    return {
        "total_societies": total_societies,
        "active_societies": active_societies,
        "blocked_societies": total_societies - active_societies,
        "total_admins": total_admins,
        "pending_admins": pending_admins,
        "total_residents": total_residents
    }


# ============ BAZAAR SETTINGS ============

@router.get("/bazaar-settings")
async def get_bazaar_settings(current_user: dict = Depends(require_role("platform_owner"))):
    """Get Bazaar API settings"""
    settings = await platform_settings_collection.find_one({"id": "platform_settings"}, {"_id": 0})
    if not settings:
        return {
            "bazaar_api_url": None,
            "bazaar_secret_key": None,
            "bazaar_connected": False,
            "shopping_link": None
        }
    return {
        "bazaar_api_url": settings.get("bazaar_api_url"),
        "bazaar_secret_key": settings.get("bazaar_secret_key"),
        "bazaar_connected": settings.get("bazaar_connected", False),
        "shopping_link": settings.get("shopping_link")
    }

@router.put("/bazaar-settings")
async def update_bazaar_settings(
    data: BazaarSettingsUpdate,
    current_user: dict = Depends(require_role("platform_owner"))
):
    """Update Bazaar API URL and Secret Key"""
    await platform_settings_collection.update_one(
        {"id": "platform_settings"},
        {
            "$set": {
                "bazaar_api_url": data.bazaar_api_url,
                "bazaar_secret_key": data.bazaar_secret_key,
                "bazaar_connected": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    return {
        "message": "Bazaar settings updated successfully",
        "bazaar_connected": True
    }
