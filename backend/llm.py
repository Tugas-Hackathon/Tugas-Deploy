import os
from pathlib import Path
from typing import TypeVar
from fastapi import HTTPException
from pydantic import BaseModel
from openai import OpenAI

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "gemini-3.6-flash"

# Per task rather than per call site, so changing a model is one line here.
MODELS: dict[str, str] = {
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


def _client_and_model_for(task: str, user: str | None = None) -> tuple[OpenAI, str]:
    """One server key for everyone. Students do not supply their own, so there is
    nothing to misconfigure during a demo."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise NoAPIKey("GEMINI_API_KEY is not set on the server.")

    # Google exposes an OpenAI-compatible endpoint, so the same client works.
    client = OpenAI(
        api_key=key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        max_retries=2,
    )
    return client, MODELS.get(task, DEFAULT_MODEL)


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

