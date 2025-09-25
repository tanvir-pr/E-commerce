"""JSON logs. Every event includes request_id (null outside a request)."""

import logging
import sys
from typing import Any

import structlog

_REDACT_KEYS = {"authorization", "cookie", "secret"}


def _ensure_request_id(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict.setdefault("request_id", None)
    return event_dict


def _redact(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict):
        lowered = key.lower()
        sensitive = ("password", "token", "secret", "otpauth", "ciphertext")
        if any(part in lowered for part in sensitive) or lowered in _REDACT_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict


def setup_logging() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    pre_chain: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        _ensure_request_id,
        _redact,
    ]
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=pre_chain,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "asyncio"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    structlog.configure(
        processors=[
            *pre_chain,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def current_request_id() -> str | None:
    value = structlog.contextvars.get_contextvars().get("request_id")
    if value is None:
        return None
    return str(value)
