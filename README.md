# Store (Week 2)

A single-vendor shop for Bangladesh. Week 2 adds TOTP two-factor authentication, staff roles and permissions, password reset, optional phone OTP, profile and session endpoints, and an empty admin shell. Catalog, cart, orders, payments, and search are not in this tree.

The browser talks to Next.js at port 3000. Next.js proxies `/api/v1` to FastAPI so session cookies stay on `localhost:3000`.

Chromium treats `http://localhost` as a secure context, so the `Secure` `__Host-` cookies work on `http://localhost`. Open the site as `http://localhost:3000`, not `http://127.0.0.1:3000`.

`BREACH_CHECK=stub` accepts any password of at least 10 characters. `password_is_breached` is the Have I Been Pwned k-anonymity hook and returns false in stub mode. It does not call the HIBP API.

Money will be stored later as integer poisha (1 BDT = 100 poisha). There are no price tables yet.

The worker uses the API image. Compose starts it as:

```text
arq app.worker.WorkerSettings
```

It must not log email verification tokens, password reset tokens, staff invite tokens, or TOTP secrets. `SMS_PROVIDER=console` may log a phone OTP at info, with a dev-only message, and only after a phone code was requested.

## Run

If the stack is already up, rebuild and migrate:

```powershell
cd D:\Full-web-4-project
docker compose up --build -d
docker compose exec api alembic upgrade head
```

First time, copy the example env and set `SEED_ADMIN_PASSWORD` to 10 or more characters. `TOTP_ENCRYPTION_KEY` in `.env.example` is a local Fernet key. If `.env` has no `TOTP_ENCRYPTION_KEY`, add one. Do not commit `.env`.

```powershell
cd D:\Full-web-4-project
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_superadmin
```

The seed script creates a super admin when `SEED_ADMIN_EMAIL` is missing, assigns `super_admin`, and skips when that user already exists. It refuses to run when `APP_ENV=production` and `SEED_ADMIN_PASSWORD` is still `replace-this-password`.

The seeded super admin must enroll TOTP on the next sign-in. A correct password does not set `__Host-access` or `__Host-refresh` until enrollment is confirmed. Open `http://localhost:3000/en/login`, sign in, and follow `/en/enroll`. After the authenticator code is confirmed, the recovery codes are shown once and the session cookies are set. `/en/admin` stays closed until that enrollment is confirmed.

- http://localhost:3000/en
- http://localhost:3000/en/account
- http://localhost:3000/en/admin
- http://localhost:3000/en/forgot-password
- http://localhost:3000/api/v1/health
- http://localhost:8000/api/v1/health
- http://localhost:8000/docs
- http://localhost:8025

Mailpit is http://localhost:8025. Password reset and staff invite links are delivered there. Reset links expire in about 30 minutes and work once. The API response is the same whether or not the email exists.

`PHONE_REGISTRATION_ENABLED` stays `false` unless you turn it on. The register page hides the phone form unless `GET /api/v1/auth/config` reports the flag. While it is false, `POST /api/v1/auth/phone/start` returns a problem response.

`DELETE /api/v1/users/me` sets `deleted_at` and revokes refresh sessions. It does not erase the user row or audit history. Full erasure is incomplete.

For `next dev` on the host without Compose, set `API_INTERNAL_URL` (also read as `API_URL`) to `http://localhost:8000`. Compose sets `API_INTERNAL_URL=http://api:8000` for the web container.

## Tests

```powershell
cd D:\Full-web-4-project\apps\api
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
python -m ruff check app tests
python -m mypy app
```

Or, with the stack up: `docker compose exec api python -m pytest`.

Generate the TypeScript types in `packages/api-client` while the API is running:

```powershell
cd D:\Full-web-4-project
pnpm dlx openapi-typescript@7.6.1 http://localhost:8000/openapi.json -o packages/api-client/src/schema.ts
```

The web app still calls the API with `fetch` in `apps/web/src/lib/api.ts`.

## Not in this tree

Catalog, cart, orders, payments, search, chatbot, coupons, reviews, feature flags, Google OAuth, Storybook, Bangla catalogs, and security scanners. See `docs/week2-gaps.md`.
