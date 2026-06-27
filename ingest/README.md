# Agent Memory Graph — ingestion

Stages four agent-memory layers into one corpus that `graphify extract` turns into a
queryable knowledge graph. Permission-gated by the Nico L0–L6 model. Nico card **#33**.

## Sources → corpus

| Source | Collector | Default level |
|---|---|---|
| agent-core (`~/.agent-core` CORE/NODES/PLAYBOOKS) | `collectors/agent_core.py` | L1 |
| Obsidian vault (`~/Documents/ObsidianVault` 01–04) | `collectors/vault.py` | L1 (honors frontmatter) |
| Nico export (NocoDB `commander_ops`) | `collectors/nico.py` | from card `permission_level` |
| Per-agent memory (`~/.claude/.../memory`) | `collectors/agent_memory.py` | L2 |

## Run

```bash
uv venv .venv && uv pip install --python .venv pyyaml pytest
.venv/bin/python -m ingest.run            # writes build/corpus/ + manifest.json
.venv/bin/python -m ingest.run --dry-run  # counts only
.venv/bin/python -m pytest ingest/tests   # security-gate evidence (card #35)
```

## Two-stage permission model

1. **Hard gate at ingest** (`sanitize.py`): secrets redacted (`[REDACTED:<kind>]`),
   anything ≥ `drop_at` (L4) dropped entirely → `build/excluded.log` (reason, no content).
   Fail-closed: a residual-secret match drops the whole record. Levels are normalized,
   so Nico labels like `"L5 PRODUCTION OPS"` gate the same as bare `L5`.
2. **Soft filter at query** (Phase 3, `amg/filter.py` — TODO): the MCP wrapper maps each
   returned node back to its corpus file via **`build/corpus/manifest.json`** and drops
   nodes above the asking agent's clearance.

### manifest.json contract (consumed by the clearance filter)

```json
{
  "agent_core/CORE/USER.md": {
    "source": "agent_core", "permission_level": "L1",
    "sensitivity": "constitutional", "origin": "agent-core:CORE/USER.md",
    "title": "USER"
  }
}
```

Key = corpus-relative path (also the graphify input filename → recoverable from node
provenance). `permission_level` is canonical `L0`–`L3` (L4+ never reach the corpus).
