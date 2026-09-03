"""FastAPI entrypoint for the RecoverAI dashboard and recovery APIs."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.data_generator import generate_failed_transactions
from app.recovery_engine import get_audit_trail, run_batch, set_promise_to_pay
from app.schemas import AuditRecord, BatchMetrics, PtpRequest

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="RecoverAI",
    description="Autonomous revenue recovery engine for Razorpay AI Buildathon Track 03.",
    version="1.0.0",
)


@app.post("/api/run-batch", response_model=BatchMetrics)
def run_batch_recovery() -> BatchMetrics:
    records = generate_failed_transactions(50)
    return run_batch(records)


@app.get("/api/audit-trail", response_model=list[AuditRecord])
def audit_trail() -> list[AuditRecord]:
    return get_audit_trail()


@app.post("/api/transactions/{txn_id}/ptp", response_model=AuditRecord)
def record_promise_to_pay(txn_id: str, body: PtpRequest) -> AuditRecord:
    try:
        return set_promise_to_pay(txn_id, body.promise_date)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Transaction not found") from exc


app.mount(
    "/",
    StaticFiles(directory=str(BASE_DIR / "static"), html=True),
    name="static",
)
