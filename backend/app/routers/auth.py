from fastapi import APIRouter, HTTPException, status, Depends
from datetime import timedelta
from ..models.user import UserCreate, UserLogin, User, UserResponse, TokenResponse, SwitchRoleRequest
from ..core.database import users_collection, societies_collection
from ..core.security import (
    get_password_hash, verify_password, create_access_token, 
    get_current_user, settings
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    # Check if user with same mobile and role exists
    existing = await users_collection.find_one({
        "mobile": user_data.mobile, 
        "role": "resident"
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this mobile already exists"
        )
    
    # Create new user
    user = User(
        mobile=user_data.mobile,
        name=user_data.name,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role="resident",
        society_id=user_data.society_id,
        wing_id=user_data.wing_id,
        flat_id=user_data.flat_id,
        status="pending"  # Needs admin approval
    )
    
    user_dict = user.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    user_dict['updated_at'] = user_dict['updated_at'].isoformat()
    
    await users_collection.insert_one(user_dict)
    
    return UserResponse(
        id=user.id,
        mobile=user.mobile,
        name=user.name,
        email=user.email,
        role=user.role,
        society_id=user.society_id,
        wing_id=user.wing_id,
        flat_id=user.flat_id,
        status=user.status,
        created_at=user.created_at
    )

@router.post("/register-admin", response_model=UserResponse)
async def register_admin(user_data: UserCreate, society_name: str, society_address: str):
    """Register as admin with a new society - requires platform owner approval"""
    # Check if user with same mobile and role exists
    existing = await users_collection.find_one({
        "mobile": user_data.mobile, 
        "role": "admin"
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this mobile already exists"
        )
    
    # Create society
    from ..models.society import Society
    society = Society(name=society_name, address=society_address)
    society_dict = society.model_dump()
    society_dict['created_at'] = society_dict['created_at'].isoformat()
    await societies_collection.insert_one(society_dict)
    
    # Create admin user
    user = User(
        mobile=user_data.mobile,
        name=user_data.name,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role="admin",
        society_id=society.id,
        status="pending"  # Needs platform owner approval
    )
    
    user_dict = user.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    user_dict['updated_at'] = user_dict['updated_at'].isoformat()
    
    await users_collection.insert_one(user_dict)
    
    # Update society with admin_id
    await societies_collection.update_one(
        {"id": society.id},
        {"$set": {"admin_id": user.id}}
    )
    
    return UserResponse(
        id=user.id,
        mobile=user.mobile,
        name=user.name,
        email=user.email,
        role=user.role,
        society_id=user.society_id,
        wing_id=user.wing_id,
        flat_id=user.flat_id,
        status=user.status,
        created_at=user.created_at
    )

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    # Find user by mobile
    query = {"mobile": credentials.mobile}
    if credentials.role:
        query["role"] = credentials.role
    
    user = await users_collection.find_one(query, {"_id": 0})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if user["status"] == "blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been blocked"
        )
    
    if user["status"] == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending approval"
        )
    
    # Check if society is blocked
    if user.get("role") != "platform_owner" and user.get("society_id"):
        society = await societies_collection.find_one({"id": user["society_id"]}, {"_id": 0})
        if society and society.get("status") == "blocked":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your society has been blocked"
            )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user["id"], "role": user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Parse created_at if it's a string
    created_at = user["created_at"]
    if isinstance(created_at, str):
        from datetime import datetime
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user["id"],
            mobile=user["mobile"],
            name=user["name"],
            email=user.get("email"),
            role=user["role"],
            society_id=user.get("society_id"),
            wing_id=user.get("wing_id"),
            flat_id=user.get("flat_id"),
            status=user["status"],
            created_at=created_at
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    created_at = current_user["created_at"]
    if isinstance(created_at, str):
        from datetime import datetime
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    
    return UserResponse(
        id=current_user["id"],
        mobile=current_user["mobile"],
        name=current_user["name"],
        email=current_user.get("email"),
        role=current_user["role"],
        society_id=current_user.get("society_id"),
        wing_id=current_user.get("wing_id"),
        flat_id=current_user.get("flat_id"),
        status=current_user["status"],
        created_at=created_at
    )

@router.get("/roles")
async def get_user_roles(current_user: dict = Depends(get_current_user)):
    """Get all roles for current user's mobile number"""
    roles = await users_collection.find(
        {"mobile": current_user["mobile"], "status": "active"},
        {"_id": 0, "role": 1, "id": 1}
    ).to_list(10)
    return roles

@router.post("/switch-role", response_model=TokenResponse)
async def switch_role(request: SwitchRoleRequest, current_user: dict = Depends(get_current_user)):
    """Switch to another role (same mobile can have multiple roles)"""
    target_user = await users_collection.find_one({
        "mobile": current_user["mobile"],
        "role": request.target_role,
        "status": "active"
    }, {"_id": 0})
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You don't have access to {request.target_role} role"
        )
    
    # Create new token for target role
    access_token = create_access_token(
        data={"sub": target_user["id"], "role": target_user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    created_at = target_user["created_at"]
    if isinstance(created_at, str):
        from datetime import datetime
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=target_user["id"],
            mobile=target_user["mobile"],
            name=target_user["name"],
            email=target_user.get("email"),
            role=target_user["role"],
            society_id=target_user.get("society_id"),
            wing_id=target_user.get("wing_id"),
            flat_id=target_user.get("flat_id"),
            status=target_user["status"],
            created_at=created_at
        )
    )
