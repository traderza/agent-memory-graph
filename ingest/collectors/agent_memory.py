"""Collector: per-agent episodic memory (~/.claude/.../memory, Codex equivalents).

These files are the most likely to contain credentials, so they default to L2 and
get the heaviest scrutiny in the sanitizer. The MEMORY.md index is skipped (it is a
pointer list; the per-topic files hold the real content).
"""
from __future__ import annotations

from pathlib import Path

from .base import Record, expand, parse_frontmatter


def collect(cfg: dict) -> list[Record]:
    default = cfg.get("default_permission", "L2")
    skip_files = set(cfg.get("skip_files", []))
    records: list[Record] = []
    for root_cfg in cfg.get("roots", []):
        root = expand(root_cfg)
        if not root.exists():
            continue
        for path in sorted(root.glob(cfg.get("glob", "**/*.md"))):
            if not path.is_file() or path.name in skip_files:
                continue
            rel = path.relative_to(root)
            text = path.read_text(encoding="utf-8", errors="replace")
            fm, _ = parse_frontmatter(text)
            perm = (fm.get("permission_level") or default).upper()
            records.append(Record(
                source="agent_memory",
                rel_path=f"agent_memory/{rel.as_posix()}",
                title=fm.get("name") or path.stem,
                body=text,
                permission_level=perm,
                sensitivity=fm.get("metadata", "") or "episodic",
                origin=f"agent_memory:{rel.as_posix()}",
            ))
    return records
