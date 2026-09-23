# Restaurant SaaS Backend

FastAPI backend for multi-tenant restaurant SaaS.

## Quick Start

```bash
cd backend
cp .env.example .env
# edit .env and set DATABASE_URL + JWT_SECRET_KEY
python3 start_backend.py
```

Backend starts on:

```text
http://localhost:8099
```

Health check:

```bash
curl http://localhost:8099/health
```

## DB Sync Only

Run all pending migrations without starting server:

```bash
cd backend
python3 sync_db.py
```

Direct Alembic command:

```bash
venv/bin/alembic upgrade head
```

## First Run Notes

`start_backend.py` does these steps:

1. Uses existing `venv` or creates it.
2. Installs `requirements.txt` when packages are missing.
3. Runs `sync_db.py`.
4. Starts `run.py`.

Force dependency install:

```bash
python3 start_backend.py --install
```

## Main Features

- JWT auth with access and refresh tokens.
- Restaurant staff roles: `super_admin`, `admin`, `kitchen`, `waiter`.
- Restaurant, settings, user, menu, table, order, kitchen APIs.
- Frontend-generated QR codes backed by DB `qr_id` and `qr_token`.
- Public QR ordering.
- Waiter calls from public QR page.
- Billing and payment records.
- Order and kitchen ticket status history.
- RBAC, customer session, cart, QR scan, subscription plan/payment tables.

## Useful Commands

```bash
python3 start_backend.py       # sync DB and run API
python3 sync_db.py             # migrate DB only
venv/bin/python run.py         # run API without DB sync helper
```
