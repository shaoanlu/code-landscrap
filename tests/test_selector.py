from __future__ import annotations

import random

from code_landscrap.selector import _score_fragment, select_fragments


def test_score_fragment_given_blank_and_neutral_input_when_scored_then_floor_and_baseline_weights_are_returned() -> None:
    # Given
    blank = "   "
    punctuation_only = "{}"

    # When
    blank_score = _score_fragment(blank)
    punctuation_score = _score_fragment(punctuation_only)

    # Then
    assert blank_score == 0.01
    assert punctuation_score == 1.0


def test_select_fragments_given_same_rng_seed_when_selected_then_result_is_reproducible() -> None:
    # Given
    candidates = [
        {"id": 1, "content": "def a(x): return x"},
        {"id": 2, "content": "const a = (x) => x + 1"},
        {"id": 3, "content": "SELECT id FROM artifacts;"},
        {"id": 4, "content": "// comment block with context"},
    ]

    # When
    chosen_a = select_fragments(candidates, count=3, entropy=0.7, rng=random.Random(42))
    chosen_b = select_fragments(candidates, count=3, entropy=0.7, rng=random.Random(42))

    # Then
    assert [item["id"] for item in chosen_a] == [item["id"] for item in chosen_b]
    assert len(chosen_a) == 3
    assert len({item["id"] for item in chosen_a}) == 3


def test_select_fragments_given_out_of_bounds_entropy_and_count_when_selected_then_values_are_clamped() -> None:
    # Given
    candidates = [{"id": 1, "content": "x = 1"}, {"id": 2, "content": "y = 2"}]

    # When
    chosen = select_fragments(candidates, count=10, entropy=-1.5, rng=random.Random(1))

    # Then
    assert len(chosen) == 2
