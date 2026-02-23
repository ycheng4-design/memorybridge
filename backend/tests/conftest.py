"""Pytest configuration and shared fixtures for the MemoryBridge backend test suite.

Fixtures provided:
    app            — Flask test application (Firebase mocked)
    client         — Flask test client
    sample_jpeg    — Minimal valid JPEG bytes
    sample_png     — Minimal valid PNG bytes
    sample_wav     — Minimal valid WAV bytes
    mock_firebase  — Auto-used fixture that stubs out all Firebase calls
"""

from __future__ import annotations

import io
import os
import struct
import uuid
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# ------------------------------------------------------------------ #
# Environment setup — must run before app import                       #
# ------------------------------------------------------------------ #

os.environ.setdefault("FIREBASE_SERVICE_ACCOUNT_PATH", "./serviceAccount.json")
os.environ.setdefault("FIREBASE_STORAGE_BUCKET", "test-bucket.appspot.com")
os.environ.setdefault("ELEVENLABS_API_KEY", "test-elevenlabs-key")
os.environ.setdefault("AMD_API_KEY", "test-amd-key")
os.environ.setdefault("AMD_ENDPOINT", "https://api.amd.test/v1")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-for-ci")


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #


@pytest.fixture(scope="session")
def sample_jpeg() -> bytes:
    """Return a minimal valid JPEG file as bytes (1x1 white pixel).

    Uses a hardcoded minimal JPEG binary so tests have no file-system
    dependency and remain fast.

    Returns:
        Valid JPEG bytes.
    """
    # Minimal 1x1 white JPEG
    return bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
        b"hj}~\x82\x88\x9a\xa4\xb5\xb5\xb5\xff\xc0\x00\x0b\x08\x00\x01"
        b"\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01"
        b"\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02"
        b"\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02"
        b"\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02"
        b"\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1"
        b"\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a"
        b"%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz"
        b"\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98"
        b"\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5"
        b"\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2"
        b"\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7"
        b"\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda"
        b"\x00\x08\x01\x01\x00\x00?\x00\xfb\xff\xd9"
    )


@pytest.fixture(scope="session")
def sample_png() -> bytes:
    """Return a minimal valid 1x1 red-pixel PNG as bytes.

    Constructed programmatically to avoid file-system dependencies.

    Returns:
        Valid PNG bytes.
    """
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    # 1x1 red pixel: filter byte 0x00, then R=255, G=0, B=0
    raw_data = b"\x00\xff\x00\x00"
    compressed = zlib.compress(raw_data)
    idat = _chunk(b"IDAT", compressed)
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


@pytest.fixture(scope="session")
def sample_wav() -> bytes:
    """Return a minimal valid WAV file as bytes (44-byte header, 1 sample of silence).

    Returns:
        Valid WAV bytes (PCM 16-bit, mono, 44100 Hz).
    """
    sample_rate = 44100
    num_channels = 1
    bits_per_sample = 16
    num_samples = 1
    data_size = num_samples * num_channels * (bits_per_sample // 8)
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,        # subchunk1 size
        1,         # PCM format
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    audio_data = b"\x00\x00" * num_samples  # silence
    return header + audio_data


@pytest.fixture(scope="session")
def sample_mp3() -> bytes:
    """Return minimal MP3-like bytes (not a playable file, but passes extension check).

    Returns:
        Bytes that look like an MP3 to extension and size checks.
    """
    # ID3 header + minimal frame — sufficient for upload validation tests
    return b"ID3" + b"\x00" * 7 + b"\xff\xfb\x90\x00" + b"\x00" * 200


@pytest.fixture
def mock_firebase() -> Generator[MagicMock, None, None]:
    """Stub out Firebase Admin SDK initialisation and all service calls.

    Patches:
        firebase_admin.initialize_app
        firebase_admin.get_app
        firebase_service._get_firebase_app
        firebase_service.upload_file_to_storage
        firebase_service.save_memory_to_firestore
        firebase_service.get_memory_from_firestore
        firebase_service.get_all_photos_for_memory
        firebase_service.update_photo_embedding
        firebase_service.update_memory_status
        firebase_service.update_memory_voice_id
        firebase_service.list_memories_from_firestore

    Yields:
        A MagicMock that can be inspected in tests.
    """
    mock = MagicMock()

    # Provide sane default return values
    mock.upload_file_to_storage.return_value = "https://storage.test/photo.jpg"
    mock.save_memory_to_firestore.return_value = None
    mock.get_memory_from_firestore.return_value = _default_memory_doc()
    mock.get_all_photos_for_memory.return_value = _default_photos()
    mock.update_photo_embedding.return_value = None
    mock.update_memory_status.return_value = None
    mock.update_memory_voice_id.return_value = None
    mock.list_memories_from_firestore.return_value = [_default_memory_doc()]

    with (
        patch("firebase_admin.initialize_app", return_value=MagicMock()),
        patch("firebase_admin.get_app", side_effect=ValueError("no app")),
        patch(
            "app.services.firebase_service._get_firebase_app",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.firebase_service.upload_file_to_storage",
            side_effect=mock.upload_file_to_storage,
        ),
        patch(
            "app.services.firebase_service.save_memory_to_firestore",
            side_effect=mock.save_memory_to_firestore,
        ),
        patch(
            "app.services.firebase_service.get_memory_from_firestore",
            side_effect=mock.get_memory_from_firestore,
        ),
        patch(
            "app.services.firebase_service.get_all_photos_for_memory",
            side_effect=mock.get_all_photos_for_memory,
        ),
        patch(
            "app.services.firebase_service.update_photo_embedding",
            side_effect=mock.update_photo_embedding,
        ),
        patch(
            "app.services.firebase_service.update_memory_status",
            side_effect=mock.update_memory_status,
        ),
        patch(
            "app.services.firebase_service.update_memory_voice_id",
            side_effect=mock.update_memory_voice_id,
        ),
        patch(
            "app.services.firebase_service.list_memories_from_firestore",
            side_effect=mock.list_memories_from_firestore,
        ),
    ):
        yield mock


@pytest.fixture
def app(mock_firebase: MagicMock):
    """Create a Flask test application with Firebase fully mocked.

    Args:
        mock_firebase: Auto-injected Firebase mock fixture.

    Returns:
        Configured Flask app in testing mode.
    """
    from app import create_app

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture
def client(app):
    """Return a Flask test client.

    Args:
        app: Flask application fixture.

    Returns:
        Flask test client instance.
    """
    return app.test_client()


# ------------------------------------------------------------------ #
# Helper builders                                                      #
# ------------------------------------------------------------------ #


def _default_memory_doc() -> dict:
    """Return a realistic memory document dict for use in mock defaults."""
    return {
        "id": str(uuid.uuid4()),
        "person_name": "Margaret Chen",
        "created_at": "2026-02-22T10:00:00+00:00",
        "status": "processing",
        "voice_id": None,
        "embedding_ready": False,
        "photos": _default_photos(),
    }


def _default_photos() -> list[dict]:
    """Return a list of photo dicts for use in mock defaults."""
    return [
        {
            "photo_id": str(uuid.uuid4()),
            "url": "https://storage.test/photo_0.jpg",
            "caption": "At the beach, 1965",
            "date": "1965",
            "era": "childhood",
            "embedding": None,
        }
    ]
