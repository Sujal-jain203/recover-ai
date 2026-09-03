# RecoverAI

**Autonomous Revenue Recovery Engine** — built for **Razorpay AI Buildathon · Track 03**.

RecoverAI is an agentic state machine that detects failed transactions, diagnoses root causes, and executes a bounded recovery workflow across a synthetic batch of 50 records. It measures money recovered, enforces a strict 3-touch cap per customer, and maintains an immutable audit ledger.

**Live repo:** [github.com/Sujal-jain203/recover-ai](https://github.com/Sujal-jain203/recover-ai)

---

## Features

| Capability | Description |
|---|---|
| **Batch recovery** | Processes 50 synthetic failed checkouts (₹299–₹15,000) with mixed failure reasons |
| **Root-cause playbooks** | `BANK_DOWNTIME` → silent retry · `INSUFFICIENT_FUNDS` → Hinglish WhatsApp nudge · `EXPIRED` → UPI fallback link |
| **3-touch stopping rule** | Hard cap of 3 customer touches; further attempts become `STOP_ESCALATE` |
| **Measured recovery** | Tracks amount at risk, amount recovered, recovery rate %, and escalated count |
| **Immutable audit ledger** | Frozen records for every touch, decision, channel payload, and timestamp |
| **Razorpay payment links** | Real `payment_link.create` calls (paise conversion); mock fallback on auth failure |
| **WhatsApp deep-links** | Pre-filled `wa.me` URLs for `INSUFFICIENT_FUNDS` nudges |
| **Promise-to-Pay (PTP)** | Set a promise date and suppress retries until that date |
| **Dark-mode dashboard** | Tailwind CSS single-page UI with live metrics and ledger table |

---

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2
- **Payments:** Razorpay Python SDK
- **Frontend:** HTML + Tailwind CSS (CDN)
- **Deploy:** Vercel serverless (`@vercel/python`)

---

## Project Structure

```
recover-ai/
├── api/
│   └── index.py              # Vercel serverless entrypoint
├── app/
│   ├── main.py               # FastAPI routes + static mount
│   ├── schemas.py            # Pydantic models & enums
│   ├── data_generator.py     # 50-record synthetic batch
│   ├── recovery_engine.py    # State machine + audit ledger
│   ├── razorpay_service.py   # Payment link creation
│   ├── config.py             # .env loader (python-dotenv)
│   └── static/
│       └── index.html        # Dashboard UI
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

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and click **Run Batch Recovery**.

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
       ├── INSUFFICIENT_FUNDS → HINGLISH_NUDGE + wa.me link  (40%)
       └── EXPIRED            → UPI_FALLBACK_LINK  (45%)
       │
       ▼
  Append frozen AuditRecord to ledger
```

---

## Deploy on Vercel

1. Import the repo at [vercel.com/new](https://vercel.com/new).
2. Set environment variables in the Vercel project settings:
   - `RZP_KEY_ID`
   - `RZP_KEY_SECRET`
3. Deploy — `vercel.json` routes all traffic to `api/index.py`.

```bash
# Or deploy via CLI
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

MIT — built for the Razorpay AI Buildathon.
