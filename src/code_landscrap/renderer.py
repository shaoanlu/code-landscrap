from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_artifact(
    artifact: dict[str, Any],
    fragments: list[dict[str, Any]],
    output_root: Path,
) -> Path:
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
    fragment_blocks = []
    for frag in fragments:
        fragment_blocks.append(
            "\n".join(
                [
                    "<article class='fragment'>",
                    f"<h3>{frag['file_path']}:{frag['line_no']}</h3>",
                    f"<p><code>{frag['commit_hash'][:12]}</code></p>",
                    f"<pre><code>{_escape_html(frag['content'])}</code></pre>",
                    "</article>",
                ]
            )
        )

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{_escape_html(artifact['output_title'])}</title>
  <style>
    :root {{
      --bg-a: #f8f5ef;
      --bg-b: #ece4d8;
      --ink: #201911;
      --muted: #6f665a;
      --card: rgba(255,255,255,0.74);
      --line: #d6c9b7;
    }}
    body {{
      margin: 0;
      font-family: Georgia, 'Times New Roman', serif;
      color: var(--ink);
      background: radial-gradient(circle at 10% 10%, var(--bg-a), var(--bg-b));
      line-height: 1.5;
    }}
    main {{ max-width: 980px; margin: 2rem auto; padding: 0 1rem 4rem; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 1rem 1.1rem; margin-bottom: 1rem; }}
    h1, h2 {{ letter-spacing: 0.02em; }}
    code, pre {{ font-family: 'Courier New', monospace; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
    .meta {{ color: var(--muted); font-size: 0.95rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.8rem; }}
  </style>
</head>
<body>
  <main>
    <section class=\"card\">
      <h1>{_escape_html(artifact['output_title'])}</h1>
      <p class=\"meta\">Artifact `{_escape_html(artifact['artifact_id'])}` | Model `{_escape_html(artifact['model_name'])}` ({_escape_html(artifact['generation_mode'])})</p>
      <pre><code>{_escape_html(artifact['output_code'])}</code></pre>
    </section>
    <section class=\"card\">
      <h2>Statement</h2>
      <p>{_escape_html(artifact['output_statement'])}</p>
      <h2>Transform Notes</h2>
      <p>{_escape_html(artifact['output_notes'])}</p>
    </section>
    <section class=\"card\">
      <h2>Fragments</h2>
      <div class=\"grid\">
        {''.join(fragment_blocks)}
      </div>
    </section>
  </main>
</body>
</html>
"""


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
