# Delegation brief — Phase 3: graph build + MCP serve + clearance filter

**Assignee:** Codex (VPS heavy coding) · **Nico card:** #36 (L5 — needs Approval row before HQ deploy)
**Prereqs DONE:** Phases 1–2 merged. `python -m ingest.run` produces `build/corpus/` +
`build/corpus/manifest.json`. graphify ships `graphify extract`, `graphify-mcp`
(`graphify/serve.py`), and a `graphify query` CLI.

## Deliverables

### 1. `build.sh` (repo root)
Pipeline wrapper, idempotent:
```bash
.venv/bin/python -m ingest.run                      # stage corpus + manifest
graphify extract build/corpus --backend claude      # uses `claude` CLI on HQ (no API key)
  # -> graphify-out/graph.json, graph.html, GRAPH_REPORT.md
```
Pick backend by what HQ has. `graphify extract` is offline for code; our corpus is
markdown/docs so it needs an LLM backend — prefer the `claude` CLI binary (subscription,
no key) per graphify README, else `delegate`/LiteLLM `ANTHROPIC_API_KEY`.

### 2. `amg/filter.py` — stage-2 clearance filter (the real custom work)
Wrap the graphify MCP tools (`query_graph`, `get_node`, `get_neighbors`,
`get_community`, `shortest_path`, `god_nodes` — see `graphify/serve.py` ~L713) so every
returned node is checked against the caller's clearance:

- Load `build/corpus/manifest.json` once. Map a returned node → its source corpus file
  (graphify node provenance carries the source path / file slice; confirm the field name
  in `serve.py` `_query_graph_text` ~L538 and `ids.py`).
- Drop any node whose `manifest[path].permission_level` rank > caller clearance rank
  (`ingest.collectors.base.perm_rank`). Nodes with no manifest hit → treat as L1.
- Caller clearance: per-agent default table below; San = L6 (full). Pass clearance via an
  env var / MCP client identity (`GRAPHIFY_CALLER_CLEARANCE`, default L1 fail-safe).

Agent clearance defaults (from `~/.agent-core/CORE/AGENTS.md`):
| Agent | Clearance |
|---|---|
| San (human) | L6 |
| Claude, Oker | L3 |
| Codex, Hermes | L3 |
| Pooniclaw, Gemini, public bots | L1 |

### 3. HQ deployment (L5 — Approval row required first)
- `graphify-mcp` serving the built graph, bound to **100.85.55.57:8770**, Tailscale-only
  (Infra Registry row **#48**). systemd `--user` unit or compose under `~/docker/`.
- Static serve `graphify-out/graph.html` on **100.85.55.57:3310** (Infra Registry **#49**).
- Register both MCP endpoints in each agent's MCP config (Claude `.mcp.json`/settings,
  Codex, Oker) so all can query live.
- Update Infra Registry rows #48/#49 `status` green + `health_url` after deploy.

## Verification (evidence for card #36)
1. `./build.sh` → non-empty `graph.json/html/GRAPH_REPORT.md`; god-nodes span ≥3 sources.
2. MCP `query_graph "what links finance-slip-api to MangoStickBot"` → nodes from both the
   Nico card and the project memory file (cross-layer proof).
3. Same query as an L1 caller → no L3 nodes, no `[REDACTED]`-adjacent originals.
4. `graph.html` loads on the HQ Tailscale URL from desktop + phone.

## Guardrails
- Tailscale-only; no public funnel. No secrets in graph (Phase 2 already guarantees this).
- Treat `graphify-out/*` as generated — never hand-edit; rebuild via `build.sh`.
- Deploy steps are L5 → do not start the service without an Approved Nico Approvals row.
