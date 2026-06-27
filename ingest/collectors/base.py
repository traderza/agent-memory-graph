"""Shared types and helpers for memory-graph collectors.

Each collector turns one source (agent-core, vault, Nico, per-agent memory) into a
list of Record objects. run.py pipes every Record through ingest/sanitize.py before
writing it to the staging corpus that `graphify extract` consumes.

No collector writes to the corpus directly and none of them carry secrets — the
sanitizer is the single chokepoint (see Nico card 35, the security gate).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

PERMISSION_ORDER = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

_LEVEL_RE = re.compile(r"L\s*([0-6])", re.IGNORECASE)


def normalize_level(level: str) -> str:
    """Coerce any Nico/frontmatter permission string to canonical 'L0'..'L6'.

    Handles bare 'L2', full labels like 'L5 PRODUCTION OPS' / 'L1 Prepare', and
    blanks. Unknown/blank -> 'L1'. This is security-critical: the L4+ drop gate
    relies on it, so a label format must never silently rank as low.
    """
    m = _LEVEL_RE.search(level or "")
    return f"L{m.group(1)}" if m else "L1"


def perm_rank(level: str) -> int:
    """Numeric rank of a permission level; unknown/blank -> L1."""
    return PERMISSION_ORDER.index(normalize_level(level))


@dataclass
class Record:
    """One unit of memory destined for the graph.

    `rel_path` is the corpus-relative file path the collector wants (used as the
    graphify input filename and the manifest key). `body` is markdown text. `meta`
    holds provenance + the permission_level the clearance filter will key on.
    """
    source: str                       # agent_core | vault | nico | agent_memory
    rel_path: str                     # e.g. "agent_core/CORE/USER.md"
    title: str
    body: str
    permission_level: str = "L1"
    sensitivity: str = ""             # free-text tag mirrored from frontmatter/Nico
    origin: str = ""                  # human-readable origin (path or table row)
    meta: dict[str, Any] = field(default_factory=dict)

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "permission_level": self.permission_level,
            "sensitivity": self.sensitivity,
            "origin": self.origin,
            "title": self.title,
        }


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Cheap YAML-ish frontmatter parser (key: value lines only).

    Avoids a hard PyYAML dependency for the common flat-frontmatter case used by
    Obsidian typed notes. Returns (frontmatter_dict, body_without_frontmatter).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            fm[k.strip().lower()] = v.strip().strip('"').strip("'")
    return fm, text[m.end():]


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def to_corpus_md(rec: Record) -> str:
    """Render a Record as a markdown doc with provenance frontmatter.

    The frontmatter is human/graph readable; the authoritative permission data the
    clearance filter uses lives in manifest.json (frontmatter can be summarized
    away by extraction, the manifest cannot).
    """
    fm = [
        "---",
        f"source: {rec.source}",
        f"title: {rec.title}",
        f"permission_level: {rec.permission_level}",
        f"sensitivity: {rec.sensitivity}",
        f"origin: {rec.origin}",
        "---",
        "",
    ]
    return "\n".join(fm) + rec.body.strip() + "\n"


__all__ = [
    "Record", "PERMISSION_ORDER", "perm_rank",
    "parse_frontmatter", "expand", "to_corpus_md",
]
