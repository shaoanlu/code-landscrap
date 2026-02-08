"""Typer-based CLI for mining, generating, and rendering code artifacts."""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from code_landscrap.generator import (
    GeminiGenerator,
    local_fallback_generate,
    parse_output,
    resolve_gemini_api_key,
)
from code_landscrap.miner import extract_deleted_fragments
from code_landscrap.models import ArtifactRecord, Fragment
from code_landscrap.prompting import build_system_prompt, build_user_prompt
from code_landscrap.repo_source import resolve_repo_source
from code_landscrap.renderer import render_artifact
from code_landscrap.selector import select_fragments
from code_landscrap.store import Store

app = typer.Typer(add_completion=False, help="code-landscrap: reconstruct discarded code into art artifacts")

DEFAULT_DB_PATH = Path(".code_landscrap/landscrap.db")
DEFAULT_REPO_CACHE_DIR = Path(".code_landscrap/repos")
DEFAULT_OUTPUT_ROOT = Path("artifacts")


def _echo_step(step: int, total: int, message: str) -> None:
    """Print a normalized progress step line."""
    typer.echo(f"[{step}/{total}] {message}")


def _echo_mining_progress(done: int, total: int, fragments: int) -> None:
    """Print incremental mining progress from the git extractor callback."""
    percent = int((done / total) * 100) if total else 100
    typer.echo(f"    mining commits... {done}/{total} ({percent}%) fragments={fragments}")


def _fragment_to_candidate(fragment: Fragment, row_id: int) -> dict[str, Any]:
    """Convert a ``Fragment`` model into generator candidate payload shape."""
    return {
        "id": row_id,
        "repo_path": fragment.repo_path,
        "repo_name": fragment.repo_name,
        "commit_hash": fragment.commit_hash,
        "commit_author": fragment.commit_author,
        "commit_timestamp": fragment.commit_timestamp.isoformat(),
        "file_path": fragment.file_path,
        "language": fragment.language,
        "line_no": fragment.line_no,
        "content": fragment.content,
    }


def _build_artifact_record(
    *,
    candidates: list[dict[str, Any]],
    fragment_count: int,
    entropy: float,
    seed: int | None,
    model_name: str,
    local_only: bool,
    source_repo: str | None,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[ArtifactRecord, list[dict[str, Any]]]:
    """Generate one artifact record and return selected fragment lineage.

    The function handles selection, prompt construction, generation (Gemini or
    local fallback), and record assembly.
    """
    if not candidates:
        raise typer.BadParameter("No fragments found. Run ingest first.")

    seed_value = seed if seed is not None else random.SystemRandom().randint(1, 2**31 - 1)
    rng = random.Random(seed_value)

    if progress_callback:
        progress_callback("selecting candidate fragments")
    chosen = select_fragments(candidates, count=fragment_count, entropy=entropy, rng=rng)
    if not chosen:
        raise typer.BadParameter("Unable to select fragments from current dataset.")

    if progress_callback:
        progress_callback("building prompts")
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(chosen, entropy=entropy, seed=seed_value)

    raw_response: str
    output = None
    generation_mode = "gemini"

    if local_only:
        if progress_callback:
            progress_callback("running local generator")
        raw_response, output = local_fallback_generate(chosen, entropy=entropy, seed=seed_value)
        generation_mode = "local"
    else:
        if progress_callback:
            progress_callback(f"calling model {model_name}")
        generator = GeminiGenerator(model_name=model_name)
        raw_response = generator.generate(system_prompt=system_prompt, user_prompt=user_prompt)
        output = parse_output(raw_response)

    record = ArtifactRecord(
        artifact_id=uuid.uuid4().hex[:12],
        created_at=datetime.now(timezone.utc),
        seed=seed_value,
        entropy=entropy,
        source_repo=source_repo or chosen[0]["repo_name"],
        model_name=model_name,
        generation_mode=generation_mode,
        prompt_text=user_prompt,
        raw_response=raw_response,
        output_title=output.title,
        output_language=output.language,
        output_code=output.artifact_code,
        output_statement=output.artist_statement,
        output_notes=output.transform_notes,
    )

    return record, chosen


def _record_to_render_payload(record: ArtifactRecord) -> dict[str, Any]:
    """Convert a record model to JSON-serializable renderer input."""
    return record.model_dump(mode="json")


@app.command("init-db")
def init_db(
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="SQLite database path"),
) -> None:
    """Initialize the SQLite database schema."""
    store = Store(db_path)
    store.init_db()
    typer.echo(f"DB initialized: {db_path}")


