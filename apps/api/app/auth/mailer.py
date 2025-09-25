"""Enqueue mail and console SMS. The worker performs delivery and does not log secrets."""

from arq.connections import ArqRedis

from app.jobs import (
    SEND_PASSWORD_RESET_EMAIL,
    SEND_PHONE_OTP,
    SEND_STAFF_INVITE_EMAIL,
    SEND_VERIFICATION_EMAIL,
)


class ArqMailer:
    def __init__(self, pool: ArqRedis) -> None:
        self.pool = pool

    async def send_verification(self, email: str, token: str) -> None:
        await self.pool.enqueue_job(SEND_VERIFICATION_EMAIL, email, token)

    async def send_password_reset(self, email: str, token: str) -> None:
        await self.pool.enqueue_job(SEND_PASSWORD_RESET_EMAIL, email, token)

    async def send_staff_invite(self, email: str, token: str) -> None:
        await self.pool.enqueue_job(SEND_STAFF_INVITE_EMAIL, email, token)


class ArqSms:
    def __init__(self, pool: ArqRedis) -> None:
        self.pool = pool

    async def send_otp(self, phone: str, code: str) -> None:
        await self.pool.enqueue_job(SEND_PHONE_OTP, phone, code)
