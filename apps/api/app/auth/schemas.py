"""Auth request and response bodies."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PhoneLoginIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=1, max_length=128)


class VerifyIn(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    password: str = Field(min_length=10, max_length=128)


class PhoneStartIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(min_length=1, max_length=200)


class PhoneConfirmIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=6, max_length=6)


class SecondFactorIn(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class MessageOut(BaseModel):
    message: str


class LoginOut(BaseModel):
    message: str
    next: Literal["session", "enroll", "challenge"]


class CsrfOut(BaseModel):
    token: str


class AuthConfigOut(BaseModel):
    phone_registration_enabled: bool


class TotpSetupOut(BaseModel):
    otpauth_uri: str
    secret: str
    qr_svg: str


class TotpConfirmOut(BaseModel):
    message: str
    recovery_codes: list[str]


class SessionOut(BaseModel):
    family_id: UUID
    created_at: datetime
    expires_at: datetime
    current: bool


class SessionsOut(BaseModel):
    sessions: list[SessionOut]
