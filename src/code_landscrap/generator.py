from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_landscrap.models import ArtifactOutput


class GeminiGenerator:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("System prompt must be a non-empty string.")
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError("User prompt must be a non-empty string.")

        # api_key = os.getenv("GEMINI_API_KEY")
        key_file = ".api_keys/Gemini.md"
        path = Path(key_file)
        if path.exists():
            api_key = path.read_text(encoding="utf-8").strip()
        else:
            raise FileNotFoundError(key_file)
        if not api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")

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
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()


def parse_output(raw: str) -> ArtifactOutput:
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
