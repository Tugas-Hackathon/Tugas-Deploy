import os
from pathlib import Path
from typing import TypeVar
from fastapi import HTTPException
from pydantic import BaseModel
from openai import OpenAI

T = TypeVar("T", bound=BaseModel)

OPENROUTER_MODELS: dict[str, str] = {
    "tutor":   "anthropic/claude-opus-5",
    "rubric":  "anthropic/claude-opus-5",
    "outline": "anthropic/claude-opus-5",
    "ocr":     "google/gemini-flash-1.5",
    "extract": "google/gemini-flash-1.5",
    "plan":    "anthropic/claude-opus-5",
    "quiz":    "anthropic/claude-opus-5",
    "polish":  "anthropic/claude-opus-5",
}

GEMINI_MODELS: dict[str, str] = {
    "tutor":   "gemini-3.6-flash",
    "rubric":  "gemini-3.6-flash",
    "outline": "gemini-3.6-flash",
    "ocr":     "gemini-3.6-flash",
    "extract": "gemini-3.6-flash",
    "plan":    "gemini-3.6-flash",
    "quiz":    "gemini-3.6-flash",
    "polish":  "gemini-3.6-flash",
}


_FIXTURES_DIR = Path(__file__).parent / "tests" / "fixtures" / "llm"


class LLMDeclined(Exception):
    pass


class NoAPIKey(Exception):
    """No student key and no server key — the caller should point at Settings."""


def _is_google_key(key: str) -> bool:
    return key.startswith("AQ.") or key.startswith("AIza")


def _client_and_model_for(task: str, user: str | None = None) -> tuple[OpenAI, str]:
    """One server key for everyone. Students do not supply their own."""
    key = os.getenv("OPENROUTER_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise NoAPIKey("No API key configured. Set OPENROUTER_API_KEY in the environment.")

    if _is_google_key(key):
        client = OpenAI(
            api_key=key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            max_retries=2,
        )
        model = GEMINI_MODELS.get(task, "gemini-3.6-flash")
    else:
        client = OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            max_retries=2,
        )
        model = OPENROUTER_MODELS.get(task, "openai/gpt-4o")

    return client, model


def chat(task: str, messages: list[dict], user: str | None = None) -> str:
    if os.getenv("LLM_FIXTURES") == "1":
        fixture = _FIXTURES_DIR / f"{task}.txt"
        if fixture.exists():
            return fixture.read_text()
        raise FileNotFoundError(f"fixture missing: {fixture}")

    client, model = _client_and_model_for(task, user)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            timeout=60,
        )
    except Exception as e:
        raise HTTPException(502, f"AI Provider error ({model}): {e}")

    content = resp.choices[0].message.content if resp.choices else None
    if not content:
        raise LLMDeclined("model returned empty content")
    return content


def parse(task: str, prompt: str, schema: type[T], user: str | None = None) -> T:
    if os.getenv("LLM_FIXTURES") == "1":
        fixture = _FIXTURES_DIR / f"{task}.json"
        if fixture.exists():
            return schema.model_validate_json(fixture.read_text())
        raise FileNotFoundError(f"fixture missing: {fixture}")

    client, model = _client_and_model_for(task, user)
    schema_json = schema.model_json_schema()

    def _call(messages):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema_json, "strict": True}},
                timeout=60,
            )
        except Exception as e:
            raise HTTPException(502, f"AI Provider error ({model}): {e}")

    messages = [{"role": "user", "content": prompt}]
    resp = _call(messages)
    content = resp.choices[0].message.content if resp.choices else None
    if not content:
        raise LLMDeclined("model returned empty content")

    try:
        return schema.model_validate_json(content)
    except Exception as e:
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": f"Your response failed validation: {e}. Reply with valid JSON only."})
        resp2 = _call(messages)
        content2 = resp2.choices[0].message.content if resp2.choices else None
        if not content2:
            raise LLMDeclined("model declined on retry")
        return schema.model_validate_json(content2)

