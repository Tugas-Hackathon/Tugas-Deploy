# Vercel entry point. Its Python runtime imports `app` from this module and
# serves it; nothing here runs locally, where uvicorn loads main:app directly.
import os, sys
from pathlib import Path

# On Vercel, /api/* is forwarded to this function with the path intact.
# We set API_PREFIX here so main.py mounts every router under /api,
# matching what the frontend calls.  Locally this file is never imported.
os.environ.setdefault("API_PREFIX", "/api")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402

__all__ = ["app"]
