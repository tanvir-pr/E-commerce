# Week 2 gaps

Week 2 adds TOTP, staff permissions, password reset, optional phone OTP, profile and session endpoints, and an empty admin shell. The items below are still deferred.

- Catalog, cart, orders, payments, search, chatbot, coupons, reviews, and a feature-flag table are not in this tree.
- Google OAuth is not implemented. Sign-in is email and password, plus phone OTP only when `PHONE_REGISTRATION_ENABLED=true`.
- Storybook is not set up. UI is the Next.js pages under `apps/web`.
- Message catalogs are English only. Bangla is not loaded.
- CI runs ruff, mypy, alembic, pytest, eslint, and `tsc`. It does not run dependency, SAST, or container scanners.
- `DELETE /api/v1/users/me` sets `deleted_at` and revokes refresh sessions. It does not erase the row, reuse of that email, or audit history. Full erasure is incomplete.
- `BREACH_CHECK=stub` still does not call Have I Been Pwned.
- `SMS_PROVIDER=console` logs the OTP for local development. There is no real SMS gateway.
- The admin shell lists audit events and can invite staff. It does not manage catalog, orders, or customers beyond that.
- Account export is the profile JSON from `GET /api/v1/users/me`. It is not a full data archive.
