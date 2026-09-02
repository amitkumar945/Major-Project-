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
os.environ.setdefault("VERCEL", "1")

try:
    from app import create_app

    app = create_app()
except Exception:
    from flask import Flask, jsonify

    app = Flask(__name__)

    @app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def fallback(path):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The app is starting or the database is unavailable. Check the deployment environment and MongoDB connection.",
                    "error": {"code": "SERVICE_UNAVAILABLE"},
                }
            ),
            503,
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
