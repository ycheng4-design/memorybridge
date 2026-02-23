"""Memories route — GET /api/memories and GET /api/memories/:id.

Reads memory documents from Firestore including the photos subcollection
and returns them as JSON. Returns 404 when a memory does not exist.
"""

from __future__ import annotations

import logging
from typing import Tuple

from flask import Blueprint, jsonify, request

from ..services import firebase_service

logger = logging.getLogger(__name__)

memories_bp = Blueprint("memories", __name__)


@memories_bp.get("/memories/<string:memory_id>")
def get_memory(memory_id: str) -> Tuple[object, int]:
    """Return the full memory record including its photos subcollection.

    Path parameter:
        memory_id — UUID of the memory document.

    Returns:
        200:
            {
                "id": str,
                "person_name": str,
                "created_at": str,
                "status": str,
                "voice_id": str | null,
                "embedding_ready": bool,
                "photos": [
                    {
                        "photo_id": str,
                        "url": str,
                        "caption": str,
                        "date": str,
                        "era": str,
                        "embedding": list | null
                    },
                    ...
                ]
            }
        404: {"error": "not_found", "detail": str}
        500: {"error": "server_error", "detail": str}
    """
    if not memory_id or not memory_id.strip():
        return jsonify({"error": "not_found", "detail": "memory_id is required"}), 404

    try:
        memory = firebase_service.get_memory_from_firestore(memory_id.strip())
    except Exception:  # noqa: BLE001
        logger.exception("Failed to retrieve memory %s", memory_id)
        return jsonify({"error": "server_error", "detail": "An internal error occurred. Please try again."}), 500

    if memory is None:
        return (
            jsonify(
                {
                    "error": "not_found",
                    "detail": f"Memory '{memory_id}' does not exist",
                }
            ),
            404,
        )

    return jsonify(memory), 200


@memories_bp.get("/memories")
def list_memories() -> Tuple[object, int]:
    """Return a paginated list of all memory documents (without photo embeddings).

    Query parameters:
        limit  (int, default 20) — maximum number of records to return
        offset (int, default 0)  — number of records to skip

    Returns:
        200: {"memories": [...], "total": int}
        500: {"error": "server_error", "detail": str}
    """
    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return (
            jsonify(
                {
                    "error": "validation_failed",
                    "detail": "limit and offset must be integers",
                }
            ),
            400,
        )

    limit = min(max(limit, 1), 100)   # clamp: 1 – 100
    offset = max(offset, 0)

    try:
        memories = firebase_service.list_memories_from_firestore(limit=limit, offset=offset)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to list memories")
        return jsonify({"error": "server_error", "detail": "An internal error occurred. Please try again."}), 500

    return jsonify({"memories": memories, "total": len(memories)}), 200
