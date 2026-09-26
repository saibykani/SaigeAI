"""Serverless entrypoint (Vercel). Local and container runs use `uvicorn app.main:app`."""

from app.main import app

__all__ = ["app"]
