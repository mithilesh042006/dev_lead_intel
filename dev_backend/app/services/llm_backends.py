"""LLM provider backends.

The pipeline only ever asks for "give me JSON matching this schema". Which
vendor answers is a configuration detail, kept behind this interface so the
prompts, caching and evidence-binding in llm_service.py stay provider-agnostic.

Adding a provider means adding a class here — nothing above it changes.
"""
from __future__ import annotations

import copy
import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Transient failure — worth retrying (timeout, 5xx)."""


class LLMFatalError(RuntimeError):
    """Permanent failure — bad key, unknown model, malformed request."""


class LLMQuotaError(LLMFatalError):
    """Rate limit or quota exhausted. Retrying inside this run cannot help.

    Gemini's free tier allows 20 requests per day per model, so a single search
    can exhaust it. The quota is per model, so switching LLM_MODEL is the
    quickest workaround. OpenAI raises this on 429 rate limits too.
    """


# 400 = bad request, 401/403 = bad key, 404 = unknown/retired model. Retrying
# any of these just burns wall-clock.
_FATAL_MARKERS = (
    "400", "401", "403", "404",
    "INVALID_ARGUMENT", "PERMISSION_DENIED",
    "invalid_api_key", "model_not_found",
)


def classify_error(message: str) -> Exception:
    if "RESOURCE_EXHAUSTED" in message or "429" in message or "rate_limit" in message:
        return LLMQuotaError(message)
    if any(marker in message for marker in _FATAL_MARKERS):
        return LLMFatalError(message)
    return LLMError(message)


def as_strict_schema(schema: dict) -> dict:
    """OpenAI strict mode requires additionalProperties:false on every object.

    Applied here rather than in the shared schema definition because Gemini's
    OpenAPI subset does not accept the key.
    """
    out = copy.deepcopy(schema)

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                node["additionalProperties"] = False
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(out)
    return out


class LLMBackend(ABC):
    name: str = "base"

    def __init__(self, api_key: str, model: str, temperature: float):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    @abstractmethod
    def generate(self, system: str, user: str, schema: dict | None) -> str:
        """Return the model's raw text, JSON-encoded when a schema is given."""


class GeminiBackend(LLMBackend):
    name = "gemini"

    def __init__(self, api_key: str, model: str, temperature: float):
        super().__init__(api_key, model, temperature)
        from google import genai

        self.client = genai.Client(api_key=api_key)

    def generate(self, system: str, user: str, schema: dict | None) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system, temperature=self.temperature
        )
        if schema is not None:
            config.response_mime_type = "application/json"
            config.response_schema = schema

        try:
            resp = self.client.models.generate_content(
                model=self.model, contents=user, config=config
            )
        except Exception as exc:
            raise classify_error(str(exc)) from exc
        return (resp.text or "").strip()


class OpenAIBackend(LLMBackend):
    name = "openai"

    def __init__(self, api_key: str, model: str, temperature: float):
        super().__init__(api_key, model, temperature)
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        # Newer reasoning models reject any temperature but their default
        # (gpt-5.5 does; gpt-5.4-mini does not). Discovered on first use rather
        # than hardcoded, so a new model does not need a code change.
        self._supports_temperature = True

    def generate(self, system: str, user: str, schema: dict | None) -> str:
        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": as_strict_schema(schema),
                    "strict": True,
                },
            }

        for attempt in (1, 2):
            call_kwargs = dict(kwargs)
            if self._supports_temperature:
                call_kwargs["temperature"] = self.temperature
            try:
                resp = self.client.chat.completions.create(**call_kwargs)
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                message = str(exc)
                if (
                    attempt == 1
                    and self._supports_temperature
                    and "temperature" in message
                ):
                    log.info("%s rejects a custom temperature; using its default", self.model)
                    self._supports_temperature = False
                    continue
                raise classify_error(message) from exc

        raise LLMError("unreachable")


def build_backend(provider: str, model: str, temperature: float, keys: dict) -> LLMBackend:
    """`provider` may be 'auto', 'openai' or 'gemini'."""
    resolved = provider.lower().strip()
    if resolved == "auto":
        resolved = "openai" if model.startswith(("gpt", "o1", "o3", "o4")) else "gemini"

    if resolved == "openai":
        key = keys.get("openai") or ""
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set (see .env.example)")
        return OpenAIBackend(key, model, temperature)

    if resolved == "gemini":
        key = keys.get("gemini") or ""
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set (see .env.example)")
        return GeminiBackend(key, model, temperature)

    raise RuntimeError(f"unknown LLM_PROVIDER: {provider!r} (use auto, openai or gemini)")
