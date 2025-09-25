# 0002. PostgreSQL is the source of truth

PostgreSQL 16 holds users, roles, sessions, verification tokens, and the audit log. Primary keys are UUIDv7. Timestamps are `timestamptz` in UTC. Email is `citext`.

Redis is only for the login rate limit and the ARQ queue. If Redis is empty, accounts and sessions in Postgres are unchanged. Mailpit is a local SMTP sink, not a database.

The audit log is append-only from the application: the repository exposes `add` and no update method.
