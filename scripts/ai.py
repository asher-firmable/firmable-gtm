import base64
import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None


def _using_bifrost() -> bool:
    return bool(os.getenv("BIFROST_BASE_URL") and os.getenv("BIFROST_VIRTUAL_KEY"))


def _resolve_model(model: str) -> str:
    """On Bifrost, swap Claude models for BIFROST_MODEL (e.g. gpt-5.4-mini) if set,
    else add the anthropic/ provider prefix Bifrost needs. Non-Claude models pass through."""
    if not _using_bifrost() or not model.startswith("claude"):
        return model
    return os.getenv("BIFROST_MODEL") or f"anthropic/{model}"


def _get_client():
    global _client
    if _client is None:
        # Route via Bifrost gateway when both BIFROST_* vars are set; otherwise call Anthropic directly
        bifrost_url = os.getenv("BIFROST_BASE_URL")
        bifrost_key = os.getenv("BIFROST_VIRTUAL_KEY")
        if _using_bifrost():
            _client = anthropic.Anthropic(api_key=bifrost_key, base_url=bifrost_url)
        else:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY is not set in .env")
            _client = anthropic.Anthropic(api_key=api_key)
    return _client


def ask_claude(prompt: str, context: str = "", model: str = "claude-sonnet-4-6") -> str:
    client = _get_client()
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    message = client.messages.create(
        model=_resolve_model(model),
        max_tokens=1024,
        messages=[{"role": "user", "content": full_prompt}],
    )
    return message.content[0].text


def ask_claude_with_vision(image_bytes: bytes, prompt: str, model: str = "claude-sonnet-4-6") -> str:
    """Send an image + prompt to Claude Vision. image_bytes should be raw PNG/JPEG bytes."""
    client = _get_client()
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")
    message = client.messages.create(
        model=_resolve_model(model),
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return message.content[0].text
