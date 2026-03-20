import os
import uuid
import logging
import requests
from typing import Optional, Tuple
from fastapi import UploadFile

logger = logging.getLogger(__name__)

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "societyhub"

# Module-level storage key - set once and reused
_storage_key: Optional[str] = None

MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "json": "application/json",
    "csv": "text/csv",
    "txt": "text/plain"
}

def init_storage() -> Optional[str]:
    """Initialize storage and get session key. Call once at startup."""
    global _storage_key
    if _storage_key:
        return _storage_key
    
    if not EMERGENT_KEY:
        logger.warning("EMERGENT_LLM_KEY not set - file uploads disabled")
        return None
    
    try:
        resp = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": EMERGENT_KEY},
            timeout=30
        )
        resp.raise_for_status()
        _storage_key = resp.json()["storage_key"]
        logger.info("Object storage initialized successfully")
        return _storage_key
    except Exception as e:
        logger.error(f"Failed to initialize storage: {e}")
        return None

def get_storage_key() -> Optional[str]:
    """Get storage key, initializing if needed."""
    global _storage_key
    if not _storage_key:
        return init_storage()
    return _storage_key

def put_object(path: str, data: bytes, content_type: str) -> Optional[dict]:
    """Upload a file to object storage."""
    key = get_storage_key()
    if not key:
        return None
    
    try:
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={
                "X-Storage-Key": key,
                "Content-Type": content_type
            },
            data=data,
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        return None

def get_object(path: str) -> Optional[Tuple[bytes, str]]:
    """Download a file from object storage."""
    key = get_storage_key()
    if not key:
        return None
    
    try:
        resp = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key},
            timeout=60
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        return resp.content, content_type
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        return None

async def upload_file(file: UploadFile, folder: str = "uploads") -> Optional[dict]:
    """
    Upload a file and return metadata.
    
    Args:
        file: FastAPI UploadFile object
        folder: Subfolder path (e.g., "expenses", "receipts")
    
    Returns:
        Dict with path, original_filename, content_type, size or None if failed
    """
    # Get file extension
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    
    # Generate unique path
    file_id = str(uuid.uuid4())
    path = f"{APP_NAME}/{folder}/{file_id}.{ext}"
    
    # Determine content type
    content_type = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    
    # Read file data
    data = await file.read()
    
    # Upload to storage
    result = put_object(path, data, content_type)
    if not result:
        return None
    
    return {
        "id": file_id,
        "path": result["path"],
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data))
    }

def is_storage_enabled() -> bool:
    """Check if storage is available."""
    return get_storage_key() is not None
