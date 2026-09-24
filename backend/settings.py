import os
from fastapi import APIRouter, Depends
from auth import current_user

router = APIRouter(prefix="/settings")


@router.get("")
def read(_user: str = Depends(current_user)):
    """Whether AI is usable. There is no per-student key any more — one server
    key serves everyone, so there is nothing to configure and nothing a visitor
    can get wrong."""
    return {
        "provider": "Google Gemini",
        "ai_ready": bool(os.getenv("GEMINI_API_KEY")),
    }
