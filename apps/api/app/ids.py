"""UUIDv7 primary keys."""

from uuid import UUID

from uuid_utils import uuid7


def new_id() -> UUID:
    generated = uuid7()
    return UUID(str(generated))
