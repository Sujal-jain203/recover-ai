"""FastAPI entrypoint for the RecoverAI dashboard and recovery APIs."""

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import RZP_KEY_ID
from app.data_generator import generate_failed_transactions
from app.razorpay_service import MOCK_KEY_ID, RazorpayService
from app.recovery_engine import get_audit_trail, get_transaction, run_batch, set_promise_to_pay
from app.schemas import (
    AuditRecord,
    BatchMetrics,
    CheckoutOrderResponse,
    CheckoutRequest,
    PtpRequest,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="RecoverAI",
    description="Autonomous revenue recovery engine.",
    version="1.0.0",
)

api = APIRouter()


@api.post("/run-batch", response_model=BatchMetrics)
def run_batch_recovery() -> BatchMetrics:
    records = generate_failed_transactions(50)
    return run_batch(records)


@api.get("/audit-trail", response_model=list[AuditRecord])
def audit_trail() -> list[AuditRecord]:
    return get_audit_trail()


@api.post("/transactions/{txn_id}/ptp", response_model=AuditRecord)
def record_promise_to_pay(txn_id: str, body: PtpRequest) -> AuditRecord:
    try:
        return set_promise_to_pay(txn_id, body.promise_date)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Transaction not found") from exc


def _checkout_response(
    txn_id: str,
    amount_inr: float | None,
    customer_name: str | None,
    phone: str | None,
) -> CheckoutOrderResponse:
    name = customer_name or ""
    contact = phone or ""
    amount_value = amount_inr
    try:
        row = get_transaction(txn_id)
        name = row.customer_name
        contact = row.phone
        amount_value = row.amount_inr
    except KeyError:
        if amount_value is None:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found. Run Batch Recovery first, then click Pay Now.",
            )
    amount = int(round(float(amount_value)))
    if amount < 1:
        raise HTTPException(status_code=400, detail="Amount must be at least ₹1")
    order_id = RazorpayService().create_checkout_order(amount, txn_id)
    return CheckoutOrderResponse(
        order_id=order_id,
        amount_inr=amount,
        key_id=RZP_KEY_ID or MOCK_KEY_ID,
        txn_id=txn_id,
        customer_name=name,
        phone=contact,
    )


@api.post("/create-checkout/{txn_id}", response_model=CheckoutOrderResponse)
def create_checkout_post(txn_id: str, body: CheckoutRequest | None = None) -> CheckoutOrderResponse:
    payload = body or CheckoutRequest()
    return _checkout_response(
        txn_id=txn_id,
        amount_inr=payload.amount_inr,
        customer_name=payload.customer_name,
        phone=payload.phone,
    )


@api.get("/create-checkout/{txn_id}", response_model=CheckoutOrderResponse)
def create_checkout_get(
    txn_id: str,
    amount_inr: float | None = Query(default=None),
    customer_name: str | None = Query(default=None),
    phone: str | None = Query(default=None),
) -> CheckoutOrderResponse:
    return _checkout_response(
        txn_id=txn_id,
        amount_inr=amount_inr,
        customer_name=customer_name,
        phone=phone,
    )


# Local uvicorn uses /api/*. Vercel may strip the /api prefix from api/index.py.
app.include_router(api, prefix="/api")
app.include_router(api, prefix="")


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
