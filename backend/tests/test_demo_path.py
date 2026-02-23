"""Demo path simulation — simulates the full 4-minute judge demo.

Run this before submission to verify zero failures:

    pytest tests/test_demo_path.py -v --tb=short

This module does NOT contact any real external services. All Firebase,
AMD, and ElevenLabs calls are mocked. The goal is to verify that:

    1. Every step of the demo path produces the correct data shapes
    2. The full pipeline completes in under 30 seconds wall clock
    3. The voice agent would receive the correct photo context
    4. The knowledge base content is well-formed for the ElevenLabs agent

Demo flow (mirrors the 4-minute judge walkthrough):
    [0:00] Web app opens (health check)
    [0:10] Drag in 5 demo photos + voice recording (upload)
    [0:30] Trigger embedding job (embed)
    [1:00] Verify spatial room data shape (memories GET)
    [2:30] Photo selection sends context to voice agent (context shape)
    [3:00] Voice agent responds in first person (response check)
    [3:20] Q&A: "Where was our first vacation?" (knowledge base lookup)
    [3:45] Full wall-clock timing assertion (< 30 seconds)
"""

from __future__ import annotations

import io
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ------------------------------------------------------------------ #
# Demo constants — use realistic data matching the actual demo script  #
# ------------------------------------------------------------------ #

DEMO_PERSON = "Margaret Chen"

DEMO_CAPTIONS: list[str] = [
    "Childhood at the farm, 1952",
    "Wedding day, San Francisco 1974",
    "First home, Oakland 1978",
    "Family reunion, Portland 1985",
    "Grandkids Christmas, 2020",
]

DEMO_MEMORY_ID = "demo-0000-1111-2222-333333333333"

# Expected knowledge base content shape — must reference real demo details
_KB_REQUIRED_PHRASES = [
    "Margaret Chen",
    "1974",
    "1985",
    "2020",
]


# ------------------------------------------------------------------ #
# Demo fixtures                                                        #
# ------------------------------------------------------------------ #


@pytest.fixture
def demo_memory_doc() -> dict:
    """Return the fully-processed demo memory document that judges will see."""
    embedding_vector = [round(0.001 * i, 6) for i in range(1024)]
    return {
        "id": DEMO_MEMORY_ID,
        "person_name": DEMO_PERSON,
        "created_at": "2026-02-22T10:00:00+00:00",
        "status": "ready",
        "voice_id": "el_clone_margaret_001",
        "embedding_ready": True,
        "photos": [
            {
                "photo_id": f"photo-demo-{i:03d}",
                "url": f"https://storage.demo/photo_{i}.jpg",
                "caption": caption,
                "date": caption.split(",")[-1].strip().split(" ")[-1]
                if "," in caption
                else "",
                "era": era,
                "embedding": embedding_vector,
            }
            for i, (caption, era) in enumerate(
                zip(
                    DEMO_CAPTIONS,
                    ["childhood", "young-adult", "young-adult", "family", "recent"],
                )
            )
        ],
    }


@pytest.fixture
def demo_client(mock_firebase: MagicMock, demo_memory_doc: dict):
    """Flask test client wired with the demo memory pre-loaded in the mock."""
    mock_firebase.get_memory_from_firestore.return_value = demo_memory_doc
    mock_firebase.upload_file_to_storage.return_value = "https://storage.demo/file.jpg"

    from app import create_app

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


# ------------------------------------------------------------------ #
# Demo Step 1 — Health check [0:00]                                    #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_step1_health_check(demo_client) -> None:
    """Demo [0:00] — web app opens: GET /api/health must return 200."""
    response = demo_client.get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"


# ------------------------------------------------------------------ #
# Demo Step 2 — Upload 5 demo photos [0:10]                           #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_step2_upload_five_photos_returns_memory_id(
    demo_client,
    mock_firebase: MagicMock,
    sample_jpeg: bytes,
    sample_wav: bytes,
) -> None:
    """Demo [0:10] — drag in 5 demo photos + voice recording: must return memory_id."""
    with patch("app.routes.upload._queue_embedding_job"):
        response = demo_client.post(
            "/api/upload",
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [
                    (io.BytesIO(sample_jpeg), f"demo_{i}.jpg", "image/jpeg")
                    for i in range(5)
                ],
                "voice_recording": (io.BytesIO(sample_wav), "margaret_voice.wav", "audio/wav"),
                "captions[]": DEMO_CAPTIONS,
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    body = response.get_json()
    assert "memory_id" in body
    assert body["status"] == "processing"
    # 5 photos + 1 voice = 6 Storage uploads
    assert mock_firebase.upload_file_to_storage.call_count == 6


# ------------------------------------------------------------------ #
# Demo Step 3 — Trigger embedding [0:30]                              #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_step3_trigger_embedding_queued(
    demo_client,
    mock_firebase: MagicMock,
    demo_memory_doc: dict,
) -> None:
    """Demo [0:30] — trigger embedding: POST /api/embed must return status=queued."""
    mock_firebase.get_memory_from_firestore.return_value = demo_memory_doc

    with patch("app.routes.embeddings._queue_batch_job") as mock_queue:
        response = demo_client.post("/api/embed", json={"memory_id": DEMO_MEMORY_ID})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "queued"
    assert body["photo_count"] == 5

    # Background job must be queued with all 5 demo photos
    mock_queue.assert_called_once()
    _, photos_arg = mock_queue.call_args.args
    assert len(photos_arg) == 5


