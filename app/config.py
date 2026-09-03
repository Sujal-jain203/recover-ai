"""Load RecoverAI settings from `.env` via python-dotenv."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

RZP_KEY_ID = os.getenv("RZP_KEY_ID", "")
RZP_KEY_SECRET = os.getenv("RZP_KEY_SECRET", "")
