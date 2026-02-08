from __future__ import annotations

from code_landscrap.prompting import build_system_prompt, build_user_prompt


def test_build_system_prompt_given_no_args_when_called_then_core_sections_exist() -> None:
    # Given
    # No input is required.

    # When
    prompt = build_system_prompt()

    # Then
    assert "## Core LLM Prompt" in prompt
    assert "**Constraints**" in prompt
    assert "**Output Format**" in prompt


def test_build_user_prompt_given_fragments_entropy_seed_when_called_then_prompt_contains_contract_and_lineage(
    sample_fragments,
) -> None:
    # Given
    entropy = 0.55
    seed = 99

    # When
    prompt = build_user_prompt(sample_fragments, entropy=entropy, seed=seed)

    # Then
    assert "Seed: 99" in prompt
    assert "Entropy dial (0=archival, 1=surreal): 0.55" in prompt
    assert '"artifact_code": "string"' in prompt
    assert "Fragment 1" in prompt
    assert "repo: demo-repo" in prompt
    assert "file: src/main.py:10" in prompt
