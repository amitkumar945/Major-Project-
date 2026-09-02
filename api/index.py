import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

sys.path.insert(0, str(BACKEND))

os.environ.setdefault("FLASK_RUN_FROM_CLI", "1")
# This function serves the bundled static frontend as well as the API.
os.environ["SERVE_FRONTEND"] = "true"
os.environ["FRONTEND_FOLDER"] = str(FRONTEND)
os.environ.setdefault("VERCEL", "1")

def _build_app():
    try:
        from app import create_app

        return create_app()
    except Exception:
        from flask import Flask, jsonify

        fallback_app = Flask(__name__)

        @fallback_app.route(
            "/",
            defaults={"path": ""},
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        )
        @fallback_app.route(
            "/<path:path>",
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        )
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

        return fallback_app


# Keep this as a direct module-level assignment for Vercel's entrypoint scanner.
app = _build_app()
handler = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
