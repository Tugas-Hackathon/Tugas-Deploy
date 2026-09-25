import os, json, urllib.request, urllib.error, urllib.parse
from pathlib import Path

# Supabase Storage in production, local disk otherwise. Vercel's filesystem is
# ephemeral, so an uploaded PDF written to disk there is gone by the next
# request.
def _project_url() -> str:
    """Supabase's REST base, https://<ref>.supabase.co.

    SUPABASE_URL is sometimes set to the Postgres connection string instead,
    which is not an HTTP URL at all. The project ref appears in both forms, so
    derive it rather than failing with 'unknown url type: postgresql'.
    """
    from urllib.parse import urlsplit
    import re as _re

    for candidate in (os.getenv("SUPABASE_URL", ""), os.getenv("DATABASE_URL", "")):
        if not candidate:
            continue
        if candidate.startswith("http"):
            return candidate.rstrip("/")
        host = urlsplit(candidate).hostname or ""
        # db.<ref>.supabase.co, or <user>.<ref> on the pooler
        m = _re.match(r"^db\.([a-z0-9]+)\.supabase\.co$", host)
        if m:
            return f"https://{m.group(1)}.supabase.co"
        user = urlsplit(candidate).username or ""
        if "." in user:
            return f"https://{user.split('.', 1)[1]}.supabase.co"
    return ""


SUPABASE_URL = _project_url()
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
BUCKET = os.getenv("SUPABASE_BUCKET", "materials")
REMOTE = bool(SUPABASE_URL and SUPABASE_KEY)

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))


def _url(key: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{urllib.parse.quote(key)}"


def _headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY}
    h.update(extra or {})
    return h


def put(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Store bytes, returning the reference to persist alongside the row."""
    if not REMOTE:
        dest = DATA_DIR / "files" / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    req = urllib.request.Request(
        _url(key), data=data, method="POST",
        headers=_headers({"Content-Type": content_type, "x-upsert": "true"}),
    )
    try:
        with urllib.request.urlopen(req, timeout=60):
            pass
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"upload failed: {e.read().decode(errors='replace')[:200]}")
    return f"supabase://{BUCKET}/{key}"


def get(ref: str) -> bytes:
    if not ref.startswith("supabase://"):
        return Path(ref).read_bytes()

    key = ref.split("/", 3)[3]
    req = urllib.request.Request(_url(key), headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise FileNotFoundError(f"not in storage: {e.code}")


def delete(ref: str) -> None:
    if not ref.startswith("supabase://"):
        Path(ref).unlink(missing_ok=True)
        return

    key = ref.split("/", 3)[3]
    req = urllib.request.Request(_url(key), method="DELETE", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30):
            pass
    except urllib.error.HTTPError:
        pass  # already gone is the desired end state
