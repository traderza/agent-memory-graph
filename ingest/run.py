"""Orchestrator: collect -> sanitize -> stage corpus + manifest.

    python -m ingest.run                 # uses ingest/config.yaml
    python -m ingest.run --config x.yaml --dry-run

Output:
    build/corpus/<source>/...md   one doc per surviving record (with provenance frontmatter)
    build/corpus/manifest.json    relpath -> {source, permission_level, sensitivity, origin}
    build/excluded.log            one line per dropped record (reason only, no content)

`graphify extract build/corpus` then turns the staged corpus into the graph; the MCP
clearance filter reads manifest.json to map a returned node back to its permission level.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .collectors import agent_core, agent_memory, nico, vault
from .collectors.base import to_corpus_md
from .sanitize import sanitize_record

COLLECTORS = {
    "agent_core": agent_core.collect,
    "vault": vault.collect,
    "nico": nico.collect,
    "agent_memory": agent_memory.collect,
}


def _load_config(path: Path) -> dict:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text())
    except ModuleNotFoundError:
        # Minimal fallback parser is intentionally not implemented; PyYAML is a
        # declared dependency. Fail loudly so CI installs it.
        raise SystemExit("PyYAML required: pip install pyyaml")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage agent memory into a graphify corpus")
    ap.add_argument("--config", default=str(Path(__file__).parent / "config.yaml"))
    ap.add_argument("--dry-run", action="store_true", help="report counts, write nothing")
    args = ap.parse_args(argv)

    cfg = _load_config(Path(args.config))
    repo_root = Path(__file__).resolve().parents[1]

    def _resolve(p: str, default: str) -> Path:
        # Honor ~ and absolute paths; otherwise resolve relative to the repo root.
        raw = Path(os.path.expanduser(p or default))
        return raw if raw.is_absolute() else (repo_root / raw)

    corpus = _resolve(cfg.get("corpus_dir"), "build/corpus")
    excluded_log = _resolve(cfg.get("excluded_log"), "build/excluded.log")
    manifest_path = _resolve(cfg.get("manifest"), str(corpus / "manifest.json"))
    drop_at = cfg.get("drop_at", "L4")

    manifest: dict[str, dict] = {}
    excluded: list[str] = []
    stats = {"collected": 0, "written": 0, "dropped": 0, "redactions": 0}

    for name, scfg in cfg.get("sources", {}).items():
        if not scfg.get("enabled", True):
            continue
        records = COLLECTORS[name](scfg)
        stats["collected"] += len(records)
        for rec in records:
            res = sanitize_record(rec, drop_at=drop_at)
            if res.dropped:
                stats["dropped"] += 1
                excluded.append(f"{rec.origin}\t{res.reason}")
                continue
            stats["written"] += 1
            stats["redactions"] += res.redactions
            manifest[rec.rel_path] = rec.manifest_entry()
            if not args.dry_run:
                out = corpus / rec.rel_path
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(to_corpus_md(rec), encoding="utf-8")

    if not args.dry_run:
        corpus.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2))
        excluded_log.parent.mkdir(parents=True, exist_ok=True)
        excluded_log.write_text("\n".join(excluded) + ("\n" if excluded else ""))

    print(json.dumps(stats, indent=2))
    print(f"corpus: {corpus}  manifest: {manifest_path} ({len(manifest)} docs)  excluded: {len(excluded)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
