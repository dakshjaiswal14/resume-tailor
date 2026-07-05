"""
Gemini LLM client — thin wrapper around the Google GenAI SDK.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root once
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in root .env")

# Lazy import so startup doesn't fail if google-genai isn't installed yet
_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def clean_model_output(raw: str) -> str:
    """Strip markdown fences from LLM output."""
    raw = raw.strip()

    if raw.startswith("```json"):
        raw = raw[len("```json"):].strip()
    elif raw.startswith("```"):
        raw = raw[len("```"):].strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    return raw


def _fix_json_text_field(raw: str) -> dict | None:
    """
    Many LLMs emit JSON with raw newlines inside string values, like:
        {"text": "Line 1\nLine 2\nLine 3"}
    which is invalid JSON.  This extracts the text content by finding
    the "text" key and capturing everything until the final closing "}.
    """
    import re as _re

    # Find the start of the text value:  "text": "
    start_match = _re.search(r'"text"\s*:\s*"', raw)
    if not start_match:
        return None

    content_start = start_match.end()

    # Find the end — the final "} at the end of the string
    # Search backwards for "} or just }
    end_match = _re.search(r'"\s*\}\s*$', raw[content_start:])
    if not end_match:
        # Try just } at end
        end_match = _re.search(r'\}\s*$', raw[content_start:])
    if end_match:
        text = raw[content_start:content_start + end_match.start()]
        return {"text": text}

    return None


def generate_json_response(prompt: str, temperature: float = 0.3) -> dict | list:
    """
    Send `prompt` to Gemini and parse the response as JSON.
    Returns a dict or list depending on the expected output shape.
    """
    client = _get_client()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": temperature,
            },
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}")

    if not response.text:
        raise ValueError("Empty response from Gemini")

    raw = clean_model_output(response.text)

    # Try standard JSON parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try fixing malformed JSON with raw newlines in text field
    text_result = _fix_json_text_field(raw)
    if text_result is not None:
        return text_result

    raise ValueError(
        f"Failed to parse Gemini JSON response\n"
        f"Raw output (first 500 chars):\n{raw[:500]}"
    )
