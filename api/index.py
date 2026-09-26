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
    except Exception as startup_error:
        import logging
        import traceback

        # Log the real reason before serving 503s. Without this the fallback
        # below answers every route with an identical "service unavailable"
        # and the actual cause - a missing JWT_SECRET_KEY, an unreachable
        # MONGO_URI, an import error - never appears in the Vercel logs, so
        # the deployment looks broken for no discoverable reason.
        logging.getLogger(__name__).error(
            "create_app() failed; serving 503 fallback. Cause: %s: %s\n%s",
            type(startup_error).__name__,
            startup_error,
            traceback.format_exc(),
        )
        # Also to stderr, which Vercel captures even before logging is set up.
        print(
            f"STARTUP FAILURE: {type(startup_error).__name__}: {startup_error}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc(file=sys.stderr)

        from flask import Flask, jsonify

        fallback_app = Flask(__name__)

        # Bound to a plain local: Python unbinds the `except ... as` name when
        # the block exits, so the view functions below cannot close over it.
        failure_type = type(startup_error).__name__

        @fallback_app.route("/api/startup-check", methods=["GET"])
        def startup_check():
            """Which required variables are missing, without revealing values.

            Reports only presence, never contents, so it is safe to call on a
            live deployment while diagnosing a 503.
            """
            required = ("JWT_SECRET_KEY", "MONGO_URI")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Application failed to start. See the deployment logs for the traceback.",
                        "error": {
                            "code": "STARTUP_FAILED",
                            "type": failure_type,
                            "missingEnv": [
                                name
                                for name in required
                                if not (os.environ.get(name) or "").strip()
                            ],
                        },
                    }
                ),
                503,
            )

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
