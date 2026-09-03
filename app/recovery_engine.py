"""Agentic recovery state machine with a hard 3-touch cap per customer."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from random import Random
from urllib.parse import quote
from uuid import uuid4

from app.razorpay_service import create_payment_link
from app.schemas import (
    AuditRecord,
    BatchMetrics,
    FailureReason,
    PtpStatus,
    RecoveryAction,
    RecoveryStatus,
    TransactionRecord,
)

MAX_TOUCHES = 3

# Simulated conversion by playbook. Silent bank retries convert highest.
SUCCESS_RATES: dict[RecoveryAction, float] = {
    RecoveryAction.SCHEDULE_SILENT_RETRY: 0.68,
    RecoveryAction.HINGLISH_NUDGE: 0.40,
    RecoveryAction.UPI_FALLBACK_LINK: 0.45,
    RecoveryAction.STOP_ESCALATE: 0.0,
}

AUDIT_LEDGER: list[AuditRecord] = []
_LATEST_BATCH_ID: str | None = None


@dataclass
class PtpState:
    promise_date: date
    status: PtpStatus
    set_at: datetime


PTP_STORE: dict[str, PtpState] = {}


def get_audit_trail(batch_id: str | None = None) -> list[AuditRecord]:
    """Return an append-only snapshot. Records themselves are frozen."""
    target = batch_id or _LATEST_BATCH_ID
    if target is None:
        rows = list(AUDIT_LEDGER)
    else:
        rows = [row for row in AUDIT_LEDGER if row.batch_id == target]
    return [_overlay_ptp(row) for row in rows]


def _find_audit(txn_id: str) -> AuditRecord | None:
    latest = [row for row in reversed(AUDIT_LEDGER) if row.txn_id == txn_id]
    return latest[0] if latest else None


def _wa_local_number(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("91") and len(digits) >= 12:
        return digits[2:]
    return digits.lstrip("0")


def build_whatsapp_deep_link(phone: str, message: str) -> str:
    """Hinglish body encoded into a clickable wa.me URL."""
    return f"https://wa.me/91{_wa_local_number(phone)}?text={quote(message)}"


def _resolve_ptp_status(row: AuditRecord, state: PtpState) -> PtpStatus:
    if row.recovered or row.status == RecoveryStatus.RECOVERED:
        return PtpStatus.HONORED
    if state.promise_date < date.today():
        return PtpStatus.BROKEN
    return PtpStatus.PROMISED_PAYMENT


def _overlay_ptp(row: AuditRecord) -> AuditRecord:
    state = PTP_STORE.get(row.txn_id)
    if state is None:
        return row
    status = _resolve_ptp_status(row, state)
    return row.model_copy(update={"ptp_status": status, "ptp_date": state.promise_date})


def _ptp_holds(txn_id: str) -> PtpState | None:
    state = PTP_STORE.get(txn_id)
    if state is None:
        return None
    if state.status == PtpStatus.HONORED:
        return None
    if state.promise_date >= date.today():
        return state
    return None


def set_promise_to_pay(txn_id: str, promise_date: date) -> AuditRecord:
    """Record a PTP date and hold further recovery touches until that date."""
    row = _find_audit(txn_id)
    if row is None:
        raise KeyError(txn_id)
    initial = PtpStatus.HONORED if row.recovered else PtpStatus.PROMISED_PAYMENT
    PTP_STORE[txn_id] = PtpState(
        promise_date=promise_date,
        status=initial,
        set_at=datetime.now(timezone.utc),
    )
    return _overlay_ptp(row)


def _action_for_failure(reason: FailureReason) -> RecoveryAction:
    mapping = {
        FailureReason.BANK_DOWNTIME: RecoveryAction.SCHEDULE_SILENT_RETRY,
        FailureReason.INSUFFICIENT_FUNDS: RecoveryAction.HINGLISH_NUDGE,
        FailureReason.EXPIRED: RecoveryAction.UPI_FALLBACK_LINK,
    }
    return mapping[reason]


def _simulate_success(txn_id: str, action: RecoveryAction) -> bool:
    rate = SUCCESS_RATES[action]
    rng = Random(int(abs(hash(txn_id)) % (2**32)))
    return rng.random() < rate


def _whatsapp_hinglish(name: str, amount: float, link: str) -> str:
    first = name.split()[0]
    return (
        f"Namaste {first} ji! Aapka ₹{amount:,.2f} payment fail ho gaya. "
        f"UPI pe 1-tap se complete kijiye — link 15 min valid hai: {link}"
    )


def _upi_fallback_copy(name: str, amount: float, link: str) -> str:
    return (
        f"Hi {name}, your checkout session expired before ₹{amount:,.2f} was captured. "
        f"Complete via this Razorpay UPI fallback link: {link}"
    )


def _silent_retry_copy(txn_id: str) -> str:
    return (
        f"Bank rails marked down. Silent retry queued for {txn_id} "
        "with no customer notification."
    )


def run_batch(records: list[TransactionRecord]) -> BatchMetrics:
    """Evaluate each failed txn, enforce the 3-touch rule, append the ledger."""
    global _LATEST_BATCH_ID

    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}"
    _LATEST_BATCH_ID = batch_id

    touches_by_customer: dict[str, int] = defaultdict(int)
    amount_at_risk = 0.0
    amount_recovered = 0.0
    escalated_count = 0
    recovered_count = 0
    retrying_count = 0

    for txn in records:
        amount_at_risk += txn.amount_inr
        current_touches = touches_by_customer[txn.phone]
        payment_link: str | None = None
        whatsapp_url: str | None = None
        hold = _ptp_holds(txn.txn_id)

        if hold is not None:
            action = _action_for_failure(txn.failure_reason)
            recovered = False
            status = RecoveryStatus.RETRYING
            touch_count = current_touches
            decision = (
                f"PTP hold active until {hold.promise_date.isoformat()}. "
                "Retries suppressed; no customer touch consumed."
            )
            channel_payload = (
                f"Outreach paused for promised payment on {hold.promise_date.isoformat()}."
            )
        elif current_touches >= MAX_TOUCHES:
            action = RecoveryAction.STOP_ESCALATE
            recovered = False
            status = RecoveryStatus.ESCALATED
            touch_count = current_touches
            decision = (
                f"Stopping rule fired: customer {txn.phone} already has "
                f"{current_touches} touches. No further outreach."
            )
            channel_payload = "HALTED — max 3 customer touches reached"
        else:
            action = _action_for_failure(txn.failure_reason)
            if action in (
                RecoveryAction.HINGLISH_NUDGE,
                RecoveryAction.UPI_FALLBACK_LINK,
            ):
                payment_link = create_payment_link(
                    amount_inr=txn.amount_inr,
                    customer_name=txn.customer_name,
                    phone=txn.phone,
                    txn_id=txn.txn_id,
                )

            recovered = _simulate_success(txn.txn_id, action)
            touches_by_customer[txn.phone] = current_touches + 1
            touch_count = touches_by_customer[txn.phone]

            if recovered:
                status = RecoveryStatus.RECOVERED
            else:
                status = RecoveryStatus.RETRYING

            if action == RecoveryAction.SCHEDULE_SILENT_RETRY:
                channel_payload = _silent_retry_copy(txn.txn_id)
                decision = (
                    "BANK_DOWNTIME diagnosed. Scheduled silent gateway retry; "
                    "customer is not messaged."
                )
            elif action == RecoveryAction.HINGLISH_NUDGE:
                channel_payload = _whatsapp_hinglish(
                    txn.customer_name, txn.amount_inr, payment_link or ""
                )
                whatsapp_url = build_whatsapp_deep_link(txn.phone, channel_payload)
                decision = (
                    "INSUFFICIENT_FUNDS diagnosed. WhatsApp Hinglish nudge sent "
                    "with a dynamic Razorpay UPI link."
                )
            else:
                channel_payload = _upi_fallback_copy(
                    txn.customer_name, txn.amount_inr, payment_link or ""
                )
                decision = (
                    "EXPIRED session diagnosed. Fresh UPI fallback payment link issued."
                )

        if recovered and txn.txn_id in PTP_STORE:
            PTP_STORE[txn.txn_id].status = PtpStatus.HONORED

        recovered_amount = txn.amount_inr if recovered else 0.0
        amount_recovered += recovered_amount
        if status == RecoveryStatus.ESCALATED:
            escalated_count += 1
        elif status == RecoveryStatus.RECOVERED:
            recovered_count += 1
        else:
            retrying_count += 1

        ptp_state = PTP_STORE.get(txn.txn_id)
        ptp_status = txn.ptp_status
        ptp_date = txn.ptp_date
        if ptp_state is not None:
            ptp_date = ptp_state.promise_date
            ptp_status = (
                PtpStatus.HONORED
                if recovered
                else (
                    PtpStatus.BROKEN
                    if ptp_state.promise_date < date.today()
                    else PtpStatus.PROMISED_PAYMENT
                )
            )

        AUDIT_LEDGER.append(
            AuditRecord(
                audit_id=f"aud_{uuid4().hex[:12]}",
                batch_id=batch_id,
                txn_id=txn.txn_id,
                customer_name=txn.customer_name,
                phone=txn.phone,
                amount_inr=txn.amount_inr,
                failure_reason=txn.failure_reason,
                action=action,
                status=status,
                recovered=recovered,
                amount_recovered=round(recovered_amount, 2),
                touch_count=touch_count,
                decision=decision,
                channel_payload=channel_payload,
                payment_link=payment_link,
                whatsapp_url=whatsapp_url,
                ptp_status=ptp_status,
                ptp_date=ptp_date,
                timestamp=datetime.now(timezone.utc),
            )
        )

    recovery_rate = (amount_recovered / amount_at_risk * 100.0) if amount_at_risk else 0.0
    return BatchMetrics(
        total_records=len(records),
        amount_at_risk=round(amount_at_risk, 2),
        amount_recovered=round(amount_recovered, 2),
        recovery_rate_pct=round(recovery_rate, 2),
        escalated_count=escalated_count,
        batch_id=batch_id,
        recovered_count=recovered_count,
        retrying_count=retrying_count,
    )
