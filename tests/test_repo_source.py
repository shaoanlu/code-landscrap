from __future__ import annotations

from pathlib import Path

import pytest

from code_landscrap import repo_source


def test_looks_like_git_url_given_various_sources_when_checked_then_expected_values_returned() -> None:
    # Given
    valid_sources = [
        "https://github.com/org/repo.git",
        "http://github.com/org/repo.git",
        "git@github.com:org/repo.git",
        "ssh://git@github.com/org/repo.git",
    ]
    invalid_source = "./local/repo"

    # When
    valid_results = [repo_source.looks_like_git_url(source) for source in valid_sources]
    invalid_result = repo_source.looks_like_git_url(invalid_source)

    # Then
    assert all(valid_results)
    assert invalid_result is False


def test_resolve_repo_source_given_local_git_repo_when_resolved_then_returns_local_mode(tmp_path) -> None:
    # Given
    local_repo = tmp_path / "repo"
    (local_repo / ".git").mkdir(parents=True)

    # When
    resolved, mode = repo_source.resolve_repo_source(str(local_repo), cache_dir=tmp_path / "cache")

    # Then
    assert resolved == local_repo.resolve()
    assert mode == "local"


def test_resolve_repo_source_given_local_non_repo_when_resolved_then_raises_value_error(tmp_path) -> None:
    # Given
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()

    # When
    with pytest.raises(ValueError, match="Directory is not a git repo"):
        repo_source.resolve_repo_source(str(non_repo), cache_dir=tmp_path / "cache")

    # Then
    # ValueError indicates non-git directories are rejected.


def test_resolve_repo_source_given_missing_remote_cache_when_resolved_then_clones_repo(tmp_path, monkeypatch) -> None:
    # Given
    source = "https://github.com/example/sample-repo.git"
    cache_dir = tmp_path / "cache"
    commands: list[list[str]] = []

    def fake_run_cmd(cmd: list[str]) -> str:
        commands.append(cmd)
        if cmd[:3] == ["git", "clone", "--quiet"]:
            Path(cmd[-1]).mkdir(parents=True, exist_ok=True)
        return ""

    monkeypatch.setattr(repo_source, "run_cmd", fake_run_cmd)

    # When
    resolved, mode = repo_source.resolve_repo_source(source, cache_dir=cache_dir, update_remote=True)

    # Then
    assert mode == "cloned"
    assert resolved.exists()
    assert commands[0][:3] == ["git", "clone", "--quiet"]


def test_resolve_repo_source_given_cached_remote_when_update_enabled_then_fetches_and_pulls(tmp_path, monkeypatch) -> None:
    # Given
    source = "git@github.com:example/sample-repo.git"
    cache_dir = tmp_path / "cache"
    target = cache_dir / repo_source.build_cache_repo_name(source)
    target.mkdir(parents=True)
    commands: list[list[str]] = []

    def fake_run_cmd(cmd: list[str]) -> str:
        commands.append(cmd)
        if "rev-parse" in cmd:
            return "origin/main\n"
        return ""

    monkeypatch.setattr(repo_source, "run_cmd", fake_run_cmd)

    # When
    resolved, mode = repo_source.resolve_repo_source(source, cache_dir=cache_dir, update_remote=True)

    # Then
    assert mode == "updated"
    assert resolved == target.resolve()
    assert any("fetch" in cmd for cmd in commands)
    assert any("checkout" in cmd for cmd in commands)
    assert any(cmd[-2:] == ["origin", "main"] for cmd in commands if "pull" in cmd)


def test_build_cache_repo_name_given_same_source_when_called_then_name_is_stable() -> None:
    # Given
    source = "https://github.com/example/sample-repo.git"

    # When
    first = repo_source.build_cache_repo_name(source)
    second = repo_source.build_cache_repo_name(source)

    # Then
    assert first == second
    assert first.startswith("sample-repo-")
    assert len(first) == len("sample-repo-") + 10
