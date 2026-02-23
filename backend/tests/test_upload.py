"""Unit tests for the POST /api/upload route.

Tests cover:
    - Successful upload returns memory_id and 'processing' status
    - Missing photos[] returns 400
    - Missing voice_recording returns 400
    - Mismatched captions[] length returns 400
    - Missing person_name returns 400
    - Too many photos returns 400
    - Unsupported image MIME type returns 400
    - Unsupported audio extension returns 400
    - Empty file returns 400
    - GET /api/health returns 200
"""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def _make_upload(
    client,
    photos: list[tuple[bytes, str, str]] | None = None,
    voice: tuple[bytes, str, str] | None = None,
    captions: list[str] | None = None,
    person_name: str = "Margaret Chen",
):
    """Send a multipart POST to /api/upload and return the response.

    Args:
        client: Flask test client.
        photos: List of (bytes, filename, content_type) tuples.
        voice: (bytes, filename, content_type) tuple.
        captions: List of caption strings (parallel to photos).
        person_name: Name of the person.

    Returns:
        Flask test Response object.
    """
    data: dict = {"person_name": person_name}

    if photos is not None:
        photo_files = [
            (io.BytesIO(b), name, ct) for b, name, ct in photos
        ]
        data["photos[]"] = [(buf, fname) for buf, fname, _ in photo_files]
        # Werkzeug test client supports content_type per file via tuple (buf, fname, mime)
        data["photos[]"] = [
            (io.BytesIO(b), name, ct) for b, name, ct in photos
        ]

    if voice is not None:
        vbytes, vname, vct = voice
        data["voice_recording"] = (io.BytesIO(vbytes), vname, vct)

    if captions is not None:
        data["captions[]"] = captions

    return client.post(
        "/api/upload",
        data=data,
        content_type="multipart/form-data",
    )


# ------------------------------------------------------------------ #
# Health check                                                          #
# ------------------------------------------------------------------ #