@app.command("ingest")
def ingest(
    source: str = typer.Argument(..., help="Local git repo path or git URL"),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="SQLite database path"),
    max_commits: int = typer.Option(200, help="Max commits to inspect"),
    max_fragments_per_commit: int = typer.Option(80, help="Cap extracted fragments per commit"),
    repo_cache_dir: Path = typer.Option(
        DEFAULT_REPO_CACHE_DIR, "--repo-cache-dir", help="Cache directory for cloned remote repos"
    ),
    no_remote_update: bool = typer.Option(
        False, "--no-remote-update", help="Do not fetch/pull when using cached remote repos"
    ),
) -> None:
    """Mine deleted fragments from a repository and store them in SQLite."""
    _echo_step(1, 4, "Initializing storage")
    store = Store(db_path)
    store.init_db()

    _echo_step(2, 4, "Resolving source repository")
    try:
        repo_path, source_mode = resolve_repo_source(
            source=source,
            cache_dir=repo_cache_dir,
            update_remote=not no_remote_update,
        )
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Using repo: {repo_path} ({source_mode})")

    _echo_step(3, 4, "Mining deleted fragments from git history")
    fragments = extract_deleted_fragments(
        repo_path=repo_path,
        max_commits=max_commits,
        max_fragments_per_commit=max_fragments_per_commit,
        progress_callback=_echo_mining_progress,
    )

    _echo_step(4, 4, "Persisting fragments")
    inserted = store.insert_fragments(fragments)
    typer.echo(
        f"Ingest complete. repo={repo_path.name} extracted={len(fragments)} inserted={inserted} db={db_path}"
    )


@app.command("generate")
def generate(
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="SQLite database path"),
    repo_name: str | None = typer.Option(None, help="Optional repo filter"),
    fragment_count: int = typer.Option(200, help="Fragments per piece"),
    entropy: float = typer.Option(0.55, min=0.0, max=1.0, help="0 archival -> 1 surreal"),
    seed: int | None = typer.Option(None, help="Random seed"),
    model_name: str = typer.Option("gemini-3-flash-preview", help="Gemini model name"),
    output_root: Path = typer.Option(DEFAULT_OUTPUT_ROOT, help="Artifact output directory"),
    local_only: bool = typer.Option(False, help="Skip Gemini and force local fallback"),
) -> None:
    """Generate and persist one artifact from previously ingested fragments."""
    _echo_step(1, 4, "Loading fragments from storage")
    store = Store(db_path)
    store.init_db()

    candidates = store.fetch_candidate_fragments(repo_name=repo_name, limit=max(500, fragment_count * 60))
    _echo_step(2, 4, "Generating artifact content")
    record, chosen = _build_artifact_record(
        candidates=candidates,
        fragment_count=fragment_count,
        entropy=entropy,
        seed=seed,
        model_name=model_name,
        local_only=local_only,
        source_repo=repo_name,
        progress_callback=lambda msg: typer.echo(f"    {msg}"),
    )

    _echo_step(3, 4, "Saving artifact lineage")
    fragment_ids = [int(item["id"]) for item in chosen]
    store.save_artifact(record, fragment_ids)

    saved = store.get_artifact(record.artifact_id)
    linked = store.get_artifact_fragments(record.artifact_id)
    if not saved:
        raise RuntimeError("Artifact insert failed unexpectedly")

    _echo_step(4, 4, "Rendering artifact package")
    out_dir = render_artifact(saved, linked, output_root=output_root)
    typer.echo(
        "Artifact generated. "
        f"id={record.artifact_id} mode={record.generation_mode} seed={record.seed} path={out_dir}"
    )


