from __future__ import annotations

import json

from code_landscrap.renderer import (
    _escape_html,
    _escape_html_with_breaks,
    _relative_marker,
    render_artifact,
)


def test_render_artifact_given_payload_when_rendered_then_writes_expected_outputs(
    tmp_path,
    sample_artifact,
    sample_fragments,
) -> None:
    # Given
    output_root = tmp_path / "artifacts"

    # When
    target_dir = render_artifact(sample_artifact, sample_fragments, output_root=output_root)

    # Then
    assert target_dir == output_root / str(sample_artifact["artifact_id"])
    assert (target_dir / "artifact.md").exists()
    assert (target_dir / "artifact.json").exists()
    assert (target_dir / "artifact.html").exists()

    markdown = (target_dir / "artifact.md").read_text(encoding="utf-8")
    assert "# Signal <Residue>" in markdown
    assert "### Fragment 1" in markdown
    assert "1234567890ab" in markdown

    payload = json.loads((target_dir / "artifact.json").read_text(encoding="utf-8"))
    assert payload["artifact"]["artifact_id"] == "artifact123abc"
    assert len(payload["fragments"]) == 2

    html = (target_dir / "artifact.html").read_text(encoding="utf-8")
    assert "{{TITLE}}" not in html
    assert "&lt;hello&gt; &amp; &quot;world&quot;" in html
    assert "Line one<br />Line &lt;two&gt;" in html
    assert 'data-fragment-total="2"' in html


def test_escape_helpers_given_special_text_when_escaped_then_html_is_safe() -> None:
    # Given
    raw = '<tag attr="x">& one\ntwo'

    # When
    escaped = _escape_html(raw)
    escaped_with_breaks = _escape_html_with_breaks(raw)

    # Then
    assert escaped == "&lt;tag attr=&quot;x&quot;&gt;&amp; one\ntwo"
    assert escaped_with_breaks == "&lt;tag attr=&quot;x&quot;&gt;&amp; one<br />two"


def test_relative_marker_given_indexes_when_mapped_then_markers_cycle() -> None:
    # Given
    indexes = [0, 1, 2, 3, 4, 5]

    # When
    markers = [_relative_marker(index) for index in indexes]

    # Then
    assert markers == ["earlier", "later", "not yet", "earlier", "later", "not yet"]