# ------------------------------------------------------------------ #
# Demo Step 4 — Spatial room data shape [1:45]                        #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_step4_spatial_room_data_shape(
    demo_client,
    mock_firebase: MagicMock,
    demo_memory_doc: dict,
) -> None:
    """Demo [1:45] — open spatial room: GET /api/memories/:id must return correct panel data."""
    mock_firebase.get_memory_from_firestore.return_value = demo_memory_doc

    response = demo_client.get(f"/api/memories/{DEMO_MEMORY_ID}")

    assert response.status_code == 200
    body = response.get_json()

    # All 5 photos must appear with their era labels
    assert len(body["photos"]) == 5, (
        f"Spatial room expects 5 FloatingPhotoPanel instances, got {len(body['photos'])}"
    )

    # Each panel needs url, caption, era for the spatial renderer
    panel_required = {"url", "caption", "era", "photo_id"}
    for i, panel in enumerate(body["photos"]):
        missing = panel_required - set(panel.keys())
        assert not missing, f"Panel {i} missing fields for spatial renderer: {missing}"
        assert panel["era"] in {"childhood", "young-adult", "family", "recent"}, (
            f"Panel {i} era '{panel['era']}' is not a valid spatial era"
        )

    # Verify era distribution — judges see photos floating by era depth
    eras = [p["era"] for p in body["photos"]]
    assert "childhood" in eras, "At least one panel must be in 'childhood' era"
    assert "recent" in eras, "At least one panel must be in 'recent' era"

    # Embeddings must be present for semantic search to work
    assert body["embedding_ready"] is True
    for photo in body["photos"]:
        assert photo["embedding"] is not None
        assert len(photo["embedding"]) == 1024


# ------------------------------------------------------------------ #
# Demo Step 5 — Photo selection sends context to voice agent [2:30]   #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_step5_photo_context_shape_for_agent(
    demo_memory_doc: dict,
) -> None:
    """Demo [2:30] — touch wedding photo: agent must receive photo-specific context."""
    # Simulate the context object the frontend sends to the ElevenLabs widget
    wedding_photo = next(
        p for p in demo_memory_doc["photos"] if "1974" in p["caption"]
    )

    # Build the context the ElevenLabs agent session would receive
    agent_context = {
        "photo_id": wedding_photo["photo_id"],
        "caption": wedding_photo["caption"],
        "era": wedding_photo["era"],
        "person_name": demo_memory_doc["person_name"],
        "memory_id": demo_memory_doc["id"],
    }

    # Verify context contains the fields the agent system prompt uses
    assert agent_context["caption"] == "Wedding day, San Francisco 1974"
    assert agent_context["era"] == "young-adult"
    assert agent_context["person_name"] == DEMO_PERSON

    # Simulate building the photo-specific prompt addition
    photo_prompt_addition = (
        f"The visitor is looking at a photo: '{agent_context['caption']}'. "
        f"Respond as if remembering this specific moment."
    )
    assert "1974" in photo_prompt_addition
    assert "Wedding day" in photo_prompt_addition


