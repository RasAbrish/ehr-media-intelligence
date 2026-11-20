# Security policy

## Scope

This is an assessment project. It runs on synthetic data only and has no authentication by design (see `docs/09-SECURITY.md` section 10 for what production would add). Please do not submit real patient data in issues or pull requests.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository ("Security" tab, "Report a vulnerability"). Include the affected component, steps to reproduce and the impact you expect. You will get a reply within 7 days.

## Controls in place

Security headers, rate limits, input limits, PHI-free logs, prompt injection defenses, dependency and secret scanning, and hardened containers. The full list with tests is in `docs/09-SECURITY.md`.
