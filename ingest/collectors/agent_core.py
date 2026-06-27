"""Collector: agent-core repo (CORE/, NODES/, PLAYBOOKS/) — the constitutional layer."""
from __future__ import annotations

from pathlib import Path

from .base import Record, expand


def collect(cfg: dict) -> list[Record]:
    root = expand(cfg["root"])
    if not root.exists():
        return []
    default = cfg.get("default_permission", "L1")
    records: list[Record] = []
    for sub in cfg.get("include", []):
        base = root / sub
        if not base.exists():
            continue
        for path in sorted(base.glob(cfg.get("glob", "**/*.md"))):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            text = path.read_text(encoding="utf-8", errors="replace")
            records.append(Record(
                source="agent_core",
                rel_path=f"agent_core/{rel.as_posix()}",
                title=path.stem,
                body=text,
                permission_level=default,
                sensitivity="constitutional",
                origin=f"agent-core:{rel.as_posix()}",
            ))
    return records