@app.command("run")
def run(
    source: str = typer.Argument(..., help="Local git repo path or git URL"),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="SQLite database path"),
    max_commits: int = typer.Option(100, help="Max commits to inspect"),
    max_fragments_per_commit: int = typer.Option(80, help="Cap extracted fragments per commit"),
    repo_cache_dir: Path = typer.Option(
        DEFAULT_REPO_CACHE_DIR, "--repo-cache-dir", help="Cache directory for cloned remote repos"
    ),
    no_remote_update: bool = typer.Option(
        False, "--no-remote-update", help="Do not fetch/pull when using cached remote repos"
    ),
    repo_name: str | None = typer.Option(None, help="Optional repo filter at generation time"),
    fragment_count: int = typer.Option(200, help="Fragments per piece"),
    entropy: float = typer.Option(0.55, min=0.0, max=1.0, help="0 archival -> 1 surreal"),
    seed: int | None = typer.Option(None, help="Random seed"),
    model_name: str = typer.Option("gemini-3-flash-preview", help="Gemini model name"),
    output_root: Path = typer.Option(DEFAULT_OUTPUT_ROOT, help="Artifact output directory"),
    local_only: bool = typer.Option(False, help="Skip Gemini and force local fallback"),
    no_db: bool = typer.Option(False, "--no-db", help="Do not persist fragments/artifacts to SQLite"),
) -> None:
    """Run ingest and generate in one flow, with optional no-database mode."""
    total_steps = 6

    _echo_step(1, total_steps, "Resolving source repository")
    try:
        repo_path, source_mode = resolve_repo_source(
            source=source,
            cache_dir=repo_cache_dir,
            update_remote=not no_remote_update,
        )
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Using repo: {repo_path} ({source_mode})")

    _echo_step(2, total_steps, "Mining deleted fragments from git history")
    fragments = extract_deleted_fragments(
        repo_path=repo_path,
        max_commits=max_commits,
        max_fragments_per_commit=max_fragments_per_commit,
        progress_callback=_echo_mining_progress,
    )
    if not fragments:
        raise typer.BadParameter("No usable deleted fragments found in the selected history range.")

    store: Store | None = None
    effective_repo_name = repo_name or repo_path.name
    candidates: list[dict[str, Any]]

    _echo_step(3, total_steps, "Preparing candidate pool")
    if no_db:
        typer.echo("    --no-db enabled: using in-memory fragments for this run only")
        candidates = [_fragment_to_candidate(fragment, row_id=index + 1) for index, fragment in enumerate(fragments)]
    else:
        store = Store(db_path)
        store.init_db()
        inserted = store.insert_fragments(fragments)
        typer.echo(f"    persisted fragments: extracted={len(fragments)} inserted={inserted}")
        candidates = store.fetch_candidate_fragments(
            repo_name=effective_repo_name,
            limit=max(500, fragment_count * 60),
        )

    _echo_step(4, total_steps, "Generating artifact content")
    record, chosen = _build_artifact_record(
        candidates=candidates,
        fragment_count=fragment_count,
        entropy=entropy,
        seed=seed,
        model_name=model_name,
        local_only=local_only,
        source_repo=effective_repo_name,
        progress_callback=lambda msg: typer.echo(f"    {msg}"),
    )

    _echo_step(5, total_steps, "Persisting artifact metadata")
    linked_fragments = chosen
    if store:
        fragment_ids = [int(item["id"]) for item in chosen]
        store.save_artifact(record, fragment_ids)
        saved = store.get_artifact(record.artifact_id)
        if not saved:
            raise RuntimeError("Artifact insert failed unexpectedly")
        linked_fragments = store.get_artifact_fragments(record.artifact_id)
        render_input = saved
    else:
        typer.echo("    --no-db enabled: skipping artifact persistence")
        render_input = _record_to_render_payload(record)

    _echo_step(6, total_steps, "Rendering artifact package")
    out_dir = render_artifact(render_input, linked_fragments, output_root=output_root)
    typer.echo(
        "Run complete. "
        f"id={record.artifact_id} mode={record.generation_mode} seed={record.seed} path={out_dir}"
    )


@app.command("render")
def render(
    artifact_id: str = typer.Argument(..., help="Artifact ID from database"),
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="SQLite database path"),
    output_root: Path = typer.Option(DEFAULT_OUTPUT_ROOT, help="Artifact output directory"),
) -> None:
    """Render a persisted artifact to Markdown, JSON, and HTML outputs."""
    store = Store(db_path)
    artifact = store.get_artifact(artifact_id)
    if not artifact:
        raise typer.BadParameter(f"Artifact not found: {artifact_id}")

    fragments = store.get_artifact_fragments(artifact_id)
    out_dir = render_artifact(artifact, fragments, output_root=output_root)
    typer.echo(f"Rendered artifact to: {out_dir}")


@app.command("doctor")
def doctor(
    db_path: Path = typer.Option(DEFAULT_DB_PATH, "--db", help="SQLite database path"),
) -> None:
    """Print local environment diagnostics used by the CLI."""
    api_key = resolve_gemini_api_key()
    has_db = db_path.exists()
    typer.echo(f"DB exists: {has_db} ({db_path})")
    typer.echo(f"GEMINI_API_KEY set: {bool(api_key)}")


if __name__ == "__main__":
    app()
