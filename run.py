"""
Entry point — run with:
  Development:  python run.py
  Production:   gunicorn run:sio_app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8099 --workers 4
"""
import uvicorn
from app.main import sio_app  # noqa: F401

if __name__ == "__main__":
    uvicorn.run(
        "app.main:sio_app",
        host="0.0.0.0",
        port=8099,
        reload=True,
        log_level="info",
    )
