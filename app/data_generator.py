"""Synthetic failed-transaction batch for RecoverAI demos."""

from datetime import datetime, timedelta, timezone
from random import Random

from app.schemas import FailureReason, TransactionRecord

CUSTOMERS: list[tuple[str, str]] = [
    ("Aarav Mehta", "919811000001"),
    ("Diya Sharma", "919811000002"),
    ("Kabir Iyer", "919811000003"),
    ("Ananya Reddy", "919811000004"),
    ("Ishaan Kapoor", "919811000005"),
    ("Meera Nair", "919811000006"),
    ("Rohan Joshi", "919811000007"),
    ("Saanvi Gupta", "919811000008"),
    ("Vivaan Rao", "919811000009"),
    ("Aisha Khan", "919811000010"),
    ("Arjun Patel", "919811000011"),
    ("Kiara Singh", "919811000012"),
    ("Advait Desai", "919811000013"),
    ("Myra Banerjee", "919811000014"),
    ("Reyansh Malhotra", "919811000015"),
    ("Zara Qureshi", "919811000016"),
    ("Neil Choudhary", "919811000017"),
    ("Pari Menon", "919811000018"),
    ("Harshvardhan Das", "919811000019"),
    ("Navya Pillai", "919811000020"),
    ("Yash Bansal", "919811000021"),
    ("Tara Krishnan", "919811000022"),
]

FAILURE_WEIGHTS = (
    (FailureReason.BANK_DOWNTIME, 0.38),
    (FailureReason.INSUFFICIENT_FUNDS, 0.37),
    (FailureReason.EXPIRED, 0.25),
)


def _pick_failure(rng: Random) -> FailureReason:
    roll = rng.random()
    cumulative = 0.0
    for reason, weight in FAILURE_WEIGHTS:
        cumulative += weight
        if roll <= cumulative:
            return reason
    return FailureReason.EXPIRED


def generate_failed_transactions(n: int = 50) -> list[TransactionRecord]:
    """Build n failed checkouts. Repeat customers so the 3-touch cap can fire."""
    rng = Random(42)
    now = datetime.now(timezone.utc)
    records: list[TransactionRecord] = []

    # Guarantee a handful of customers appear 4+ times so STOP_ESCALATE is visible.
    heavy_hitters = CUSTOMERS[:4]
    assigned: list[tuple[str, str]] = []
    for customer in heavy_hitters:
        assigned.extend([customer] * 4)
    remaining = n - len(assigned)
    for _ in range(remaining):
        assigned.append(CUSTOMERS[rng.randrange(len(CUSTOMERS))])
    rng.shuffle(assigned)
    assigned = assigned[:n]

    for index, (name, phone) in enumerate(assigned, start=1):
        amount = round(rng.uniform(299.0, 15000.0), 2)
        records.append(
            TransactionRecord(
                txn_id=f"txn_{index:03d}_{rng.randint(1000, 9999)}",
                customer_name=name,
                phone=phone,
                amount_inr=amount,
                failure_reason=_pick_failure(rng),
                timestamp=now - timedelta(minutes=rng.randint(5, 18 * 60)),
            )
        )
    return records