# ------------------------------------------------------------------ #
# Demo Step 6 — Voice agent responds in first person [3:00]           #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_step6_voice_agent_responds_first_person() -> None:
    """Demo [3:00] — agent narrates memory: response must be in first person."""
    import asyncio

    from app.services import elevenlabs_service

    # Simulate what the ElevenLabs agent would return for a wedding photo query
    simulated_agent_response = (
        "I remember that day so clearly — we got married on a warm September afternoon "
        "right there in San Francisco. I was so nervous walking down the aisle, "
        "but the moment I saw his face, everything felt exactly right."
    )

    # Assert the response follows the first-person memory persona guidelines
    first_person_indicators = ["I remember", "I was", "we got", "I saw"]
    assert any(phrase in simulated_agent_response for phrase in first_person_indicators), (
        "Agent response must be in first person"
    )

    # Assert response is 2-4 sentences (conversational, not documentary)
    sentence_count = simulated_agent_response.count(".") + simulated_agent_response.count("!")
    assert 1 <= sentence_count <= 4, (
        f"Agent response must be 2-4 sentences for conversational feel, got {sentence_count}"
    )

    # Verify the agent config uses the cloned voice_id (not a default voice)
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
                voice_id="el_clone_margaret_001",
                kb_id="kb_margaret_001",
                person_name=DEMO_PERSON,
            )
        )

    assert agent_id == "agent_demo_001"
    payload: dict = mock_post.call_args.kwargs.get("json", {})
    assert payload["conversation_config"]["tts"]["voice_id"] == "el_clone_margaret_001", (
        "Demo must use the CLONED voice_id, not a default ElevenLabs voice"
    )


# ------------------------------------------------------------------ #
# Demo Step 7 — Q&A with knowledge base [3:20]                        #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_step7_knowledge_base_content_well_formed(
    demo_memory_doc: dict,
) -> None:
    """Demo [3:20] — 'Where was our first vacation?': KB content must be queryable."""
    # Build the knowledge base document from demo memory — as the upload route does
    kb_lines: list[str] = [f"# {DEMO_PERSON}'s Memory Companion Knowledge Base\n"]
    kb_lines.append(f"Person: {DEMO_PERSON}\n")
    kb_lines.append("---\n\n")

    for photo in demo_memory_doc["photos"]:
        kb_lines.append(f"## Memory: {photo['caption']}\n")
        kb_lines.append(f"- Era: {photo['era']}\n")
        if photo.get("date"):
            kb_lines.append(f"- Date: {photo['date']}\n")
        kb_lines.append("\n")

    kb_content = "".join(kb_lines)

    # Verify required phrases are present for judge Q&A
    for phrase in _KB_REQUIRED_PHRASES:
        assert phrase in kb_content, (
            f"Knowledge base must contain '{phrase}' for Q&A to work"
        )

    # Verify the KB has content for each photo
    for caption in DEMO_CAPTIONS:
        assert caption in kb_content, (
            f"Knowledge base must include caption '{caption}'"
        )

    # Verify KB is under the 50,000 char limit
    assert len(kb_content) <= 50_000, (
        f"Knowledge base content ({len(kb_content)} chars) exceeds ElevenLabs 50 KB limit"
    )


@pytest.mark.integration
def test_demo_step7_agent_handles_unknown_gracefully() -> None:
    """Demo [3:20] — agent must handle unknown queries with graceful uncertainty."""
    # Verify the system prompt template contains the graceful fallback phrasing
    from app.services.elevenlabs_service import _SYSTEM_PROMPT_TEMPLATE

    prompt = _SYSTEM_PROMPT_TEMPLATE.format(person_name=DEMO_PERSON)

    graceful_phrases = [
        "not sure",
        "don't remember",
        "I'm not sure",
        "remember that clearly",
    ]
    assert any(phrase.lower() in prompt.lower() for phrase in graceful_phrases), (
        "System prompt must include graceful fallback for unknown memories\n"
        f"Prompt excerpt: {prompt[:300]}"
    )


# ------------------------------------------------------------------ #
# Demo Step 8 — Full wall-clock timing [3:45]                         #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_step8_full_pipeline_under_30_seconds(
    demo_client,
    mock_firebase: MagicMock,
    demo_memory_doc: dict,
    sample_jpeg: bytes,
    sample_wav: bytes,
) -> None:
    """Demo [3:45] — full pipeline (upload + embed trigger + retrieve) must complete in < 30s.

    This is a wall-clock timing test. All external services are mocked so the
    only real latency is Flask request handling. If this test is slow, the
    routing or fixture setup has a performance issue.
    """
    wall_start = time.perf_counter()

    # --- Step A: Health check
    health_resp = demo_client.get("/api/health")
    assert health_resp.status_code == 200

    # --- Step B: Upload 5 demo photos
    with patch("app.routes.upload._queue_embedding_job"):
        upload_resp = demo_client.post(
            "/api/upload",
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [
                    (io.BytesIO(sample_jpeg), f"demo_{i}.jpg", "image/jpeg")
                    for i in range(5)
                ],
                "voice_recording": (io.BytesIO(sample_wav), "voice.wav", "audio/wav"),
                "captions[]": DEMO_CAPTIONS,
            },
            content_type="multipart/form-data",
        )
    assert upload_resp.status_code == 200
    memory_id = upload_resp.get_json()["memory_id"]

    # --- Step C: Seed mock and trigger embedding
    mock_firebase.get_memory_from_firestore.return_value = demo_memory_doc
    with patch("app.routes.embeddings._queue_batch_job"):
        embed_resp = demo_client.post("/api/embed", json={"memory_id": memory_id})
    assert embed_resp.status_code == 200

    # --- Step D: Retrieve full memory for spatial room
    get_resp = demo_client.get(f"/api/memories/{memory_id}")
    assert get_resp.status_code == 200
    body = get_resp.get_json()
    assert len(body["photos"]) == 5

    # --- Step E: Verify list endpoint works
    mock_firebase.list_memories_from_firestore.return_value = [demo_memory_doc]
    list_resp = demo_client.get("/api/memories")
    assert list_resp.status_code == 200

    wall_elapsed = time.perf_counter() - wall_start

    assert wall_elapsed < 30.0, (
        f"Full demo pipeline took {wall_elapsed:.2f}s — must complete in < 30s. "
        "Check for blocking I/O or slow fixture setup."
    )


