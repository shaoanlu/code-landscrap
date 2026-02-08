from __future__ import annotations

import json
import sys
import types

import pytest

from code_landscrap.generator import (
    GeminiGenerator,
    _strip_json_fence,
    local_fallback_generate,
    parse_output,
    resolve_gemini_api_key,
)


def test_resolve_gemini_api_key_given_env_and_file_when_resolved_then_env_wins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    # Given
    key_file = tmp_path / "Gemini.md"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")

    # When
    value = resolve_gemini_api_key(key_file=key_file)

    # Then
    assert value == "env-key"


def test_resolve_gemini_api_key_given_only_file_when_resolved_then_file_value_is_used(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    # Given
    key_file = tmp_path / "Gemini.md"
    key_file.write_text("file-key\n", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # When
    value = resolve_gemini_api_key(key_file=key_file)

    # Then
    assert value == "file-key"


def test_resolve_gemini_api_key_given_no_sources_when_resolved_then_none_is_returned(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    # Given
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    missing_file = tmp_path / "missing.md"

    # When
    value = resolve_gemini_api_key(key_file=missing_file)

    # Then
    assert value is None


def test_strip_json_fence_given_fenced_json_when_stripped_then_payload_is_returned() -> None:
    # Given
    raw = '```json\n{"title":"t","language":"python","artifact_code":"x"}\n```'

    # When
    stripped = _strip_json_fence(raw)

    # Then
    assert stripped == '{"title":"t","language":"python","artifact_code":"x"}'


def test_parse_output_given_valid_json_when_parsed_then_schema_model_is_returned() -> None:
    # Given
    raw = json.dumps(
        {
            "title": "Artifact",
            "language": "python",
            "artifact_code": "print('ok')",
            "artist_statement": "statement",
            "transform_notes": "notes",
        }
    )

    # When
    parsed = parse_output(raw)

    # Then
    assert parsed.title == "Artifact"
    assert parsed.language == "python"
    assert parsed.artifact_code == "print('ok')"


def test_parse_output_given_non_json_text_when_parsed_then_fallback_contract_is_used() -> None:
    # Given
    raw = "not-json body"

    # When
    parsed = parse_output(raw)

    # Then
    assert parsed.title == "Untitled Landscrap"
    assert parsed.language == "text"
    assert parsed.artifact_code == raw
    assert "Fallback parser path used." in parsed.transform_notes


def test_parse_output_given_invalid_schema_when_parsed_then_runtime_error_is_raised() -> None:
    # Given
    raw = '{"title":"x","language":"python"}'

    # When
    with pytest.raises(RuntimeError) as excinfo:
        parse_output(raw)

    # Then
    assert "schema validation" in str(excinfo.value)


def test_local_fallback_generate_given_same_seed_when_generated_then_output_is_deterministic(
    sample_fragments,
) -> None:
    # Given
    entropy = 0.4
    seed = 123

    # When
    raw_a, out_a = local_fallback_generate(sample_fragments, entropy=entropy, seed=seed)
    raw_b, out_b = local_fallback_generate(sample_fragments, entropy=entropy, seed=seed)

    # Then
    assert raw_a == raw_b
    assert out_a.model_dump() == out_b.model_dump()
    assert out_a.language == "python"
    assert "Seed=123, entropy=0.40" in out_a.transform_notes


def test_gemini_generator_given_mocked_sdk_when_generated_then_no_real_key_or_network_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("code_landscrap.generator.resolve_gemini_api_key", lambda: "fake-key")

    captured: dict[str, object] = {}

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeModels:
        def generate_content(self, **kwargs: object):
            captured["request"] = kwargs
            return types.SimpleNamespace(text="  mocked-response  ")

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.models = FakeModels()

    fake_google_genai = types.ModuleType("google.genai")
    fake_google_genai.Client = FakeClient
    fake_google_genai.types = types.SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_google_genai

    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_google_genai)

    # When
    generator = GeminiGenerator(model_name="gemini-test")
    result = generator.generate(system_prompt="system prompt", user_prompt="user prompt")

    # Then
    assert result == "mocked-response"
    assert captured["api_key"] == "fake-key"
    request = captured["request"]
    assert isinstance(request, dict)
    assert request["model"] == "gemini-test"
    assert request["contents"] == "user prompt"


def test_gemini_generator_given_missing_key_when_generated_then_runtime_error_is_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("code_landscrap.generator.resolve_gemini_api_key", lambda: None)
    generator = GeminiGenerator(model_name="gemini-test")

    # When
    with pytest.raises(RuntimeError, match="Missing GEMINI_API_KEY"):
        generator.generate(system_prompt="system prompt", user_prompt="user prompt")
