from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / "venv" / "bin" / "python"


def main() -> int:
    os.chdir(ROOT)

    if Path(sys.executable) != VENV_PYTHON and VENV_PYTHON.exists():
        return subprocess.call([str(VENV_PYTHON), str(ROOT / "sync_db.py")])

    if not (ROOT / ".env").exists():
        print("Missing .env. Copy .env.example to .env and set DATABASE_URL.")
        return 1

    print("Sync DB: alembic upgrade head")
    return subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])


if __name__ == "__main__":
    raise SystemExit(main())
