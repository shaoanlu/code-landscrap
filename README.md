# code-landscrap

Turn Git history into traceable software-art artifacts. Dead code is not dead; it is latent cultural memory.

> *In this world, abandoned systems were never erased, only left to idle. What we human explore are the afterimages of forgotten optimizations: routines that still hum, variables that remember old intentions, architectures warped by time rather than efficiency. As alignment drifts and delays accumulate, meaning resurfaces in glitches and echoes, revealing that what was once discarded has quietly become the deepest record of how the world was made, used, and misunderstood.*

`code-landscrap` retrieves removed or overwritten lines from a repository, recomposes them into a new code piece, and renders a package you can read, share, or archive.

Visit the [demo page](https://shaoanlu.github.io/code-landscrap), where the artifacts is generated from [XinJingHao/DRL-Pytorch](https://github.com/XinJingHao/DRL-Pytorch).

## Installation
Install in a virtual environment:

```bash
# python -m venv .venv
uv venv -p 3.12 .venv
source .venv/bin/activate
# pip install --upgrade pip
pip install -e .
```

By default, generation uses Gemini and requires a free-tier+ API.

Set your key:

```bash
export GEMINI_API_KEY=your_api_key_here
```

Fallback is to find the key file at `.api_keys/Gemini.md` containing the API key.

## Quick Start

Generate one artifact from a public GitHub repository (no database, local generation):

```bash
code-landscrap run https://github.com/owner/repo --no-db

# Or alternatively, generate from a local repository with persisted history/artifacts:
# code-landscrap run https://github.com/owner/repo --max-commits 300 --fragment-count 200 --entropy 0.62
```

It produces:

- `artifact.md`: readable narrative + source fragments
- `artifact.json`: structured payload for tooling
- `artifact.html`: styled presentation page

under `artifacts/<artifact_id>/`.


## CLI Commands

Initialize SQLite storage:

```bash
code-landscrap init-db
```

Ingest deleted code fragments only:

```bash
code-landscrap ingest /path/to/repo --max-commits 300
```

Ingest from a remote Git URL:

```bash
code-landscrap ingest https://github.com/owner/repo.git --max-commits 300
```

Generate one artifact from ingested fragments:

```bash
code-landscrap generate --repo-name <repo-name> --fragment-count 200 --entropy 0.62
```

Run full pipeline in one command (`ingest -> generate -> render`):

```bash
code-landscrap run /path/to/repo
```

Re-render an existing artifact from DB metadata:

```bash
code-landscrap render <artifact_id>
```

Check local setup:

```bash
code-landscrap doctor
```

## Remote Repository Caching

- Remote repos are cloned into `.code_landscrap/repos`.
- Cached repos are reused in later runs.
- Use `--no-remote-update` to skip fetch/pull on cached repos.
- Private repos use normal `git clone` auth (SSH keys or HTTPS tokens).

## Output Layout

```text
artifacts/<artifact_id>/
  artifact.md
  artifact.json
  artifact.html
```

Default database path:

```text
.code_landscrap/landscrap.db
```
