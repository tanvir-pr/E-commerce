# 0003. Cookie session on the Next.js origin

The browser talks only to Next.js on port 3000. `apps/web/src/app/api/v1/[...path]/route.ts` proxies `/api/v1/*` to the API and copies `Set-Cookie` through unchanged. `next.config.js` also rewrites that path; the route handler wins so cookies are not dropped. Inside Compose the target is `http://api:8000`. On the host, set `API_INTERNAL_URL` (or `API_URL`) to `http://localhost:8000`.

Cookies are first-party on `http://localhost:3000`. Names:

- `__Host-access` — signed access token, about 15 minutes, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`
- `__Host-refresh` — opaque random token, about 14 days, same flags. Postgres stores only the SHA-256 hash. Every refresh rotates it. Reuse of an already rotated token revokes the whole family.
- `__Host-csrf` — not `HttpOnly`. Unsafe methods must send the same value in `X-CSRF-Token`. `GET /api/v1/auth/csrf` issues it.

`__Host-` requires `Secure`, `Path=/`, and no `Domain`. Do not set `Path=/api/v1/auth` on these cookies. Chromium treats `http://localhost` as a secure context, so `Secure` cookies work on `http://localhost`. Use `localhost`, not `127.0.0.1`.

No tokens in `localStorage` or `sessionStorage`. CORS is limited to `http://localhost:3000` and is only a fallback; cookie auth does not depend on cross-origin calls.
