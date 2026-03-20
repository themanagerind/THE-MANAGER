from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from ..models.society import WingCreate, Wing, WingResponse, FlatCreate, Flat, FlatResponse, FlatToggle
from ..models.user import User, UserResponse
from ..core.database import (
    users_collection, wings_collection, flats_collection, 
    societies_collection
)
from ..core.security import require_role, get_password_hash

router = APIRouter(prefix="/admin", tags=["Admin"])

# ============ WINGS ============
@router.post("/wings", response_model=WingResponse)
async def create_wing(wing_data: WingCreate, current_user: dict = Depends(require_role("admin"))):
    """Create a new wing in the society"""
    # Verify society belongs to admin
    if wing_data.society_id != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own society")
    
    # Check if wing name already exists in society
    existing = await wings_collection.find_one({
        "society_id": wing_data.society_id,
        "name": wing_data.name
    })
    if existing:
        raise HTTPException(status_code=400, detail="Wing with this name already exists")
    
    wing = Wing(
        society_id=wing_data.society_id,
        name=wing_data.name
    )
    
    wing_dict = wing.model_dump()
    wing_dict['created_at'] = wing_dict['created_at'].isoformat()
    await wings_collection.insert_one(wing_dict)
    
    return WingResponse(
        id=wing.id,
        society_id=wing.society_id,
        name=wing.name,
        sub_admin_id=wing.sub_admin_id,
        created_at=wing.created_at
    )

@router.get("/wings", response_model=List[WingResponse])
async def get_wings(current_user: dict = Depends(require_role("admin", "sub_admin"))):
    """Get all wings in the society"""
    society_id = current_user.get("society_id")
    wings = await wings_collection.find({"society_id": society_id}, {"_id": 0}).to_list(100)
    
    result = []
    for wing in wings:
        sub_admin_name = None
        if wing.get("sub_admin_id"):
            sub_admin = await users_collection.find_one({"id": wing["sub_admin_id"]}, {"_id": 0, "name": 1})
            if sub_admin:
                sub_admin_name = sub_admin["name"]
        
        created_at = wing.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        result.append(WingResponse(
            id=wing["id"],
            society_id=wing["society_id"],
            name=wing["name"],
            sub_admin_id=wing.get("sub_admin_id"),
            sub_admin_name=sub_admin_name,
            created_at=created_at
        ))
    
    return result

@router.put("/wings/{wing_id}")
async def update_wing(wing_id: str, name: str, current_user: dict = Depends(require_role("admin"))):
    """Update wing name"""
    wing = await wings_collection.find_one({"id": wing_id})
    if not wing:
        raise HTTPException(status_code=404, detail="Wing not found")
    
    if wing["society_id"] != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own society")
    
    await wings_collection.update_one(
        {"id": wing_id},
        {"$set": {"name": name}}
    )
    return {"message": "Wing updated successfully"}

@router.delete("/wings/{wing_id}")
async def delete_wing(wing_id: str, current_user: dict = Depends(require_role("admin"))):
    """Delete a wing (only if no flats exist)"""
    wing = await wings_collection.find_one({"id": wing_id})
    if not wing:
        raise HTTPException(status_code=404, detail="Wing not found")
    
    if wing["society_id"] != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own society")
    
    # Check if flats exist
    flat_count = await flats_collection.count_documents({"wing_id": wing_id})
    if flat_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete wing with existing flats")
    
    await wings_collection.delete_one({"id": wing_id})
    return {"message": "Wing deleted successfully"}

