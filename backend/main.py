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
API_PREFIX = os.getenv("API_PREFIX", "/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:5173")],
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

for name in ROUTERS:
    try:
        module = importlib.import_module(name)
        app.include_router(module.router, prefix=API_PREFIX)
        loaded.append(name)
    except Exception as exc:
        failed[name] = f"{type(exc).__name__}: {exc}"
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
    return {
        "ok": not failed,
        "loaded": loaded,
        "failed": failed,
    }
