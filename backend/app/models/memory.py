"""MemoryBridge domain models.

All dataclasses are frozen (immutable) as per coding-style guidelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class PhotoMeta:
    """Metadata for a single uploaded photo.

    Attributes:
        photo_id: Unique identifier for this photo document.
        url: Firebase Storage public download URL.
        caption: User-provided caption for this photo.
        date: Date string in YYYY or YYYY-MM-DD format.
        era: Life-era category for the photo.
        embedding: Optional 1024-dimensional embedding vector.
    """

    photo_id: str
    url: str
    caption: str
    date: str
    era: str
    embedding: Optional[List[float]] = None


@dataclass(frozen=True)
class Memory:
    """A complete memory record for a person.

    Attributes:
        id: Unique memory document ID (UUID).
        person_name: Name of the person this memory belongs to.
        created_at: ISO 8601 creation timestamp string.
        status: Processing status — 'processing' or 'ready'.
        voice_id: ElevenLabs voice clone ID, once created.
        photos: List of photo metadata documents.
        embedding_ready: Whether all photo embeddings have been generated.
    """

    id: str
    person_name: str
    created_at: str
    status: str
    voice_id: Optional[str] = None
    photos: List[PhotoMeta] = field(default_factory=list)
    embedding_ready: bool = False

    def to_dict(self) -> dict:
        """Serialize this Memory to a JSON-serialisable dictionary."""
        return {
            "id": self.id,
            "person_name": self.person_name,
            "created_at": self.created_at,
            "status": self.status,
            "voice_id": self.voice_id,
            "embedding_ready": self.embedding_ready,
            "photos": [
                {
                    "photo_id": p.photo_id,
                    "url": p.url,
                    "caption": p.caption,
                    "date": p.date,
                    "era": p.era,
                    "embedding": p.embedding,
                }
                for p in self.photos
            ],
        }


@dataclass(frozen=True)
class UploadRequest:
    """Validated data extracted from a multipart upload request.

    Attributes:
        person_name: Name of the person.
        captions: List of captions, parallel to photo_files.
        photo_filenames: Original filenames of the uploaded photos.
        voice_filename: Original filename of the voice recording.
    """

    person_name: str
    captions: List[str]
    photo_filenames: List[str]
    voice_filename: str