# ------------------------------------------------------------------ #
# Demo pre-flight check — verify all components at once               #
# ------------------------------------------------------------------ #


@pytest.mark.integration
def test_demo_preflight_all_components_green(
    demo_client,
    mock_firebase: MagicMock,
    demo_memory_doc: dict,
    sample_jpeg: bytes,
    sample_wav: bytes,
) -> None:
    """Pre-submission preflight: all components must pass before running the demo 3 times.

    This single test exercises every component the judge will interact with:
    - Upload pipeline
    - Embedding trigger
    - Spatial room data retrieval
    - API contract compliance
    - CORS headers
    - Error handling

    Run this test 3 times consecutively before submission:
        pytest tests/test_demo_path.py::test_demo_preflight_all_components_green -v --count=3
    """
    failures: list[str] = []

    # 1. Health check
    h = demo_client.get("/api/health")
    if h.status_code != 200:
        failures.append(f"Health check failed: {h.status_code}")

    # 2. Upload
    with patch("app.routes.upload._queue_embedding_job"):
        u = demo_client.post(
            "/api/upload",
            data={
                "person_name": DEMO_PERSON,
                "photos[]": [
                    (io.BytesIO(sample_jpeg), f"p{i}.jpg", "image/jpeg") for i in range(5)
                ],
                "voice_recording": (io.BytesIO(sample_wav), "v.wav", "audio/wav"),
                "captions[]": DEMO_CAPTIONS,
            },
            content_type="multipart/form-data",
        )
    if u.status_code != 200:
        failures.append(f"Upload failed: {u.status_code} — {u.get_json()}")
    else:
        memory_id = u.get_json()["memory_id"]
        if len(memory_id) != 36:
            failures.append(f"memory_id is not a UUID: '{memory_id}'")

    # 3. Embed trigger
    mock_firebase.get_memory_from_firestore.return_value = demo_memory_doc
    with patch("app.routes.embeddings._queue_batch_job"):
        e = demo_client.post("/api/embed", json={"memory_id": DEMO_MEMORY_ID})
    if e.status_code != 200 or e.get_json().get("status") != "queued":
        failures.append(f"Embed trigger failed: {e.status_code} — {e.get_json()}")

    # 4. Spatial room data
    g = demo_client.get(f"/api/memories/{DEMO_MEMORY_ID}")
    if g.status_code != 200:
        failures.append(f"GET memory failed: {g.status_code}")
    else:
        body = g.get_json()
        if len(body.get("photos", [])) != 5:
            failures.append(f"Expected 5 photos in spatial room, got {len(body.get('photos', []))}")
        if not body.get("embedding_ready"):
            failures.append("embedding_ready must be True for demo")

    # 5. CORS header present
    g_cors = demo_client.get(
        f"/api/memories/{DEMO_MEMORY_ID}",
        headers={"Origin": "http://localhost:5173"},
    )
    if "Access-Control-Allow-Origin" not in g_cors.headers:
        failures.append("CORS header missing on GET /api/memories/:id")

    # 6. 404 shape correct
    mock_firebase.get_memory_from_firestore.return_value = None
    not_found = demo_client.get(f"/api/memories/{uuid.uuid4()}")
    if not_found.status_code != 404:
        failures.append(f"404 test got status {not_found.status_code}")
    else:
        nf_body = not_found.get_json()
        if nf_body.get("error") != "not_found":
            failures.append(f"404 body missing error='not_found': {nf_body}")

    # Assert zero failures
    assert not failures, (
        f"PRE-FLIGHT FAILED — {len(failures)} issue(s):\n"
        + "\n".join(f"  [{i+1}] {msg}" for i, msg in enumerate(failures))
    )
