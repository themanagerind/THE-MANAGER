"""FastAPI application entrypoint."""
import logging
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.account_entries import router as account_entries_router
from app.api.v1.admin_change import router as admin_change_router
from app.api.v1.admins import router as admins_router
from app.api.v1.amenities import router as amenities_router
from app.api.v1.auth import router as auth_router
from app.api.v1.complaints import router as complaints_router
from app.api.v1.expense_bills import router as expense_bills_router
from app.api.v1.manager_todos import router as manager_todos_router
from app.api.v1.notices import router as notices_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.payments import router as payments_router
from app.api.v1.properties import router as properties_router
from app.api.v1.proposals import router as proposals_router
from app.api.v1.reports import router as reports_router
from app.api.v1.residents import router as residents_router
from app.api.v1.societies import router as societies_router
from app.api.v1.staff import router as staff_router
from app.api.v1.subadmins import router as subadmins_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.users import router as users_router
from app.api.v1.visitors import router as visitors_router
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("app")

app = FastAPI(title=settings.app_name)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(admins_router, prefix="/api/v1")
app.include_router(admin_change_router, prefix="/api/v1")
app.include_router(societies_router, prefix="/api/v1")
app.include_router(properties_router, prefix="/api/v1")
app.include_router(residents_router, prefix="/api/v1")
app.include_router(subadmins_router, prefix="/api/v1")
app.include_router(staff_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
app.include_router(proposals_router, prefix="/api/v1")
app.include_router(expense_bills_router, prefix="/api/v1")
app.include_router(manager_todos_router, prefix="/api/v1")
app.include_router(complaints_router, prefix="/api/v1")
app.include_router(visitors_router, prefix="/api/v1")
app.include_router(notices_router, prefix="/api/v1")
app.include_router(amenities_router, prefix="/api/v1")
app.include_router(account_entries_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")

# Audit fix: uploaded payment-proof files used to be served by a public
# StaticFiles mount here with no authentication at all. Files are now only
# readable through GET /payments/{payment_id}/proofs/{proof_id}/file
# (app/api/v1/payments.py), which enforces the same authorization as the
# proof-listing endpoint. This just ensures the storage directory exists.
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """API Contract Freeze — production security: never leak a stack trace
    or internal error detail to the client. HTTPException (400/401/403/404/
    409/429 etc, all raised deliberately throughout the services) is NOT
    caught here — FastAPI handles those with their own status + detail as
    normal; this only catches genuinely unexpected exceptions (Section 41:
    structured logging, no print statements)."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health() -> dict:
    """Section 41 — required for load balancer health checks."""
    return {"status": "ok"}
