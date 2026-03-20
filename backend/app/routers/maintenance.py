from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from datetime import datetime, timezone
from ..models.maintenance import (
    MaintenancePreviewRequest, MaintenanceGenerateRequest,
    MaintenanceBatch, FlatBill, FlatBillAudit,
    PaymentSubmitRequest, PaymentVerifyRequest, BillCancelRequest,
    MaintenancePreviewResponse
)
from ..core.database import (
    flats_collection, wings_collection, users_collection,
    maintenance_batches_collection, flat_bills_collection,
    flat_bill_audits_collection, wallet_transactions_collection
)
from ..core.security import require_role, get_current_user

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

# ============ ADMIN - BILL GENERATION ============
@router.get("/admin/preview")
async def preview_maintenance(
    month: str,
    amount_per_flat: float,
    current_user: dict = Depends(require_role("admin"))
):
    """Preview maintenance bill generation before creating"""
    society_id = current_user.get("society_id")
    
    # Check if batch already exists for this month
    existing_batch = await maintenance_batches_collection.find_one({
        "society_id": society_id,
        "month": month
    })
    if existing_batch:
        raise HTTPException(
            status_code=400,
            detail=f"Bills already generated for {month}"
        )
    
    # Get all active flats
    flats = await flats_collection.find({
        "society_id": society_id,
        "is_active": True
    }, {"_id": 0}).to_list(1000)
    
    flat_list = []
    for flat in flats:
        wing = await wings_collection.find_one({"id": flat["wing_id"]}, {"_id": 0, "name": 1})
        resident_name = None
        if flat.get("resident_id"):
            resident = await users_collection.find_one({"id": flat["resident_id"]}, {"_id": 0, "name": 1})
            if resident:
                resident_name = resident["name"]
        
        flat_list.append({
            "id": flat["id"],
            "number": flat["number"],
            "wing_id": flat["wing_id"],
            "wing_name": wing["name"] if wing else "Unknown",
            "floor": flat["floor"],
            "resident_id": flat.get("resident_id"),
            "resident_name": resident_name,
            "amount": amount_per_flat,
            "is_active": True
        })
    
    return {
        "month": month,
        "amount_per_flat": amount_per_flat,
        "total_active_flats": len(flat_list),
        "total_amount": len(flat_list) * amount_per_flat,
        "flats": flat_list
    }

