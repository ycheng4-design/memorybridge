"""Embeddings route — POST /api/embed.

Accepts a memory_id and queues a batch AMD embedding job for all
photos in that memory. The HTTP response is returned immediately
(status 'queued') and the work happens in a background thread.
"""

from __future__ import annotations

import logging
import threading
from typing import Tuple

from flask import Blueprint, jsonify, request

from ..services import firebase_service

logger = logging.getLogger(__name__)

embeddings_bp = Blueprint("embeddings", __name__)


@embeddings_bp.post("/embed")
def trigger_embedding() -> Tuple[object, int]:
    """Queue a batch embedding job for all photos in a memory.

    Request body (JSON):
        {"memory_id": "uuid-string"}

    Returns:
        200: {"status": "queued", "memory_id": str, "photo_count": int}
        400: {"error": "validation_failed", "detail": str}
        404: {"error": "not_found", "detail": str}
        500: {"error": "server_error", "detail": str}
    """
    body = request.get_json(silent=True) or {}
    memory_id: str = (body.get("memory_id") or "").strip()

    if not memory_id:
        return (
            jsonify(
                {"error": "validation_failed", "detail": "memory_id is required in JSON body"}
            ),
            400,
        )

    # Verify the memory exists before queuing work
    try:
        memory = firebase_service.get_memory_from_firestore(memory_id)
    except Exception:  # noqa: BLE001
        logger.exception("Error looking up memory %s", memory_id)
        return jsonify({"error": "server_error", "detail": "An internal error occurred. Please try again."}), 500

    if memory is None:
        return (
            jsonify(
                {"error": "not_found", "detail": f"Memory '{memory_id}' does not exist"}
            ),
            404,
        )

    photos: list[dict] = memory.get("photos", [])
    if not photos:
        return (
            jsonify(
                {
                    "status": "no_photos",
                    "memory_id": memory_id,
                    "photo_count": 0,
                    "detail": "No photos found for this memory",
                }
            ),
            200,
        )

    # Queue the batch job — does NOT block this response
    _queue_batch_job(memory_id, photos)

    return (
        jsonify(
            {
                "status": "queued",
                "memory_id": memory_id,
                "photo_count": len(photos),
            }
        ),
        200,
    )


# ------------------------------------------------------------------ #
# Background job                                                        #
# ------------------------------------------------------------------ #


def _queue_batch_job(memory_id: str, photos: list[dict]) -> None:
    """Launch a daemon thread that runs the AMD embedding batch.

    The thread is named 'embed-batch-{memory_id[:8]}' for easier
    identification in logs and thread dumps.

    Args:
        memory_id: UUID of the memory document.
        photos: List of photo dicts with 'url', 'photo_id', 'caption'.
    """
    def _worker() -> None:
        import asyncio

        logger.info(
            "Embedding batch job started — memory=%s photos=%d",
            memory_id,
            len(photos),
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_batch(memory_id, photos))
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Embedding batch job failed — memory=%s: %s", memory_id, exc
            )
        finally:
            loop.close()

    thread = threading.Thread(
        target=_worker,
        daemon=True,
        name=f"embed-batch-{memory_id[:8]}",
    )
    thread.start()
    logger.info("Queued embedding batch thread for memory %s.", memory_id)


async def _run_batch(memory_id: str, photos: list[dict]) -> None:
    """Download each photo, generate its AMD embedding, and persist it.

    Uses httpx for async photo downloads and the amd_service for inference.
    Falls back to CPU automatically via amd_service when AMD cloud is unavailable.

    Args:
        memory_id: Parent memory UUID.
        photos: List of photo dicts (must have 'url', 'photo_id', 'caption').
    """
    import httpx

    from ..services.amd_service import generate_embedding

    failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for photo in photos:
            photo_id: str = photo["photo_id"]
            url: str = photo["url"]
            caption: str = photo.get("caption", "")

            # Skip photos that already have an embedding
            if photo.get("embedding") is not None:
                logger.debug(
                    "Skipping photo %s — embedding already present.", photo_id
                )
                continue

            try:
                response = await client.get(url)
                response.raise_for_status()
                image_bytes = response.content

                embedding = await generate_embedding(image_bytes, caption)

                firebase_service.update_photo_embedding(
                    memory_id=memory_id,
                    photo_id=photo_id,
                    embedding=embedding,
                )
                logger.info(
                    "Embedded photo %s for memory %s (%d dims).",
                    photo_id,
                    memory_id,
                    len(embedding),
                )

            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.error(
                    "Failed to embed photo %s for memory %s: %s",
                    photo_id,
                    memory_id,
                    exc,
                )

    # C2: Only mark "ready" when all embeddings succeeded; use "error" on any failure.
    final_status = "ready" if failed == 0 else "error"
    firebase_service.update_memory_status(memory_id, final_status)
    logger.info(
        "Batch embedding complete for memory %s — %d failed — status set to '%s'.",
        memory_id, failed, final_status,
    )
