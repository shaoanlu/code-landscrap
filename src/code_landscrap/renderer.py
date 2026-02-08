"""Render persisted artifacts into Markdown, JSON, and HTML bundles."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def render_artifact(
    artifact: dict[str, Any],
    fragments: list[dict[str, Any]],
    output_root: Path,
) -> Path:
    """Write an artifact package to disk and return the output directory.

    Args:
        artifact: Artifact record payload from the database or runtime model.
        fragments: Source fragment records linked to the artifact.
        output_root: Root directory where artifact folders are created.

    Returns:
        The artifact-specific directory containing rendered files.
    """
    artifact_id = artifact["artifact_id"]
    target_dir = output_root / artifact_id
    target_dir.mkdir(parents=True, exist_ok=True)

    md_path = target_dir / "artifact.md"
    json_path = target_dir / "artifact.json"
    html_path = target_dir / "artifact.html"

    markdown = _render_markdown(artifact, fragments)
    md_path.write_text(markdown, encoding="utf-8")

    json_payload = {
        "artifact": artifact,
        "fragments": fragments,
    }
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    html = _render_html(artifact, fragments)
    html_path.write_text(html, encoding="utf-8")

    return target_dir


def _render_markdown(artifact: dict[str, Any], fragments: list[dict[str, Any]]) -> str:
    """Render a human-readable Markdown representation of an artifact."""
    lines = [
        f"# {artifact['output_title']}",
        "",
        f"- Artifact ID: `{artifact['artifact_id']}`",
        f"- Created: `{artifact['created_at']}`",
        f"- Model: `{artifact['model_name']}` ({artifact['generation_mode']})",
        f"- Entropy: `{artifact['entropy']}`",
        "",
        "## Artifact",
        "",
        f"```{artifact['output_language']}",
        artifact["output_code"],
        "```",
        "",
        "## Artist Statement",
        "",
        artifact["output_statement"],
        "",
        "## Transform Notes",
        "",
        artifact["output_notes"],
        "",
        "## Source Fragments",
        "",
    ]

    for idx, fragment in enumerate(fragments, start=1):
        lines.extend(
            [
                f"### Fragment {idx}",
                f"- `{fragment['repo_name']}` `{fragment['commit_hash'][:12]}` `{fragment['file_path']}:{fragment['line_no']}`",
                "",
                f"```{fragment['language']}",
                fragment["content"],
                "```",
                "",
            ]
        )

    return "\n".join(lines)


def _render_html(artifact: dict[str, Any], fragments: list[dict[str, Any]]) -> str:
    """Render artifact HTML by injecting values into the frontend template."""
    meta = (
        f"artifact {_escape_html(artifact['artifact_id'])} | "
        f"model {_escape_html(artifact['model_name'])} "
        f"({_escape_html(artifact['generation_mode'])}) | "
        f"created {_escape_html(artifact['created_at'])}"
    )

    replacements = {
        "TITLE": _escape_html(artifact["output_title"]),
        "META": meta,
        "ARTIFACT_CODE": _escape_html(artifact["output_code"]),
        "STATEMENT": _escape_html_with_breaks(artifact["output_statement"]),
        "NOTES": _escape_html_with_breaks(artifact["output_notes"]),
        "FRAGMENT_BLOCKS": _render_fragment_blocks(fragments),
        "ARTIFACT_ID_ATTR": _escape_html(artifact["artifact_id"]),
        "FRAGMENT_TOTAL": str(len(fragments)),
        "CSS": _load_frontend_asset("artifact.css"),
        "JS": _load_frontend_asset("artifact.js"),
    }

    return _render_template(_load_frontend_asset("artifact.html"), replacements)


def _render_fragment_blocks(fragments: list[dict[str, Any]]) -> str:
    """Build HTML blocks for fragment cards and nearby-context echoes."""
    blocks: list[str] = []
    total_fragments = len(fragments)

    for idx, frag in enumerate(fragments):
        earlier = fragments[idx - 1]["content"] if idx > 0 else frag["content"]
        later = fragments[idx + 1]["content"] if idx + 1 < total_fragments else frag["content"]
        marker = _relative_marker(idx)

        blocks.append(
            "\n".join(
                [
                    f"<article class=\"fragment drift\" data-drift=\"{0.018 + ((idx % 5) * 0.009):.3f}\" data-fragment-index=\"{idx}\">",
                    "<header class=\"fragment-head\">",
                    f"<h3>{_escape_html(frag['file_path'])}:{frag['line_no']}</h3>",
                    (
                        "<p class=\"fragment-meta\">"
                        f"<code>{_escape_html(frag['commit_hash'][:12])}</code> "
                        f"<span class=\"relative-marker\">{marker}</span>"
                        "</p>"
                    ),
                    "</header>",
                    f"<pre><code>{_escape_html(frag['content'])}</code></pre>",
                    "<div class=\"fragment-echo\" aria-hidden=\"true\">",
                    "<p>earlier/later traces</p>",
                    f"<pre><code>{_escape_html(earlier)}</code></pre>",
                    f"<pre><code>{_escape_html(later)}</code></pre>",
                    "</div>",
                    "</article>",
                ]
            )
        )

    return "".join(blocks)


def _render_template(template: str, replacements: dict[str, str]) -> str:
    """Replace ``{{TOKEN}}`` placeholders in a template string."""
    rendered = template
    for token, value in replacements.items():
        rendered = rendered.replace(f"{{{{{token}}}}}", value)
    return rendered


@lru_cache(maxsize=None)
def _load_frontend_asset(filename: str) -> str:
    """Load and cache static template assets from ``templates/``."""
    asset_path = Path(__file__).with_name("templates") / filename
    return asset_path.read_text(encoding="utf-8")


def _relative_marker(index: int) -> str:
    """Return a rotating temporal label used in fragment metadata."""
    options = ("earlier", "later", "not yet")
    return options[index % len(options)]


def _escape_html_with_breaks(value: Any) -> str:
    """Escape HTML-sensitive characters and preserve line breaks."""
    return _escape_html(value).replace("\n", "<br />")


def _escape_html(value: Any) -> str:
    """Escape a value for direct inclusion in HTML text content."""
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
