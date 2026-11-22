# ADR-013: Server-side sessions with scrypt password hashes

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

The app shows patient records, so the API must not answer anyone who is not signed in. There is no identity provider for a local assessment, and the demo must keep working on a free host.

## Decision

Accounts live in SQLite and are created by `ehr-mip users add`. Passwords are hashed with the standard library's scrypt (N=2^14, r=8, p=5, 16 byte salt). Signing in creates a random 256 bit token. The browser keeps it in an `HttpOnly`, `SameSite=Strict` cookie, `Secure` when `ENV=prod`, and the database keeps only its SHA-256. Every POST must carry `X-Requested-With: ehr-mip` as a CSRF check. A session ends after 8 hours, or 60 minutes without a request, or at sign-out. Every route except `/health`, `/ready`, `/metrics` and `/auth/login` needs a session.

## Alternatives rejected

- **JWT in local storage.** Any script on the page can read it, and it cannot be ended before it expires.
- **An OIDC provider.** Right for production, but it needs a service and a registration that reviewers do not have.
- **Argon2 or bcrypt packages.** Good choices, but scrypt is in the standard library and meets the OWASP settings.

## Consequences

- Sign-out and disabling a user take effect on the next request.
- Each sign-in costs about 16 MB and a few tens of milliseconds of CPU, and sign-in is limited to 10 per minute per IP.
- The public demo publishes its login on the sign-in page. Its data is synthetic.
