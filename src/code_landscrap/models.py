"""Pydantic models shared across mining, generation, and persistence layers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Fragment(BaseModel):
    """A single deleted code line with repository lineage metadata."""

    repo_path: str
    repo_name: str
    commit_hash: str
    commit_author: str
    commit_timestamp: datetime
    file_path: str
    language: str
    line_no: int
    content: str


class ArtifactOutput(BaseModel):
    """Normalized model output payload for a generated artifact."""

    title: str = "Untitled Landscrap"
    language: str = "text"
    artifact_code: str
    artist_statement: str = ""
    transform_notes: str = ""


class ArtifactRecord(BaseModel):
    """Fully materialized artifact record stored in the database."""

    artifact_id: str
    created_at: datetime
    seed: int
    entropy: float = Field(ge=0.0, le=1.0)
    source_repo: str
    model_name: str
    generation_mode: Literal["gemini", "local"]
    prompt_text: str
    raw_response: str
    output_title: str
    output_language: str
    output_code: str
    output_statement: str
    output_notes: str
