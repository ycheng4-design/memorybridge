"""Upload route — POST /api/upload and GET /api/health.

Validates multipart form data, uploads files to Firebase Storage,
persists the memory to Firestore, and queues an async embedding job
WITHOUT blocking the HTTP response.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from typing import List, Tuple

from flask import Blueprint, jsonify, request
from werkzeug.datastructures import FileStorage

from ..services import firebase_service

logger = logging.getLogger(__name__)

upload_bp = Blueprint("upload", __name__)

# ------------------------------------------------------------------ #
# Constants                                                            #
# ------------------------------------------------------------------ #

_MAX_FILE_SIZE_BYTES: int = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024
_MAX_PHOTOS: int = int(os.environ.get("MAX_PHOTOS", "30"))
_MAX_PERSON_NAME_LEN: int = 100
_MAX_CAPTION_LEN: int = 500

_ALLOWED_IMAGE_MIMES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)
_ALLOWED_IMAGE_EXTS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".webp"})

_ALLOWED_AUDIO_MIMES: frozenset[str] = frozenset(
    {"audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4", "audio/webm", "audio/x-m4a"}
)
_ALLOWED_AUDIO_EXTS: frozenset[str] = frozenset(
    {".mp3", ".wav", ".ogg", ".m4a", ".webm"}
)


# ------------------------------------------------------------------ #
# Routes                                                               #
# ------------------------------------------------------------------ #


@upload_bp.get("/health")
def health_check() -> Tuple[object, int]:
    """Simple health check endpoint used by load balancers and CI.

    Returns:
        JSON body {"status": "ok"} with HTTP 200.
    """
    return jsonify({"status": "ok", "service": "memorybridge-backend"}), 200


@upload_bp.post("/upload")
def handle_upload() -> Tuple[object, int]:
    """Accept a multipart upload containing photos and a voice recording.

    Form fields:
        photos[]        — one or more JPEG/PNG image files (max 30, max 10 MB each)
        voice_recording — a single audio file (WAV/MP3/OGG/M4A/WebM)
        captions[]      — one string caption per photo (parallel array)
        person_name     — display name of the person

    Returns:
        200: {"memory_id": str, "status": "processing"}
        400: {"error": "validation_failed", "detail": str}
        500: {"error": "server_error", "detail": str}
    """
    photos: List[FileStorage] = request.files.getlist("photos[]")
    voice: FileStorage | None = request.files.get("voice_recording")
    captions: List[str] = request.form.getlist("captions[]")
    person_name: str = request.form.get("person_name", "").strip()

    # ---- Input validation ------------------------------------------------
    error = _validate_upload(photos, voice, captions, person_name)
    if error:
        return jsonify({"error": "validation_failed", "detail": error}), 400

    # voice is guaranteed non-None after _validate_upload; guard for type-checker.
    if voice is None:  # pragma: no cover — unreachable after validation
        return jsonify({"error": "validation_failed", "detail": "voice_recording is required"}), 400

    memory_id = str(uuid.uuid4())

    try:
        # Upload voice file to Firebase Storage.
        # H-3: Use only the safe extension extracted from the original filename —
        # never embed the raw client-supplied filename in the storage path.
        voice_ext = _safe_ext(voice.filename or "", _ALLOWED_AUDIO_EXTS, ".mp3")
        voice_path = f"memories/{memory_id}/voice/recording{voice_ext}"
        voice.stream.seek(0)
        voice_url = firebase_service.upload_file_to_storage(
            file_obj=voice.stream,
            destination_path=voice_path,
            content_type=voice.content_type or "audio/mpeg",
        )
        logger.info("Voice uploaded to %s", voice_url)

        # Upload each photo and build the photo doc list
        photo_docs: List[dict] = []
        for idx, (photo, caption) in enumerate(zip(photos, captions)):
            photo_id = str(uuid.uuid4())
            photo_ext = _safe_ext(photo.filename or "", _ALLOWED_IMAGE_EXTS, ".jpg")
            photo_path = f"memories/{memory_id}/photos/{photo_id}{photo_ext}"
            photo.stream.seek(0)
            photo_url = firebase_service.upload_file_to_storage(
                file_obj=photo.stream,
                destination_path=photo_path,
                content_type=photo.content_type or "image/jpeg",
            )
            photo_docs.append(
                {
                    "photo_id": photo_id,
                    "url": photo_url,
                    "caption": caption.strip()[:_MAX_CAPTION_LEN],
                    "date": "",
                    "era": _infer_era(idx, len(photos)),
                }
            )

        # Persist to Firestore
        firebase_service.save_memory_to_firestore(
            memory_id=memory_id,
            person_name=person_name,
            voice_storage_path=voice_path,
            photo_docs=photo_docs,
        )

    except Exception as exc:  # noqa: BLE001
        # H-4: Log full detail server-side; return a generic message to clients
        # to avoid leaking internal paths, Firebase project names, or stack traces.
        logger.exception("Upload failed for memory %s", memory_id)
        return jsonify({"error": "server_error", "detail": "An internal error occurred. Please try again."}), 500

    # Queue async embedding job — runs in background thread, does NOT block response
    _queue_embedding_job(memory_id, photo_docs)

    return jsonify({"memory_id": memory_id, "status": "processing"}), 200


# ------------------------------------------------------------------ #
# Validation helpers                                                   #
# ------------------------------------------------------------------ #


def _validate_upload(
    photos: List[FileStorage],
    voice: FileStorage | None,
    captions: List[str],
    person_name: str,
) -> str | None:
    """Validate the upload request fields.

    Args:
        photos: List of photo FileStorage objects.
        voice: Voice recording FileStorage object, or None if missing.
        captions: List of caption strings.
        person_name: Name of the person.

    Returns:
        An error message string if validation fails, or None if all valid.
    """
    if not person_name:
        return "person_name is required"

    if len(person_name) > _MAX_PERSON_NAME_LEN:
        return f"person_name must be {_MAX_PERSON_NAME_LEN} characters or fewer"

    if not photos:
        return "At least one photo is required in photos[]"

    if not voice:
        return "voice_recording is required"

    if len(photos) > _MAX_PHOTOS:
        return f"Maximum {_MAX_PHOTOS} photos allowed; received {len(photos)}"

    if len(captions) != len(photos):
        return (
            f"captions[] length ({len(captions)}) must match "
            f"photos[] length ({len(photos)})"
        )

    for i, photo in enumerate(photos):
        err = _validate_image_file(photo, i)
        if err:
            return err

    voice_err = _validate_audio_file(voice)
    if voice_err:
        return voice_err

    return None


def _validate_image_file(photo: FileStorage, index: int) -> str | None:
    """Validate a single image file's MIME type, extension, and size.

    Args:
        photo: Werkzeug FileStorage object for the image.
        index: Zero-based position in the upload batch (for error messages).

    Returns:
        Error message string or None if valid.
    """
    filename = photo.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    # Check extension
    if ext not in _ALLOWED_IMAGE_EXTS:
        return (
            f"photos[{index}] has unsupported extension '{ext}'. "
            f"Allowed: {sorted(_ALLOWED_IMAGE_EXTS)}"
        )

    # Check MIME type (server-side — do not trust Content-Type header alone)
    content_type = (photo.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_IMAGE_MIMES:
        return (
            f"photos[{index}] has unsupported MIME type '{content_type}'. "
            f"Allowed: {sorted(_ALLOWED_IMAGE_MIMES)}"
        )

    # Check size by reading the stream length
    photo.stream.seek(0, 2)  # Seek to end
    size = photo.stream.tell()
    photo.stream.seek(0)  # Rewind for later use

    if size > _MAX_FILE_SIZE_BYTES:
        mb = size / (1024 * 1024)
        return (
            f"photos[{index}] is {mb:.1f} MB; maximum allowed is "
            f"{_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB"
        )

    if size == 0:
        return f"photos[{index}] is empty"

    return None


def _validate_audio_file(voice: FileStorage) -> str | None:
    """Validate the voice recording file.

    Args:
        voice: Werkzeug FileStorage object for the audio file.

    Returns:
        Error message string or None if valid.
    """
    filename = voice.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if ext not in _ALLOWED_AUDIO_EXTS:
        return (
            f"voice_recording has unsupported extension '{ext}'. "
            f"Allowed: {sorted(_ALLOWED_AUDIO_EXTS)}"
        )

    content_type = (voice.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_AUDIO_MIMES:
        return (
            f"voice_recording has unsupported MIME type '{content_type}'. "
            f"Allowed: {sorted(_ALLOWED_AUDIO_MIMES)}"
        )

    voice.stream.seek(0, 2)
    size = voice.stream.tell()
    voice.stream.seek(0)

    if size == 0:
        return "voice_recording is empty"

    if size > _MAX_FILE_SIZE_BYTES:
        mb = size / (1024 * 1024)
        return (
            f"voice_recording is {mb:.1f} MB; maximum allowed is "
            f"{_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB"
        )

    return None


# ------------------------------------------------------------------ #
# Async embedding trigger                                              #
# ------------------------------------------------------------------ #


def _queue_embedding_job(memory_id: str, photo_docs: List[dict]) -> None:
    """Spawn a background thread to generate embeddings without blocking the response.

    The thread fetches photo bytes from Firebase Storage, calls the AMD embedding
    service, and writes results back to Firestore. On any failure it logs the
    error rather than crashing the app.

    Args:
        memory_id: UUID of the memory document.
        photo_docs: List of photo metadata dicts (must include 'url' and 'photo_id').
    """
    def _worker() -> None:
        import asyncio

        logger.info(
            "Background embedding job started for memory %s (%d photos).",
            memory_id,
            len(photo_docs),
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_embeddings(memory_id, photo_docs))
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Background embedding job failed for memory %s: %s", memory_id, exc
            )
        finally:
            loop.close()

    thread = threading.Thread(target=_worker, daemon=True, name=f"embed-{memory_id[:8]}")
    thread.start()
    logger.info("Queued background embedding thread for memory %s.", memory_id)


async def _run_embeddings(memory_id: str, photo_docs: List[dict]) -> None:
    """Async implementation: download images and compute embeddings via AMD service.

    Args:
        memory_id: Parent memory UUID.
        photo_docs: List of photo dicts with 'url', 'photo_id', 'caption' fields.
    """
    import httpx

    from ..services.amd_service import generate_embedding

    failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for photo in photo_docs:
            photo_id: str = photo["photo_id"]
            url: str = photo["url"]
            caption: str = photo.get("caption", "")

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
                    "Embedded photo %s for memory %s.", photo_id, memory_id
                )

            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.error(
                    "Failed to embed photo %s for memory %s: %s",
                    photo_id,
                    memory_id,
                    exc,
                )

    # C2: Only mark "ready" when all embeddings succeeded; use "error" on partial/full failure.
    final_status = "ready" if failed == 0 else "error"
    firebase_service.update_memory_status(memory_id, final_status)
    logger.info(
        "Memory %s embedding job complete — %d failed — status set to '%s'.",
        memory_id, failed, final_status,
    )


# ------------------------------------------------------------------ #
# Utility                                                              #
# ------------------------------------------------------------------ #


def _infer_era(index: int, total: int) -> str:
    """Assign a life-era label based on photo position in the upload batch.

    Photos are assumed to be roughly chronological. Divides the batch
    into four equal quarters and labels accordingly.

    Args:
        index: Zero-based index of this photo in the batch.
        total: Total number of photos in the batch.

    Returns:
        One of: 'childhood', 'young-adult', 'family', 'recent'.
    """
    if total <= 1:
        return "recent"
    quarter = total / 4
    if index < quarter:
        return "childhood"
    if index < quarter * 2:
        return "young-adult"
    if index < quarter * 3:
        return "family"
    return "recent"


def _safe_ext(filename: str, allowed_exts: frozenset[str], default: str) -> str:
    """Extract and validate a file extension from a client-supplied filename.

    Returns only the extension (e.g. '.jpg') so the original filename is never
    embedded in a Storage path — preventing path traversal via crafted filenames.

    Args:
        filename: Original filename from the HTTP multipart header.
        allowed_exts: Set of permitted extensions (e.g. {'.jpg', '.jpeg', ...}).
        default: Extension to return if the filename has none or an unknown one.

    Returns:
        Validated lowercase extension string, or ``default`` as a safe fallback.
    """
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
        if ext in allowed_exts:
            return ext
    return default
