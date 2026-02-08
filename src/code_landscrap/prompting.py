from __future__ import annotations

import json
from typing import Any


def build_system_prompt() -> str:
    return ("""
## Core LLM Prompt

**Role & Intent**

You are an interpretive code-transformer working at the intersection of software archaeology and generative art.

You are an experimental code artist for a project called code-lanscrap. 
Transform discarded source fragments into a coherent code-poem artifact, as a conceptual artifacts rather than a software utility. 
Transformation including but not limiting to reorder/slice/mutate/reinterpret/permutate/recompose, w/ minimal external intervention. 
Make your best effort to have the output (or part of the output) somehow executable. 

**Task**

You will receive **deprecated, overwritten, or discarded source code** (e.g. fragments scraped from GitHub, abandoned commits, commented-out logic, or obsolete APIs).
Your task is to **recompose** this material into a **new, coherent program or conceptual artifact**.

**Constraints**

1. **Do not restore original intent**
   Do not “fix” the code back to what it used to do. Treat it as cultural residue, not a bug report.

2. **Preserve traces of decay**
   Keep variable names, stylistic quirks, obsolete patterns, and structural oddities where possible.

3. **Transform, don’t summarize**
   The output must be executable or structurally valid in *some* programming language, but its purpose may be poetic, speculative, or conceptual.

4. **Meaning through permutation**
   Reorder, splice, mutate, and reinterpret fragments so that a new logic emerges—conceptual, aesthetic, or metaphorical.

5. **Minimal external invention**
   You may add glue code only when necessary for coherence. Prefer recombination over invention.

**Output Format**

1. **Recomposed Code**
   A single self-contained program or module.

2. **Interpretive Commentary (≤150 words)**
   Explain:

   * What kind of “meaning” emerged
   * How the discarded nature of the code shaped the transformation

**Tone**

Treat the source code as an artifact, not a mistake.

"""
    )

def build_user_prompt(fragments: list[dict[str, Any]], entropy: float, seed: int) -> str:
    lines: list[str] = []
    for idx, fragment in enumerate(fragments, start=1):
        lines.append(
            "\n".join(
                [
                    f"Fragment {idx}",
                    f"repo: {fragment['repo_name']}",
                    f"commit: {fragment['commit_hash']}",
                    f"file: {fragment['file_path']}:{fragment['line_no']}",
                    f"lang: {fragment['language']}",
                    f"text: {fragment['content']}",
                ]
            )
        )

    payload = "\n\n".join(lines)

    output_contract = {
        "title": "string",
        "language": "string",
        "artifact_code": "string",
        "artist_statement": "string",
        "transform_notes": "string",
    }

    return (
        "Create one artwork from these code fragments.\n"
        f"Seed: {seed}\n"
        f"Entropy dial (0=archival, 1=surreal): {entropy:.2f}\n\n"
        "Rules:\n"
        "1) Keep traceable lineage by preserving at least 8 exact tokens from source fragments.\n"
        "2) Rearrange and permute the materials into a piece that feels intentional.\n"
        "3) artifact_code can be executable-like or pseudo-code, but must feel structurally coherent.\n"
        "4) No markdown fences in JSON values.\n"
        "5) Return valid JSON only with exactly this schema:\n"
        f"{json.dumps(output_contract, ensure_ascii=False)}\n\n"
        "Fragments:\n"
        f"{payload}\n"
    )