@router.put("/wings/{wing_id}/assign-subadmin")
async def assign_subadmin_to_wing(
    wing_id: str, 
    sub_admin_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Assign a sub-admin to a wing"""
    wing = await wings_collection.find_one({"id": wing_id})
    if not wing:
        raise HTTPException(status_code=404, detail="Wing not found")
    
    if wing["society_id"] != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own society")
    
    # Verify sub_admin exists and is a sub_admin
    sub_admin = await users_collection.find_one({"id": sub_admin_id, "role": "sub_admin"})
    if not sub_admin:
        raise HTTPException(status_code=404, detail="Sub-admin not found")
    
    # Update wing
    await wings_collection.update_one(
        {"id": wing_id},
        {"$set": {"sub_admin_id": sub_admin_id}}
    )
    
    # Update sub_admin's wing_id
    await users_collection.update_one(
        {"id": sub_admin_id},
        {"$set": {"wing_id": wing_id}}
    )
    
    return {"message": "Sub-admin assigned to wing successfully"}

# ============ FLATS ============
@router.post("/flats", response_model=FlatResponse)
async def create_flat(flat_data: FlatCreate, current_user: dict = Depends(require_role("admin"))):
    """Create a new flat"""
    wing = await wings_collection.find_one({"id": flat_data.wing_id})
    if not wing:
        raise HTTPException(status_code=404, detail="Wing not found")
    
    if wing["society_id"] != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own society")
    
    # Check if flat number already exists in wing
    existing = await flats_collection.find_one({
        "wing_id": flat_data.wing_id,
        "number": flat_data.number
    })
    if existing:
        raise HTTPException(status_code=400, detail="Flat with this number already exists in this wing")
    
    flat = Flat(
        wing_id=flat_data.wing_id,
        society_id=wing["society_id"],
        number=flat_data.number,
        floor=flat_data.floor
    )
    
    flat_dict = flat.model_dump()
    flat_dict['created_at'] = flat_dict['created_at'].isoformat()
    await flats_collection.insert_one(flat_dict)
    
    return FlatResponse(
        id=flat.id,
        wing_id=flat.wing_id,
        society_id=flat.society_id,
        number=flat.number,
        floor=flat.floor,
        is_active=flat.is_active,
        wing_name=wing["name"],
        created_at=flat.created_at
    )

@router.post("/flats/bulk")
async def create_flats_bulk(
    wing_id: str,
    floor_count: int,
    flats_per_floor: int,
    current_user: dict = Depends(require_role("admin"))
):
    """Create multiple flats at once"""
    wing = await wings_collection.find_one({"id": wing_id})
    if not wing:
        raise HTTPException(status_code=404, detail="Wing not found")
    
    if wing["society_id"] != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own society")
    
    created_flats = []
    for floor in range(1, floor_count + 1):
        for flat_num in range(1, flats_per_floor + 1):
            flat_number = f"{wing['name']}-{floor}{flat_num:02d}"
            
            # Check if already exists
            existing = await flats_collection.find_one({
                "wing_id": wing_id,
                "number": flat_number
            })
            if existing:
                continue
            
            flat = Flat(
                wing_id=wing_id,
                society_id=wing["society_id"],
                number=flat_number,
                floor=floor
            )
            
            flat_dict = flat.model_dump()
            flat_dict['created_at'] = flat_dict['created_at'].isoformat()
            await flats_collection.insert_one(flat_dict)
            created_flats.append(flat_number)
    
    return {"message": f"Created {len(created_flats)} flats", "flats": created_flats}

@router.get("/flats", response_model=List[FlatResponse])
async def get_flats(
    wing_id: Optional[str] = None,
    current_user: dict = Depends(require_role("admin", "sub_admin"))
):
    """Get all flats, optionally filtered by wing"""
    query = {"society_id": current_user.get("society_id")}
    if wing_id:
        query["wing_id"] = wing_id
    
    flats = await flats_collection.find(query, {"_id": 0}).to_list(1000)
    
    result = []
    for flat in flats:
        wing = await wings_collection.find_one({"id": flat["wing_id"]}, {"_id": 0, "name": 1})
        resident_name = None
        if flat.get("resident_id"):
            resident = await users_collection.find_one({"id": flat["resident_id"]}, {"_id": 0, "name": 1})
            if resident:
                resident_name = resident["name"]
        
        created_at = flat.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        result.append(FlatResponse(
            id=flat["id"],
            wing_id=flat["wing_id"],
            society_id=flat["society_id"],
            number=flat["number"],
            floor=flat["floor"],
            is_active=flat.get("is_active", True),
            resident_id=flat.get("resident_id"),
            resident_name=resident_name,
            wing_name=wing["name"] if wing else None,
            created_at=created_at
        ))
    
    return result

@router.get("/flats/mapping")
async def get_flat_mapping(current_user: dict = Depends(require_role("admin"))):
    """Get flat mapping grid view - organized by wing and floor"""
    society_id = current_user.get("society_id")
    
    wings = await wings_collection.find({"society_id": society_id}, {"_id": 0}).to_list(100)
    
    result = []
    for wing in wings:
        flats = await flats_collection.find({"wing_id": wing["id"]}, {"_id": 0}).to_list(1000)
        
        # Group by floor
        floors = {}
        for flat in flats:
            floor = flat.get("floor", 1)
            if floor not in floors:
                floors[floor] = []
            
            resident_name = None
            if flat.get("resident_id"):
                resident = await users_collection.find_one({"id": flat["resident_id"]}, {"_id": 0, "name": 1})
                if resident:
                    resident_name = resident["name"]
            
            floors[floor].append({
                "id": flat["id"],
                "number": flat["number"],
                "is_active": flat.get("is_active", True),
                "resident_id": flat.get("resident_id"),
                "resident_name": resident_name
            })
        
        result.append({
            "wing_id": wing["id"],
            "wing_name": wing["name"],
            "floors": floors,
            "total_flats": len(flats),
            "active_flats": sum(1 for f in flats if f.get("is_active", True))
        })
    
    return result

@router.put("/flats/{flat_id}/toggle")
async def toggle_flat_active(
    flat_id: str,
    data: FlatToggle,
    current_user: dict = Depends(require_role("admin"))
):
    """Toggle flat active/inactive status"""
    flat = await flats_collection.find_one({"id": flat_id})
    if not flat:
        raise HTTPException(status_code=404, detail="Flat not found")
    
    if flat["society_id"] != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own society")
    
    await flats_collection.update_one(
        {"id": flat_id},
        {"$set": {"is_active": data.is_active}}
    )
    
    return {"message": f"Flat {'activated' if data.is_active else 'deactivated'} successfully"}

@router.put("/flats/{flat_id}/assign-resident")
async def assign_resident_to_flat(
    flat_id: str,
    resident_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Assign a resident to a flat"""
    flat = await flats_collection.find_one({"id": flat_id})
    if not flat:
        raise HTTPException(status_code=404, detail="Flat not found")
    
    if flat["society_id"] != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="You can only manage your own society")
    
    resident = await users_collection.find_one({"id": resident_id, "role": "resident"})
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    
    # Update flat
    await flats_collection.update_one(
        {"id": flat_id},
        {"$set": {"resident_id": resident_id}}
    )
    
    # Update resident
    await users_collection.update_one(
        {"id": resident_id},
        {"$set": {
            "flat_id": flat_id,
            "wing_id": flat["wing_id"],
            "society_id": flat["society_id"]
        }}
    )
    
    return {"message": "Resident assigned to flat successfully"}

