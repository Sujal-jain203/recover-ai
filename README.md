# RecoverAI

**Autonomous Revenue Recovery Engine** for Razorpay merchants.

RecoverAI is an agentic state machine that detects failed transactions, diagnoses root causes, and executes a bounded recovery workflow across a synthetic batch of 50 records. It measures money recovered, enforces a strict 3-touch cap per customer, and maintains an immutable audit ledger.

**Repository:** [github.com/Sujal-jain203/recover-ai](https://github.com/Sujal-jain203/recover-ai)

---

## Features

| Capability | Description |
|---|---|
| **Batch recovery** | Processes 50 synthetic failed checkouts (₹299–₹15,000) with mixed failure reasons |
| **Root-cause playbooks** | `BANK_DOWNTIME` → silent retry · `INSUFFICIENT_FUNDS` → Hinglish WhatsApp nudge · `EXPIRED` → UPI fallback link |
| **3-touch stopping rule** | Hard cap of 3 customer touches; further attempts become `STOP_ESCALATE` |
| **Measured recovery** | Tracks amount at risk, amount recovered, recovery rate %, and escalated count |
| **Immutable audit ledger** | Frozen records for every touch, decision, channel payload, and timestamp |
| **Razorpay payment links** | Live `payment_link.create` calls (INR → paise); deterministic mock fallback on auth failure |
| **WhatsApp deep-links** | URL-encoded `wa.me` links with Hinglish message + Razorpay pay link for `INSUFFICIENT_FUNDS` |
| **One-click WhatsApp UI** | Dedicated dashboard column with green WhatsApp icon button opening pre-filled chat |
| **Promise-to-Pay (PTP)** | Set a promise date via API or dashboard; retries suppressed until that date |
| **PTP lifecycle** | Tracks `NOT_SET` → `PROMISED_PAYMENT` → `HONORED` / `BROKEN` per transaction |
| **Demo-ready batch** | First transaction is primed as `INSUFFICIENT_FUNDS` with a live demo phone for instant WhatsApp testing |
| **Dark-mode dashboard** | Single-page UI with metric cards, ledger table, PTP modal, and recovery toasts |

---

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2
- **Payments:** Razorpay Python SDK
- **Frontend:** HTML + Tailwind CSS (CDN) with inline-styled WhatsApp actions
- **Deploy:** Vercel serverless (`@vercel/python`)

---

## Project Structure

```
recover-ai/
├── api/
│   └── index.py              # Vercel serverless entrypoint
├── app/
│   ├── main.py               # FastAPI routes + static mount
│   ├── schemas.py            # Pydantic models (RecoveryAction, AuditRecord, PTP)
│   ├── data_generator.py     # 50-record synthetic batch (demo row primed)
│   ├── recovery_engine.py    # State machine + audit ledger + WhatsApp URLs
│   ├── razorpay_service.py   # Payment link creation
│   ├── config.py             # .env loader (python-dotenv)
│   └── static/
│       └── index.html        # Dashboard UI (metrics, ledger, PTP, WhatsApp)
├── requirements.txt
├── pyproject.toml
├── vercel.json
└── .env                      # Local secrets (gitignored)
```

---

## Quick Start (Local)

### 1. Clone & install

```bash
git clone https://github.com/Sujal-jain203/recover-ai.git
cd recover-ai
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Razorpay test keys

Create a `.env` file in the project root:

```env
RZP_KEY_ID=rzp_test_your_key_id
RZP_KEY_SECRET=your_key_secret
```

> `.env` is listed in `.gitignore` and is never committed.

### 3. Run the server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), click **Run Batch Recovery**, then use the green **WhatsApp** button on row 1.

---

## Dashboard

The dashboard exposes four live metric cards and a full audit ledger:

- **At Risk / Recovered / Rate % / Escalated** — batch-level recovery KPIs
- **Ledger table** — txn, customer, amount, failure reason, action, WhatsApp, touches, status
- **WhatsApp column** — green button with icon for `INSUFFICIENT_FUNDS` rows; opens `wa.me` with pre-filled Hinglish message
- **Set PTP** — modal to record a promise date and pause retries
- **Toasts** — alerts when transactions recover or hit the 3-touch cap

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/run-batch` | Run recovery on 50 synthetic failed transactions; returns `BatchMetrics` |
| `GET` | `/api/audit-trail` | Return the immutable audit ledger for the latest batch |
| `POST` | `/api/transactions/{txn_id}/ptp` | Set a promise-to-pay date; body: `{ "promise_date": "YYYY-MM-DD" }` |
| `GET` | `/` | Dashboard (served from `app/static/`) |

### Example: run a batch

```bash
curl -X POST http://127.0.0.1:8000/api/run-batch
```

```json
{
  "total_records": 50,
  "amount_at_risk": 411279.08,
  "amount_recovered": 172813.84,
  "recovery_rate_pct": 42.02,
  "escalated_count": 14,
  "batch_id": "batch_20260903T090218_c35d49e7",
  "recovered_count": 22,
  "retrying_count": 14
}
```

### Example: audit record with WhatsApp action

```json
{
  "txn_id": "txn_001_4598",
  "phone": "917020167758",
  "failure_reason": "INSUFFICIENT_FUNDS",
  "action": {
    "name": "HINGLISH_NUDGE",
    "whatsapp_url": "https://wa.me/917020167758?text=Hi%20..."
  },
  "whatsapp_url": "https://wa.me/917020167758?text=Hi%20...",
  "payment_link": "https://rzp.io/i/recoverai-txn_001_4598",
  "ptp_status": "NOT_SET",
  "status": "RETRYING",
  "touch_count": 1
}
```

### Example: set promise-to-pay

```bash
curl -X POST http://127.0.0.1:8000/api/transactions/txn_001_4598/ptp \
  -H "Content-Type: application/json" \
  -d '{"promise_date": "2026-09-10"}'
```

---

## Recovery State Machine

```
Failed Transaction
       │
       ▼
  touch_count >= 3? ──yes──► STOP_ESCALATE
       │ no
       ▼
  PTP hold active? ──yes──► Suppress retry (no touch consumed)
       │ no
       ▼
  Diagnose failure reason
       │
       ├── BANK_DOWNTIME      → SCHEDULE_SILENT_RETRY  (68% sim. success)
       ├── INSUFFICIENT_FUNDS → HINGLISH_NUDGE + Razorpay link + wa.me URL  (40%)
       └── EXPIRED            → UPI_FALLBACK_LINK  (45%)
       │
       ▼
  Append frozen AuditRecord to ledger
```

---

## WhatsApp Recovery Flow

For `INSUFFICIENT_FUNDS` failures, RecoverAI:

1. Creates a Razorpay payment link (amount in paise).
2. Builds a Hinglish message with customer name, amount, and pay link.
3. URL-encodes the message into a `https://wa.me/{phone}?text=...` deep link.
4. Stores the link on `RecoveryAction.whatsapp_url` and `AuditRecord.whatsapp_url`.
5. Renders a one-click **WhatsApp** button in the dashboard.

---

## Deploy on Vercel

1. Import the repo at [vercel.com/new](https://vercel.com/new).
2. Set environment variables in the Vercel project settings:
   - `RZP_KEY_ID`
   - `RZP_KEY_SECRET`
3. Deploy — `vercel.json` routes all traffic to `api/index.py` via `@vercel/python`.

```bash
npm i -g vercel
vercel
```

> **Note:** Audit ledger and PTP state are in-memory and reset on serverless cold starts. For production persistence, add Redis or a database.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `RZP_KEY_ID` | Yes (prod) | Razorpay test/live key ID |
| `RZP_KEY_SECRET` | Yes (prod) | Razorpay test/live key secret |

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for the full text.