def test_health_check_returns_200(client) -> None:
    """GET /api/health must return 200 with status ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"


# ------------------------------------------------------------------ #
# Successful upload                                                     #
# ------------------------------------------------------------------ #


def test_upload_success(client, sample_jpeg: bytes, sample_wav: bytes, mock_firebase) -> None:
    """A valid upload with one photo must return 200 with memory_id and processing status."""
    with patch("app.routes.upload._queue_embedding_job"):  # prevent background thread
        response = _make_upload(
            client,
            photos=[(sample_jpeg, "photo1.jpg", "image/jpeg")],
            voice=(sample_wav, "voice.wav", "audio/wav"),
            captions=["Grandma at the beach"],
        )

    assert response.status_code == 200
    body = response.get_json()
    assert "memory_id" in body
    assert body["status"] == "processing"
    assert len(body["memory_id"]) == 36  # UUID format

    # Verify Firebase service was called
    mock_firebase.save_memory_to_firestore.assert_called_once()
    assert mock_firebase.upload_file_to_storage.call_count == 2  # voice + 1 photo


def test_upload_multiple_photos(
    client, sample_jpeg: bytes, sample_png: bytes, sample_wav: bytes, mock_firebase
) -> None:
    """Upload with multiple photos must include all photos in save_memory call."""
    with patch("app.routes.upload._queue_embedding_job"):
        response = _make_upload(
            client,
            photos=[
                (sample_jpeg, "photo1.jpg", "image/jpeg"),
                (sample_png, "photo2.png", "image/png"),
                (sample_jpeg, "photo3.jpg", "image/jpeg"),
            ],
            voice=(sample_wav, "voice.wav", "audio/wav"),
            captions=["Caption 1", "Caption 2", "Caption 3"],
            person_name="John Doe",
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "processing"
    # 1 voice + 3 photos = 4 storage uploads
    assert mock_firebase.upload_file_to_storage.call_count == 4


# ------------------------------------------------------------------ #
# Validation failures — photos                                          #
# ------------------------------------------------------------------ #


def test_upload_missing_photos_returns_400(
    client, sample_wav: bytes
) -> None:
    """Missing photos[] must return 400 with validation_failed error."""
    response = _make_upload(
        client,
        photos=None,
        voice=(sample_wav, "voice.wav", "audio/wav"),
        captions=[],
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "photo" in body["detail"].lower()


def test_upload_empty_photos_list_returns_400(
    client, sample_wav: bytes
) -> None:
    """Empty photos[] list must return 400."""
    response = _make_upload(
        client,
        photos=[],
        voice=(sample_wav, "voice.wav", "audio/wav"),
        captions=[],
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"


def test_upload_too_many_photos_returns_400(
    client, sample_jpeg: bytes, sample_wav: bytes
) -> None:
    """More than MAX_PHOTOS (30) photos must return 400."""
    photos = [(sample_jpeg, f"photo{i}.jpg", "image/jpeg") for i in range(31)]
    captions = [f"Caption {i}" for i in range(31)]
    response = _make_upload(
        client,
        photos=photos,
        voice=(sample_wav, "voice.wav", "audio/wav"),
        captions=captions,
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "31" in body["detail"] or "maximum" in body["detail"].lower()


def test_upload_mismatched_captions_returns_400(
    client, sample_jpeg: bytes, sample_wav: bytes
) -> None:
    """captions[] length not matching photos[] must return 400."""
    response = _make_upload(
        client,
        photos=[(sample_jpeg, "photo1.jpg", "image/jpeg")],
        voice=(sample_wav, "voice.wav", "audio/wav"),
        captions=["Cap1", "Cap2"],  # 2 captions for 1 photo
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "captions" in body["detail"].lower()


def test_upload_unsupported_image_extension_returns_400(
    client, sample_wav: bytes
) -> None:
    """A .gif image file must be rejected with 400."""
    gif_bytes = b"GIF89a" + b"\x00" * 10
    response = _make_upload(
        client,
        photos=[(gif_bytes, "photo.gif", "image/gif")],
        voice=(sample_wav, "voice.wav", "audio/wav"),
        captions=["Some caption"],
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert ".gif" in body["detail"]


def test_upload_empty_image_returns_400(
    client, sample_wav: bytes
) -> None:
    """A zero-byte image file must be rejected with 400."""
    response = _make_upload(
        client,
        photos=[(b"", "photo.jpg", "image/jpeg")],
        voice=(sample_wav, "voice.wav", "audio/wav"),
        captions=["Some caption"],
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "empty" in body["detail"].lower()


# ------------------------------------------------------------------ #
# Validation failures — voice                                           #
# ------------------------------------------------------------------ #


def test_upload_missing_voice_returns_400(
    client, sample_jpeg: bytes
) -> None:
    """Missing voice_recording must return 400."""
    response = _make_upload(
        client,
        photos=[(sample_jpeg, "photo1.jpg", "image/jpeg")],
        voice=None,
        captions=["Caption"],
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "voice" in body["detail"].lower()


def test_upload_unsupported_audio_extension_returns_400(
    client, sample_jpeg: bytes
) -> None:
    """An .aac audio file must be rejected with 400."""
    aac_bytes = b"\xff\xf1" + b"\x00" * 100  # fake AAC
    response = _make_upload(
        client,
        photos=[(sample_jpeg, "photo1.jpg", "image/jpeg")],
        voice=(aac_bytes, "voice.aac", "audio/aac"),
        captions=["Caption"],
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert ".aac" in body["detail"]


def test_upload_empty_voice_returns_400(
    client, sample_jpeg: bytes
) -> None:
    """A zero-byte voice file must be rejected with 400."""
    response = _make_upload(
        client,
        photos=[(sample_jpeg, "photo1.jpg", "image/jpeg")],
        voice=(b"", "voice.wav", "audio/wav"),
        captions=["Caption"],
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "empty" in body["detail"].lower()


# ------------------------------------------------------------------ #
# Validation failures — person_name                                     #
# ------------------------------------------------------------------ #


def test_upload_missing_person_name_returns_400(
    client, sample_jpeg: bytes, sample_wav: bytes
) -> None:
    """Missing person_name must return 400."""
    response = _make_upload(
        client,
        photos=[(sample_jpeg, "photo1.jpg", "image/jpeg")],
        voice=(sample_wav, "voice.wav", "audio/wav"),
        captions=["Caption"],
        person_name="",  # empty
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "person_name" in body["detail"].lower()


# ------------------------------------------------------------------ #
# Era inference helper                                                  #
# ------------------------------------------------------------------ #


def test_infer_era_quarters() -> None:
    """_infer_era must divide photos into four era labels by position."""
    from app.routes.upload import _infer_era

    total = 8
    labels = [_infer_era(i, total) for i in range(total)]
    assert labels[0] == "childhood"
    assert labels[1] == "childhood"
    assert labels[2] == "young-adult"
    assert labels[3] == "young-adult"
    assert labels[4] == "family"
    assert labels[5] == "family"
    assert labels[6] == "recent"
    assert labels[7] == "recent"


def test_infer_era_single_photo() -> None:
    """A single photo must be labelled 'recent'."""
    from app.routes.upload import _infer_era

    assert _infer_era(0, 1) == "recent"


def test_infer_era_zero_total() -> None:
    """Zero-photo edge case must not raise and must return 'recent'."""
    from app.routes.upload import _infer_era

    assert _infer_era(0, 0) == "recent"
