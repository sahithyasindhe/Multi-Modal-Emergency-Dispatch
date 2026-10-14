"""Logging helpers with basic PII redaction."""
from __future__ import annotations

import logging
import re
from typing import Any

from backend.config import get_settings

# Obvious PII patterns — production systems need stronger controls.
_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def redact_pii(text: str) -> str:
    text = _PHONE.sub("[REDACTED_PHONE]", text)
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _SSN.sub("[REDACTED_SSN]", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_pii(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_pii(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_pii(a) if isinstance(a, str) else a for a in record.args
                )
        return True


def setup_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactingFilter())


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def safe_log_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Return a log-safe copy (no raw audio bytes)."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        if k in {"audio_bytes", "raw_audio", "audio_data"}:
            out[k] = "[AUDIO_OMITTED]"
        elif isinstance(v, str):
            out[k] = redact_pii(v)
        else:
            out[k] = v
    return out
