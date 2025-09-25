# Login threat model (v1)

Scope is signing in: email and password, the second-factor step for accounts that require it, session cookies, and password reset. Catalog, payments, and other product areas are out of scope.

## Spoofing

An attacker tries to sign in as someone else.

- Passwords are stored as Argon2id hashes and checked in `verify_password`. Unknown emails still run a hash check so the failure path is not a cheap "no such user" response.
- Failed and successful password checks return the same invalid-credentials problem. Register and password reset use the same response whether or not the email exists.
- Staff and super admins do not receive `__Host-access` or `__Host-refresh` after a correct password. The API sets a short-lived `__Host-enroll` or `__Host-challenge` cookie (HS256, `typ` is not `access`) until a TOTP or one-time recovery code matches.
- Customers with 2FA turned on follow the same challenge step. Customers with 2FA off still receive the session cookies.
- The access cookie is an HttpOnly HS256 JWT. `decode_access_token` rejects any token whose `typ` is not `access`, so an enrollment or challenge ticket cannot be used as a session.

## Tampering

An attacker tries to change a request, a cookie, or a stored secret.

- Unsafe methods require the `X-CSRF-Token` header to match the `__Host-csrf` cookie (`CSRFMiddleware`).
- Refresh tokens are opaque and only their SHA-256 hashes are stored. Reuse of a rotated refresh token revokes the whole family.
- TOTP secrets are encrypted with Fernet (`TOTP_ENCRYPTION_KEY`) before they are written. The database stores ciphertext.
- Recovery codes, password-reset tokens, staff invite tokens, email verification tokens, and phone OTP codes are stored as SHA-256 hashes. Reset, invite, verification, and recovery codes are single-use.
- Session and ticket cookies are `Secure`, `Path=/`, and have no `Domain` attribute (`__Host-` prefix).

## Repudiation

A privileged user denies performing an action.

- `audit_logs` is append-only. `AuditRepository` exposes add, and `AuditQuery` only reads. There is no update or delete method.
- Password failures, accepted passwords that still need a second factor, full sign-ins, logouts, password resets, TOTP enrollment, staff creation, and staff permission changes write a row with the actor, action, entity, and request id.

## Information disclosure

An attacker tries to learn secrets or whether an account exists.

- Register and reset responses do not say whether the email is registered. Phone registration, when enabled, uses the same pattern for a duplicate number.
- The worker logs a fixed event after sending mail. It does not log verification, reset, or invite tokens. ARQ's own logger is set to warning so job arguments are not written at info. The structlog redactor drops fields whose names contain `token`, `secret`, `password`, `otpauth`, or `ciphertext`.
- The console SMS provider may log a phone OTP at info with an explicit dev-only message, and only when `SMS_PROVIDER=console` and a code was requested.
- Setup shows the TOTP secret and otpauth URI once. Recovery codes are shown once. Later responses expose `totp_enabled`, not the secret.
- `GET /api/v1/auth/config` returns only `phone_registration_enabled`.
- `GET /api/v1/users/me` loads the user id from the access token. `require_self` denies a caller who names a different user id.

## Denial of service

An attacker tries to overwhelm login, reset, or code guessing.

- Login is rate limited in Redis per IP and per email hash.
- Password reset is rate limited per IP and per email hash.
- Phone OTP start is rate limited per IP and per phone hash, and each challenge allows a small number of wrong codes.
- TOTP setup, confirm, challenge, and disable are rate limited per IP and per user id.

## Elevation of privilege

An attacker tries to use another role or skip 2FA.

- `decide` denies when the route's role set is empty or does not intersect the caller's roles.
- Admin routes declare the role and, for staff work, the permission: support queue requires `support`, warehouse queue requires `warehouse`, staff creation and audit require `super_admin`.
- A super admin still fails those routes until `totp_confirmed_at` is set (`require_totp`).
- Staff and super admins cannot turn 2FA off.
- Customer accounts are not accepted by staff routes. A warehouse permission does not satisfy a support route.
- Deleting an account sets `deleted_at`, revokes refresh families, and leaves audit rows in place. A deleted account cannot sign in.
