import json
import logging
import time
import re

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Raised when all Gemini API retries are exhausted."""
    pass


def get_gemini_response(prompt, *, parse_json=False, retries=3):
    """
    Central Gemini API wrapper with exponential backoff.

    Args:
        prompt: The text prompt to send to Gemini.
        parse_json: If True, strip markdown fences and parse JSON from response.
        retries: Max number of attempts (default 3).

    Returns:
        str if parse_json=False, dict/list if parse_json=True.

    Raises:
        GeminiError: If all retries fail.
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    last_error = None
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()

            if parse_json:
                return _extract_json(text)
            return text

        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning("Gemini attempt %d failed: %s. Retrying in %ds...", attempt + 1, e, wait)
                time.sleep(wait)
            else:
                logger.error("Gemini failed after %d attempts: %s", retries, e)

    raise GeminiError(f"Gemini API unavailable after {retries} attempts: {last_error}")


def _extract_json(text):
    """Strip markdown code fences and parse JSON from response text."""
    # Remove ```json ... ``` or ``` ... ``` wrappers
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON array or object
    for start_char, end_char in [('[', ']'), ('{', '}')]:
        start = cleaned.find(start_char)
        end = cleaned.rfind(end_char)
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue

    raise GeminiError(f"Could not parse JSON from Gemini response: {cleaned[:200]}")
