import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set in .env")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def ask_claude(prompt: str, context: str = "", model: str = "claude-sonnet-4-6") -> str:
    client = _get_client()
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": full_prompt}],
    )
    return message.content[0].text
