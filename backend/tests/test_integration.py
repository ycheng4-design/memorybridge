"""Integration tests for the MemoryBridge backend.

These tests exercise the full request-response cycle with all external services
stubbed at the service layer. They verify that:

    T1  Upload pipeline — POST /api/upload creates memory in Firestore and Storage
    T2  AMD embedding pipeline — POST /api/embed queues job and triggers AMD/fallback
    T3  ElevenLabs agent — voice clone, knowledge base, and agent creation signatures
    T4  Memories retrieval — shape matches TypeScript interface, 404 on missing
    T5  Full E2E pipeline — upload → Firestore doc → embed → status transition
    T6  Security validation — rejected file types, sizes, and field constraints
    T7  API contract compliance — response shapes, status codes, CORS headers

Run with:
    pytest tests/test_integration.py -v -m integration

Note: No real Firebase, AMD, or ElevenLabs endpoints are contacted. All external
services are stubbed via the mock_firebase fixture (conftest.py) and inline patches.
"""

from __future__ import annotations

import io
import threading
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ------------------------------------------------------------------ #
# Shared constants                                                      #
# ------------------------------------------------------------------ #

KNOWN_MEMORY_ID = "11111111-2222-3333-4444-555555555555"

# Realistic demo person used across tests
DEMO_PERSON = "Margaret Chen"


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #


@pytest.fixture
def seeded_memory(mock_firebase: MagicMock) -> dict:
    """Return a seeded memory document in the mock Firestore.

    Returns:
        Dict representing the memory document.
    """
    memory: dict = {
        "id": KNOWN_MEMORY_ID,
        "person_name": DEMO_PERSON,
        "created_at": "2026-02-22T10:00:00+00:00",
        "status": "processing",
        "voice_id": None,
        "embedding_ready": False,
        "photos": [
            {
                "photo_id": "photo-aaa-001",
                "url": "https://storage.test/photo_0.jpg",
                "caption": "Wedding day 1974",
                "date": "1974",
                "era": "young-adult",
                "embedding": None,
            },
            {
                "photo_id": "photo-aaa-002",
                "url": "https://storage.test/photo_1.jpg",
                "caption": "Family reunion 1985",
                "date": "1985",
                "era": "family",
                "embedding": None,
            },
            {
                "photo_id": "photo-aaa-003",
                "url": "https://storage.test/photo_2.jpg",
                "caption": "Grandkids 2020",
                "date": "2020",
                "era": "recent",
                "embedding": None,
            },
        ],
    }
    mock_firebase.get_memory_from_firestore.return_value = memory
    return memory


@pytest.fixture
def ready_memory(mock_firebase: MagicMock) -> dict:
    """Return a memory document where all photos have embeddings (embedding_ready=True).

    Returns:
        Dict representing a fully-processed memory document.
    """
    embedding = [round(0.001 * i, 6) for i in range(1024)]
    memory: dict = {
        "id": KNOWN_MEMORY_ID,
        "person_name": DEMO_PERSON,
        "created_at": "2026-02-22T10:00:00+00:00",
        "status": "ready",
        "voice_id": "el_clone_abc123",
        "embedding_ready": True,
        "photos": [
            {
                "photo_id": "photo-aaa-001",
                "url": "https://storage.test/photo_0.jpg",
                "caption": "Wedding day 1974",
                "date": "1974",
                "era": "young-adult",
                "embedding": embedding,
            },
        ],
    }
    mock_firebase.get_memory_from_firestore.return_value = memory
    return memory


