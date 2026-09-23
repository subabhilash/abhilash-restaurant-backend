from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV = ROOT / "venv"
VENV_PYTHON = VENV / "bin" / "python"
PIP = VENV / "bin" / "pip"


def run(command: list[str]) -> None:
    print(" ".join(command))
    subprocess.check_call(command, cwd=ROOT)


def venv_ready() -> bool:
    if not VENV_PYTHON.exists():
        return False
    check = subprocess.run(
        [str(VENV_PYTHON), "-c", "import uvicorn, alembic, sqlalchemy"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return check.returncode == 0


def main() -> int:
    os.chdir(ROOT)

    if not (ROOT / ".env").exists():
        print("Missing .env. Copy .env.example to .env and set DATABASE_URL.")
        return 1

    if not VENV_PYTHON.exists():
        print("Create venv")
        venv.create(VENV, with_pip=True)

    if "--install" in sys.argv or not venv_ready():
        run([str(PIP), "install", "-r", "requirements.txt"])

    run([str(VENV_PYTHON), "sync_db.py"])
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), "run.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
