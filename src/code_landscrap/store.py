from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from code_landscrap.models import ArtifactRecord, Fragment


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fragments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    commit_author TEXT NOT NULL,
    commit_timestamp TEXT NOT NULL,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    line_no INTEGER NOT NULL,
    content TEXT NOT NULL,
    UNIQUE(commit_hash, file_path, line_no, content)
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    seed INTEGER NOT NULL,
    entropy REAL NOT NULL,
    source_repo TEXT NOT NULL,
    model_name TEXT NOT NULL,
    generation_mode TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    output_title TEXT NOT NULL,
    output_language TEXT NOT NULL,
    output_code TEXT NOT NULL,
    output_statement TEXT NOT NULL,
    output_notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact_fragments (
    artifact_id TEXT NOT NULL,
    fragment_id INTEGER NOT NULL,
    PRIMARY KEY (artifact_id, fragment_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id),
    FOREIGN KEY (fragment_id) REFERENCES fragments(id)
);
"""


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def insert_fragments(self, fragments: Iterable[Fragment]) -> int:
        payload = [
            (
                f.repo_path,
                f.repo_name,
                f.commit_hash,
                f.commit_author,
                f.commit_timestamp.isoformat(),
                f.file_path,
                f.language,
                f.line_no,
                f.content,
            )
            for f in fragments
        ]
        if not payload:
            return 0
        with self._connect() as conn:
            before = conn.total_changes
            conn.executemany(
                """
                INSERT OR IGNORE INTO fragments(
                    repo_path, repo_name, commit_hash, commit_author, commit_timestamp,
                    file_path, language, line_no, content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            return conn.total_changes - before

    def fetch_candidate_fragments(self, repo_name: str | None = None, limit: int = 3000) -> list[dict]:
        query = """
            SELECT id, repo_path, repo_name, commit_hash, commit_author, commit_timestamp,
                   file_path, language, line_no, content
            FROM fragments
        """
        params: tuple = ()
        if repo_name:
            query += " WHERE repo_name = ?"
            params = (repo_name,)
        query += " ORDER BY RANDOM() LIMIT ?"
        params = (*params, limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def save_artifact(self, record: ArtifactRecord, fragment_ids: list[int]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts(
                    artifact_id, created_at, seed, entropy, source_repo, model_name,
                    generation_mode, prompt_text, raw_response, output_title,
                    output_language, output_code, output_statement, output_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.created_at.isoformat(),
                    record.seed,
                    record.entropy,
                    record.source_repo,
                    record.model_name,
                    record.generation_mode,
                    record.prompt_text,
                    record.raw_response,
                    record.output_title,
                    record.output_language,
                    record.output_code,
                    record.output_statement,
                    record.output_notes,
                ),
            )
            conn.executemany(
                "INSERT INTO artifact_fragments(artifact_id, fragment_id) VALUES (?, ?)",
                [(record.artifact_id, fragment_id) for fragment_id in fragment_ids],
            )

    def get_artifact(self, artifact_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
            return dict(row) if row else None

    def get_artifact_fragments(self, artifact_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT f.id, f.repo_name, f.commit_hash, f.file_path, f.line_no, f.language, f.content
                FROM artifact_fragments af
                JOIN fragments f ON af.fragment_id = f.id
                WHERE af.artifact_id = ?
                ORDER BY f.id
                """,
                (artifact_id,),
            ).fetchall()
            return [dict(r) for r in rows]
