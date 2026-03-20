from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timedelta, timezone
import random
import hashlib
import uuid
import logging

from ..models.user import (
    UserCreate, UserLogin, User, UserResponse, TokenResponse, SwitchRoleRequest,
    SendOTPRequest, VerifyOTPRequest, ResidentSignupRequest, SetPasswordRequest,
    ForgotPasswordResetRequest, OTPRecord
)
from ..core.database import (
    users_collection, societies_collection, flats_collection, wings_collection,
    otp_records_collection
)
from ..core.security import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, settings
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

OTP_EXPIRY_MINUTES = 5
OTP_MAX_ATTEMPTS = 3
OTP_BLOCK_MINUTES = 10

def generate_otp():
    return str(random.randint(100000, 999999))

def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()

def verify_otp_hash(otp: str, otp_hash: str) -> bool:
    return hashlib.sha256(otp.encode()).hexdigest() == otp_hash

# ============ OTP ENDPOINTS ============

@router.post("/send-otp")
async def send_otp(data: SendOTPRequest):
    """Send OTP to mobile number"""
    mobile = data.mobile
    purpose = data.purpose

    # Check if blocked
    existing = await otp_records_collection.find_one(
        {"mobile": mobile, "purpose": purpose},
        {"_id": 0},
        sort=[("created_at", -1)]
    )
    if existing and existing.get("blocked_until"):
        blocked_until = existing["blocked_until"]
        if isinstance(blocked_until, str):
            blocked_until = datetime.fromisoformat(blocked_until.replace('Z', '+00:00'))
        if blocked_until > datetime.now(timezone.utc):
            remaining = int((blocked_until - datetime.now(timezone.utc)).total_seconds())
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in {remaining} seconds."
            )

    # For signup: check if user already exists and is active
    if purpose == "signup":
        existing_user = await users_collection.find_one(
            {"mobile": mobile, "role": "resident", "status": {"$in": ["active", "pending", "approved"]}}
        )
        if existing_user:
            if existing_user["status"] == "active":
                raise HTTPException(status_code=400, detail="Account already exists. Please login.")
            elif existing_user["status"] in ["pending", "approved"]:
                raise HTTPException(status_code=400, detail="Registration already submitted. Please wait for admin approval.")

    # For forgot_password: check user exists
    if purpose == "forgot_password":
        existing_user = await users_collection.find_one(
            {"mobile": mobile, "status": "active"}
        )
        if not existing_user:
            raise HTTPException(status_code=404, detail="No active account found with this mobile number.")

    # Generate OTP
    otp = generate_otp()
    otp_hashed = hash_otp(otp)

    # Delete old OTP records for this mobile+purpose
    await otp_records_collection.delete_many({"mobile": mobile, "purpose": purpose})

    # Store new OTP
    record = OTPRecord(
        mobile=mobile,
        otp_hash=otp_hashed,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    )
    record_dict = record.model_dump()
    record_dict['expires_at'] = record_dict['expires_at'].isoformat()
    record_dict['created_at'] = record_dict['created_at'].isoformat()
    await otp_records_collection.insert_one(record_dict)

    # MOCK: Log OTP to console (replace with SMS API later)
    logger.info(f"[MOCK SMS] OTP for {mobile}: {otp} (purpose: {purpose})")
    print(f"\n{'='*50}")
    print(f"  MOCK SMS - OTP for {mobile}: {otp}")
    print(f"  Purpose: {purpose}")
    print(f"  Valid for {OTP_EXPIRY_MINUTES} minutes")
    print(f"{'='*50}\n")

    return {
        "message": f"OTP sent to {mobile}",
        "expires_in": OTP_EXPIRY_MINUTES * 60,
        "mock_otp": otp  # Remove in production
    }


@router.post("/verify-otp")
async def verify_otp_endpoint(data: VerifyOTPRequest):
    """Verify OTP and return a temporary token"""
    mobile = data.mobile
    purpose = data.purpose

    record = await otp_records_collection.find_one(
        {"mobile": mobile, "purpose": purpose},
        {"_id": 0},
        sort=[("created_at", -1)]
    )

    if not record:
        raise HTTPException(status_code=400, detail="No OTP found. Please request a new one.")

    # Check if blocked
    if record.get("blocked_until"):
        blocked_until = record["blocked_until"]
        if isinstance(blocked_until, str):
            blocked_until = datetime.fromisoformat(blocked_until.replace('Z', '+00:00'))
        if blocked_until > datetime.now(timezone.utc):
            remaining = int((blocked_until - datetime.now(timezone.utc)).total_seconds())
            raise HTTPException(
                status_code=429,
                detail=f"Too many attempts. Try again in {remaining} seconds."
            )

    # Check expiry
    expires_at = record["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    # Verify OTP
    if not verify_otp_hash(data.otp, record["otp_hash"]):
        new_attempts = record.get("attempts", 0) + 1
        update_data = {"attempts": new_attempts}

        if new_attempts >= OTP_MAX_ATTEMPTS:
            update_data["blocked_until"] = (
                datetime.now(timezone.utc) + timedelta(minutes=OTP_BLOCK_MINUTES)
            ).isoformat()

        await otp_records_collection.update_one(
            {"id": record["id"]},
            {"$set": update_data}
        )
        remaining_attempts = OTP_MAX_ATTEMPTS - new_attempts
        if remaining_attempts <= 0:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Blocked for {OTP_BLOCK_MINUTES} minutes."
            )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OTP. {remaining_attempts} attempt(s) remaining."
        )

    # OTP verified - generate temp token
    otp_token = str(uuid.uuid4())

    # Update record as verified
    await otp_records_collection.update_one(
        {"id": record["id"]},
        {"$set": {"verified": True, "otp_token": otp_token}}
    )

    return {
        "message": "OTP verified successfully",
        "otp_token": otp_token,
        "mobile": mobile
    }