# ------------------------------------------------------------------ #
# T1 — Upload pipeline                                                 #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_t1_upload_returns_200_and_memory_id(
    client,
    sample_jpeg: bytes,
    sample_wav: bytes,
    mock_firebase: MagicMock,
) -> None:
    """POST /api/upload with 3 test photos + voice + captions returns 200 with memory_id."""
    with patch("app.routes.upload._queue_embedding_job"):
        response = client.post(
            "/api/upload",
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [
                    (io.BytesIO(sample_jpeg), "photo_wedding.jpg", "image/jpeg"),
                    (io.BytesIO(sample_jpeg), "photo_reunion.jpg", "image/jpeg"),
                    (io.BytesIO(sample_jpeg), "photo_grandkids.jpg", "image/jpeg"),
                ],
                "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
                "captions[]": ["Wedding day 1974", "Family reunion 1985", "Grandkids 2020"],
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    body = response.get_json()
    assert "memory_id" in body, "Response must include memory_id"
    assert len(body["memory_id"]) == 36, "memory_id must be a UUID (36 chars)"
    assert body["status"] == "processing"


@pytest.mark.integration
def test_t1_upload_creates_firestore_document(
    client,
    sample_jpeg: bytes,
    sample_wav: bytes,
    mock_firebase: MagicMock,
) -> None:
    """POST /api/upload must call save_memory_to_firestore exactly once with correct args."""
    with patch("app.routes.upload._queue_embedding_job"):
        response = client.post(
            "/api/upload",
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [
                    (io.BytesIO(sample_jpeg), "p1.jpg", "image/jpeg"),
                    (io.BytesIO(sample_jpeg), "p2.jpg", "image/jpeg"),
                    (io.BytesIO(sample_jpeg), "p3.jpg", "image/jpeg"),
                ],
                "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
                "captions[]": ["Caption 1", "Caption 2", "Caption 3"],
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200

    # Firestore save must have been called exactly once
    mock_firebase.save_memory_to_firestore.assert_called_once()

    save_kwargs = mock_firebase.save_memory_to_firestore.call_args.kwargs
    assert save_kwargs["person_name"] == DEMO_PERSON
    # 3 photos must be included in the document
    assert len(save_kwargs["photo_docs"]) == 3
    # Each photo doc must have the required fields
    for photo_doc in save_kwargs["photo_docs"]:
        assert "photo_id" in photo_doc
        assert "url" in photo_doc
        assert "caption" in photo_doc
        assert "era" in photo_doc


@pytest.mark.integration
def test_t1_upload_calls_firebase_storage_for_each_file(
    client,
    sample_jpeg: bytes,
    sample_png: bytes,
    sample_wav: bytes,
    mock_firebase: MagicMock,
) -> None:
    """Each photo and the voice file must each trigger one Firebase Storage upload."""
    with patch("app.routes.upload._queue_embedding_job"):
        response = client.post(
            "/api/upload",
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [
                    (io.BytesIO(sample_jpeg), "a.jpg", "image/jpeg"),
                    (io.BytesIO(sample_png), "b.png", "image/png"),
                    (io.BytesIO(sample_jpeg), "c.jpg", "image/jpeg"),
                ],
                "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
                "captions[]": ["Cap A", "Cap B", "Cap C"],
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    # 3 photos + 1 voice = 4 Storage upload calls
    assert mock_firebase.upload_file_to_storage.call_count == 4, (
        f"Expected 4 Storage uploads (3 photos + 1 voice), "
        f"got {mock_firebase.upload_file_to_storage.call_count}"
    )

    # Verify Storage path format includes the memory_id prefix
    all_calls = mock_firebase.upload_file_to_storage.call_args_list
    memory_id = response.get_json()["memory_id"]
    for storage_call in all_calls:
        dest_path: str = storage_call.kwargs["destination_path"]
        assert memory_id in dest_path, (
            f"Storage path '{dest_path}' must contain the memory_id '{memory_id}'"
        )


# ------------------------------------------------------------------ #
# T2 — AMD embedding pipeline                                          #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_t2_embed_returns_200_status_queued(
    client,
    mock_firebase: MagicMock,
    seeded_memory: dict,
) -> None:
    """POST /api/embed with valid memory_id returns 200 with status='queued'."""
    with patch("app.routes.embeddings._queue_batch_job") as mock_queue:
        response = client.post(
            "/api/embed",
            json={"memory_id": KNOWN_MEMORY_ID},
        )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "queued"
    assert body["memory_id"] == KNOWN_MEMORY_ID
    assert body["photo_count"] == 3


@pytest.mark.integration
def test_t2_embed_verifies_background_thread_spawned(
    client,
    mock_firebase: MagicMock,
    seeded_memory: dict,
) -> None:
    """POST /api/embed must call _queue_batch_job which spawns a background thread."""
    spawned_threads: list[threading.Thread] = []
    original_thread_start = threading.Thread.start

    def capture_thread_start(self: threading.Thread) -> None:
        spawned_threads.append(self)
        original_thread_start(self)

    with patch.object(threading.Thread, "start", capture_thread_start):
        response = client.post(
            "/api/embed",
            json={"memory_id": KNOWN_MEMORY_ID},
        )

    assert response.status_code == 200
    # At least one daemon thread named 'embed-batch-*' must be started
    embed_threads = [t for t in spawned_threads if "embed-batch" in (t.name or "")]
    assert len(embed_threads) >= 1, (
        "Expected at least one embed-batch-* daemon thread to be spawned"
    )
    for thread in embed_threads:
        assert thread.daemon is True, "Embedding threads must be daemon threads"


@pytest.mark.integration
def test_t2_embed_amd_fallback_when_endpoint_empty() -> None:
    """generate_embedding must use CPU fallback when AMD_ENDPOINT is effectively empty."""
    import asyncio

    import httpx

    from app.services.amd_service import generate_embedding

    # Simulate AMD endpoint being unreachable (connection refused)
    with patch(
        "app.services.amd_service._amd_cloud_embedding",
        side_effect=httpx.ConnectError("Connection refused: AMD endpoint unavailable"),
    ):
        embedding = asyncio.run(
            generate_embedding(b"fake image bytes", "Wedding day 1974")
        )

    assert len(embedding) == 1024, "CPU fallback must return 1024-dimensional embedding"

    # Verify it is unit-normalised (L2 norm ≈ 1.0)
    import math

    norm = math.sqrt(sum(v * v for v in embedding))
    assert abs(norm - 1.0) < 1e-6, f"CPU fallback embedding must be unit-normalised, got norm={norm}"


@pytest.mark.integration
def test_t2_embed_amd_fallback_on_timeout() -> None:
    """generate_embedding must fall back to CPU on AMD timeout."""
    import asyncio

    import httpx

    from app.services.amd_service import generate_embedding

    with patch(
        "app.services.amd_service._amd_cloud_embedding",
        side_effect=httpx.TimeoutException("AMD request timed out"),
    ):
        embedding = asyncio.run(
            generate_embedding(b"image bytes", "Family reunion 1985")
        )

    assert len(embedding) == 1024


@pytest.mark.integration
def test_t2_embed_batch_calls_update_photo_embedding_per_photo(
    mock_firebase: MagicMock,
    seeded_memory: dict,
) -> None:
    """_run_batch must call update_photo_embedding once per photo in the memory."""
    import asyncio

    from app.routes.embeddings import _run_batch

    fake_embedding = [0.0] * 1024

    with (
        patch(
            "app.routes.embeddings.firebase_service.get_all_photos_for_memory",
            return_value=seeded_memory["photos"],
        ),
        patch(
            "app.services.amd_service.generate_embedding",
            new_callable=AsyncMock,
            return_value=fake_embedding,
        ),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        # Simulate photo download response
        fake_response = MagicMock()
        fake_response.content = b"fake image data"
        fake_response.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=fake_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.routes.embeddings.firebase_service.update_photo_embedding"
        ) as mock_update:
            with patch(
                "app.routes.embeddings.firebase_service.update_memory_status"
            ):
                asyncio.run(
                    _run_batch(KNOWN_MEMORY_ID, seeded_memory["photos"])
                )

    # One call per photo that has no embedding yet (all 3 in seeded_memory)
    assert mock_update.call_count == 3, (
        f"Expected update_photo_embedding called 3 times, got {mock_update.call_count}"
    )


# ------------------------------------------------------------------ #
# T3 — ElevenLabs agent (mocked)                                       #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_t3_create_voice_clone_called_with_correct_params(tmp_path) -> None:
    """create_voice_clone must be called with the audio file path and person_name."""
    import asyncio

    from app.services import elevenlabs_service

    # Create a temporary audio file to satisfy the file-existence check
    audio_path = str(tmp_path / "voice_sample.wav")
    with open(audio_path, "wb") as f:
        f.write(b"RIFF" + b"\x00" * 40)  # minimal WAV stub

    mock_response = MagicMock()
    mock_response.json.return_value = {"voice_id": "el_cloned_voice_001"}
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch(
        "app.services.elevenlabs_service._post_with_retry",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_post:
        result = asyncio.run(
            elevenlabs_service.create_voice_clone(audio_path, DEMO_PERSON)
        )

    # Verify the result type and values
    assert result.voice_id == "el_cloned_voice_001"
    assert result.name == DEMO_PERSON

    # Verify _post_with_retry was called with the voices/add endpoint
    mock_post.assert_called_once()
    call_url: str = mock_post.call_args.args[1]
    assert "/voices/add" in call_url

    # Verify the data payload contains the person_name
    call_data: dict = mock_post.call_args.kwargs.get("data", {})
    assert call_data.get("name") == DEMO_PERSON


@pytest.mark.integration
def test_t3_knowledge_base_upload_correct_format(tmp_path) -> None:
    """upload_knowledge_base_document must send the content as a .md file to the KB endpoint."""
    import asyncio

    from app.services import elevenlabs_service

    kb_content = (
        "# Margaret Chen's Memories\n\n"
        "## Wedding Day 1974\n"
        "We got married on a sunny afternoon in San Francisco.\n\n"
        "## Family Reunion 1985\n"
        "The whole family came together at Grandma's house in Oregon.\n"
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "kb_doc_abc999"}
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch(
        "app.services.elevenlabs_service._post_with_retry",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_post:
        kb_id = asyncio.run(
            elevenlabs_service.upload_knowledge_base_document(
                kb_content, "Margaret_Chen_memories"
            )
        )

    assert kb_id == "kb_doc_abc999"

    # Verify correct API endpoint
    call_url: str = mock_post.call_args.args[1]
    assert "/convai/knowledge-base/text" in call_url

    # Verify the file was submitted as markdown
    call_files: dict = mock_post.call_args.kwargs.get("files", {})
    assert "file" in call_files
    file_tuple = call_files["file"]
    assert file_tuple[0].endswith(".md"), "Knowledge base file must have .md extension"
    assert file_tuple[2] == "text/markdown", "Knowledge base file MIME type must be text/markdown"


@pytest.mark.integration
def test_t3_create_conversational_agent_uses_cloned_voice_id() -> None:
    """create_conversational_agent must wire the cloned voice_id into the TTS config."""
    import asyncio

    from app.services import elevenlabs_service

    cloned_voice_id = "el_clone_xyz789"
    kb_id = "kb_doc_abc999"

    mock_response = MagicMock()
    mock_response.json.return_value = {"agent_id": "agent_demo_001"}
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch(
        "app.services.elevenlabs_service._post_with_retry",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_post:
        agent_id = asyncio.run(
            elevenlabs_service.create_conversational_agent(
                voice_id=cloned_voice_id,
                kb_id=kb_id,
                person_name=DEMO_PERSON,
            )
        )

    assert agent_id == "agent_demo_001"

    # Verify the payload sent to the API
    call_url: str = mock_post.call_args.args[1]
    assert "/convai/agents/create" in call_url

    payload: dict = mock_post.call_args.kwargs.get("json", {})
    tts_config = payload["conversation_config"]["tts"]
    assert tts_config["voice_id"] == cloned_voice_id, (
        f"TTS config must use the cloned voice_id '{cloned_voice_id}', "
        f"got '{tts_config['voice_id']}'"
    )

    # Verify knowledge base is wired in
    kb_entries = payload["conversation_config"]["agent"]["prompt"]["knowledge_base"]
    assert len(kb_entries) == 1
    assert kb_entries[0]["id"] == kb_id
    assert kb_entries[0]["type"] == "file"


@pytest.mark.integration
def test_t3_agent_system_prompt_is_first_person() -> None:
    """Agent system prompt must include first-person phrasing for the persona."""
    import asyncio

    from app.services import elevenlabs_service

    mock_response = MagicMock()
    mock_response.json.return_value = {"agent_id": "agent_demo_002"}
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch(
        "app.services.elevenlabs_service._post_with_retry",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_post:
        asyncio.run(
            elevenlabs_service.create_conversational_agent(
                voice_id="el_clone_xyz",
                kb_id="kb_001",
                person_name=DEMO_PERSON,
            )
        )

    payload: dict = mock_post.call_args.kwargs.get("json", {})
    system_prompt: str = payload["conversation_config"]["agent"]["prompt"]["prompt"]

    first_person_phrases = ["first person", "I remember", "We went", "remember"]
    assert any(phrase.lower() in system_prompt.lower() for phrase in first_person_phrases), (
        "System prompt must include first-person phrasing"
    )
    assert DEMO_PERSON in system_prompt, (
        f"System prompt must reference the person name '{DEMO_PERSON}'"
    )


@pytest.mark.integration
def test_t3_knowledge_base_truncated_at_50k_chars() -> None:
    """upload_knowledge_base_document must truncate content exceeding 50,000 chars."""
    import asyncio

    from app.services import elevenlabs_service

    # 60,000-char content — over the 50 KB limit
    oversized_content = "A" * 60_000

    mock_response = MagicMock()
    mock_response.json.return_value = {"id": "kb_truncated"}
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch(
        "app.services.elevenlabs_service._post_with_retry",
        new_callable=AsyncMock,
        return_value=mock_response,
    ) as mock_post:
        asyncio.run(
            elevenlabs_service.upload_knowledge_base_document(oversized_content, "big_doc")
        )

    call_files: dict = mock_post.call_args.kwargs.get("files", {})
    uploaded_bytes: bytes = call_files["file"][1]
    # After truncation to 50,000 chars, the encoded bytes must not exceed 50,000
    assert len(uploaded_bytes) <= 50_000, (
        f"Uploaded content must be truncated to 50,000 chars, got {len(uploaded_bytes)}"
    )


# ------------------------------------------------------------------ #
# T4 — Memories retrieval                                              #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_t4_memory_response_shape_matches_typescript_interface(
    client,
    mock_firebase: MagicMock,
    seeded_memory: dict,
) -> None:
    """GET /api/memories/:id response must match the TypeScript Memory interface shape."""
    response = client.get(f"/api/memories/{KNOWN_MEMORY_ID}")
    assert response.status_code == 200
    body = response.get_json()

    # Top-level required fields (matches Memory interface in frontend types)
    required_top_level = {"id", "person_name", "created_at", "status", "voice_id",
                          "embedding_ready", "photos"}
    missing = required_top_level - set(body.keys())
    assert not missing, f"Response missing top-level fields: {missing}"

    # Field type assertions
    assert isinstance(body["id"], str)
    assert isinstance(body["person_name"], str)
    assert isinstance(body["created_at"], str)
    assert body["status"] in {"processing", "ready", "error"}
    assert isinstance(body["embedding_ready"], bool)
    assert isinstance(body["photos"], list)

    # Photo sub-document shape (matches Photo interface in frontend types)
    required_photo_fields = {"photo_id", "url", "caption", "date", "era", "embedding"}
    for photo in body["photos"]:
        missing_photo = required_photo_fields - set(photo.keys())
        assert not missing_photo, f"Photo missing fields: {missing_photo}"
        assert isinstance(photo["url"], str)
        assert isinstance(photo["caption"], str)
        assert photo["era"] in {"childhood", "young-adult", "family", "recent"}


@pytest.mark.integration
def test_t4_embedding_ready_true_when_all_photos_have_embeddings(
    client,
    mock_firebase: MagicMock,
    ready_memory: dict,
) -> None:
    """GET /api/memories/:id must return embedding_ready=True when all photos have embeddings."""
    response = client.get(f"/api/memories/{KNOWN_MEMORY_ID}")
    assert response.status_code == 200
    body = response.get_json()

    assert body["embedding_ready"] is True
    assert body["status"] == "ready"
    for photo in body["photos"]:
        assert photo["embedding"] is not None
        assert len(photo["embedding"]) == 1024


@pytest.mark.integration
def test_t4_memory_returns_404_when_not_found(
    client,
    mock_firebase: MagicMock,
) -> None:
    """GET /api/memories/:id for a non-existent memory must return 404 with not_found error."""
    mock_firebase.get_memory_from_firestore.return_value = None
    nonexistent_id = str(uuid.uuid4())

    response = client.get(f"/api/memories/{nonexistent_id}")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"] == "not_found"
    assert "detail" in body
    assert len(body["detail"]) > 0


@pytest.mark.integration
def test_t4_voice_id_present_after_cloning(
    client,
    mock_firebase: MagicMock,
    ready_memory: dict,
) -> None:
    """GET /api/memories/:id must return the cloned voice_id once voice cloning completes."""
    response = client.get(f"/api/memories/{KNOWN_MEMORY_ID}")
    assert response.status_code == 200
    body = response.get_json()

    assert body["voice_id"] is not None
    assert body["voice_id"] == "el_clone_abc123"
    assert body["voice_id"].startswith("el_"), "voice_id must start with 'el_' prefix"


# ------------------------------------------------------------------ #
# T5 — Full E2E pipeline (mocked services)                            #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_t5_upload_then_embed_full_pipeline(
    client,
    sample_jpeg: bytes,
    sample_wav: bytes,
    mock_firebase: MagicMock,
) -> None:
    """Upload → Firestore doc → trigger embed → verify embedding job queued.

    Simulates the complete processing pipeline:
    1. POST /api/upload with 5 demo photos
    2. Assert Firestore document created
    3. POST /api/embed with returned memory_id
    4. Assert embedding job queued
    5. Verify memory status transitions to processing → queued
    """
    # Step 1: Upload 5 demo photos
    with patch("app.routes.upload._queue_embedding_job"):
        upload_resp = client.post(
            "/api/upload",
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [
                    (io.BytesIO(sample_jpeg), f"demo_photo_{i}.jpg", "image/jpeg")
                    for i in range(5)
                ],
                "voice_recording": (io.BytesIO(sample_wav), "voice_demo.wav", "audio/wav"),
                "captions[]": [
                    "Childhood at the farm",
                    "Wedding day 1974",
                    "First home 1978",
                    "Family reunion 1985",
                    "Grandkids 2020",
                ],
            },
            content_type="multipart/form-data",
        )

    assert upload_resp.status_code == 200
    upload_body = upload_resp.get_json()
    memory_id = upload_body["memory_id"]
    assert upload_body["status"] == "processing"

    # Step 2: Firestore document must have been created with 5 photos
    mock_firebase.save_memory_to_firestore.assert_called_once()
    save_kwargs = mock_firebase.save_memory_to_firestore.call_args.kwargs
    assert len(save_kwargs["photo_docs"]) == 5

    # Step 3: Seed Firestore mock to return the uploaded memory
    demo_photos = [
        {
            "photo_id": f"photo-demo-{i:03d}",
            "url": f"https://storage.test/photo_{i}.jpg",
            "caption": cap,
            "date": "",
            "era": ["childhood", "young-adult", "young-adult", "family", "recent"][i],
            "embedding": None,
        }
        for i, cap in enumerate([
            "Childhood at the farm",
            "Wedding day 1974",
            "First home 1978",
            "Family reunion 1985",
            "Grandkids 2020",
        ])
    ]
    mock_firebase.get_memory_from_firestore.return_value = {
        "id": memory_id,
        "person_name": DEMO_PERSON,
        "created_at": "2026-02-22T10:00:00+00:00",
        "status": "processing",
        "voice_id": None,
        "embedding_ready": False,
        "photos": demo_photos,
    }

    # Step 4: Trigger embedding
    with patch("app.routes.embeddings._queue_batch_job") as mock_queue:
        embed_resp = client.post("/api/embed", json={"memory_id": memory_id})

    assert embed_resp.status_code == 200
    embed_body = embed_resp.get_json()
    assert embed_body["status"] == "queued"
    assert embed_body["photo_count"] == 5

    # Step 5: Background job was queued with all 5 photos
    mock_queue.assert_called_once_with(memory_id, demo_photos)


@pytest.mark.integration
def test_t5_memory_status_transitions_processing_to_ready(
    client,
    mock_firebase: MagicMock,
    seeded_memory: dict,
) -> None:
    """Memory status must transition: upload sets 'processing', embed completion sets 'ready'."""
    # Initial state after upload
    assert seeded_memory["status"] == "processing"

    # Verify GET reflects 'processing' state
    response = client.get(f"/api/memories/{KNOWN_MEMORY_ID}")
    assert response.status_code == 200
    assert response.get_json()["status"] == "processing"

    # Simulate embedding completion by updating mock return value
    seeded_memory["status"] = "ready"
    seeded_memory["embedding_ready"] = True
    for photo in seeded_memory["photos"]:
        photo["embedding"] = [0.1] * 1024
    mock_firebase.get_memory_from_firestore.return_value = seeded_memory

    # Verify GET now reflects 'ready' state
    response = client.get(f"/api/memories/{KNOWN_MEMORY_ID}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ready"
    assert body["embedding_ready"] is True


# ------------------------------------------------------------------ #
# T6 — Security validation                                             #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_t6_upload_exe_file_rejected_400(
    client,
    sample_wav: bytes,
) -> None:
    """Upload with .exe file must return 400 validation_failed."""
    exe_bytes = b"MZ" + b"\x00" * 100  # Windows PE header magic bytes
    response = client.post(
        "/api/upload",
        data={
            "person_name": DEMO_PERSON,
            "photos[]": [(io.BytesIO(exe_bytes), "malware.exe", "application/octet-stream")],
            "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
            "captions[]": ["Caption"],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert ".exe" in body["detail"]


@pytest.mark.integration
def test_t6_upload_oversized_file_rejected_400(
    client,
    sample_wav: bytes,
) -> None:
    """Upload with file exceeding 10 MB size limit must return 400 validation_failed."""
    # 11 MB image (exceeds the default 10 MB limit)
    large_bytes = b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)
    response = client.post(
        "/api/upload",
        data={
            "person_name": DEMO_PERSON,
            "photos[]": [(io.BytesIO(large_bytes), "huge.jpg", "image/jpeg")],
            "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
            "captions[]": ["Caption"],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "MB" in body["detail"]


@pytest.mark.integration
def test_t6_upload_31_photos_rejected_400(
    client,
    sample_jpeg: bytes,
    sample_wav: bytes,
) -> None:
    """Upload with 31 photos (exceeding MAX_PHOTOS=30) must return 400 validation_failed."""
    photos = [(io.BytesIO(sample_jpeg), f"p{i}.jpg", "image/jpeg") for i in range(31)]
    captions = [f"Caption {i}" for i in range(31)]
    response = client.post(
        "/api/upload",
        data={
            "person_name": DEMO_PERSON,
            "photos[]": photos,
            "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
            "captions[]": captions,
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "31" in body["detail"] or "maximum" in body["detail"].lower()


@pytest.mark.integration
def test_t6_upload_mismatched_captions_rejected_400(
    client,
    sample_jpeg: bytes,
    sample_wav: bytes,
) -> None:
    """Upload with caption count not matching photo count must return 400 validation_failed."""
    response = client.post(
        "/api/upload",
        data={
            "person_name": DEMO_PERSON,
            "photos[]": [
                (io.BytesIO(sample_jpeg), "p1.jpg", "image/jpeg"),
                (io.BytesIO(sample_jpeg), "p2.jpg", "image/jpeg"),
            ],
            "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
            "captions[]": ["Only one caption"],  # 1 caption for 2 photos
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "captions" in body["detail"].lower()


@pytest.mark.integration
def test_t6_upload_empty_person_name_rejected_400(
    client,
    sample_jpeg: bytes,
    sample_wav: bytes,
) -> None:
    """Upload with empty person_name must return 400 validation_failed."""
    response = client.post(
        "/api/upload",
        data={
            "person_name": "   ",  # whitespace-only
            "photos[]": [(io.BytesIO(sample_jpeg), "p1.jpg", "image/jpeg")],
            "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
            "captions[]": ["Caption"],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "person_name" in body["detail"].lower()


@pytest.mark.integration
def test_t6_upload_gif_image_rejected_400(
    client,
    sample_wav: bytes,
) -> None:
    """Upload with a .gif image (unsupported format) must return 400 validation_failed."""
    gif_bytes = b"GIF89a" + b"\x00" * 50
    response = client.post(
        "/api/upload",
        data={
            "person_name": DEMO_PERSON,
            "photos[]": [(io.BytesIO(gif_bytes), "animation.gif", "image/gif")],
            "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
            "captions[]": ["Caption"],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert ".gif" in body["detail"]


@pytest.mark.integration
def test_t6_upload_zero_byte_image_rejected_400(
    client,
    sample_wav: bytes,
) -> None:
    """Upload with zero-byte image file must return 400 validation_failed."""
    response = client.post(
        "/api/upload",
        data={
            "person_name": DEMO_PERSON,
            "photos[]": [(io.BytesIO(b""), "empty.jpg", "image/jpeg")],
            "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
            "captions[]": ["Caption"],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "empty" in body["detail"].lower()


@pytest.mark.integration
def test_t6_upload_unsupported_audio_rejected_400(
    client,
    sample_jpeg: bytes,
) -> None:
    """Upload with .aac audio file (unsupported extension) must return 400 validation_failed."""
    aac_bytes = b"\xff\xf1" + b"\x00" * 200
    response = client.post(
        "/api/upload",
        data={
            "person_name": DEMO_PERSON,
            "photos[]": [(io.BytesIO(sample_jpeg), "p1.jpg", "image/jpeg")],
            "voice_recording": (io.BytesIO(aac_bytes), "recording.aac", "audio/aac"),
            "captions[]": ["Caption"],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert ".aac" in body["detail"]


# ------------------------------------------------------------------ #
# T7 — API contract compliance                                         #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_t7_upload_response_matches_contract(
    client,
    sample_jpeg: bytes,
    sample_wav: bytes,
    mock_firebase: MagicMock,
) -> None:
    """POST /api/upload response must contain exactly the fields the frontend expects."""
    with patch("app.routes.upload._queue_embedding_job"):
        response = client.post(
            "/api/upload",
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [(io.BytesIO(sample_jpeg), "p.jpg", "image/jpeg")],
                "voice_recording": (io.BytesIO(sample_wav), "v.wav", "audio/wav"),
                "captions[]": ["A caption"],
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    body = response.get_json()

    # Exact required fields per TypeScript UploadResponse interface
    required = {"memory_id", "status"}
    missing = required - set(body.keys())
    assert not missing, f"Upload response missing required keys: {missing}"

    # Type checks
    assert isinstance(body["memory_id"], str) and len(body["memory_id"]) == 36
    assert body["status"] == "processing"


@pytest.mark.integration
def test_t7_embed_response_matches_contract(
    client,
    mock_firebase: MagicMock,
    seeded_memory: dict,
) -> None:
    """POST /api/embed response must match the EmbedResponse interface."""
    with patch("app.routes.embeddings._queue_batch_job"):
        response = client.post("/api/embed", json={"memory_id": KNOWN_MEMORY_ID})

    assert response.status_code == 200
    body = response.get_json()

    required = {"status", "memory_id", "photo_count"}
    missing = required - set(body.keys())
    assert not missing, f"Embed response missing required keys: {missing}"

    assert body["status"] == "queued"
    assert body["memory_id"] == KNOWN_MEMORY_ID
    assert isinstance(body["photo_count"], int)
    assert body["photo_count"] >= 0


@pytest.mark.integration
def test_t7_health_endpoint_returns_200(client) -> None:
    """GET /api/health must return 200 with status=ok."""
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"


@pytest.mark.integration
def test_t7_404_response_has_required_shape(
    client,
    mock_firebase: MagicMock,
) -> None:
    """All 404 error responses must have error='not_found' and a detail message."""
    mock_firebase.get_memory_from_firestore.return_value = None
    response = client.get(f"/api/memories/{uuid.uuid4()}")
    assert response.status_code == 404
    body = response.get_json()
    assert body["error"] == "not_found"
    assert isinstance(body["detail"], str) and len(body["detail"]) > 0


@pytest.mark.integration
def test_t7_400_response_has_required_shape(
    client,
    sample_wav: bytes,
) -> None:
    """All 400 error responses must have error='validation_failed' and a detail message."""
    # Trigger a 400 by uploading no photos
    response = client.post(
        "/api/upload",
        data={
            "person_name": DEMO_PERSON,
            "voice_recording": (io.BytesIO(sample_wav), "v.wav", "audio/wav"),
            "captions[]": [],
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert isinstance(body["detail"], str) and len(body["detail"]) > 0


@pytest.mark.integration
def test_t7_cors_headers_present_on_upload(
    client,
    sample_jpeg: bytes,
    sample_wav: bytes,
    mock_firebase: MagicMock,
) -> None:
    """Responses to /api/upload must include CORS headers for the Vite dev origin."""
    with patch("app.routes.upload._queue_embedding_job"):
        response = client.post(
            "/api/upload",
            headers={"Origin": "http://localhost:5173"},
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [(io.BytesIO(sample_jpeg), "p.jpg", "image/jpeg")],
                "voice_recording": (io.BytesIO(sample_wav), "v.wav", "audio/wav"),
                "captions[]": ["A caption"],
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    # Flask-CORS must inject the Access-Control-Allow-Origin header
    assert "Access-Control-Allow-Origin" in response.headers, (
        "CORS header 'Access-Control-Allow-Origin' must be present on upload responses"
    )


@pytest.mark.integration
def test_t7_cors_headers_present_on_memories(
    client,
    mock_firebase: MagicMock,
    seeded_memory: dict,
) -> None:
    """Responses to /api/memories/:id must include CORS headers."""
    response = client.get(
        f"/api/memories/{KNOWN_MEMORY_ID}",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" in response.headers


@pytest.mark.integration
def test_t7_embed_missing_memory_id_returns_400(
    client,
    mock_firebase: MagicMock,
) -> None:
    """POST /api/embed with empty body must return 400 validation_failed."""
    response = client.post("/api/embed", json={})
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation_failed"
    assert "memory_id" in body["detail"].lower()


@pytest.mark.integration
def test_t7_list_memories_response_matches_contract(
    client,
    mock_firebase: MagicMock,
) -> None:
    """GET /api/memories must return {memories: [], total: int} shape."""
    response = client.get("/api/memories")
    assert response.status_code == 200
    body = response.get_json()
    assert "memories" in body
    assert "total" in body
    assert isinstance(body["memories"], list)
    assert isinstance(body["total"], int)
    assert body["total"] == len(body["memories"])
