from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from code_landscrap.models import ArtifactRecord, Fragment


@pytest.fixture
def sample_fragments() -> list[dict[str, object]]:
    return [
        {
            "id": 1,
            "repo_path": "/tmp/repo",
            "repo_name": "demo-repo",
            "commit_hash": "1234567890abcdef1234567890abcdef12345678",
            "commit_author": "alice",
            "commit_timestamp": "2026-01-01T00:00:00+00:00",
            "file_path": "src/main.py",
            "language": "python",
            "line_no": 10,
            "content": "def old_logic(x):\n    return x + 1",
        },
        {
            "id": 2,
            "repo_path": "/tmp/repo",
            "repo_name": "demo-repo",
            "commit_hash": "abcdef1234567890abcdef1234567890abcdef12",
            "commit_author": "bob",
            "commit_timestamp": "2026-01-02T00:00:00+00:00",
            "file_path": "src/util.py",
            "language": "python",
            "line_no": 42,
            "content": "class Echo:\n    pass",
        },
    ]


@pytest.fixture
def sample_artifact() -> dict[str, object]:
    return {
        "artifact_id": "artifact123abc",
        "created_at": "2026-01-03T00:00:00+00:00",
        "seed": 99,
        "entropy": 0.42,
        "source_repo": "demo-repo",
        "model_name": "gemini-test",
        "generation_mode": "local",
        "prompt_text": "prompt body",
        "raw_response": "{}",
        "output_title": "Signal <Residue>",
        "output_language": "python",
        "output_code": 'print("<hello> & \\"world\\"")',
        "output_statement": "Line one\nLine <two>",
        "output_notes": "Note & track",
    }


@pytest.fixture
def fragment_model() -> Fragment:
    return Fragment(
        repo_path="/tmp/repo",
        repo_name="demo-repo",
        commit_hash="a" * 40,
        commit_author="alice",
        commit_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        file_path="src/app.py",
        language="python",
        line_no=7,
        content="return old_value",
    )


@pytest.fixture
def artifact_record_model() -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id="artifact0001",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        seed=1234,
        entropy=0.33,
        source_repo="demo-repo",
        model_name="gemini-test",
        generation_mode="local",
        prompt_text="prompt",
        raw_response='{"title":"x"}',
        output_title="Local Landscrap Study",
        output_language="python",
        output_code="print('hi')",
        output_statement="statement",
        output_notes="notes",
    )
