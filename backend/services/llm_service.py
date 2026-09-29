"""LLM service abstraction.

Provider-agnostic wrapper over any OpenAI-compatible chat-completions API.
All LLM calls flow through this service; route handlers never call providers
directly. Structured outputs are validated with Pydantic (one corrective
retry, then a safe error).
"""

import json
import logging
from typing import Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when the LLM is unavailable or returns unusable output."""


class LLMService:
    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.llm_api_key
        self.base_url = (s.llm_base_url or "").rstrip("/")
        self.model = s.llm_model
        self.timeout = s.llm_timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _url(self) -> str:
        return self.base_url + "/chat/completions"

    def _headers(self) -> dict:
        return {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }

    # ----------------------------------------------------------- raw calls ----

    def chat_text(self, system: str, user: str, temperature: float = 0.4) -> str:
        """Plain text completion. Raises LLMError on failure."""
        if not self.available:
            raise LLMError("LLM is not configured (missing LLM_API_KEY or LLM_BASE_URL)")
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = httpx.post(self._url(), json=payload, headers=self._headers(), timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise LLMError("LLM request failed: %s" % exc) from exc
        if resp.status_code != 200:
            raise LLMError("LLM returned %s: %s" % (resp.status_code, resp.text[:200]))
        try:
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("Malformed LLM response") from exc

    def chat_json(self, system: str, user: str, schema: Type[T], temperature: float = 0.2) -> T:
        """JSON completion validated against a Pydantic schema, with one retry."""
        if not self.available:
            raise LLMError("LLM is not configured (missing LLM_API_KEY or LLM_BASE_URL)")
        instruction = (
            "Respond with ONLY a single JSON object matching this shape (no markdown, "
            "no commentary):\n%s" % json.dumps(_schema_hint(schema), indent=2)
        )
        sys_prompt = system + "\n\n" + instruction
        last_error: Exception | None = None
        for attempt in range(2):
            retry_note = ""
            if attempt == 1 and last_error is not None:
                retry_note = (
                    "\n\nYour previous response was invalid: %s\n"
                    "Fix it and return ONLY valid JSON matching the schema." % last_error
                )
            raw = self.chat_text(sys_prompt, user + retry_note, temperature=temperature)
            try:
                return schema.model_validate_json(_extract_json(raw))
            except (ValidationError, ValueError) as exc:
                last_error = exc
                logger.warning("LLM JSON validation failed (attempt %d): %s", attempt + 1, exc)
        raise LLMError("LLM returned invalid JSON after retry: %s" % last_error)


def _schema_hint(schema: Type[T]) -> dict:
    """Small JSON-shape hint derived from a Pydantic model."""
    hint: dict = {}
    for name, field in schema.model_fields.items():
        hint[name] = _type_hint(field.annotation)
    return hint


def _type_hint(annotation) -> object:  # noqa: ANN001
    name = str(annotation)
    if "list" in name or "List" in name:
        return []
    if "float" in name:
        return 0.0
    if "int" in name:
        return 0
    if "bool" in name:
        return False
    if "None" in name:
        return None
    return "string"


def _extract_json(raw: str) -> str:
    """Extract the outermost JSON object from a raw LLM response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in response")
    return text[start : end + 1]


llm_service = LLMService()
