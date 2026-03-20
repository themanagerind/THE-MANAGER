from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_indexes, close_db, users_collection
from app.core.security import get_password_hash
from app.routers import auth, platform, admin, maintenance, finance, misc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Housing Society Management API...")
    await init_indexes()
    
    # Create default platform owner if not exists
    existing_owner = await users_collection.find_one({"role": "platform_owner"})
    if not existing_owner:
        from datetime import datetime, timezone
        import uuid
        owner = {
            "id": str(uuid.uuid4()),
            "mobile": "9999999999",
            "name": "Platform Owner",
            "email": "owner@platform.com",
            "role": "platform_owner",
            "status": "active",
            "password_hash": get_password_hash("owner123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await users_collection.insert_one(owner)
        logger.info("Created default platform owner: mobile=9999999999, password=owner123")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db()

# Create the main app
app = FastAPI(
    title="Housing Society Management API",
    description="API for Housing Society Management PWA",
    version="1.0.0",
    lifespan=lifespan
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Include all routers
api_router.include_router(auth.router)
api_router.include_router(platform.router)
api_router.include_router(admin.router)
api_router.include_router(maintenance.router)
api_router.include_router(finance.router)
api_router.include_router(misc.router)

# Health check
@api_router.get("/")
async def root():
    return {"message": "Housing Society Management API", "status": "running"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include the router in the main app
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS.split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
