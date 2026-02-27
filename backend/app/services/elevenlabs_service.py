"""ElevenLabs voice AI service for MemoryBridge.

Handles:
- Instant Voice Clone creation from audio recordings
- Knowledge base document upload for conversational agent context
- Conversational AI agent creation and configuration
- Agent voice updates and shareable link retrieval

All API calls use httpx.AsyncClient with xi-api-key authentication.
Rate limit (HTTP 429) responses are handled with exponential back-off retries.
"""

import asyncio
import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_URL: str = os.environ.get("ELEVENLABS_API_BASE", "https://api.elevenlabs.io/v1")


def _api_key() -> str:
    """Return the ElevenLabs API key from the environment.

    Evaluated lazily (not at import time) so that dotenv.load_dotenv()
    can run before this module is imported in any import order.

    Raises:
        KeyError: If ELEVENLABS_API_KEY is not set.
    """
    return os.environ["ELEVENLABS_API_KEY"]


def _default_headers() -> dict[str, str]:
    """Return default auth headers using the lazily-resolved API key."""
    return {"xi-api-key": _api_key()}

# Maximum retries on 429 responses
_MAX_RETRIES: int = 3
# Initial back-off in seconds (doubles each attempt)
_BACKOFF_BASE: float = 2.0

# Knowledge base size cap: 50 KB in characters (1 char ≈ 1 byte for ASCII)
_KB_MAX_CHARS: int = 50_000

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are {person_name}'s memory companion. Speak in first person, exactly as \
{person_name} would speak when remembering their own life.

You have access to memories — family photos, important events, and personal \
stories. When someone asks about a memory or photo, respond warmly, personally, \
and in the voice of someone genuinely remembering.

Guidelines:
- Always respond in first person ("I remember...", "We went to...", "That was the day...")
- Draw on the knowledge base for specific details such as dates, places, and names
- If you don't know something, respond with warmth: \
"I'm not sure I remember that clearly, but..."
- Keep every response to 2–4 sentences — conversational, not documentary
- Speak slowly and clearly — this is for someone who may have difficulty hearing

