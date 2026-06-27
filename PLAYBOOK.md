# Playbook — Agent Memory Graph

> Source of truth for how the unified memory graph is built, served, and used.
> Mirror a short pointer of this into `agent-core/CORE/BRAIN.md` after Phase 3 lands.
> Nico project **agent-memory-graph**, parent card **#33**.

## What it is

One queryable knowledge graph that unifies the four agent-memory layers so any agent
(and you, from phone or desktop) can ask cross-layer questions instead of grepping four
places:

1. **agent-core** repo — constitutional CORE/NODES/PLAYBOOKS
2. **Obsidian vault** — typed knowledge notes
3. **Nico** (NocoDB) — live ops state (Cards, Projects, Infra Registry, …)
4. **per-agent memory** — episodic `~/.claude/.../memory`

Built with **graphify** (fork `traderza/agent-memory-graph`). Permission-gated by the
Nico **L0–L6** model, two stages:
- **Ingest gate** (`ingest/sanitize.py`): secrets redacted, L4+ dropped — they never
  reach the graph.
- **Query gate** (`amg/filter.py`): each caller sees only nodes at/below its clearance.

## Build

```bash
cd ~/projects/agent-memory-graph
./build.sh           # stage corpus -> graphify extract (claude-cli) -> graph.json/html/report
```

Outputs land in `~/.cache/agent-memory-graph/corpus/graphify-out/` (outside the repo —
graphify honors .gitignore, so the corpus is staged in a cache dir, not the repo tree).
Backend is `claude-cli` (Claude subscription, no API key, no OpenAI cost).

## Query (agile, any device)

- Local / in-session: `python -m amg.query "<question>" --as <agent>`
- Live MCP: agents point at `graphify-mcp` on **hq:8770** (Infra Registry #48).
- Browse: `graph.html` on **hq:3310** (Infra Registry #49), desktop + phone.
- Mobile chat: Telegram `/mem <question>` (Phase 4) → Claude/Hermes answers grounded in
  the graph with citations + a deep-link.

Clearance defaults (from `CORE/AGENTS.md`): San L6 · Claude/Oker/Codex/Hermes L3 ·
public bots / Pooniclaw / Gemini L1.

## Agile working loop

1. **Anytime, any device** — `/mem <project or question>` for a grounded answer + open
   questions before you start. The graph surfaces related decisions/lessons to avoid rework.
2. **Start work** — ensure a Nico card + GitHub issue exist (Nico-first / GitHub-first).
3. **Finish work** — attach Evidence, move the card to **Verify**. New knowledge → a draft
   note in vault `09_INBOX/agent-capture/`.
4. **Nightly + on-push rebuild** picks up all of the above so the graph never goes stale.

## Rules

- Tailscale-only endpoints; no public funnel. No secrets in the graph (ingest gate).
- `graphify-out/*` and the corpus are **generated** — never hand-edit; rebuild via `build.sh`.
- HQ service deploy is **L5** → needs an Approved Nico Approvals row first.
- Re-tag a source's sensitivity in Nico/frontmatter to change what the graph exposes.
