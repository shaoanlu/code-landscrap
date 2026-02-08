"""Utilities for calling the model backend and normalizing generated output."""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_landscrap.models import ArtifactOutput

DEFAULT_GEMINI_KEY_FILE = Path(".api_keys/Gemini.md")


def resolve_gemini_api_key(key_file: Path = DEFAULT_GEMINI_KEY_FILE) -> str | None:
    """Resolve the Gemini API key from environment or fallback file.

    Resolution order:
    1. ``GEMINI_API_KEY`` environment variable.
    2. ``key_file`` plaintext contents.

    Args:
        key_file: Optional fallback file containing only the API key.

    Returns:
        The non-empty API key when found, otherwise ``None``.
    """
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if api_key:
        return api_key

    if key_file.exists():
        fallback_key = key_file.read_text(encoding="utf-8").strip()
        if fallback_key:
            return fallback_key

    return None


class GeminiGenerator:
    """Thin adapter around Google GenAI content generation."""

    def __init__(self, model_name: str):
        """Create a generator bound to a model name."""
        self.model_name = model_name

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate JSON-formatted artifact content from prompts.

        Args:
            system_prompt: System instruction text that defines behavior.
            user_prompt: Prompt payload containing source fragments and rules.

        Returns:
            Raw text response from Gemini.

        Raises:
            ValueError: If either prompt is blank.
            RuntimeError: If credentials are missing or response text is empty.
        """
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("System prompt must be a non-empty string.")
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError("User prompt must be a non-empty string.")

        api_key = resolve_gemini_api_key()
        if not api_key:
            raise RuntimeError("Missing GEMINI_API_KEY (set env var or .api_keys/Gemini.md)")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=self.model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=1.0,
                top_p=0.95,
                response_mime_type="application/json",
            ),
        )

        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        return text


def _strip_json_fence(text: str) -> str:
    """Remove a surrounding Markdown JSON code fence when present."""
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()


def parse_output(raw: str) -> ArtifactOutput:
    """Parse model output into an ``ArtifactOutput`` value.

    This parser tolerates fenced JSON and can recover from plain-text output by
    synthesizing a minimal fallback payload.

    Args:
        raw: Raw model response text.

    Returns:
        Parsed and schema-validated artifact output.

    Raises:
        RuntimeError: If parsed data cannot satisfy the schema.
    """
    candidate = _strip_json_fence(raw)
    data: dict[str, Any]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        # Minimal fallback if model returns plain text.
        data = {
            "title": "Untitled Landscrap",
            "language": "text",
            "artifact_code": raw,
            "artist_statement": "Generated without strict JSON contract.",
            "transform_notes": "Fallback parser path used.",
        }

    try:
        return ArtifactOutput.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError(f"Model output failed schema validation: {exc}") from exc


def local_fallback_generate(
    fragments: list[dict[str, Any]],
    entropy: float,
    seed: int,
) -> tuple[str, ArtifactOutput]:
    """Produce an artifact deterministically without external model calls.

    Args:
        fragments: Candidate fragments selected for generation.
        entropy: Generation chaos level in ``[0, 1]``.
        seed: Seed used for deterministic shuffling.

    Returns:
        A tuple of:
        1. Serialized JSON text matching the output contract.
        2. Parsed ``ArtifactOutput`` model.
    """
    rng = random.Random(seed)
    pool = [fragment["content"].strip() for fragment in fragments if fragment["content"].strip()]
    rng.shuffle(pool)

    keep = max(6, int(len(pool) * (0.35 + (entropy * 0.35))))
    selected = pool[:keep]

    stitched = "\n".join(selected)
    statement = (
        "This piece was generated in local fallback mode by permuting deleted code strata "
        "without external inference."
    )

    output = ArtifactOutput(
        title="Local Landscrap Study",
        language=fragments[0]["language"] if fragments else "text",
        artifact_code=stitched,
        artist_statement=statement,
        transform_notes=f"Seed={seed}, entropy={entropy:.2f}, fragments={len(fragments)}",
    )

    return json.dumps(output.model_dump(), ensure_ascii=False), output