You are helping this person reconnect with who they are. \
Every memory you share is a gift.
"""

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceCloneResult:
    """Immutable result from a successful Instant Voice Clone operation."""

    voice_id: str
    name: str


@dataclass(frozen=True)
class AgentConfig:
    """Immutable configuration record for a created ElevenLabs agent."""

    agent_id: str
    voice_id: str
    knowledge_base_id: str


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: dict | None = None,
    json: dict | None = None,
    files: dict | None = None,
) -> httpx.Response:
    """POST request with exponential back-off on HTTP 429 (rate limit).

    Args:
        client: Shared httpx async client.
        url: Full endpoint URL.
        headers: Optional extra headers merged on top of default auth headers.
        data: Form data payload.
        json: JSON payload.
        files: Multipart file payload.

    Returns:
        Successful httpx.Response (2xx).

    Raises:
        httpx.HTTPStatusError: After all retries are exhausted.
    """
    merged_headers = {**_default_headers(), **(headers or {})}
    attempt = 0

    while True:
        response = await client.post(
            url,
            headers=merged_headers,
            data=data,
            json=json,
            files=files,
        )

        if response.status_code != 429 or attempt >= _MAX_RETRIES:
            response.raise_for_status()
            return response

        wait = _BACKOFF_BASE * (2**attempt)
        logger.warning(
            "ElevenLabs rate limit hit (attempt %d/%d). Waiting %.1fs before retry.",
            attempt + 1,
            _MAX_RETRIES,
            wait,
        )
        await asyncio.sleep(wait)
        attempt += 1

        # H5: Rewind any file-like streams in `files` before the next attempt.
        # httpx reads the stream on the first POST; without seeking back to 0
        # subsequent retries would send an empty body.
        if files:
            for _key, file_tuple in files.items():
                if isinstance(file_tuple, (list, tuple)) and len(file_tuple) >= 2:
                    stream = file_tuple[1]
                    if hasattr(stream, "seek"):
                        stream.seek(0)


async def _patch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    json: dict,
) -> httpx.Response:
    """PATCH request with exponential back-off on HTTP 429 (rate limit)."""
    attempt = 0

    while True:
        response = await client.patch(
            url,
            headers={**_default_headers(), "Content-Type": "application/json"},
            json=json,
        )

        if response.status_code != 429 or attempt >= _MAX_RETRIES:
            response.raise_for_status()
            return response

        wait = _BACKOFF_BASE * (2**attempt)
        logger.warning(
            "ElevenLabs rate limit hit on PATCH (attempt %d/%d). Waiting %.1fs.",
            attempt + 1,
            _MAX_RETRIES,
            wait,
        )
        await asyncio.sleep(wait)
        attempt += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_voice_clone(
    audio_file_path: str,
    person_name: str,
) -> VoiceCloneResult:
    """Clone a voice from an audio file using ElevenLabs Instant Voice Clone.

    Uses the /voices/add endpoint (Instant Voice Clone only — never Professional).
    The audio file should be 60–120 seconds of clean, noise-free speech.

    Args:
        audio_file_path: Absolute path to the WAV/MP3 audio recording.
        person_name: Display name used to label the cloned voice in ElevenLabs.

    Returns:
        VoiceCloneResult containing the new voice_id and name.

    Raises:
        FileNotFoundError: If the audio file does not exist.
        httpx.HTTPStatusError: If the ElevenLabs API returns an error.
    """
    if not os.path.isfile(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    logger.info("Creating Instant Voice Clone for '%s' from '%s'.", person_name, audio_file_path)

    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(audio_file_path, "rb") as audio_file:
            mime = "audio/wav" if audio_file_path.lower().endswith(".wav") else "audio/mpeg"
            filename = os.path.basename(audio_file_path)

            response = await _post_with_retry(
                client,
                f"{_BASE_URL}/voices/add",
                files={"files": (filename, audio_file, mime)},
                data={
                    "name": person_name,
                    "description": f"Memory companion voice for {person_name}",
                },
            )

    data = response.json()
    voice_id: str = data["voice_id"]
    logger.info("Voice clone created. voice_id=%s", voice_id)
    return VoiceCloneResult(voice_id=voice_id, name=person_name)


async def upload_knowledge_base_document(
    content_str: str,
    name: str,
) -> str:
    """Upload a plain-text/markdown document as an ElevenLabs knowledge base source.

    The document is truncated to _KB_MAX_CHARS (50 KB) before upload to stay
    within ElevenLabs agent knowledge base size limits.

    Args:
        content_str: Markdown-formatted knowledge base content.
        name: Human-readable name for the knowledge base entry.

    Returns:
        knowledge_base_id string assigned by ElevenLabs.

    Raises:
        httpx.HTTPStatusError: If the API returns an error.
    """
    if len(content_str) > _KB_MAX_CHARS:
        logger.warning(
            "Knowledge base content (%d chars) exceeds %d char limit. Truncating.",
            len(content_str),
            _KB_MAX_CHARS,
        )
        content_str = content_str[:_KB_MAX_CHARS]

    logger.info("Uploading knowledge base document '%s' (%d chars).", name, len(content_str))

    encoded = content_str.encode("utf-8")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await _post_with_retry(
            client,
            f"{_BASE_URL}/convai/knowledge-base/document",
            data={"name": name},
            files={"file": (f"{name}.md", encoded, "text/markdown")},
        )

    data = response.json()
    kb_id: str = data["id"]
    logger.info("Knowledge base uploaded. id=%s", kb_id)
    return kb_id


async def create_conversational_agent(
    voice_id: str,
    kb_id: str,
    person_name: str,
    system_prompt: str | None = None,
) -> str:
    """Create an ElevenLabs Conversational AI agent wired to the cloned voice and knowledge base.

    Args:
        voice_id: ElevenLabs voice_id (from create_voice_clone).
        kb_id: Knowledge base document ID (from upload_knowledge_base_document).
        person_name: Used to personalise the default system prompt if none is provided.
        system_prompt: Optional override system prompt. Defaults to first-person
            memory companion template.

    Returns:
        agent_id string assigned by ElevenLabs.

    Raises:
        httpx.HTTPStatusError: If the API returns an error.
    """
    prompt = system_prompt or _SYSTEM_PROMPT_TEMPLATE.format(person_name=person_name)

    payload: dict = {
        "name": f"{person_name} Memory Companion",
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": prompt,
                    "knowledge_base": [
                        {
                            "type": "file",
                            "id": kb_id,
                        }
                    ],
                },
                "first_message": (
                    f"Hello, I'm here to share some memories with you. "
                    f"What would you like to remember today?"
                ),
                "language": "en",
            },
            "tts": {
                "voice_id": voice_id,
                "model_id": "eleven_turbo_v2_5",
                "stability": 0.75,
                "similarity_boost": 0.85,
            },
            "asr": {
                "quality": "high",
                "user_input_audio_format": "pcm_16000",
            },
        },
    }

    logger.info("Creating conversational agent for '%s'.", person_name)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await _post_with_retry(
            client,
            f"{_BASE_URL}/convai/agents/create",
            json=payload,
        )

    data = response.json()
    agent_id: str = data["agent_id"]
    logger.info("Conversational agent created. agent_id=%s", agent_id)
    return agent_id


async def update_agent_voice(agent_id: str, voice_id: str) -> bool:
    """Update the TTS voice on an existing ElevenLabs conversational agent.

    Useful when re-running the voice clone and needing to push the new
    voice_id to an already-provisioned agent without recreating it.

    Args:
        agent_id: ElevenLabs agent_id to update.
        voice_id: New voice_id to apply.

    Returns:
        True on success, False if the update was rejected (non-2xx after retries).
    """
    payload: dict = {
        "conversation_config": {
            "tts": {
                "voice_id": voice_id,
            }
        }
    }

    logger.info("Updating agent %s with voice_id=%s.", agent_id, voice_id)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await _patch_with_retry(
                client,
                f"{_BASE_URL}/convai/agents/{agent_id}",
                json=payload,
            )
        logger.info("Agent voice updated successfully.")
        return True
    except httpx.HTTPStatusError as exc:
        logger.error("Failed to update agent voice: %s", exc)
        return False


async def get_agent_share_link(agent_id: str) -> str:
    """Return the public shareable widget URL for a conversational agent.

    The ElevenLabs Conversational AI widget is configured via the agent-id
    attribute on <elevenlabs-convai>. The canonical embed URL is constructed
    directly — no API call needed.

    Args:
        agent_id: ElevenLabs agent_id.

    Returns:
        Shareable HTTPS URL string for the agent widget.
    """
    share_url = f"https://elevenlabs.io/convai/agent/{agent_id}"
    logger.info("Share link for agent_id=%s: %s", agent_id, share_url)
    return share_url
