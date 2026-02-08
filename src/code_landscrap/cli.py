from __future__ import annotations

import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

import typer

from code_landscrap.generator import GeminiGenerator, local_fallback_generate, parse_output
from code_landscrap.miner import extract_deleted_fragments
from code_landscrap.models import ArtifactRecord
from code_landscrap.prompting import build_system_prompt, build_user_prompt
from code_landscrap.repo_source import resolve_repo_source
from code_landscrap.renderer import render_artifact
from code_landscrap.selector import select_fragments
from code_landscrap.store import Store

app = typer.Typer(add_completion=False, help="code-landscrap: reconstruct discarded code into art artifacts")


@app.command("init-db")
def init_db(
    db_path: Path = typer.Option(Path(".code_landscrap/landscrap.db"), "--db", help="SQLite database path"),
) -> None:
    store = Store(db_path)
    store.init_db()
    typer.echo(f"DB initialized: {db_path}")


@app.command("ingest")
def ingest(
    source: str = typer.Argument(..., help="Local git repo path or git URL"),
    db_path: Path = typer.Option(Path(".code_landscrap/landscrap.db"), "--db", help="SQLite database path"),
    max_commits: int = typer.Option(200, help="Max commits to inspect"),
    max_fragments_per_commit: int = typer.Option(80, help="Cap extracted fragments per commit"),
    repo_cache_dir: Path = typer.Option(
        Path(".code_landscrap/repos"), "--repo-cache-dir", help="Cache directory for cloned remote repos"
    ),
    no_remote_update: bool = typer.Option(
        False, "--no-remote-update", help="Do not fetch/pull when using cached remote repos"
    ),
) -> None:
    store = Store(db_path)
    store.init_db()

    try:
        repo_path, source_mode = resolve_repo_source(
            source=source,
            cache_dir=repo_cache_dir,
            update_remote=not no_remote_update,
        )
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Using repo: {repo_path} ({source_mode})")

    fragments = extract_deleted_fragments(
        repo_path=repo_path,
        max_commits=max_commits,
        max_fragments_per_commit=max_fragments_per_commit,
    )

    inserted = store.insert_fragments(fragments)
    typer.echo(
        f"Ingest complete. repo={repo_path.name} extracted={len(fragments)} inserted={inserted} db={db_path}"
    )


@app.command("generate")
def generate(
    db_path: Path = typer.Option(Path(".code_landscrap/landscrap.db"), "--db", help="SQLite database path"),
    repo_name: str | None = typer.Option(None, help="Optional repo filter"),
    fragment_count: int = typer.Option(20, help="Fragments per piece"),
    entropy: float = typer.Option(0.55, min=0.0, max=1.0, help="0 archival -> 1 surreal"),
    seed: int | None = typer.Option(None, help="Random seed"),
    model_name: str = typer.Option("gemini-3-flash-preview", help="Gemini model name"),
    output_root: Path = typer.Option(Path("artifacts"), help="Artifact output directory"),
    local_only: bool = typer.Option(False, help="Skip Gemini and force local fallback"),
) -> None:
    store = Store(db_path)
    store.init_db()

    candidates = store.fetch_candidate_fragments(repo_name=repo_name, limit=max(500, fragment_count * 60))
    if not candidates:
        raise typer.BadParameter("No fragments found. Run ingest first.")

    seed_value = seed if seed is not None else random.SystemRandom().randint(1, 2**31 - 1)
    rng = random.Random(seed_value)

    chosen = select_fragments(candidates, count=fragment_count, entropy=entropy, rng=rng)
    if not chosen:
        raise typer.BadParameter("Unable to select fragments from current dataset.")

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(chosen, entropy=entropy, seed=seed_value)

    raw_response: str
    parsed_output = None
    generation_mode = "gemini"

    if local_only:
        raw_response, parsed_output = local_fallback_generate(chosen, entropy=entropy, seed=seed_value)
        generation_mode = "local"
    else:
        try:
            generator = GeminiGenerator(model_name=model_name)
            raw_response = generator.generate(system_prompt=system_prompt, user_prompt=user_prompt)
            parsed_output = parse_output(raw_response)
        except Exception as exc:
            # Maintain momentum during prototyping by degrading to local generation.
            typer.echo(f"Gemini path unavailable ({exc}); using local fallback.")
            raw_response, parsed_output = local_fallback_generate(chosen, entropy=entropy, seed=seed_value)
            generation_mode = "local"

    artifact_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    source_repo = repo_name or chosen[0]["repo_name"]

    record = ArtifactRecord(
        artifact_id=artifact_id,
        created_at=now,
        seed=seed_value,
        entropy=entropy,
        source_repo=source_repo,
        model_name=model_name,
        generation_mode=generation_mode,
        prompt_text=user_prompt,
        raw_response=raw_response,
        output_title=parsed_output.title,
        output_language=parsed_output.language,
        output_code=parsed_output.artifact_code,
        output_statement=parsed_output.artist_statement,
        output_notes=parsed_output.transform_notes,
    )

    fragment_ids = [int(item["id"]) for item in chosen]
    store.save_artifact(record, fragment_ids)

    saved = store.get_artifact(artifact_id)
    linked = store.get_artifact_fragments(artifact_id)
    if not saved:
        raise RuntimeError("Artifact insert failed unexpectedly")

    out_dir = render_artifact(saved, linked, output_root=output_root)
    typer.echo(
        f"Artifact generated. id={artifact_id} mode={generation_mode} seed={seed_value} path={out_dir}"
    )


@app.command("render")
def render(
    artifact_id: str = typer.Argument(..., help="Artifact ID from database"),
    db_path: Path = typer.Option(Path(".code_landscrap/landscrap.db"), "--db", help="SQLite database path"),
    output_root: Path = typer.Option(Path("artifacts"), help="Artifact output directory"),
) -> None:
    store = Store(db_path)
    artifact = store.get_artifact(artifact_id)
    if not artifact:
        raise typer.BadParameter(f"Artifact not found: {artifact_id}")

    fragments = store.get_artifact_fragments(artifact_id)
    out_dir = render_artifact(artifact, fragments, output_root=output_root)
    typer.echo(f"Rendered artifact to: {out_dir}")


@app.command("doctor")
def doctor(
    db_path: Path = typer.Option(Path(".code_landscrap/landscrap.db"), "--db", help="SQLite database path"),
) -> None:
    #api_key = os.getenv("GEMINI_API_KEY")
    key_file = ".api_keys/Gemini.md"
    path = Path(key_file)
    if path.exists():
        api_key = path.read_text(encoding="utf-8").strip()
    else:
        raise FileNotFoundError(key_file)
    has_db = db_path.exists()
    typer.echo(f"DB exists: {has_db} ({db_path})")
    # typer.echo(f"GEMINI_API_KEY set: {bool(api_key)}")


if __name__ == "__main__":
    app()
