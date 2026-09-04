"""Pydantic contracts for RecoverAI transactions, decisions, and batch metrics."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class FailureReason(str, Enum):
    BANK_DOWNTIME = "BANK_DOWNTIME"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    EXPIRED = "EXPIRED"


class RecoveryActionType(str, Enum):
    SCHEDULE_SILENT_RETRY = "SCHEDULE_SILENT_RETRY"
    HINGLISH_NUDGE = "HINGLISH_NUDGE"
    UPI_FALLBACK_LINK = "UPI_FALLBACK_LINK"
    STOP_ESCALATE = "STOP_ESCALATE"


class RecoveryAction(BaseModel):
    name: RecoveryActionType
    whatsapp_url: str | None = None


class RecoveryStatus(str, Enum):
    RECOVERED = "RECOVERED"
    RETRYING = "RETRYING"
    ESCALATED = "ESCALATED"


class PtpStatus(str, Enum):
    NOT_SET = "NOT_SET"
    PROMISED_PAYMENT = "PROMISED_PAYMENT"
    HONORED = "HONORED"
    BROKEN = "BROKEN"


class TransactionRecord(BaseModel):
    txn_id: str
    customer_name: str
    phone: str
    amount_inr: float = Field(ge=299, le=15000)
    failure_reason: FailureReason
    timestamp: datetime
    ptp_status: PtpStatus = PtpStatus.NOT_SET
    ptp_date: date | None = None


class AuditRecord(BaseModel):
    """Immutable ledger entry. Once created, fields cannot be mutated."""

    model_config = ConfigDict(frozen=True)

    audit_id: str
    batch_id: str
    txn_id: str
    customer_name: str
    phone: str
    amount_inr: float
    failure_reason: FailureReason
    action: RecoveryAction
    status: RecoveryStatus
    recovered: bool
    amount_recovered: float
    touch_count: int = Field(ge=0, le=3)
    decision: str
    channel_payload: str
    payment_link: str | None
    whatsapp_url: str | None = None
    ptp_status: PtpStatus = PtpStatus.NOT_SET
    ptp_date: date | None = None
    timestamp: datetime


class PtpRequest(BaseModel):
    promise_date: date


class CheckoutRequest(BaseModel):
    amount_inr: float | None = None
    customer_name: str | None = None
    phone: str | None = None


class CheckoutOrderResponse(BaseModel):
    order_id: str
    amount_inr: int
    key_id: str
    txn_id: str
    customer_name: str
    phone: str


class BatchMetrics(BaseModel):
    total_records: int
    amount_at_risk: float
    amount_recovered: float
    recovery_rate_pct: float
    escalated_count: int
    batch_id: str
    recovered_count: int
    retrying_count: int
