import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

sys.path.insert(0, str(BACKEND))

os.environ.setdefault("FLASK_RUN_FROM_CLI", "1")
os.environ.setdefault("SERVE_FRONTEND", "true")
os.environ.setdefault("FRONTEND_FOLDER", str(FRONTEND))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
