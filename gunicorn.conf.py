"""Gunicorn configuration for production.

Usage:
  gunicorn run:sio_app -c gunicorn.conf.py

Neon pooler note:
  The DATABASE_URL uses PgBouncer pooler (pool_size=1, max_overflow=0 per worker).
  Avoid more than 4 workers to stay within Neon's free-tier connection limits.
  Each uvicorn worker = 1 DB connection to the pooler.
"""
import os
import multiprocessing

# ── Worker config ──────────────────────────────────────────────────────────────
worker_class = "uvicorn.workers.UvicornWorker"

# Cap at 4 workers for Neon pooler compatibility.
# Override with GUNICORN_WORKERS env var for dedicated Postgres (no pooler).
_db_url = os.getenv("DATABASE_URL", "")
_is_pooler = "-pooler." in _db_url or "pgbouncer" in _db_url.lower()
_default_workers = 2 if _is_pooler else min(multiprocessing.cpu_count() * 2 + 1, 8)
workers = int(os.getenv("GUNICORN_WORKERS", _default_workers))

worker_connections = 1000
timeout = 60
keepalive = 5

# ── Binding ───────────────────────────────────────────────────────────────────
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8099")
backlog = 512

# ── Logging ───────────────────────────────────────────────────────────────────
# Container-friendly: log everything to stdout/stderr.
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── Process naming ────────────────────────────────────────────────────────────
proc_name = "admizo-api"

# ── Graceful shutdown ─────────────────────────────────────────────────────────
graceful_timeout = 30
