from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / "venv" / "bin" / "python"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Alembic migrations and verify DB schema.")
    parser.add_argument("--env-file", default=".env", help="Env file to load. Default: .env")
    parser.add_argument("--database-url", help="Override DATABASE_URL for this run.")
    parser.add_argument("--check-only", action="store_true", help="Only verify schema. Do not run migrations.")
    parser.add_argument("--skip-check", action="store_true", help="Run migrations without schema verification.")
    return parser.parse_args()


def reexec_in_venv() -> int | None:
    if Path(sys.executable) == VENV_PYTHON or not VENV_PYTHON.exists():
        return None
    return subprocess.call([str(VENV_PYTHON), str(ROOT / "sync_db.py"), *sys.argv[1:]])


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def masked_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return ""
    parts = urlsplit(database_url)
    if not parts.password:
        return database_url
    user = parts.username or ""
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{user}:***@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def run(command: list[str]) -> None:
    print(" ".join(command))
    subprocess.check_call(command, cwd=ROOT, env=os.environ.copy())


def verify_schema() -> None:
    from sqlalchemy import create_engine, inspect

    from app.database import Base
    import app.models  # noqa: F401

    engine = create_engine(os.environ["DATABASE_URL"])
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    missing: list[str] = []
    for table in Base.metadata.tables.values():
        if table.name not in existing_tables:
            missing.append(f"{table.name} table missing")
            continue

        existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing_columns:
                missing.append(f"{table.name}.{column.name} column missing")

    engine.dispose()

    if missing:
        for item in missing[:50]:
            print(f"Schema mismatch: {item}")
        if len(missing) > 50:
            print(f"Schema mismatch: {len(missing) - 50} more")
        raise SystemExit(2)

    print("Schema check OK")


def main() -> int:
    os.chdir(ROOT)

    reexec_code = reexec_in_venv()
    if reexec_code is not None:
        return reexec_code

    args = parse_args()
    load_env_file(ROOT / args.env_file)

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    if not os.environ.get("DATABASE_URL"):
        print("Missing DATABASE_URL. Set env var, pass --database-url, or create env file.")
        return 1

    print(f"DB target: {masked_database_url()}")

    if not args.check_only:
        run([sys.executable, "-m", "alembic", "current"])
        run([sys.executable, "-m", "alembic", "upgrade", "head"])
        run([sys.executable, "-m", "alembic", "current"])

    if not args.skip_check:
        verify_schema()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