# ============ RESIDENT SIGNUP ============

@router.post("/register", response_model=UserResponse)
async def register_resident(data: ResidentSignupRequest):
    """Register new resident after OTP verification"""
    # Verify OTP token
    otp_record = await otp_records_collection.find_one(
        {"mobile": data.mobile, "purpose": "signup", "otp_token": data.otp_token, "verified": True},
        {"_id": 0}
    )
    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP verification. Please verify OTP again.")

    # Check duplicate
    existing = await users_collection.find_one(
        {"mobile": data.mobile, "role": "resident"}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Account with this mobile already exists.")

    # Validate society, wing, flat exist
    society = await societies_collection.find_one({"id": data.society_id, "status": "active"}, {"_id": 0})
    if not society:
        raise HTTPException(status_code=404, detail="Society not found or not active.")

    wing = await wings_collection.find_one({"id": data.wing_id, "society_id": data.society_id}, {"_id": 0})
    if not wing:
        raise HTTPException(status_code=404, detail="Wing not found in this society.")

    flat = await flats_collection.find_one({"id": data.flat_id, "wing_id": data.wing_id}, {"_id": 0})
    if not flat:
        raise HTTPException(status_code=404, detail="Flat not found in this wing.")

    if flat.get("resident_id"):
        raise HTTPException(status_code=400, detail="This flat already has a resident assigned.")

    # Create user without password (pending approval)
    user = User(
        mobile=data.mobile,
        name=data.name,
        role="resident",
        society_id=data.society_id,
        wing_id=data.wing_id,
        flat_id=data.flat_id,
        status="pending",
        password_hash=None,
        needs_password_setup=True
    )

    user_dict = user.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    user_dict['updated_at'] = user_dict['updated_at'].isoformat()
    await users_collection.insert_one(user_dict)

    # Clean up OTP records
    await otp_records_collection.delete_many({"mobile": data.mobile, "purpose": "signup"})

    created_at = user.created_at

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
        needs_password_setup=user.needs_password_setup,
        created_at=created_at
    )


@router.post("/register-admin", response_model=UserResponse)
async def register_admin(user_data: UserCreate, society_name: str, society_address: str):
    """Register as admin with a new society - requires platform owner approval"""
    existing = await users_collection.find_one(
        {"mobile": user_data.mobile, "role": "admin"}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Admin with this mobile already exists")

    from ..models.society import Society
    society = Society(name=society_name, address=society_address)
    society_dict = society.model_dump()
    society_dict['created_at'] = society_dict['created_at'].isoformat()
    await societies_collection.insert_one(society_dict)

    user = User(
        mobile=user_data.mobile,
        name=user_data.name,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role="admin",
        society_id=society.id,
        status="pending"
    )

    user_dict = user.model_dump()
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    user_dict['updated_at'] = user_dict['updated_at'].isoformat()
    await users_collection.insert_one(user_dict)

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
        needs_password_setup=False,
        created_at=user.created_at
    )


# ============ SET PASSWORD ============

