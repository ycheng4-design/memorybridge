"""MemoryBridge Flask entry point.

Loads environment variables, creates the app via factory, and runs on port 5000.
"""

import logging
import os
import sys

from dotenv import load_dotenv

# Add the project root (one level above backend/) to sys.path so that
# `import ai` resolves to memorybridge/ai/ regardless of working directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


load_dotenv()

# Configure logging before app import so all modules inherit this format.
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("FLASK_ENV") == "development" else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from app import create_app  # noqa: E402 — import after dotenv load

app = create_app()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
