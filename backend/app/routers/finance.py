from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime, timezone
from ..models.finance import (
    IncomeEntry, IncomeEntryCreate,
    ExpenseBill, ExpenseBillCreate, ExpenseVerification, ExpenseVerifyRequest,
    Plan, PlanCreate, PlanApproval, PlanApprovalRequest
)
from ..core.database import (
    income_entries_collection, expense_bills_collection, expense_verifications_collection,
    plans_collection, plan_approvals_collection, users_collection, wings_collection,
    flat_bills_collection, maintenance_batches_collection
)
from ..core.security import require_role, get_current_user

router = APIRouter(tags=["Finance"])

# ============ INCOME ENTRIES ============
@router.post("/admin/income", response_model=dict)
async def create_income_entry(
    data: IncomeEntryCreate,
    current_user: dict = Depends(require_role("admin"))
):
    """Create a new income entry"""
    entry = IncomeEntry(
        society_id=current_user["society_id"],
        title=data.title,
        category=data.category,
        amount=data.amount,
        entry_date=data.entry_date,
        description=data.description,
        created_by=current_user["id"]
    )
    
    entry_dict = entry.model_dump()
    entry_dict['created_at'] = entry_dict['created_at'].isoformat()
    await income_entries_collection.insert_one(entry_dict)
    
    return {"message": "Income entry created", "id": entry.id}

@router.get("/admin/income")
async def get_income_entries(current_user: dict = Depends(require_role("admin"))):
    """Get all income entries for admin's society"""
    entries = await income_entries_collection.find(
        {"society_id": current_user["society_id"]},
        {"_id": 0}
    ).sort("entry_date", -1).to_list(1000)
    
    for entry in entries:
        if isinstance(entry.get("created_at"), str):
            entry["created_at"] = datetime.fromisoformat(entry["created_at"].replace('Z', '+00:00'))
    
    return entries

# ============ EXPENSE BILLS ============
@router.post("/admin/expenses", response_model=dict)
async def create_expense_bill(
    data: ExpenseBillCreate,
    current_user: dict = Depends(require_role("admin"))
):
    """Create a new expense bill"""
    expense = ExpenseBill(
        society_id=current_user["society_id"],
        title=data.title,
        category=data.category,
        amount=data.amount,
        bill_date=data.bill_date,
        description=data.description,
        created_by=current_user["id"]
    )
    
    expense_dict = expense.model_dump()
    expense_dict['created_at'] = expense_dict['created_at'].isoformat()
    await expense_bills_collection.insert_one(expense_dict)
    
    # Create verification entries for all sub-admins
    sub_admins = await users_collection.find({
        "society_id": current_user["society_id"],
        "role": "sub_admin",
        "status": "active"
    }, {"_id": 0}).to_list(100)
    
    for sa in sub_admins:
        verification = ExpenseVerification(
            expense_bill_id=expense.id,
            sub_admin_id=sa["id"],
            sub_admin_name=sa["name"]
        )
        v_dict = verification.model_dump()
        v_dict['created_at'] = v_dict['created_at'].isoformat()
        await expense_verifications_collection.insert_one(v_dict)
    
    return {"message": "Expense bill created", "id": expense.id}

@router.get("/admin/expenses")
async def get_expense_bills(current_user: dict = Depends(require_role("admin"))):
    """Get all expense bills for admin's society"""
    expenses = await expense_bills_collection.find(
        {"society_id": current_user["society_id"]},
        {"_id": 0}
    ).sort("bill_date", -1).to_list(1000)
    
    result = []
    for expense in expenses:
        # Get verifications
        verifications = await expense_verifications_collection.find(
            {"expense_bill_id": expense["id"]},
            {"_id": 0}
        ).to_list(100)
        
        if isinstance(expense.get("created_at"), str):
            expense["created_at"] = datetime.fromisoformat(expense["created_at"].replace('Z', '+00:00'))
        
        result.append({
            **expense,
            "verifications": verifications
        })
    
    return result

@router.get("/subadmin/expenses/pending")
async def get_pending_expense_verifications(
    current_user: dict = Depends(require_role("sub_admin"))
):
    """Get expense bills pending verification by this sub-admin"""
    verifications = await expense_verifications_collection.find({
        "sub_admin_id": current_user["id"],
        "decision": "pending"
    }, {"_id": 0}).to_list(100)
    
    result = []
    for v in verifications:
        expense = await expense_bills_collection.find_one(
            {"id": v["expense_bill_id"]},
            {"_id": 0}
        )
        if expense:
            if isinstance(expense.get("created_at"), str):
                expense["created_at"] = datetime.fromisoformat(expense["created_at"].replace('Z', '+00:00'))
            result.append({
                "verification_id": v["id"],
                "expense": expense
            })
    
    return result

