"""ARQ worker. Command: arq app.worker.WorkerSettings"""

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

import structlog
from arq.connections import RedisSettings

from app.config import get_settings
from app.email_content import (
    build_invite_url,
    build_reset_url,
    build_verification_url,
    invite_email_body,
    reset_email_body,
    verification_email_body,
)
from app.logging_config import setup_logging


def _quiet_arq_logs() -> None:
    # ARQ's default info line prints job arguments, including raw tokens.
    logging.getLogger("arq").setLevel(logging.WARNING)


setup_logging()
_quiet_arq_logs()
log = structlog.get_logger()


def _deliver(to_email: str, subject: str, body: str, success_event: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, int(settings.smtp_port), timeout=10) as smtp:
            smtp.send_message(message)
    except Exception as exc:
        log.error(f"{success_event}_failed", error_type=type(exc).__name__)
        raise RuntimeError("email failed") from None
    log.info(success_event)


async def send_verification_email(ctx: dict[str, Any], to_email: str, token: str) -> None:
    job_id = ctx.get("job_id")
    structlog.contextvars.bind_contextvars(request_id=str(job_id or "worker"))
    settings = get_settings()
    url = build_verification_url(settings.public_web_url, token)
    _deliver(to_email, "Verify your email", verification_email_body(url), "verification_email_sent")


async def send_password_reset_email(ctx: dict[str, Any], to_email: str, token: str) -> None:
    job_id = ctx.get("job_id")
    structlog.contextvars.bind_contextvars(request_id=str(job_id or "worker"))
    settings = get_settings()
    url = build_reset_url(settings.public_web_url, token)
    _deliver(to_email, "Reset your password", reset_email_body(url), "password_reset_email_sent")


async def send_staff_invite_email(ctx: dict[str, Any], to_email: str, token: str) -> None:
    job_id = ctx.get("job_id")
    structlog.contextvars.bind_contextvars(request_id=str(job_id or "worker"))
    settings = get_settings()
    url = build_invite_url(settings.public_web_url, token)
    _deliver(to_email, "Set your staff password", invite_email_body(url), "staff_invite_email_sent")


async def send_phone_otp(ctx: dict[str, Any], phone: str, code: str) -> None:
    job_id = ctx.get("job_id")
    structlog.contextvars.bind_contextvars(request_id=str(job_id or "worker"))
    settings = get_settings()
    if settings.sms_provider != "console":
        log.error("sms_provider_unsupported")
        raise RuntimeError("sms provider unsupported")
    log.info(
        "sms_console_dev_only",
        message="DEV ONLY: console SMS provider. This code is not sent to a real phone.",
        phone=phone,
        otp=code,
    )


async def startup(_ctx: dict[str, Any]) -> None:
    _quiet_arq_logs()
    structlog.contextvars.bind_contextvars(request_id="worker")
    log.info("worker_started")


async def shutdown(_ctx: dict[str, Any]) -> None:
    log.info("worker_stopped")


class WorkerSettings:
    functions = [
        send_verification_email,
        send_password_reset_email,
        send_staff_invite_email,
        send_phone_otp,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 5
    job_timeout = 30
