"""Vercel serverless entrypoint — re-exports the RecoverAI FastAPI app."""

from app.main import app

__all__ = ["app"]
