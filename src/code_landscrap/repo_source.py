"""Repository source resolution helpers for local paths and remote git URLs."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def looks_like_git_url(source: str) -> bool:
    """Return ``True`` when ``source`` matches common git URL prefixes."""
    return (
        source.startswith("https://")
        or source.startswith("http://")
        or source.startswith("git@")
        or source.startswith("ssh://")
    )


def resolve_repo_source(source: str, cache_dir: Path, update_remote: bool = True) -> tuple[Path, str]:
    """Resolve a source string to a local git repository path.

    Behavior:
    - Existing local git repos are used directly.
    - Remote URLs are cloned into ``cache_dir`` when absent.
    - Cached remotes may be fetched/pulled when ``update_remote`` is enabled.

    Returns:
        A tuple of `(resolved_path, mode)` where mode is one of
        ``local``, ``cloned``, ``updated``, or ``cached``.
    """
    candidate = Path(source).expanduser()
    if candidate.exists():
        if not candidate.is_dir():
            raise ValueError(f"Source exists but is not a directory: {candidate}")
        if not (candidate / ".git").exists():
            raise ValueError(f"Directory is not a git repo: {candidate}")
        return candidate.resolve(), "local"

    if not looks_like_git_url(source):
        raise ValueError(
            f"Source is neither an existing local repo path nor a recognized git URL: {source}"
        )

    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / build_cache_repo_name(source)

    if not target.exists():
        run_cmd(["git", "clone", "--quiet", source, str(target)])
        return target.resolve(), "cloned"

    if update_remote:
        run_cmd(["git", "-C", str(target), "fetch", "--all", "--prune"])
        default_ref = (
            run_cmd(["git", "-C", str(target), "rev-parse", "--abbrev-ref", "origin/HEAD"])
            .strip()
        )
        branch = default_ref.split("/", 1)[1] if default_ref.startswith("origin/") else "main"
        run_cmd(["git", "-C", str(target), "checkout", branch])
        run_cmd(["git", "-C", str(target), "pull", "--ff-only", "origin", branch])
        return target.resolve(), "updated"

    return target.resolve(), "cached"


def build_cache_repo_name(source: str) -> str:
    """Build a stable cache directory name from URL slug and source hash."""
    parsed = urlparse(source if "://" in source else f"ssh://{source.replace(':', '/', 1)}")
    base = Path(parsed.path).name
    stem = base[:-4] if base.endswith(".git") else base
    slug = stem or "repo"
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{digest}"


def run_cmd(cmd: list[str]) -> str:
    """Run a command and return stdout, raising on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {stderr}")
    return proc.stdout
