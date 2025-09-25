# 0001. Modular monolith, ARQ for now

The store is one FastAPI process plus a Next.js process. Auth, users, and audit live in one Python package (`apps/api`) with router → service → repository layers. The web app is the only browser origin.

Background work is an ARQ worker started from the same image (`arq app.worker.WorkerSettings`). ARQ is enough for Week 1 email. Celery is not introduced. A separate worker package is not worth the split while the job is one SMTP send.

Week 2+ features (2FA, RBAC enforcement, phone OTP, catalog, payments) stay out until their week.