# ============ RESIDENTS ============
@router.get("/residents")
async def get_residents(
    status: Optional[str] = None,
    current_user: dict = Depends(require_role("admin"))
):
    """Get all residents in the society"""
    query = {"role": "resident", "society_id": current_user.get("society_id")}
    if status:
        query["status"] = status
    
    residents = await users_collection.find(query, {"_id": 0, "password_hash": 0}).to_list(1000)
    
    result = []
    for resident in residents:
        flat_info = None
        wing_info = None
        if resident.get("flat_id"):
            flat = await flats_collection.find_one({"id": resident["flat_id"]}, {"_id": 0})
            if flat:
                flat_info = {"id": flat["id"], "number": flat["number"]}
                wing = await wings_collection.find_one({"id": flat["wing_id"]}, {"_id": 0, "name": 1})
                if wing:
                    wing_info = {"id": flat["wing_id"], "name": wing["name"]}
        
        created_at = resident.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        result.append({
            **resident,
            "created_at": created_at,
            "flat": flat_info,
            "wing": wing_info
        })
    
    return result

@router.post("/residents/{resident_id}/approve")
async def approve_resident(resident_id: str, current_user: dict = Depends(require_role("admin"))):
    """Approve a pending resident signup"""
    resident = await users_collection.find_one({
        "id": resident_id,
        "role": "resident",
        "society_id": current_user.get("society_id")
    })
    
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    
    if resident["status"] != "pending":
        raise HTTPException(status_code=400, detail="Resident is not in pending status")
    
    # If resident has password (old flow), set to active directly
    # If no password (new OTP flow), set to approved so they can set password
    new_status = "active" if resident.get("password_hash") else "approved"
    
    await users_collection.update_one(
        {"id": resident_id},
        {"$set": {
            "status": new_status,
            "needs_password_setup": not bool(resident.get("password_hash")),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Link resident to flat if flat_id exists and status is active
    if resident.get("flat_id") and new_status == "active":
        await flats_collection.update_one(
            {"id": resident["flat_id"]},
            {"$set": {"resident_id": resident_id}}
        )
    
    status_msg = "approved - waiting for password setup" if new_status == "approved" else "approved and activated"
    return {"message": f"Resident {status_msg}"}

@router.post("/residents/{resident_id}/reject")
async def reject_resident(resident_id: str, current_user: dict = Depends(require_role("admin"))):
    """Reject a pending resident signup"""
    resident = await users_collection.find_one({
        "id": resident_id,
        "role": "resident",
        "society_id": current_user.get("society_id")
    })
    
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    
    await users_collection.delete_one({"id": resident_id})
    return {"message": "Resident rejected and removed"}

@router.post("/residents/{resident_id}/promote")
async def promote_to_subadmin(
    resident_id: str,
    wing_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Promote a resident to sub-admin for a wing"""
    resident = await users_collection.find_one({
        "id": resident_id,
        "role": "resident",
        "society_id": current_user.get("society_id")
    })
    
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    
    wing = await wings_collection.find_one({"id": wing_id})
    if not wing:
        raise HTTPException(status_code=404, detail="Wing not found")
    
    # Check if wing already has a sub-admin
    if wing.get("sub_admin_id"):
        raise HTTPException(status_code=400, detail="Wing already has a sub-admin")
    
    # Create new sub_admin user entry (same mobile, different role)
    sub_admin = User(
        mobile=resident["mobile"],
        name=resident["name"],
        email=resident.get("email"),
        password_hash=resident["password_hash"],
        role="sub_admin",
        society_id=current_user.get("society_id"),
        wing_id=wing_id,
        flat_id=resident.get("flat_id"),
        status="active"
    )
    
    sub_admin_dict = sub_admin.model_dump()
    sub_admin_dict['created_at'] = sub_admin_dict['created_at'].isoformat()
    sub_admin_dict['updated_at'] = sub_admin_dict['updated_at'].isoformat()
    
    await users_collection.insert_one(sub_admin_dict)
    
    # Update wing with sub_admin_id
    await wings_collection.update_one(
        {"id": wing_id},
        {"$set": {"sub_admin_id": sub_admin.id}}
    )
    
    return {"message": "Resident promoted to sub-admin successfully", "sub_admin_id": sub_admin.id}

@router.get("/sub-admins")
async def get_sub_admins(current_user: dict = Depends(require_role("admin"))):
    """Get all sub-admins in the society"""
    sub_admins = await users_collection.find({
        "role": "sub_admin",
        "society_id": current_user.get("society_id")
    }, {"_id": 0, "password_hash": 0}).to_list(100)
    
    result = []
    for sa in sub_admins:
        wing_name = None
        if sa.get("wing_id"):
            wing = await wings_collection.find_one({"id": sa["wing_id"]}, {"_id": 0, "name": 1})
            if wing:
                wing_name = wing["name"]
        
        created_at = sa.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        result.append({
            **sa,
            "created_at": created_at,
            "wing_name": wing_name
        })
    
    return result
