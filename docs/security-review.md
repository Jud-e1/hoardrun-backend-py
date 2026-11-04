# Security review (November 2026)

A review of the backend (FastAPI) and the web app (Next.js) before launch. What was fixed, what is left, and what must be done by hand. Read with [legal-review.md](legal-review.md).

## Do these by hand first: rotate leaked secrets

These were committed to git history. They have been removed from the files, but **anyone with the repository can still read them. Change them at the provider.**

| Secret | Where it was | Repository |
|---|---|---|
| Supabase database password | `settings.py` (commit `2c48dfc1`) | `Jud-e1/hoardrun-backend-py` |
| Render Postgres `dpg-d2v7m1og…` | `render.yaml` | `Jud-e1/hoardrun-backend-py` |
| Render Postgres `dpg-d3svuqgd…` | `hoardrun/.env.example` | `hoardrun1/hoardrun` |
| Google OAuth client secret | `hoardrun/.env.example` | `hoardrun1/hoardrun` |

## Fixed

**Sign-in and tokens**
- Swapped `python-jose` (known advisories, with `ecdsa`) for **PyJWT**. Only HS256 is accepted, so tokens using `none`, another algorithm, the wrong key, a refresh token or an expired token are all refused.
- **Admin access reads the role from the database.** An "admin" claim in a token no longer grants anything.
- The older routes now refuse **closed accounts**, the same as the newer ones.
- **5 wrong passwords lock password sign-in for 15 minutes**, stored in the database so it holds across servers. The person gets a security email. A password reset unlocks it.
- An unknown email gets the **same answer as a wrong password**, so nobody can find out who has an account.

**Limits**
- Sign-in, sign-up, codes, password resets, Google sign-in, admin sign-in and closing an account are limited to **20 tries per 10 minutes per IP address**, on top of the general limit.

**What production shows**
- The API map (`/docs`, `/redoc`, `/openapi.json`) is **off in production**.
- Old routes the app no longer uses (mock KYC, P2P, Mastercard, collective capital, market data) are **not served in production**.
- The web app's test and debug pages (`/test`, `/api-test`, `/auth/debug`, `/dev`, `/monitoring`, `/test-email`, `/test-cognito`) **return 404 in production**. Checked against a production build.

**Packages (web app)**
- Removed 15 unused packages (including `aws-sdk`, `crypto-js`, `next-i18next`, `fb`, `twitter-api-v2`). Updated Next.js to 14.2.35 and applied compatible fixes.
- **Vulnerabilities in shipped packages: 55 → 8; critical 7 → 1.**

**Checked and fine**
- Every route requires sign-in, except sign-in itself, health checks and webhooks.
- The webhooks for Stripe, Plaid, Persona, Stripe Issuing, Alpaca and Paystack check signatures, or fetch the facts from the provider.
- Bank tokens and account numbers are encrypted at rest.
- Codes and reset tokens are stored only as hashes.
- Emails never log their subject line in production, because subjects can contain codes.
- No route lets an admin create money. The old service that could is not reachable.
- The web app's 4 API routes only pass requests on with the person's own token.
- Production refuses to start without a real signing key, encryption key and Postgres database, or with an out-of-date schema.

## Left to do (ranked)

| # | Risk | Fix | Size |
|---|---|---|---|
| 1 | **Next.js 14 has a critical advisory** that is only fixed in a newer major version (15 or 16) | Upgrade Next.js, which touches routing, fonts and caching | Medium |
| 2 | **Sign-in tokens are in `localStorage` and in cookies scripts can read**, so a cross-site scripting bug could steal them. The CSP reduces the risk but still allows inline scripts. | Move tokens to `HttpOnly` cookies set by the API; then remove `'unsafe-inline'` with nonces | Medium |
| 3 | The **per-IP limit lives in each server's memory**, so with several servers the real limit is higher. The password lock is already shared. | Move the limit to Redis | Small |
| 4 | **`NEXT_PUBLIC_BYPASS_AUTH`** skips the web app's sign-in redirect. The API still requires sign-in, so no data is exposed, but it should never be set in production. | Make production builds ignore it | Small |
| 5 | 7 remaining moderate or high package issues (`glob`, `postcss`, `zod`, `ip-address`) | Mostly cleared by the Next.js upgrade; `zod` needs a major update | Small |
| 6 | No **two-step sign-in** (authenticator app or passkey) | Add it, at least for sending money and for admins | Medium |
| 7 | No **outside penetration test** | Book one before launch. The bank partner will ask. | External |

## Tests

- **218 backend tests pass**, including 12 new security tests in `tests/unit/test_security_review.py`.
- 7 older test files for services the app no longer uses fail to load or fail. They were already broken before this work.
- The web app type-checks with no new errors (124 old ones remain). It builds for production.