@router.post("/set-password")
async def set_password(data: SetPasswordRequest):
    """Set password for approved resident (after admin approval)"""
    user = await users_collection.find_one(
        {"mobile": data.mobile, "role": "resident", "status": "approved"},
        {"_id": 0}
    )
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Account not found or not yet approved by admin."
        )

    if len(data.password) < 4 or len(data.password) > 20:
        raise HTTPException(status_code=400, detail="Password must be 4-20 characters.")

    password_hash = get_password_hash(data.password)

    await users_collection.update_one(
        {"id": user["id"]},
        {"$set": {
            "password_hash": password_hash,
            "needs_password_setup": False,
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    # Link resident to flat
    if user.get("flat_id"):
        await flats_collection.update_one(
            {"id": user["flat_id"]},
            {"$set": {"resident_id": user["id"]}}
        )

    return {"message": "Password set successfully. You can now login."}


# ============ FORGOT PASSWORD ============

@router.post("/forgot-password/reset")
async def forgot_password_reset(data: ForgotPasswordResetRequest):
    """Reset password after OTP verification"""
    # Verify OTP token
    otp_record = await otp_records_collection.find_one(
        {"mobile": data.mobile, "purpose": "forgot_password", "otp_token": data.otp_token, "verified": True},
        {"_id": 0}
    )
    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP verification.")

    if len(data.new_password) < 4 or len(data.new_password) > 20:
        raise HTTPException(status_code=400, detail="Password must be 4-20 characters.")

    password_hash = get_password_hash(data.new_password)

    # Update password for all active roles of this mobile
    result = await users_collection.update_many(
        {"mobile": data.mobile, "status": "active"},
        {"$set": {
            "password_hash": password_hash,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="No active account found.")

    # Clean up OTP records
    await otp_records_collection.delete_many({"mobile": data.mobile, "purpose": "forgot_password"})

    return {"message": "Password reset successfully. You can now login."}


# ============ LOGIN ============

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with mobile + password"""
    query = {"mobile": credentials.mobile, "status": "active"}
    if credentials.role:
        query["role"] = credentials.role

    if not credentials.role:
        role_priority = ["platform_owner", "admin", "sub_admin", "resident"]
        user = None
        for role in role_priority:
            query["role"] = role
            user = await users_collection.find_one(query, {"_id": 0})
            if user:
                break
        if "role" in query:
            del query["role"]
    else:
        user = await users_collection.find_one(query, {"_id": 0})

    if not user:
        # Check if user exists but needs password setup
        pending_user = await users_collection.find_one(
            {"mobile": credentials.mobile, "status": "approved", "needs_password_setup": True}
        )
        if pending_user:
            raise HTTPException(
                status_code=403,
                detail="Your account is approved! Please set your password first."
            )
        pending_user = await users_collection.find_one(
            {"mobile": credentials.mobile, "status": "pending"}
        )
        if pending_user:
            raise HTTPException(
                status_code=403,
                detail="Your account is pending admin approval."
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.get("password_hash"):
        raise HTTPException(
            status_code=403,
            detail="Please set your password first."
        )

    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if society is blocked
    if user.get("role") != "platform_owner" and user.get("society_id"):
        society = await societies_collection.find_one({"id": user["society_id"]}, {"_id": 0})
        if society and society.get("status") == "blocked":
            raise HTTPException(status_code=403, detail="Your society has been blocked")

    access_token = create_access_token(
        data={"sub": user["id"], "role": user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    created_at = user["created_at"]
    if isinstance(created_at, str):
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
            needs_password_setup=user.get("needs_password_setup", False),
            created_at=created_at
        )
    )


# ============ USER INFO ============

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    created_at = current_user["created_at"]
    if isinstance(created_at, str):
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
        needs_password_setup=current_user.get("needs_password_setup", False),
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
    """Switch to another role"""
    target_user = await users_collection.find_one({
        "mobile": current_user["mobile"],
        "role": request.target_role,
        "status": "active"
    }, {"_id": 0})

    if not target_user:
        raise HTTPException(status_code=400, detail=f"You don't have access to {request.target_role} role")

    access_token = create_access_token(
        data={"sub": target_user["id"], "role": target_user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    created_at = target_user["created_at"]
    if isinstance(created_at, str):
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
            needs_password_setup=target_user.get("needs_password_setup", False),
            created_at=created_at
        )
    )


# ============ PUBLIC: SOCIETIES LIST (for signup dropdown) ============

@router.get("/societies")
async def get_active_societies():
    """Get list of active societies for resident signup"""
    societies = await societies_collection.find(
        {"status": "active"},
        {"_id": 0, "id": 1, "name": 1, "address": 1}
    ).to_list(1000)
    return societies


@router.get("/societies/{society_id}/wings")
async def get_society_wings(society_id: str):
    """Get wings for a society (for signup dropdown)"""
    wings = await wings_collection.find(
        {"society_id": society_id},
        {"_id": 0, "id": 1, "name": 1}
    ).to_list(100)
    return wings


@router.get("/wings/{wing_id}/flats")
async def get_wing_flats(wing_id: str):
    """Get available flats for a wing (for signup dropdown)"""
    flats = await flats_collection.find(
        {"wing_id": wing_id, "is_active": True, "resident_id": None},
        {"_id": 0, "id": 1, "number": 1, "floor": 1}
    ).to_list(1000)
    # Also get flats without resident_id field
    flats_no_field = await flats_collection.find(
        {"wing_id": wing_id, "is_active": True, "resident_id": {"$exists": False}},
        {"_id": 0, "id": 1, "number": 1, "floor": 1}
    ).to_list(1000)
    # Merge unique
    seen_ids = {f["id"] for f in flats}
    for f in flats_no_field:
        if f["id"] not in seen_ids:
            flats.append(f)
    return flats


# ============ CHECK ACCOUNT STATUS (for password setup) ============

@router.get("/check-status")
async def check_account_status(mobile: str):
    """Check if account exists and its status"""
    user = await users_collection.find_one(
        {"mobile": mobile, "role": "resident"},
        {"_id": 0, "id": 1, "status": 1, "needs_password_setup": 1, "name": 1}
    )
    if not user:
        return {"exists": False}
    return {
        "exists": True,
        "status": user["status"],
        "needs_password_setup": user.get("needs_password_setup", False),
        "name": user.get("name")
    }
