"""Unit tests for GET /api/memories/:id and GET /api/memories routes.

Tests cover:
    - Existing memory returns 200 with full structure
    - Non-existent memory returns 404
    - Firestore service error returns 500
    - embedding_ready flag reflects photo embedding state
    - GET /api/memories list returns 200 with memories array
    - Invalid pagination params return 400
"""

from __future__ import annotations

import uuid
from unittest.mock import patch


# ------------------------------------------------------------------ #
# GET /api/memories/:id                                                 #
# ------------------------------------------------------------------ #


def test_get_memory_returns_200(client, mock_firebase) -> None:
    """An existing memory must return 200 with correct JSON structure."""
    memory_id = str(uuid.uuid4())
    expected = {
        "id": memory_id,
        "person_name": "Margaret Chen",
        "created_at": "2026-02-22T10:00:00+00:00",
        "status": "ready",
        "voice_id": "el_voice_abc123",
        "embedding_ready": True,
        "photos": [
            {
                "photo_id": str(uuid.uuid4()),
                "url": "https://storage.test/photo.jpg",
                "caption": "Family reunion 1985",
                "date": "1985",
                "era": "family",
                "embedding": [0.1] * 1024,
            }
        ],
    }
    mock_firebase.get_memory_from_firestore.return_value = expected

    response = client.get(f"/api/memories/{memory_id}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == expected["id"]
    assert body["person_name"] == "Margaret Chen"
    assert body["status"] == "ready"
    assert body["voice_id"] == "el_voice_abc123"
    assert body["embedding_ready"] is True
    assert len(body["photos"]) == 1
    assert len(body["photos"][0]["embedding"]) == 1024


def test_get_memory_not_found_returns_404(client, mock_firebase) -> None:
    """A non-existent memory must return 404 with not_found error."""
    mock_firebase.get_memory_from_firestore.return_value = None

    response = client.get(f"/api/memories/{uuid.uuid4()}")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"] == "not_found"
    assert "detail" in body


def test_get_memory_firestore_error_returns_500(client, mock_firebase) -> None:
    """A Firestore service exception must return 500 with server_error."""
    mock_firebase.get_memory_from_firestore.side_effect = Exception("Firestore unavailable")

    response = client.get(f"/api/memories/{uuid.uuid4()}")

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "server_error"
    # Detail must be a generic client-safe message — internal errors must not be leaked.
    assert "detail" in body
    assert "Firestore unavailable" not in body["detail"]


def test_get_memory_embedding_not_ready(client, mock_firebase) -> None:
    """Memory with photos lacking embeddings must have embedding_ready=False."""
    memory_id = str(uuid.uuid4())
    mock_firebase.get_memory_from_firestore.return_value = {
        "id": memory_id,
        "person_name": "John",
        "created_at": "2026-02-22T10:00:00+00:00",
        "status": "processing",
        "voice_id": None,
        "embedding_ready": False,
        "photos": [
            {
                "photo_id": str(uuid.uuid4()),
                "url": "https://storage.test/photo.jpg",
                "caption": "Old photo",
                "date": "1970",
                "era": "childhood",
                "embedding": None,  # not yet computed
            }
        ],
    }

    response = client.get(f"/api/memories/{memory_id}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["embedding_ready"] is False
    assert body["photos"][0]["embedding"] is None


def test_get_memory_no_photos(client, mock_firebase) -> None:
    """Memory with no photos must return 200 with empty photos list."""
    memory_id = str(uuid.uuid4())
    mock_firebase.get_memory_from_firestore.return_value = {
        "id": memory_id,
        "person_name": "Alice",
        "created_at": "2026-02-22T10:00:00+00:00",
        "status": "processing",
        "voice_id": None,
        "embedding_ready": False,
        "photos": [],
    }

    response = client.get(f"/api/memories/{memory_id}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["photos"] == []


# ------------------------------------------------------------------ #
# GET /api/memories (list)                                              #
# ------------------------------------------------------------------ #


def test_list_memories_returns_200(client, mock_firebase) -> None:
    """GET /api/memories must return 200 with a memories array and total count."""
    response = client.get("/api/memories")

    assert response.status_code == 200
    body = response.get_json()
    assert "memories" in body
    assert "total" in body
    assert isinstance(body["memories"], list)
    assert body["total"] == len(body["memories"])


def test_list_memories_default_limit(client, mock_firebase) -> None:
    """GET /api/memories without params must call list_memories with default limit=20."""
    client.get("/api/memories")
    mock_firebase.list_memories_from_firestore.assert_called_once_with(
        limit=20, offset=0
    )


def test_list_memories_custom_pagination(client, mock_firebase) -> None:
    """GET /api/memories?limit=5&offset=10 must pass correct args to service."""
    client.get("/api/memories?limit=5&offset=10")
    mock_firebase.list_memories_from_firestore.assert_called_once_with(
        limit=5, offset=10
    )


def test_list_memories_limit_clamp(client, mock_firebase) -> None:
    """GET /api/memories?limit=9999 must clamp to maximum of 100."""
    client.get("/api/memories?limit=9999")
    call_kwargs = mock_firebase.list_memories_from_firestore.call_args.kwargs
    assert call_kwargs["limit"] <= 100


def test_list_memories_invalid_limit_returns_400(client, mock_firebase) -> None:
    """Non-integer limit param must return 400 validation error."""
    response = client.get("/api/memories?limit=abc")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"


def test_list_memories_service_error_returns_500(client, mock_firebase) -> None:
    """Firestore list service exception must return 500."""
    mock_firebase.list_memories_from_firestore.side_effect = Exception("DB down")
    response = client.get("/api/memories")
    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "server_error"
