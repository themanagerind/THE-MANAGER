from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response, Query, Header
from typing import Optional
from datetime import datetime, timezone
import uuid
from ..core.database import db
from ..core.security import get_current_user
from ..utils.storage import upload_file, get_object, is_storage_enabled

router = APIRouter(prefix="/files", tags=["Files"])

# Collection for file metadata
files_collection = db.files

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@router.get("/status")
async def storage_status():
    """Check if file storage is enabled"""
    return {"enabled": is_storage_enabled()}

@router.post("/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    expense_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Upload a receipt/file"""
    # Check if storage is enabled
    if not is_storage_enabled():
        raise HTTPException(status_code=503, detail="File storage not available")
    
    # Validate file extension
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Upload file
    result = await upload_file(file, folder="receipts")
    if not result:
        raise HTTPException(status_code=500, detail="Failed to upload file")
    
    # Store metadata in database
    file_doc = {
        "id": result["id"],
        "storage_path": result["path"],
        "original_filename": result["original_filename"],
        "content_type": result["content_type"],
        "size": result["size"],
        "expense_id": expense_id,
        "uploaded_by": current_user["id"],
        "uploaded_by_name": current_user["name"],
        "society_id": current_user.get("society_id"),
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await files_collection.insert_one(file_doc)
    
    return {
        "id": result["id"],
        "filename": result["original_filename"],
        "size": result["size"],
        "content_type": result["content_type"]
    }

@router.get("/{file_id}")
async def get_file(
    file_id: str,
    authorization: str = Header(None),
    auth: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Download a file by ID"""
    # Find file metadata
    file_doc = await files_collection.find_one({
        "id": file_id,
        "is_deleted": False
    }, {"_id": 0})
    
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check access (same society)
    if file_doc.get("society_id") and file_doc["society_id"] != current_user.get("society_id"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get file from storage
    result = get_object(file_doc["storage_path"])
    if not result:
        raise HTTPException(status_code=404, detail="File not found in storage")
    
    data, content_type = result
    return Response(
        content=data,
        media_type=file_doc.get("content_type", content_type),
        headers={
            "Content-Disposition": f'inline; filename="{file_doc["original_filename"]}"'
        }
    )

@router.get("/expense/{expense_id}")
async def get_expense_files(
    expense_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all files for an expense"""
    files = await files_collection.find({
        "expense_id": expense_id,
        "is_deleted": False
    }, {"_id": 0}).to_list(100)
    
    return files

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Soft-delete a file"""
    file_doc = await files_collection.find_one({
        "id": file_id,
        "is_deleted": False
    })
    
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Only uploader or admin can delete
    if file_doc["uploaded_by"] != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    await files_collection.update_one(
        {"id": file_id},
        {"$set": {"is_deleted": True}}
    )
    
    return {"message": "File deleted"}
