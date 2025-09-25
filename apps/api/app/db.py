"""SQLAlchemy declarative base. Import models so metadata is populated."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
