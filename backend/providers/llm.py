"""LLM providers — OpenAI-compatible or deterministic demo."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from backend.config import get_settings
from backend.utils.logging_utils import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, system: str, user: str, json_mode: bool = False) -> str:
        raise NotImplementedError


class DemoLLMProvider(LLMProvider):
    name = "demo"

    def generate(self, system: str, user: str, json_mode: bool = False) -> str:
        # Deterministic structured narrative for explanations / entity hints.
        if json_mode:
            return json.dumps(
                {
                    "summary": "Demo LLM synthesized a structured incident narrative from fused features.",
                    "confidence": 0.7,
                }
            )
        if "Insufficient protocol" in user or "low retrieval" in user.lower():
            return "Insufficient protocol evidence — human review required."
        return (
            "Based on extracted multimodal features and DEMO protocol excerpts only, "
            "the deterministic triage engine (not this LLM) assigned the urgency tier. "
            "This is a research/demo decision-support prototype — not for real dispatch."
        )


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if self.settings.openai_api_key:
            try:
                import httpx

                self._client = httpx.Client(timeout=30.0)
            except Exception as exc:
                logger.warning("OpenAI client init failed: %s", exc)

    @property
    def available(self) -> bool:
        return bool(self.settings.openai_api_key and self._client)

    def generate(self, system: str, user: str, json_mode: bool = False) -> str:
        if not self.available:
            return DemoLLMProvider().generate(system, user, json_mode)
        assert self._client is not None
        payload: dict[str, Any] = {
            "model": self.settings.openai_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.post(
                f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("OpenAI call failed, using demo LLM: %s", exc)
            return DemoLLMProvider().generate(system, user, json_mode)


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.model_mode == "demo" or not settings.openai_api_key:
        return DemoLLMProvider()
    return OpenAIProvider()
