# Scanners not required in Week 1

These are intentionally absent from `.github/workflows/ci.yml` this week:

- pip-audit
- npm audit
- Bandit
- CodeQL
- gitleaks
- Trivy
- Playwright
- ZAP
- k6

Week 1 CI is ruff, mypy, pytest, `alembic upgrade head` against Postgres, eslint, and `tsc`.