@router.post("/subadmin/expenses/{expense_id}/verify")
async def verify_expense(
    expense_id: str,
    data: ExpenseVerifyRequest,
    current_user: dict = Depends(require_role("sub_admin"))
):
    """Verify or reject an expense bill"""
    verification = await expense_verifications_collection.find_one({
        "expense_bill_id": expense_id,
        "sub_admin_id": current_user["id"]
    })
    
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    
    if verification["decision"] != "pending":
        raise HTTPException(status_code=400, detail="Already verified")
    
    # Update verification
    await expense_verifications_collection.update_one(
        {"id": verification["id"]},
        {"$set": {
            "decision": data.decision,
            "reason": data.reason,
            "created_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Check all verifications to update expense status
    all_verifications = await expense_verifications_collection.find(
        {"expense_bill_id": expense_id},
        {"_id": 0}
    ).to_list(100)
    
    approved_count = sum(1 for v in all_verifications if v["decision"] == "approved")
    rejected_count = sum(1 for v in all_verifications if v["decision"] == "rejected")
    total = len(all_verifications)
    
    if rejected_count > 0:
        new_status = "rejected"
    elif approved_count == total:
        new_status = "verified"
    elif approved_count > 0:
        new_status = "partially_verified"
    else:
        new_status = "pending"
    
    # Update verified_by_ids
    verified_by = [v["sub_admin_id"] for v in all_verifications if v["decision"] == "approved"]
    
    await expense_bills_collection.update_one(
        {"id": expense_id},
        {"$set": {
            "status": new_status,
            "verified_by_ids": verified_by
        }}
    )
    
    return {"message": f"Expense {data.decision}", "new_status": new_status}

# ============ PLANS ============
@router.post("/admin/plans", response_model=dict)
async def create_plan(
    data: PlanCreate,
    current_user: dict = Depends(require_role("admin"))
):
    """Create a new plan"""
    plan = Plan(
        society_id=current_user["society_id"],
        title=data.title,
        description=data.description,
        amount=data.amount,
        status="pending_approval",
        created_by=current_user["id"]
    )
    
    plan_dict = plan.model_dump()
    plan_dict['created_at'] = plan_dict['created_at'].isoformat()
    await plans_collection.insert_one(plan_dict)
    
    # Create approval entries for all sub-admins
    sub_admins = await users_collection.find({
        "society_id": current_user["society_id"],
        "role": "sub_admin",
        "status": "active"
    }, {"_id": 0}).to_list(100)
    
    for sa in sub_admins:
        approval = PlanApproval(
            plan_id=plan.id,
            sub_admin_id=sa["id"],
            sub_admin_name=sa["name"]
        )
        a_dict = approval.model_dump()
        a_dict['created_at'] = a_dict['created_at'].isoformat()
        await plan_approvals_collection.insert_one(a_dict)
    
    return {"message": "Plan created and sent for approval", "id": plan.id}

@router.get("/admin/plans")
async def get_plans(current_user: dict = Depends(require_role("admin"))):
    """Get all plans for admin's society"""
    plans = await plans_collection.find(
        {"society_id": current_user["society_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    result = []
    for plan in plans:
        approvals = await plan_approvals_collection.find(
            {"plan_id": plan["id"]},
            {"_id": 0}
        ).to_list(100)
        
        if isinstance(plan.get("created_at"), str):
            plan["created_at"] = datetime.fromisoformat(plan["created_at"].replace('Z', '+00:00'))
        
        result.append({
            **plan,
            "approvals": approvals
        })
    
    return result

@router.get("/subadmin/plans/pending")
async def get_pending_plan_approvals(
    current_user: dict = Depends(require_role("sub_admin"))
):
    """Get plans pending approval by this sub-admin"""
    approvals = await plan_approvals_collection.find({
        "sub_admin_id": current_user["id"],
        "decision": "pending"
    }, {"_id": 0}).to_list(100)
    
    result = []
    for a in approvals:
        plan = await plans_collection.find_one(
            {"id": a["plan_id"]},
            {"_id": 0}
        )
        if plan and plan["status"] == "pending_approval":
            if isinstance(plan.get("created_at"), str):
                plan["created_at"] = datetime.fromisoformat(plan["created_at"].replace('Z', '+00:00'))
            result.append({
                "approval_id": a["id"],
                "plan": plan
            })
    
    return result

@router.post("/subadmin/plans/{plan_id}/approve")
async def approve_plan(
    plan_id: str,
    data: PlanApprovalRequest,
    current_user: dict = Depends(require_role("sub_admin"))
):
    """Approve or reject a plan"""
    approval = await plan_approvals_collection.find_one({
        "plan_id": plan_id,
        "sub_admin_id": current_user["id"]
    })
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    if approval["decision"] != "pending":
        raise HTTPException(status_code=400, detail="Already decided")
    
    # Update approval
    await plan_approvals_collection.update_one(
        {"id": approval["id"]},
        {"$set": {
            "decision": data.decision,
            "reason": data.reason,
            "created_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Check all approvals to update plan status
    all_approvals = await plan_approvals_collection.find(
        {"plan_id": plan_id},
        {"_id": 0}
    ).to_list(100)
    
    approved_count = sum(1 for a in all_approvals if a["decision"] == "approved")
    rejected_count = sum(1 for a in all_approvals if a["decision"] == "rejected")
    total = len(all_approvals)
    
    if rejected_count > 0:
        new_status = "rejected"
        # Collect rejection reasons
        rejection_reasons = [
            {"sub_admin_name": a["sub_admin_name"], "reason": a.get("reason", "")}
            for a in all_approvals if a["decision"] == "rejected"
        ]
        await plans_collection.update_one(
            {"id": plan_id},
            {"$set": {"status": new_status, "rejection_reasons": rejection_reasons}}
        )
    elif approved_count == total:
        new_status = "approved"
        await plans_collection.update_one(
            {"id": plan_id},
            {"$set": {"status": new_status}}
        )
    else:
        new_status = "pending_approval"
    
    return {"message": f"Plan {data.decision}", "new_status": new_status}

# ============ REPORTS ============
@router.get("/reports/income")
async def get_income_report(current_user: dict = Depends(get_current_user)):
    """Get income report for society"""
    society_id = current_user.get("society_id")
    if not society_id:
        return {"entries": [], "total": 0}
    
    entries = await income_entries_collection.find(
        {"society_id": society_id},
        {"_id": 0}
    ).sort("entry_date", -1).to_list(1000)
    
    total = sum(e["amount"] for e in entries)
    
    for entry in entries:
        if isinstance(entry.get("created_at"), str):
            entry["created_at"] = datetime.fromisoformat(entry["created_at"].replace('Z', '+00:00'))
    
    return {"entries": entries, "total": total}

@router.get("/reports/expenses")
async def get_expenses_report(current_user: dict = Depends(get_current_user)):
    """Get expenses report for society"""
    society_id = current_user.get("society_id")
    if not society_id:
        return {"entries": [], "total": 0}
    
    entries = await expense_bills_collection.find(
        {"society_id": society_id},
        {"_id": 0}
    ).sort("bill_date", -1).to_list(1000)
    
    total = sum(e["amount"] for e in entries)
    
    for entry in entries:
        if isinstance(entry.get("created_at"), str):
            entry["created_at"] = datetime.fromisoformat(entry["created_at"].replace('Z', '+00:00'))
    
    return {"entries": entries, "total": total}

@router.get("/reports/outstanding")
async def get_outstanding_summary(current_user: dict = Depends(get_current_user)):
    """Get month-wise outstanding summary"""
    society_id = current_user.get("society_id")
    if not society_id:
        return []
    
    # Get all batches
    batches = await maintenance_batches_collection.find(
        {"society_id": society_id},
        {"_id": 0}
    ).sort("month", -1).to_list(100)
    
    result = []
    for batch in batches:
        # Count outstanding bills for this month
        outstanding_bills = await flat_bills_collection.count_documents({
            "batch_id": batch["id"],
            "status": {"$nin": ["verified"]},
            "is_cancelled": False
        })
        
        total_outstanding = await flat_bills_collection.find({
            "batch_id": batch["id"],
            "status": {"$nin": ["verified"]},
            "is_cancelled": False
        }, {"_id": 0, "amount": 1}).to_list(10000)
        
        total_amount = sum(b["amount"] for b in total_outstanding)
        
        result.append({
            "month": batch["month"],
            "unpaid_count": outstanding_bills,
            "total_outstanding": total_amount
        })
    
    return result

@router.get("/reports/outstanding/{month}")
async def get_outstanding_detail(
    month: str,
    current_user: dict = Depends(get_current_user)
):
    """Get flat-wise outstanding detail for a month (cumulative)"""
    society_id = current_user.get("society_id")
    if not society_id:
        return {"flats": [], "grand_total": 0}
    
    # Get all months up to and including selected month
    batches = await maintenance_batches_collection.find({
        "society_id": society_id,
        "month": {"$lte": month}
    }, {"_id": 0}).to_list(100)
    
    batch_ids = [b["id"] for b in batches]
    
    # Get all outstanding bills up to this month
    bills = await flat_bills_collection.find({
        "batch_id": {"$in": batch_ids},
        "status": {"$nin": ["verified"]},
        "is_cancelled": False
    }, {"_id": 0}).to_list(10000)
    
    # Group by flat
    flat_totals = {}
    for bill in bills:
        flat_id = bill["flat_id"]
        if flat_id not in flat_totals:
            flat_totals[flat_id] = {
                "flat_id": flat_id,
                "flat_number": bill["flat_number"],
                "wing_name": bill["wing_name"],
                "resident_name": bill.get("resident_name", "Not Assigned"),
                "total_outstanding": 0,
                "months_pending": []
            }
        flat_totals[flat_id]["total_outstanding"] += bill["amount"]
        flat_totals[flat_id]["months_pending"].append(bill["month"])
    
    flats = list(flat_totals.values())
    flats.sort(key=lambda x: x["total_outstanding"], reverse=True)
    
    grand_total = sum(f["total_outstanding"] for f in flats)
    
    return {
        "month": month,
        "flats": flats,
        "grand_total": grand_total
    }
