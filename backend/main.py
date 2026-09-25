from dotenv import load_dotenv
load_dotenv()

import importlib
import os
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Tugas API")

# Vercel forwards /api/* to this function with the path intact, so the routes
# have to carry that prefix. root_path does not do this — it only affects the
# URLs shown in the docs, which is why setting it left every route 404ing.
# Locally (uvicorn main:app) this env var is unset, so it defaults to "" and
# routes are reachable at /auth, /subjects, etc. as before.
API_PREFIX = os.getenv("API_PREFIX", "")

_cors_env = os.getenv("CORS_ORIGIN", "")
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://sisystem.org",
    "https://www.sisystem.org",
    "https://tugasos.vercel.app",
]
if _cors_env:
    for o in _cors_env.split(","):
        o = o.strip()
        if o and o not in allowed_origins:
            allowed_origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# One failing import used to take the whole API down: a missing library in any
# module meant /health and /auth returned 500 and the app looked entirely dead.
# Each router is loaded independently so a broken one costs only its own routes,
# and /health reports what failed instead of leaving it to the platform logs.
ROUTERS = [
    "auth", "subjects", "materials", "tutor",
    "branches", "milestones", "quiz", "agenda", "settings",
]

loaded: list[str] = []
failed: dict[str, str] = {}

for _name in ROUTERS:
    try:
        _module = importlib.import_module(_name)
        app.include_router(_module.router, prefix=API_PREFIX)
        loaded.append(_name)
    except Exception as _exc:
        failed[_name] = f"{type(_exc).__name__}: {_exc}"
        traceback.print_exc()


@app.on_event("startup")
def startup():
    # A database that will not initialise must not stop the app from serving
    # /health, which is the only way to see why from outside.
    try:
        from db import init_db
        init_db()
    except Exception as exc:
        failed["db"] = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()


try:
    from llm import NoAPIKey

    @app.exception_handler(NoAPIKey)
    def _no_key(request: Request, exc: NoAPIKey):
        # 402: the request was fine, it just cannot be paid for yet.
        return JSONResponse(status_code=402, content={"detail": str(exc)})
except Exception:
    traceback.print_exc()


@app.get(f"{API_PREFIX}/health")
def health():
    # Shape of the database URL only — scheme, host, port, user. Never the
    # password, which is why this is safe to return from a public endpoint.
    dsn: dict = {}
    raw = os.getenv("DATABASE_URL", "")
    if raw:
        try:
            from urllib.parse import urlsplit
            u = urlsplit(raw)
            dsn = {
                "host": u.hostname,
                "port": u.port,
                "user": u.username,
                "pooler": bool(u.hostname and "pooler" in u.hostname),
            }
        except Exception as exc:
            dsn = {"parse_error": str(exc)}
    else:
        dsn = {"set": False}

    return {
        "ok": not failed,
        "loaded": loaded,
        "failed": failed,
        "database": dsn,
        "ai": {
            "openrouter_key_set": bool(os.getenv("OPENROUTER_API_KEY")),
            "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        },
        "storage": {
            "supabase_url_set": bool(os.getenv("SUPABASE_URL")),
            "service_key_set": bool(os.getenv("SUPABASE_SERVICE_KEY")),
            "bucket": os.getenv("SUPABASE_BUCKET") or None,
        },
    }
