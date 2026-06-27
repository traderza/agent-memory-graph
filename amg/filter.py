"""Stage-2 clearance filter for the memory-graph MCP (Nico card #36).

graphify's MCP server (`graphify/serve.py`) returns nodes that each carry a
`source_file` field pointing at the corpus doc they came from. This module maps that
back to `build/corpus/manifest.json` and drops any node whose permission level
out-ranks the asking agent's clearance.

This is the *soft* second stage. The *hard* first stage (ingest/sanitize.py) already
guarantees no secrets and nothing >= L4 ever reached the corpus, so the worst this
filter prevents is, e.g., a public bot (L1) seeing an L3 ops note.

Wire it in one of two ways:
  - import `ClearanceFilter` and post-filter results inside a thin MCP wrapper, or
  - run graphify-mcp behind it and set GRAPHIFY_CALLER_CLEARANCE per client.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingest.collectors.base import perm_rank, normalize_level  # noqa: E402

# Default clearance per agent (from ~/.agent-core/CORE/AGENTS.md). Fail-safe: L1.
AGENT_CLEARANCE = {
    "san": "L6", "human": "L6",
    "claude": "L3", "oker": "L3", "codex": "L3", "hermes": "L3",
    "pooniclaw": "L1", "gemini": "L1", "public": "L1",
}


def caller_clearance(identity: str | None = None) -> str:
    ident = (identity or os.getenv("GRAPHIFY_CALLER_IDENTITY", "")).strip().lower()
    if ident in AGENT_CLEARANCE:
        return AGENT_CLEARANCE[ident]
    env = os.getenv("GRAPHIFY_CALLER_CLEARANCE")
    return normalize_level(env) if env else "L1"


class ClearanceFilter:
    def __init__(self, manifest_path: str | os.PathLike):
        raw = json.loads(Path(manifest_path).read_text())
        # Index by the corpus-relative path AND its basename tail variants so a
        # node's source_file matches regardless of how graphify roots the path.
        self._by_path: dict[str, str] = {}
        for rel, entry in raw.items():
            lvl = normalize_level(entry.get("permission_level", "L1"))
            self._by_path[rel] = lvl
            self._by_path[Path(rel).as_posix()] = lvl
            self._by_path[Path(rel).name] = lvl  # last-resort basename match

    def level_for(self, source_file: str | None) -> str:
        if not source_file:
            return "L1"
        sf = str(source_file).replace("\\", "/")
        for key in (sf, sf.split("build/corpus/")[-1], Path(sf).as_posix(), Path(sf).name):
            if key in self._by_path:
                return self._by_path[key]
        return "L1"  # unknown provenance -> treat as least-sensitive shareable

    def allows(self, node: dict, clearance: str) -> bool:
        lvl = self.level_for(node.get("source_file") or node.get("source"))
        return perm_rank(lvl) <= perm_rank(clearance)

    def filter_nodes(self, nodes: list[dict], clearance: str | None = None) -> list[dict]:
        cl = clearance or caller_clearance()
        return [n for n in nodes if self.allows(n, cl)]


__all__ = ["ClearanceFilter", "caller_clearance", "AGENT_CLEARANCE"]
