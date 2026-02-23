"""AMD MI300X embedding service for MemoryBridge.

Generates 1024-dimensional image/text embeddings using the AMD Developer Cloud
inference endpoint (CLIP-based model). Falls back to a local CPU computation
when the AMD endpoint is unreachable, so development and demos can run offline.

Includes a timing logger to capture AMD vs CPU latency — critical for the
hackathon demo that demonstrates AMD MI300X advantage.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Configuration                                                        #
# ------------------------------------------------------------------ #

_AMD_ENDPOINT: str = os.environ.get("AMD_ENDPOINT", "https://api.amd.com/v1")
_AMD_EMBEDDING_MODEL: str = os.environ.get(
    "AMD_EMBEDDING_MODEL", "clip-vit-large-patch14"
)
_EMBEDDING_DIM: int = 1024

# Timeout for AMD cloud requests — allow up to 30 s per batch
_AMD_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


def _amd_api_key() -> str:
    """Return the AMD API key from the environment.

    Returns an empty string if AMD_API_KEY is absent or blank, which causes
    the AMD endpoint to return 401 → HTTPStatusError → CPU fallback. This is
    intentional: the CPU fallback keeps the app functional in offline/dev mode.
    """
    return os.environ.get("AMD_API_KEY", "")


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #


async def generate_embedding(
    image_bytes: bytes,
    caption: str = "",
) -> List[float]:
    """Generate a 1024-dim embedding for an image, using AMD MI300X if available.

    Tries the AMD Developer Cloud endpoint first. On any connection or HTTP error
    it falls back to local CPU computation so the backend keeps running during
    development and demo rehearsal.

    Timing is logged at INFO level for both paths so the hackathon demo can
    show concrete latency numbers as evidence of AMD acceleration.

    Args:
        image_bytes: Raw bytes of a JPEG or PNG image.
        caption: Optional text caption to fuse into a text+image embedding.
            When provided, the embedding encodes both image content and caption.

    Returns:
        List of 1024 floats representing the embedding vector.
    """
    start = time.perf_counter()

    try:
        embedding = await _amd_cloud_embedding(image_bytes, caption)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "[AMD MI300X] Embedding generated in %.1f ms  (dim=%d)",
            elapsed_ms,
            len(embedding),
        )
        return embedding

    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "[AMD MI300X] Endpoint unavailable after %.1f ms: %s. "
            "Falling back to local CPU embedding.",
            elapsed_ms,
            exc,
        )

    cpu_start = time.perf_counter()
    embedding = _local_cpu_embedding(image_bytes, caption)
    cpu_elapsed_ms = (time.perf_counter() - cpu_start) * 1000
    logger.info(
        "[CPU fallback] Embedding generated in %.1f ms  (dim=%d)",
        cpu_elapsed_ms,
        len(embedding),
    )
    return embedding


async def generate_batch_embeddings(
    photo_jobs: List[dict],
) -> List[Optional[List[float]]]:
    """Generate embeddings for a batch of photos concurrently.

    Each job dict must have keys:
        - 'image_bytes': bytes  — raw image data
        - 'caption': str        — associated caption (may be empty)

    Results are returned in the same order as the input list. If a single
    job fails, its slot is filled with None and a warning is logged.

    Args:
        photo_jobs: List of {'image_bytes': bytes, 'caption': str} dicts.

    Returns:
        List of embedding vectors (List[float]) or None for any failed job.
    """
    import asyncio

    async def _safe_embed(job: dict, index: int) -> Optional[List[float]]:
        try:
            return await generate_embedding(
                image_bytes=job["image_bytes"],
                caption=job.get("caption", ""),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Embedding job %d failed: %s", index, exc)
            return None

    tasks = [_safe_embed(job, i) for i, job in enumerate(photo_jobs)]
    results: List[Optional[List[float]]] = await asyncio.gather(*tasks)
    return results


# ------------------------------------------------------------------ #
# AMD cloud path                                                       #
# ------------------------------------------------------------------ #


async def _amd_cloud_embedding(
    image_bytes: bytes,
    caption: str,
) -> List[float]:
    """Call the AMD Developer Cloud CLIP inference endpoint.

    The endpoint accepts a base64-encoded image and an optional text prompt,
    returning a JSON body with an 'embedding' array.

    Args:
        image_bytes: Raw image bytes (JPEG/PNG).
        caption: Optional caption text for multimodal embedding.

    Returns:
        1024-dimensional embedding vector.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
        httpx.ConnectError: When the endpoint is unreachable.
        httpx.TimeoutException: When the request times out.
        ValueError: If the response payload is missing the 'embedding' field.
    """
    b64_image = base64.b64encode(image_bytes).decode("ascii")

    payload: dict = {
        "model": _AMD_EMBEDDING_MODEL,
        "input": {
            "image": b64_image,
        },
    }
    if caption:
        payload["input"]["text"] = caption

    async with httpx.AsyncClient(timeout=_AMD_TIMEOUT) as client:
        response = await client.post(
            f"{_AMD_ENDPOINT}/embeddings",
            headers={
                "Authorization": f"Bearer {_amd_api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    data = response.json()

    # Handle both flat {"embedding": [...]} and OpenAI-style {"data": [{"embedding": [...]}]}
    if "embedding" in data:
        embedding: List[float] = data["embedding"]
    elif "data" in data and data["data"]:
        embedding = data["data"][0]["embedding"]
    else:
        raise ValueError(
            f"AMD endpoint returned unexpected response shape: {list(data.keys())}"
        )

    if len(embedding) != _EMBEDDING_DIM:
        logger.warning(
            "AMD returned embedding of dim %d; expected %d. "
            "Check AMD_EMBEDDING_MODEL env var.",
            len(embedding),
            _EMBEDDING_DIM,
        )

    return embedding


# ------------------------------------------------------------------ #
# Local CPU fallback                                                   #
# ------------------------------------------------------------------ #


def _local_cpu_embedding(
    image_bytes: bytes,
    caption: str,
) -> List[float]:
    """Generate a deterministic pseudo-embedding on the local CPU.

    This is NOT a real semantic embedding — it is a hash-based fallback
    that produces a stable 1024-dimensional unit vector from the image bytes
    and caption. It ensures the application remains functional in environments
    without AMD cloud access (local dev, CI).

    In the hackathon demo, calling generate_embedding() shows AMD vs CPU
    timing in the logs so judges can see the performance difference.

    Args:
        image_bytes: Raw image bytes.
        caption: Optional caption string.

    Returns:
        1024-dimensional float list (unit-normalised hash-based vector).
    """
    import hashlib
    import math

    combined = image_bytes + caption.encode("utf-8")
    digest = hashlib.sha512(combined).digest()

    # Expand 64-byte digest to 1024 floats by cycling through the bytes
    raw: List[float] = []
    for i in range(_EMBEDDING_DIM):
        byte_val = digest[i % len(digest)]
        # Map [0, 255] → [-1.0, 1.0] with deterministic variation per index
        raw.append((byte_val / 127.5 - 1.0) * math.cos(i * 0.1))

    # L2-normalise to unit vector
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]
