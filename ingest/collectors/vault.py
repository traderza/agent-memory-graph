"""Collector: Obsidian Brain vault — the knowledge layer.

Honors typed-note frontmatter (sensitivity, permission_level, confidence). Skips
generated/policy regions (00_SYSTEM) and binary note formats (.canvas/.base).
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

from .base import Record, expand, parse_frontmatter


def _skipped(rel_posix: str, skip_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_posix, g) for g in skip_globs)


def collect(cfg: dict) -> list[Record]:
    root = expand(cfg["root"])
    if not root.exists():
        return []
    default = cfg.get("default_permission", "L1")
    skip_globs = cfg.get("skip_globs", [])
    records: list[Record] = []
    for sub in cfg.get("include", []):
        base = root / sub
        if not base.exists():
            continue
        for path in sorted(base.glob(cfg.get("glob", "**/*.md"))):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            rel_posix = rel.as_posix()
            if _skipped(rel_posix, skip_globs):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            fm, _body = parse_frontmatter(text)
            perm = (fm.get("permission_level") or fm.get("permission") or default).upper()
            records.append(Record(
                source="vault",
                rel_path=f"vault/{rel_posix}",
                title=fm.get("title") or path.stem,
                body=text,                       # keep frontmatter; graph wants the id/type
                permission_level=perm,
                sensitivity=fm.get("sensitivity", ""),
                origin=f"vault:{rel_posix}",
                meta={"note_id": fm.get("id", ""), "type": fm.get("type", ""),
                      "confidence": fm.get("confidence", "")},
            ))
    return records
