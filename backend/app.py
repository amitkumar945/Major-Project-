"""
Application entry point.

    python app.py            # development server on http://127.0.0.1:5000

Flask also serves the existing `frontend/` folder, so one process runs the whole
system - no separate static server needed. Set SERVE_FRONTEND=false to disable
that and run the frontend from its own server instead.
"""

import logging
import os
import sys
from pathlib import Path

# Make `routes`, `services`, `utils` and `ai` importable as top-level packages
# regardless of the directory the server is started from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from config import get_config
from database import init_db
from utils.responses import ApiException

logger = logging.getLogger(__name__)


def create_app(config_object=None) -> Flask:
    """Application factory: build, configure and wire the Flask app."""
    config_object = config_object or get_config()

    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object)

    # ------------------------------------------------------- secret checks
    # Refuse to start without a signing key rather than falling back to a
    # default one that would be identical in every deployment.
    if not app.config.get("JWT_SECRET_KEY"):
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Copy backend/.env.example to backend/.env "
            "and set a strong random value (see the README)."
        )

    # Two distinct situations, and they need different messages.
    from config import is_otp_dev_mode

    if is_otp_dev_mode(app.config):
        logger.warning(
            "OTP dev mode is ACTIVE: verification codes are returned in API "
            "responses. This is development-only behaviour."
        )
    elif app.config.get("OTP_DEV_MODE"):
        # Asked for, but refused because this is a production environment.
        logger.warning(
            "OTP_DEV_MODE=true was ignored: codes are only returned in a "
            "development or test environment. Set OTP_DEV_MODE=false to "
            "silence this, and configure MAIL_* so codes can be delivered."
        )

    # -------------------------------------------------------------- uploads
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------- cors
    # Explicit origins only - never "*", so credentials stay safe.
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        max_age=3600,
    )

    # ------------------------------------------------------------- database
    init_db(config_object)

    if app.config.get("SEED_ON_START"):
        import seed

        with app.app_context():
            seed.run()

    _register_blueprints(app)
    _register_error_handlers(app)
    _register_meta_routes(app)

    if app.config.get("SERVE_FRONTEND"):
        _register_frontend(app)

    return app


def _register_blueprints(app: Flask) -> None:
    from routes.admin_routes import bp as admin_bp
    from routes.ai_routes import bp as ai_bp
    from routes.analytics_routes import bp as analytics_bp
    from routes.auth_routes import bp as auth_bp
    from routes.complaint_routes import bp as complaint_bp
    from routes.department_routes import bp as department_bp
    from routes.device_routes import bp as device_bp
    from routes.feedback_routes import bp as feedback_bp
    from routes.file_routes import bp as file_bp
    from routes.notification_routes import bp as notification_bp
    from routes.officer_routes import bp as officer_bp
    from routes.user_routes import bp as user_bp

    for blueprint in (
        auth_bp, complaint_bp, ai_bp, officer_bp, department_bp,
        user_bp, notification_bp, feedback_bp, analytics_bp, admin_bp, file_bp,
        device_bp,
    ):
        app.register_blueprint(blueprint)


def _register_error_handlers(app: Flask) -> None:
    """Every failure leaves as the standard error envelope."""

    @app.errorhandler(ApiException)
    def handle_api_exception(exc):
        return jsonify({"success": False, "message": exc.message, "error": exc.error}), exc.status

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(exc):
        limit_mb = app.config["MAX_FILE_SIZE"] / (1024 * 1024)
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"The upload is too large. Each file must be {limit_mb:.0f} MB or less.",
                    "error": {"maxFileSize": app.config["MAX_FILE_SIZE"]},
                }
            ),
            413,
        )

    @app.errorhandler(404)
    def handle_not_found(exc):
        if request.path.startswith("/api/"):
            return (
                jsonify({"success": False, "message": f"No API endpoint matches {request.path}.", "error": {}}),
                404,
            )
        # Non-API 404s fall through to the frontend handler.
        return exc

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc):
        if request.path.startswith("/api/"):
            return (
                jsonify({"success": False, "message": exc.description, "error": {"code": exc.code}}),
                exc.code,
            )
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        # Log the real error, return a generic message: a stack trace or a
        # database error string must never reach the client.
        logger.exception("Unhandled error on %s %s", request.method, request.path)
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Something went wrong on the server. Please try again.",
                    "error": {"type": type(exc).__name__} if app.config.get("DEBUG") else {},
                }
            ),
            500,
        )


def _register_meta_routes(app: Flask) -> None:
    @app.get("/api/health")
    def health():
        """Liveness probe - also confirms the database is reachable."""
        from database import get_db

        try:
            get_db().command("ping")
            database_ok = True
        except Exception:
            database_ok = False

        from services import email_service

        return (
            jsonify(
                {
                    "success": database_ok,
                    "message": "API is running." if database_ok else "Database is unreachable.",
                    "data": {
                        "status": "ok" if database_ok else "degraded",
                        "database": database_ok,
                        # Whether mail is usable - never any credential value.
                        "email": email_service.is_configured(),
                    },
                }
            ),
            200 if database_ok else 503,
        )

    @app.after_request
    def security_headers(response):
        """Baseline hardening for every response."""
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


def _register_frontend(app: Flask) -> None:
    """Serve the existing HTML/CSS/JS folder from Flask itself."""
    frontend = Path(app.config["FRONTEND_FOLDER"])
    if not frontend.is_dir():
        logger.warning("FRONTEND_FOLDER %s does not exist; not serving the frontend.", frontend)
        return

    @app.get("/")
    def index():
        return send_from_directory(frontend, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename):
        """Serve a file, allowing extension-less URLs like /login and /student/dashboard."""
        # The catch-all must never answer an API path: an unmatched /api/ URL
        # has to stay JSON so clients get an error they can parse, not HTML.
        if filename.startswith("api/"):
            return (
                jsonify(
                    {"success": False, "message": f"No API endpoint matches /{filename}.", "error": {}}
                ),
                404,
            )

        candidate = frontend / filename
        if candidate.is_file():
            return send_from_directory(frontend, filename)

        html = frontend / f"{filename}.html"
        if html.is_file():
            return send_from_directory(frontend, f"{filename}.html")

        if (frontend / filename).is_dir() and (frontend / filename / "index.html").is_file():
            return send_from_directory(frontend, f"{filename}/index.html")

        return send_from_directory(frontend, "404.html"), 404


app = create_app() if os.environ.get("FLASK_RUN_FROM_CLI") else None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        application = create_app()
    except RuntimeError as exc:
        print(f"\nStartup failed: {exc}\n")
        raise SystemExit(1)
    except Exception as exc:
        print(f"\nStartup failed: {exc}")
        print("Is MongoDB running? Check MONGO_URI in backend/.env\n")
        raise SystemExit(1)

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")

    print(f"\n  Grievance Management System API")
    print(f"  API      http://{host}:{port}/api")
    print(f"  Health   http://{host}:{port}/api/health")
    if application.config.get("SERVE_FRONTEND"):
        print(f"  Frontend http://{host}:{port}/")
    print()

    application.run(host=host, port=port, debug=application.config.get("DEBUG", False))
