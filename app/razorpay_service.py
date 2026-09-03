"""Razorpay payment-link helper with deterministic mock fallback."""

from __future__ import annotations

import razorpay

from app.config import RZP_KEY_ID, RZP_KEY_SECRET

MOCK_KEY_ID = "rzp_test_recoverai"
MOCK_KEY_SECRET = "recoverai_test_secret"


def get_client() -> razorpay.Client:
    key_id = RZP_KEY_ID or MOCK_KEY_ID
    key_secret = RZP_KEY_SECRET or MOCK_KEY_SECRET
    return razorpay.Client(auth=(key_id, key_secret))


def create_payment_link(
    amount_inr: float,
    customer_name: str,
    phone: str,
    txn_id: str,
    description: str | None = None,
) -> str:
    """Create a Razorpay payment link. Amount is sent in paise (INR * 100).

    Live/test credential failures fall back to a stable mock short URL so the
    batch engine never blocks on network or auth.
    """
    amount_paise = int(round(float(amount_inr) * 100))
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": description or f"RecoverAI collection for {txn_id}",
        "customer": {
            "name": customer_name,
            "contact": phone,
        },
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "notes": {"txn_id": txn_id, "source": "recover-ai"},
    }
    try:
        client = get_client()
        link = client.payment_link.create(payload)
        return str(link.get("short_url") or link.get("id") or _mock_link(txn_id))
    except Exception:
        return _mock_link(txn_id)


def _mock_link(txn_id: str) -> str:
    return f"https://rzp.io/i/recoverai-{txn_id}"
