"""AMD MI300X / text embedding service for MemoryBridge.

Generates 384-dimensional text embeddings using an OpenAI-compatible
endpoint (AMD Developer Cloud vLLM with all-MiniLM-L6-v2).

Falls back to local sentence-transformers (all-MiniLM-L6-v2) when the
AMD endpoint is unreachable or unconfigured, so development and demos
can run fully offline.

Timing is logged at INFO level for both paths so the hackathon demo can
show concrete latency numbers as evidence of AMD acceleration.
"""

from __future__ import annotations

import logging
import math
import os
import time
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Configuration                                                        #
# ------------------------------------------------------------------ #

_AMD_ENDPOINT: str = os.environ.get("AMD_ENDPOINT", "").rstrip("/")
_AMD_EMBEDDING_MODEL: str = os.environ.get(
    "AMD_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
)
_EMBEDDING_DIM: int = 384  # all-MiniLM-L6-v2 produces 384-dim vectors

_AMD_TIMEOUT = httpx.Timeout(30.0, connect=5.0)

# Lazy-loaded local SentenceTransformer instance
_local_st_model = None


def _amd_api_key() -> str:
    return os.environ.get("AMD_API_KEY", "")


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #


async def generate_embedding(
    image_bytes: bytes,
    caption: str = "",
) -> List[float]:
    """Generate a 384-dim text embedding for a photo caption.

    Uses the AMD MI300X OpenAI-compatible endpoint when AMD_ENDPOINT is
    configured; otherwise falls back to local sentence-transformers.

    The image_bytes parameter is accepted for API compatibility but is not
    sent to the backend — the all-MiniLM-L6-v2 model is text-only, so the
    caption provides the semantic embedding signal.

    Args:
        image_bytes: Raw image bytes (unused — kept for API compatibility).
        caption: Caption text to embed.

    Returns:
        L2-normalized list of 384 floats.
    """
    start = time.perf_counter()
    text = caption.strip() or ""

    if _AMD_ENDPOINT:
        try:
            embedding = await _amd_cloud_embedding(text)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "[AMD MI300X] Embedding generated in %.1f ms (dim=%d)",
                elapsed_ms,
                len(embedding),
            )
            return embedding
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                "[AMD MI300X] Endpoint unavailable after %.1f ms: %s — "
                "falling back to local CPU.",
                elapsed_ms,
                exc,
            )
    else:
        logger.info("AMD_ENDPOINT not set — using local CPU (sentence-transformers).")

    cpu_start = time.perf_counter()
    embedding = _local_cpu_embedding(text)
    cpu_elapsed_ms = (time.perf_counter() - cpu_start) * 1000
    logger.info(
        "[CPU fallback] Embedding generated in %.1f ms (dim=%d)",
        cpu_elapsed_ms,
        len(embedding),
    )
    return embedding


async def generate_batch_embeddings(
    photo_jobs: List[dict],
) -> List[Optional[List[float]]]:
    """Generate embeddings for a batch of photos concurrently.

    Each job dict must have keys:
        - 'image_bytes': bytes  (unused — kept for API compatibility)
        - 'caption': str        — text to embed

    Args:
        photo_jobs: List of {'image_bytes': bytes, 'caption': str} dicts.

    Returns:
        List of 384-dim embedding vectors, or None for any failed job.
    """
    import asyncio

    async def _safe_embed(job: dict, index: int) -> Optional[List[float]]:
        try:
            return await generate_embedding(
                image_bytes=job.get("image_bytes", b""),
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


async def _amd_cloud_embedding(text: str) -> List[float]:
    """Call the AMD Developer Cloud OpenAI-compatible embeddings endpoint.

    Sends a text string and receives a 384-dim embedding vector.
    Compatible with vLLM serving all-MiniLM-L6-v2 on AMD MI300X.

    Args:
        text: Input text to embed.

    Returns:
        384-dimensional L2-normalized embedding vector.

    Raises:
        httpx.HTTPStatusError: On non-2xx responses.
        httpx.ConnectError: When the endpoint is unreachable.
        httpx.TimeoutException: When the request times out.
        ValueError: If the response payload is missing the embedding field.
    """
    payload = {
        "model": _AMD_EMBEDDING_MODEL,
        "input": text,
    }

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

    # Handle OpenAI-style {"data": [{"embedding": [...]}]}
    if "data" in data and data["data"]:
        embedding: List[float] = data["data"][0]["embedding"]
    elif "embedding" in data:
        embedding = data["embedding"]
    else:
        raise ValueError(
            f"AMD endpoint returned unexpected response shape: {list(data.keys())}"
        )

    return _l2_normalize(embedding)


# ------------------------------------------------------------------ #
# Local CPU fallback (sentence-transformers)                           #
# ------------------------------------------------------------------ #


def _local_cpu_embedding(text: str) -> List[float]:
    """Generate a semantic embedding using local sentence-transformers.

    Lazy-loads the all-MiniLM-L6-v2 model on first call.

    Args:
        text: Input text to embed.

    Returns:
        384-dimensional L2-normalized float list.

    Raises:
        RuntimeError: If sentence-transformers is not installed.
    """
    global _local_st_model

    if _local_st_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import]

            logger.info("Loading local sentence-transformer model: all-MiniLM-L6-v2")
            _local_st_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Local model loaded successfully.")
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            ) from exc

    raw: List[float] = _local_st_model.encode(text).tolist()
    return _l2_normalize(raw)


def _l2_normalize(vector: List[float]) -> List[float]:
    """L2-normalize a float vector in-place."""
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