@router.post("/admin/generate")
async def generate_maintenance_bills(
    data: MaintenanceGenerateRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Generate maintenance bills for a month"""
    society_id = current_user.get("society_id")
    
    # Check if batch already exists
    existing_batch = await maintenance_batches_collection.find_one({
        "society_id": society_id,
        "month": data.month
    })
    if existing_batch:
        raise HTTPException(
            status_code=400,
            detail=f"Bills already generated for {data.month}"
        )
    
    # Get all active flats
    flats = await flats_collection.find({
        "society_id": society_id,
        "is_active": True
    }, {"_id": 0}).to_list(1000)
    
    # Create batch
    billed_flats = [f for f in flats if f["id"] not in data.excluded_flat_ids]
    cancelled_flats = [f for f in flats if f["id"] in data.excluded_flat_ids]
    
    batch = MaintenanceBatch(
        society_id=society_id,
        month=data.month,
        amount_per_flat=data.amount_per_flat,
        total_flats=len(flats),
        cancelled_flats=len(cancelled_flats),
        billed_flats=len(billed_flats),
        total_amount=len(billed_flats) * data.amount_per_flat,
        generated_by=current_user["id"]
    )
    
    batch_dict = batch.model_dump()
    batch_dict['created_at'] = batch_dict['created_at'].isoformat()
    await maintenance_batches_collection.insert_one(batch_dict)
    
    # Create individual bills
    created_bills = []
    for flat in flats:
        wing = await wings_collection.find_one({"id": flat["wing_id"]}, {"_id": 0, "name": 1})
        resident_name = None
        if flat.get("resident_id"):
            resident = await users_collection.find_one({"id": flat["resident_id"]}, {"_id": 0, "name": 1})
            if resident:
                resident_name = resident["name"]
        
        is_cancelled = flat["id"] in data.excluded_flat_ids
        cancel_reason = data.cancel_reasons.get(flat["id"]) if is_cancelled else None
        
        bill = FlatBill(
            batch_id=batch.id,
            flat_id=flat["id"],
            flat_number=flat["number"],
            wing_id=flat["wing_id"],
            wing_name=wing["name"] if wing else "Unknown",
            resident_id=flat.get("resident_id"),
            resident_name=resident_name,
            amount=data.amount_per_flat,
            month=data.month,
            status="pending",
            is_cancelled=is_cancelled,
            cancel_reason=cancel_reason,
            cancelled_by=current_user["id"] if is_cancelled else None,
            cancelled_at=datetime.now(timezone.utc) if is_cancelled else None
        )
        
        bill_dict = bill.model_dump()
        bill_dict['created_at'] = bill_dict['created_at'].isoformat()
        if bill_dict.get('cancelled_at'):
            bill_dict['cancelled_at'] = bill_dict['cancelled_at'].isoformat()
        
        await flat_bills_collection.insert_one(bill_dict)
        created_bills.append(bill.id)
        
        # Create audit log for cancelled bills
        if is_cancelled:
            audit = FlatBillAudit(
                flat_bill_id=bill.id,
                flat_number=flat["number"],
                month=data.month,
                action="cancelled_on_generation",
                reason=cancel_reason,
                done_by_id=current_user["id"],
                done_by_name=current_user["name"],
                done_by_role=current_user["role"]
            )
            audit_dict = audit.model_dump()
            audit_dict['created_at'] = audit_dict['created_at'].isoformat()
            await flat_bill_audits_collection.insert_one(audit_dict)
    
    return {
        "message": f"Generated {len(billed_flats)} bills for {data.month}",
        "batch_id": batch.id,
        "total_bills": len(created_bills),
        "cancelled_bills": len(cancelled_flats),
        "total_amount": batch.total_amount
    }

@router.get("/admin/bills")
async def get_bills_admin(
    month: Optional[str] = None,
    wing_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(require_role("admin"))
):
    """Get all bills for admin view"""
    society_id = current_user.get("society_id")
    
    # First get batches for this society
    batch_query = {"society_id": society_id}
    if month:
        batch_query["month"] = month
    
    batches = await maintenance_batches_collection.find(batch_query, {"_id": 0}).to_list(100)
    batch_ids = [b["id"] for b in batches]
    
    # Get bills
    bill_query = {"batch_id": {"$in": batch_ids}}
    if wing_id:
        bill_query["wing_id"] = wing_id
    if status:
        bill_query["status"] = status
    
    bills = await flat_bills_collection.find(bill_query, {"_id": 0}).to_list(10000)
    
    # Process dates
    for bill in bills:
        for date_field in ['created_at', 'cancelled_at', 'paid_at', 'verified_at']:
            if bill.get(date_field) and isinstance(bill[date_field], str):
                bill[date_field] = datetime.fromisoformat(bill[date_field].replace('Z', '+00:00'))
    
    return bills

@router.put("/admin/bills/{bill_id}/cancel")
async def cancel_bill(
    bill_id: str,
    data: BillCancelRequest,
    current_user: dict = Depends(require_role("admin"))
):
    """Cancel a flat bill"""
    bill = await flat_bills_collection.find_one({"id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    if bill.get("is_cancelled"):
        raise HTTPException(status_code=400, detail="Bill is already cancelled")
    
    if bill.get("status") == "verified":
        raise HTTPException(status_code=400, detail="Cannot cancel verified bill")
    
    # Update bill
    await flat_bills_collection.update_one(
        {"id": bill_id},
        {"$set": {
            "is_cancelled": True,
            "cancel_reason": data.reason,
            "cancelled_by": current_user["id"],
            "cancelled_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Create audit log
    audit = FlatBillAudit(
        flat_bill_id=bill_id,
        flat_number=bill["flat_number"],
        month=bill["month"],
        action="cancelled",
        reason=data.reason,
        done_by_id=current_user["id"],
        done_by_name=current_user["name"],
        done_by_role=current_user["role"]
    )
    audit_dict = audit.model_dump()
    audit_dict['created_at'] = audit_dict['created_at'].isoformat()
    await flat_bill_audits_collection.insert_one(audit_dict)
    
    return {"message": "Bill cancelled successfully"}

@router.put("/admin/bills/{bill_id}/restore")
async def restore_bill(
    bill_id: str,
    current_user: dict = Depends(require_role("admin"))
):
    """Restore a cancelled bill"""
    bill = await flat_bills_collection.find_one({"id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    if not bill.get("is_cancelled"):
        raise HTTPException(status_code=400, detail="Bill is not cancelled")
    
    await flat_bills_collection.update_one(
        {"id": bill_id},
        {"$set": {
            "is_cancelled": False,
            "cancel_reason": None,
            "cancelled_by": None,
            "cancelled_at": None
        }}
    )
    
    # Create audit log
    audit = FlatBillAudit(
        flat_bill_id=bill_id,
        flat_number=bill["flat_number"],
        month=bill["month"],
        action="restored",
        reason=None,
        done_by_id=current_user["id"],
        done_by_name=current_user["name"],
        done_by_role=current_user["role"]
    )
    audit_dict = audit.model_dump()
    audit_dict['created_at'] = audit_dict['created_at'].isoformat()
    await flat_bill_audits_collection.insert_one(audit_dict)
    
    return {"message": "Bill restored successfully"}

@router.get("/admin/audit")
async def get_bill_audit(
    month: Optional[str] = None,
    current_user: dict = Depends(require_role("admin"))
):
    """Get audit trail for bills"""
    query = {}
    if month:
        query["month"] = month
    
    audits = await flat_bill_audits_collection.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    for audit in audits:
        if isinstance(audit.get("created_at"), str):
            audit["created_at"] = datetime.fromisoformat(audit["created_at"].replace('Z', '+00:00'))
    
    return audits

@router.get("/admin/batches")
async def get_batches(current_user: dict = Depends(require_role("admin"))):
    """Get all maintenance batches"""
    society_id = current_user.get("society_id")
    batches = await maintenance_batches_collection.find(
        {"society_id": society_id},
        {"_id": 0}
    ).sort("month", -1).to_list(100)
    
    for batch in batches:
        if isinstance(batch.get("created_at"), str):
            batch["created_at"] = datetime.fromisoformat(batch["created_at"].replace('Z', '+00:00'))
    
    return batches

# ============ SUB-ADMIN - PAYMENT VERIFICATION ============
@router.get("/subadmin/pending")
async def get_pending_payments(current_user: dict = Depends(require_role("sub_admin"))):
    """Get pending payments for sub-admin's wing"""
    wing_id = current_user.get("wing_id")
    if not wing_id:
        raise HTTPException(status_code=400, detail="Sub-admin not assigned to any wing")
    
    bills = await flat_bills_collection.find({
        "wing_id": wing_id,
        "status": "paid",
        "is_cancelled": False
    }, {"_id": 0}).to_list(1000)
    
    for bill in bills:
        for date_field in ['created_at', 'paid_at']:
            if bill.get(date_field) and isinstance(bill[date_field], str):
                bill[date_field] = datetime.fromisoformat(bill[date_field].replace('Z', '+00:00'))
    
    return bills

@router.post("/subadmin/verify/{bill_id}")
async def verify_payment(
    bill_id: str,
    data: PaymentVerifyRequest,
    current_user: dict = Depends(require_role("sub_admin"))
):
    """Verify or reject a payment"""
    wing_id = current_user.get("wing_id")
    
    bill = await flat_bills_collection.find_one({
        "id": bill_id,
        "wing_id": wing_id
    }, {"_id": 0})
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found or not in your wing")
    
    if bill.get("status") != "paid":
        raise HTTPException(status_code=400, detail="Bill is not in paid status")
    
    if data.action == "approve":
        # Update bill to verified
        await flat_bills_collection.update_one(
            {"id": bill_id},
            {"$set": {
                "status": "verified",
                "verified_by": current_user["id"],
                "verified_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Credit wallet points (₹1 = 1 point)
        if bill.get("resident_id"):
            # Get current wallet balance
            last_txn = await wallet_transactions_collection.find_one(
                {"user_id": bill["resident_id"]},
                {"_id": 0},
                sort=[("created_at", -1)]
            )
            current_balance = last_txn.get("balance_after", 0) if last_txn else 0
            new_balance = current_balance + bill["amount"]
            
            from ..models.finance import WalletTransaction
            txn = WalletTransaction(
                user_id=bill["resident_id"],
                flat_bill_id=bill_id,
                type="credit",
                points=bill["amount"],
                balance_after=new_balance,
                description=f"Maintenance payment verified for {bill['month']}"
            )
            txn_dict = txn.model_dump()
            txn_dict['created_at'] = txn_dict['created_at'].isoformat()
            await wallet_transactions_collection.insert_one(txn_dict)
        
        # Create audit log
        audit = FlatBillAudit(
            flat_bill_id=bill_id,
            flat_number=bill["flat_number"],
            month=bill["month"],
            action="verified",
            reason=None,
            done_by_id=current_user["id"],
            done_by_name=current_user["name"],
            done_by_role=current_user["role"]
        )
        audit_dict = audit.model_dump()
        audit_dict['created_at'] = audit_dict['created_at'].isoformat()
        await flat_bill_audits_collection.insert_one(audit_dict)
        
        return {"message": "Payment verified and wallet credited"}
    
    else:  # reject
        if not data.reason:
            raise HTTPException(status_code=400, detail="Reason required for rejection")
        
        await flat_bills_collection.update_one(
            {"id": bill_id},
            {"$set": {
                "status": "pending",
                "paid_at": None,
                "payment_mode": None,
                "payment_ref": None
            }}
        )
        
        audit = FlatBillAudit(
            flat_bill_id=bill_id,
            flat_number=bill["flat_number"],
            month=bill["month"],
            action="payment_rejected",
            reason=data.reason,
            done_by_id=current_user["id"],
            done_by_name=current_user["name"],
            done_by_role=current_user["role"]
        )
        audit_dict = audit.model_dump()
        audit_dict['created_at'] = audit_dict['created_at'].isoformat()
        await flat_bill_audits_collection.insert_one(audit_dict)
        
        return {"message": "Payment rejected"}

# ============ RESIDENT - BILLS & PAYMENT ============
@router.get("/resident/bills")
async def get_resident_bills(current_user: dict = Depends(require_role("resident", "sub_admin", "admin"))):
    """Get bills for current resident"""
    flat_id = current_user.get("flat_id")
    if not flat_id:
        return []
    
    bills = await flat_bills_collection.find({
        "flat_id": flat_id,
        "is_cancelled": False
    }, {"_id": 0}).sort("month", -1).to_list(100)
    
    for bill in bills:
        for date_field in ['created_at', 'paid_at', 'verified_at']:
            if bill.get(date_field) and isinstance(bill[date_field], str):
                bill[date_field] = datetime.fromisoformat(bill[date_field].replace('Z', '+00:00'))
    
    return bills

@router.post("/resident/bills/{bill_id}/pay")
async def submit_payment(
    bill_id: str,
    data: PaymentSubmitRequest,
    current_user: dict = Depends(require_role("resident", "sub_admin", "admin"))
):
    """Submit payment for a bill"""
    flat_id = current_user.get("flat_id")
    
    bill = await flat_bills_collection.find_one({
        "id": bill_id,
        "flat_id": flat_id
    }, {"_id": 0})
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    if bill.get("status") not in ["pending", "overdue"]:
        raise HTTPException(status_code=400, detail="Bill cannot be paid")
    
    await flat_bills_collection.update_one(
        {"id": bill_id},
        {"$set": {
            "status": "paid",
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "payment_mode": data.payment_mode,
            "payment_ref": data.payment_ref
        }}
    )
    
    audit = FlatBillAudit(
        flat_bill_id=bill_id,
        flat_number=bill["flat_number"],
        month=bill["month"],
        action="payment_submitted",
        reason=f"Mode: {data.payment_mode}, Ref: {data.payment_ref}",
        done_by_id=current_user["id"],
        done_by_name=current_user["name"],
        done_by_role=current_user["role"]
    )
    audit_dict = audit.model_dump()
    audit_dict['created_at'] = audit_dict['created_at'].isoformat()
    await flat_bill_audits_collection.insert_one(audit_dict)
    
    return {"message": "Payment submitted. Waiting for verification."}

# ============ WALLET ============
@router.get("/wallet")
async def get_wallet(current_user: dict = Depends(get_current_user)):
    """Get wallet balance and transaction history"""
    user_id = current_user["id"]
    
    # Get last transaction for balance
    last_txn = await wallet_transactions_collection.find_one(
        {"user_id": user_id},
        {"_id": 0},
        sort=[("created_at", -1)]
    )
    balance = last_txn.get("balance_after", 0) if last_txn else 0
    
    # Get transaction history
    transactions = await wallet_transactions_collection.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    for txn in transactions:
        if isinstance(txn.get("created_at"), str):
            txn["created_at"] = datetime.fromisoformat(txn["created_at"].replace('Z', '+00:00'))
    
    return {
        "balance": balance,
        "transactions": transactions
    }
