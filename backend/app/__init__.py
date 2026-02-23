"""MemoryBridge Flask application factory.

Creates and configures the Flask app with CORS and all route blueprints.
"""

import os

from flask import Flask, jsonify
from flask_cors import CORS

# Placeholder that must never reach production.
_WEAK_SECRET_PLACEHOLDER = "change_me_to_a_random_32_char_secret"

# 320 MB ceiling: 30 × 10 MB photos + 10 MB audio + headroom.
_MAX_CONTENT_LENGTH = 320 * 1024 * 1024


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns:
        Configured Flask application instance.

    Raises:
        RuntimeError: If FLASK_SECRET_KEY is not set or is the known-weak placeholder.
    """
    app = Flask(__name__)

    flask_env = os.environ.get("FLASK_ENV", "production")
    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key or secret_key == _WEAK_SECRET_PLACEHOLDER:
        if flask_env in ("development", "testing"):
            secret_key = "dev-insecure-key-do-not-use-in-production"
        else:
            raise RuntimeError(
                "FLASK_SECRET_KEY is missing or is the default placeholder. "
                "Generate a real key: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
    app.secret_key = secret_key

    # Hard cap on incoming request body size — Werkzeug rejects oversized
    # multipart requests with 413 before they are buffered into RAM.
    app.config["MAX_CONTENT_LENGTH"] = _MAX_CONTENT_LENGTH

    # CORS — read exact origin list from CORS_ORIGINS env var (comma-separated).
    # Falls back to project-specific literals; never uses broad regex patterns.
    _raw_origins = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000,"
        "https://memorybridge-h4h-2026.web.app,"
        "https://memorybridge-h4h-2026.firebaseapp.com",
    )
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

    CORS(
        app,
        origins=_allowed_origins,
        supports_credentials=True,
    )

    from .routes.upload import upload_bp
    from .routes.memories import memories_bp
    from .routes.embeddings import embeddings_bp

    app.register_blueprint(upload_bp, url_prefix="/api")
    app.register_blueprint(memories_bp, url_prefix="/api")
    app.register_blueprint(embeddings_bp, url_prefix="/api")

    @app.get("/")
    def root():
        return jsonify({
            "service": "memorybridge-backend",
            "status": "running",
            "endpoints": {
                "health":          "GET  /api/health",
                "upload":          "POST /api/upload",
                "list_memories":   "GET  /api/memories",
                "get_memory":      "GET  /api/memories/<memory_id>",
                "trigger_embed":   "POST /api/embed",
            },
        }), 200

    return app
