from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from code_landscrap.models import Fragment


LANGUAGE_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".md": "markdown",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
}


HUNK_RE = re.compile(r"@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def _run_git(repo_path: Path, args: list[str]) -> str:
    cmd = ["git", "-C", str(repo_path), *args]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout


def _infer_language(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    return LANGUAGE_BY_EXT.get(suffix, "text")


def _is_interesting(content: str) -> bool:
    text = content.strip()
    if not text:
        return False
    if len(text) < 4:
        return False
    if text in {"{", "}", "(", ")", "[", "]", ";", ","}:
        return False
    # Skip low-signal lines that are mostly punctuation.
    alnum = sum(ch.isalnum() for ch in text)
    if alnum == 0:
        return False
    return True


def list_commits(repo_path: Path, max_commits: int | None = None) -> list[tuple[str, str, datetime]]:
    args = ["log", "--pretty=format:%H%x1f%an%x1f%aI", "--no-merges"]
    if max_commits:
        args.extend(["-n", str(max_commits)])
    output = _run_git(repo_path, args)
    commits: list[tuple[str, str, datetime]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        commit_hash, author, ts = line.split("\x1f", maxsplit=2)
        commits.append((commit_hash, author, datetime.fromisoformat(ts.replace("Z", "+00:00"))))
    return commits


def extract_deleted_fragments(
    repo_path: Path,
    max_commits: int | None = None,
    max_fragments_per_commit: int = 80,
) -> list[Fragment]:
    repo_path = repo_path.resolve()
    repo_name = repo_path.name
    commits = list_commits(repo_path, max_commits=max_commits)

    all_fragments: list[Fragment] = []
    for commit_hash, commit_author, commit_time in commits:
        diff_text = _run_git(repo_path, ["show", "--format=", "--unified=0", "--no-color", commit_hash])

        current_file = ""
        current_line_no = 0
        from_file = False
        commit_fragments = 0

        for raw in diff_text.splitlines():
            if raw.startswith("diff --git "):
                current_file = ""
                from_file = False
                continue

            if raw.startswith("--- "):
                from_file = raw != "--- /dev/null"
                continue

            if raw.startswith("+++ b/"):
                current_file = raw[6:]
                continue

            if raw.startswith("@@ "):
                match = HUNK_RE.match(raw)
                if match:
                    current_line_no = int(match.group(1))
                continue

            if not current_file or not from_file:
                continue

            if raw.startswith("-") and not raw.startswith("---"):
                content = raw[1:]
                if _is_interesting(content):
                    all_fragments.append(
                        Fragment(
                            repo_path=str(repo_path),
                            repo_name=repo_name,
                            commit_hash=commit_hash,
                            commit_author=commit_author,
                            commit_timestamp=commit_time,
                            file_path=current_file,
                            language=_infer_language(current_file),
                            line_no=current_line_no,
                            content=content.rstrip(),
                        )
                    )
                    commit_fragments += 1
                current_line_no += 1
                if commit_fragments >= max_fragments_per_commit:
                    break
            elif raw.startswith(" "):
                current_line_no += 1

    return all_fragments
