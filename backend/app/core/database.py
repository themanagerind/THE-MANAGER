from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]

# Collections
users_collection = db.users
societies_collection = db.societies
wings_collection = db.wings
flats_collection = db.flats
maintenance_batches_collection = db.maintenance_batches
flat_bills_collection = db.flat_bills
flat_bill_audits_collection = db.flat_bill_audits
income_entries_collection = db.income_entries
expense_bills_collection = db.expense_bills
expense_verifications_collection = db.expense_verifications
plans_collection = db.plans
plan_approvals_collection = db.plan_approvals
wallet_transactions_collection = db.wallet_transactions
notices_collection = db.notices
complaints_collection = db.complaints
platform_settings_collection = db.platform_settings

async def init_indexes():
    """Create database indexes"""
    await users_collection.create_index("mobile")
    await users_collection.create_index([("mobile", 1), ("role", 1)], unique=True)
    await societies_collection.create_index("admin_id")
    await wings_collection.create_index("society_id")
    await flats_collection.create_index([("wing_id", 1), ("number", 1)], unique=True)
    await flat_bills_collection.create_index([("batch_id", 1), ("flat_id", 1)])
    await flat_bills_collection.create_index("resident_id")
    await wallet_transactions_collection.create_index("user_id")

async def close_db():
    client.close()
