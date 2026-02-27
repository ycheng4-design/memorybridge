"""Firebase Admin SDK service layer.

Handles Firebase Storage uploads and Firestore read/write operations.
Guards against the 'App already exists' error so the module is safe
to import in test environments that call create_app() multiple times.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import IO, List, Optional

import firebase_admin
from firebase_admin import credentials, firestore, storage

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Lazy initialisation — safe for repeated imports and test fixtures   #
# ------------------------------------------------------------------ #

_firebase_app: Optional[firebase_admin.App] = None


def _get_firebase_app() -> firebase_admin.App:
    """Return the initialised Firebase app, creating it if necessary.

    Guards against the 'ValueError: The default Firebase app already exists'
    error that occurs when create_app() is called more than once (e.g. in tests).

    Returns:
        The singleton Firebase Admin App instance.

    Raises:
        KeyError: If required environment variables are not set.
    """
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    # Check if a default app is already registered (e.g. by a previous test run)
    try:
        _firebase_app = firebase_admin.get_app()
        logger.debug("Reusing existing Firebase default app.")
        return _firebase_app
    except ValueError:
        pass  # No app registered yet — fall through to initialise

    service_account_path = os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"]
    storage_bucket = os.environ["FIREBASE_STORAGE_BUCKET"]

    cred = credentials.Certificate(service_account_path)
    _firebase_app = firebase_admin.initialize_app(
        cred,
        {"storageBucket": storage_bucket},
    )
    logger.info("Firebase Admin SDK initialised.")
    return _firebase_app


def _db() -> firestore.Client:
    """Return a Firestore client bound to the initialised app."""
    _get_firebase_app()
    return firestore.client()


def _bucket() -> storage.Bucket:
    """Return the default Storage bucket bound to the initialised app."""
    _get_firebase_app()
    return storage.bucket()


# ------------------------------------------------------------------ #
# Storage helpers                                                      #
# ------------------------------------------------------------------ #

_SIGNED_URL_EXPIRY_HOURS: int = 24


def upload_file_to_storage(
    file_obj: IO[bytes],
    destination_path: str,
    content_type: str,
) -> str:
    """Upload a binary file-like object to Firebase Storage.

    Returns a signed URL valid for 24 hours.

    Args:
        file_obj: A readable binary stream (e.g. Werkzeug FileStorage).
        destination_path: Path within the bucket, e.g. 'memories/{id}/photo.jpg'.
        content_type: MIME type of the file.

    Returns:
        Signed download URL (24 h).

    Raises:
        Exception: If signed URL generation fails (e.g. missing IAM permissions).
    """
    bucket = _bucket()
    blob = bucket.blob(destination_path)
    blob.upload_from_file(file_obj, content_type=content_type)

    try:
        url = blob.generate_signed_url(
            expiration=timedelta(hours=_SIGNED_URL_EXPIRY_HOURS),
            method="GET",
            version="v4",
        )
        logger.info("Uploaded file to Storage (signed URL): %s", destination_path)
        return url
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Could not generate signed URL for %s: %s. "
            "Ensure the service account has roles/iam.serviceAccountTokenCreator.",
            destination_path,
            exc,
        )
        raise


# ------------------------------------------------------------------ #
# Firestore helpers                                                    #
# ------------------------------------------------------------------ #

def save_memory_to_firestore(
    memory_id: str,
    person_name: str,
    voice_storage_path: str,
    photo_docs: List[dict],
) -> None:
    """Persist a new memory document and its photos subcollection.

    Args:
        memory_id: UUID string for the memory document.
        person_name: Display name of the person.
        voice_storage_path: Storage path of the uploaded voice file.
        photo_docs: List of dicts, each containing photo metadata.
    """
    db = _db()
    now = datetime.now(timezone.utc)

    memory_ref = db.collection("memories").document(memory_id)
    memory_ref.set(
        {
            "person_name": person_name,
            "created_at": now,
            "status": "processing",
            "voice_id": None,
            "kb_id": None,
            "agent_id": None,
            "voice_storage_path": voice_storage_path,
        }
    )

    photos_ref = memory_ref.collection("photos")
    for photo in photo_docs:
        photo_id = photo.get("photo_id", str(uuid.uuid4()))
        photos_ref.document(photo_id).set(
            {
                "url": photo["url"],
                "storage_path": photo.get("storage_path", ""),
                "caption": photo["caption"],
                "date": photo.get("date", ""),
                "era": photo.get("era", "recent"),
                "embedding": None,
            }
        )

    logger.info("Saved memory %s to Firestore with %d photos.", memory_id, len(photo_docs))


def get_memory_from_firestore(memory_id: str) -> Optional[dict]:
    """Retrieve a memory document with its photos subcollection.

    Args:
        memory_id: UUID string of the memory to retrieve.

    Returns:
        A dict with memory fields and a 'photos' list, or None if not found.
    """
    db = _db()
    memory_ref = db.collection("memories").document(memory_id)
    snap = memory_ref.get()

    if not snap.exists:
        logger.warning("Memory %s not found in Firestore.", memory_id)
        return None

    data = snap.to_dict()
    photos = get_all_photos_for_memory(memory_id)

    all_embedded = bool(photos) and all(p.get("embedding") is not None for p in photos)

    return {
        "id": memory_id,
        "person_name": data.get("person_name", ""),
        "created_at": data.get("created_at").isoformat() if data.get("created_at") else "",
        "status": data.get("status", "processing"),
        "voice_id": data.get("voice_id"),
        "agent_id": data.get("agent_id"),
        "embedding_ready": all_embedded,
        "photos": photos,
    }


def get_all_photos_for_memory(memory_id: str) -> List[dict]:
    """Retrieve all photo documents from the photos subcollection.

    Args:
        memory_id: Parent memory document UUID.

    Returns:
        List of photo dicts with fields: photo_id, url, caption, date, era, embedding.
    """
    db = _db()
    photos_ref = (
        db.collection("memories").document(memory_id).collection("photos")
    )
    docs = photos_ref.stream()

    result: List[dict] = []
    for doc in docs:
        photo_data = doc.to_dict()
        url = photo_data.get("url", "")
        result.append(
            {
                # id is the canonical field name for frontend (PhotoMeta.id)
                "id": doc.id,
                # photo_id kept for backward compatibility
                "photo_id": doc.id,
                "url": url,
                # storagePath = signed URL for direct browser access
                "storagePath": url,
                # storage_path = raw bucket path for future re-signing
                "storage_path": photo_data.get("storage_path", ""),
                "caption": photo_data.get("caption", ""),
                "date": photo_data.get("date", ""),
                "era": photo_data.get("era", "recent"),
                # uploadedAt not stored separately; use empty string
                "uploadedAt": "",
                "embedding": photo_data.get("embedding"),
            }
        )

    return result


def update_photo_embedding(
    memory_id: str,
    photo_id: str,
    embedding: List[float],
) -> None:
    """Write an embedding vector to a specific photo document.

    Args:
        memory_id: Parent memory document UUID.
        photo_id: Photo document ID within the subcollection.
        embedding: 384-dimensional float vector.
    """
    db = _db()
    photo_ref = (
        db.collection("memories")
        .document(memory_id)
        .collection("photos")
        .document(photo_id)
    )
    photo_ref.update({"embedding": embedding})
    logger.debug("Updated embedding for photo %s in memory %s.", photo_id, memory_id)


def update_memory_status(memory_id: str, status: str) -> None:
    """Update the status field on a memory document.

    Args:
        memory_id: UUID of the memory document.
        status: New status string — 'processing' or 'ready'.
    """
    db = _db()
    db.collection("memories").document(memory_id).update({"status": status})
    logger.info("Memory %s status set to '%s'.", memory_id, status)


def update_memory_voice_id(memory_id: str, voice_id: str) -> None:
    """Persist an ElevenLabs voice_id onto the memory document.

    Args:
        memory_id: UUID of the memory document.
        voice_id: ElevenLabs voice clone identifier.
    """
    db = _db()
    db.collection("memories").document(memory_id).update({"voice_id": voice_id})
    logger.info("Memory %s voice_id set to '%s'.", memory_id, voice_id)


def update_memory_agent_id(memory_id: str, agent_id: str) -> None:
    """Persist an ElevenLabs agent_id onto the memory document.

    Args:
        memory_id: UUID of the memory document.
        agent_id: ElevenLabs conversational agent identifier.
    """
    db = _db()
    db.collection("memories").document(memory_id).update({"agent_id": agent_id})
    logger.info("Memory %s agent_id set to '%s'.", memory_id, agent_id)


def update_memory_kb_id(memory_id: str, kb_id: str) -> None:
    """Persist an ElevenLabs knowledge base ID onto the memory document.

    Args:
        memory_id: UUID of the memory document.
        kb_id: ElevenLabs knowledge base document identifier.
    """
    db = _db()
    db.collection("memories").document(memory_id).update({"kb_id": kb_id})
    logger.info("Memory %s kb_id set to '%s'.", memory_id, kb_id)


def list_memories_from_firestore(limit: int = 20, offset: int = 0) -> List[dict]:
    """Return a paginated list of memory documents (without photo embeddings).

    Ordered by created_at descending so newest memories appear first.

    Args:
        limit: Maximum number of documents to return (1–100).
        offset: Number of documents to skip.

    Returns:
        List of lightweight memory summary dicts (no photos subcollection).
    """
    db = _db()
    query = (
        db.collection("memories")
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit + offset)
    )
    docs = list(query.stream())
    paged_docs = docs[offset:]

    results: List[dict] = []
    for doc in paged_docs:
        data = doc.to_dict()
        created_at = data.get("created_at")
        results.append(
            {
                "id": doc.id,
                "person_name": data.get("person_name", ""),
                "created_at": created_at.isoformat() if created_at else "",
                "status": data.get("status", "processing"),
                "voice_id": data.get("voice_id"),
                "embedding_ready": False,  # lightweight list — no subcollection query
            }
        )

    return results
