"""Collector: Nico (NocoDB commander_ops) — the live ops-state layer.

Read-only. Pulls selected tables and renders each row as a small markdown doc.
Cards already carry a permission_level field, which is mirrored onto the Record so
the clearance filter and the L4+ drop both work without guessing. The Approvals and
Agent Sessions tables are never read (secrets / raw episodic).

Token is read at runtime from /home/oker/.hermes/.env (NICO_NOCODB_API_TOKEN). It is
never written to the corpus or committed.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from .base import Record

ENV_PATHS = [Path("/home/oker/.hermes/.env"), Path("/home/san/services/nico/.env")]


def _load_token(base_url_default: str) -> tuple[str, str]:
    vals: dict[str, str] = {}
    for p in ENV_PATHS:
        if p.exists():
            for line in p.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    vals[k.strip()] = v.strip().strip('"').strip("'")
            break
    token = vals.get("NICO_NOCODB_API_TOKEN") or os.getenv("NICO_NOCODB_API_TOKEN", "")
    base = vals.get("NICO_NOCODB_URL", base_url_default)
    return base.rstrip("/"), token


def _call(base: str, token: str, path: str):
    req = urllib.request.Request(base + path, headers={"xc-token": token,
                                                       "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def _row_to_md(table: str, row: dict) -> str:
    lines = [f"# {table} row {row.get('Id', '?')}", ""]
    for k, v in row.items():
        if v in (None, "", [], {}):
            continue
        lines.append(f"- **{k}**: {v}")
    return "\n".join(lines)


def collect(cfg: dict) -> list[Record]:
    base, token = _load_token(cfg.get("base_url", "http://100.85.55.57:8080"))
    if not token:
        # No token available in this environment — skip rather than fail the whole run.
        return []
    bases = _call(base, token, "/api/v2/meta/bases")
    want = cfg.get("base_name", "commander_ops").lower()
    match = [b for b in bases["list"] if want in b["title"].lower()]
    if not match:
        return []
    bid = match[0]["id"]
    tables = {t["title"]: t["id"] for t in
              _call(base, token, f"/api/v2/meta/bases/{bid}/tables")["list"]}
    exclude = set(cfg.get("exclude_tables", []))
    default = cfg.get("default_permission", "L2")
    records: list[Record] = []
    for tname in cfg.get("tables", []):
        if tname in exclude or tname not in tables:
            continue
        tid = tables[tname]
        offset = 0
        while True:
            page = _call(base, token,
                         f"/api/v2/tables/{tid}/records?limit=200&offset={offset}")
            rows = page.get("list", [])
            for row in rows:
                rid = row.get("Id", "?")
                perm = str(row.get("permission_level") or default).upper()
                if not perm.startswith("L"):
                    perm = default
                slug = tname.lower().replace(" ", "_")
                records.append(Record(
                    source="nico",
                    rel_path=f"nico/{slug}/row_{rid}.md",
                    title=f"{tname} #{rid}: {row.get('title') or row.get('name') or ''}".strip(),
                    body=_row_to_md(tname, row),
                    permission_level=perm,
                    sensitivity=f"nico:{slug}",
                    origin=f"nico:{tname}#{rid}",
                    meta={"table": tname, "risk_level": str(row.get("risk_level", ""))},
                ))
            if len(rows) < 200:
                break
            offset += 200
    return records
