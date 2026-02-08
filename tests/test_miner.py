from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from code_landscrap import miner


def test_infer_language_given_known_and_unknown_extensions_when_inferred_then_expected_language_returns() -> None:
    # Given
    known = "src/app.py"
    unknown = "docs/notes.custom"

    # When
    known_language = miner._infer_language(known)
    unknown_language = miner._infer_language(unknown)

    # Then
    assert known_language == "python"
    assert unknown_language == "text"


def test_is_interesting_given_various_lines_when_checked_then_only_high_signal_lines_pass() -> None:
    # Given
    high_signal = "def compute(value):"
    punctuation_only = ";;;"
    too_short = "ab"

    # When
    high_signal_result = miner._is_interesting(high_signal)
    punctuation_result = miner._is_interesting(punctuation_only)
    short_result = miner._is_interesting(too_short)

    # Then
    assert high_signal_result is True
    assert punctuation_result is False
    assert short_result is False


def test_list_commits_given_git_log_output_when_parsed_then_commits_are_typed_and_ordered(monkeypatch) -> None:
    # Given
    log_output = (
        "abc123\x1fAlice\x1f2026-01-01T01:02:03Z\n"
        "def456\x1fBob\x1f2026-01-02T04:05:06Z\n"
    )
    monkeypatch.setattr(miner, "_run_git", lambda _repo_path, _args: log_output)

    # When
    commits = miner.list_commits(repo_path=Path("/tmp/repo"))

    # Then
    assert len(commits) == 2
    assert commits[0][0] == "abc123"
    assert commits[1][1] == "Bob"
    assert commits[0][2].tzinfo is not None


def test_extract_deleted_fragments_given_diff_output_when_extracted_then_deleted_interesting_lines_are_returned(
    tmp_path,
    monkeypatch,
) -> None:
    # Given
    repo_path = tmp_path / "demo-repo"
    repo_path.mkdir()

    commit_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(miner, "list_commits", lambda *_args, **_kwargs: [("abc123", "Alice", commit_time)])

    diff_output = "\n".join(
        [
            "diff --git a/src/app.py b/src/app.py",
            "--- a/src/app.py",
            "+++ b/src/app.py",
            "@@ -10,3 +10,0 @@",
            "-def old_logic(x):",
            "-    return x + 1",
            "-{",
        ]
    )
    monkeypatch.setattr(miner, "_run_git", lambda *_args, **_kwargs: diff_output)

    progress_events: list[tuple[int, int, int]] = []

    # When
    fragments = miner.extract_deleted_fragments(
        repo_path=repo_path,
        max_commits=10,
        max_fragments_per_commit=10,
        progress_callback=lambda done, total, count: progress_events.append((done, total, count)),
    )

    # Then
    assert len(fragments) == 2
    assert fragments[0].file_path == "src/app.py"
    assert fragments[0].line_no == 10
    assert fragments[1].line_no == 11
    assert fragments[0].content == "def old_logic(x):"
    assert progress_events == [(1, 1, 2)]
