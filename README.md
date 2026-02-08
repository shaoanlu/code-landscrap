# code-landscrap

`code-landscrap` turns discarded git history into software-art artifacts.

> Dead code is not dead; it is latent cultural memory.

The workflow:
1. Mine deleted/overwritten lines from commit diffs.
2. Curate a random fragment bundle with a controllable entropy dial.
3. Ask Gemini to permute/recompose fragments into a meaningful code piece.
4. Render a traceable artifact package (`artifact.md`, `artifact.json`, `artifact.html`).

## Install

```bash
# python -m venv .venv
uv venv -p 3.12 .venv
source .venv/bin/activate
# pip install --upgrade pip
pip install -e .
```

## Environment

Set `GEMINI_API_KEY` to enable external LLM generation.

```bash
export GEMINI_API_KEY=your_api_key_here
```

If the key is missing or Gemini is unavailable, `generate` falls back to a local permutation mode.

## CLI

Initialize storage:

```bash
code-landscrap init-db
```

Ingest deleted code from a repo:

```bash
code-landscrap ingest /path/to/repo --max-commits 300
```

Ingest directly from a public GitHub repo URL:

```bash
code-landscrap ingest https://github.com/owner/repo.git --max-commits 300
Using repo: <path/xxx/yyy/zzz>/code-landscrap/.code_landscrap/repos/<repo_name> (cloned)
Ingest complete. repo=<repo_name> extracted=211 inserted=211 db=.code_landscrap/landscrap.db
```

Remote repos are cloned into `.code_landscrap/repos` and reused. Use `--no-remote-update` to skip fetch/pull on cached repos.

Private repos require normal git auth (SSH key or HTTPS token), same as `git clone`.

Generate one artifact:

```bash
code-landscrap generate --repo-name <repo-name> --fragment-count 20 --entropy 0.62
```

Force local generation:

```bash
code-landscrap generate --local-only
```

Re-render a saved artifact:

```bash
code-landscrap render <artifact_id>
```

Health check:

```bash
code-landscrap doctor
```

## Output Structure

Generated artifacts are saved in:

```text
artifacts/<artifact_id>/
  artifact.md
  artifact.json
  artifact.html
```

The database defaults to:

```text
.code_landscrap/landscrap.db
```
