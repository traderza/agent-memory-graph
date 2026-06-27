#!/usr/bin/env bash
# Nightly / on-demand rebuild with a change-guard (Nico card #38).
# Stages the corpus every run (cheap, deterministic), but only spends LLM tokens on
# `graphify extract` when the staged corpus actually changed since the last build.
# Runs on the build node (desktop) where all four sources are accessible.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
PY="$REPO/.venv/bin/python"
CACHE="$HOME/.cache/agent-memory-graph"
CORPUS="$CACHE/corpus"
STAMP="$CACHE/.last-corpus-hash"
LOG="$CACHE/rebuild.log"

ts() { date -Is; }
echo "[$(ts)] rebuild start" >> "$LOG"

# 1. always re-stage (collect -> sanitize -> manifest); fast, no LLM
"$PY" -m ingest.run >> "$LOG" 2>&1

# 2. hash the staged corpus content to decide whether semantic extraction is needed
NEW_HASH="$(find "$CORPUS" -name '*.md' -type f -exec sha256sum {} + | sort | sha256sum | cut -d' ' -f1)"
OLD_HASH="$(cat "$STAMP" 2>/dev/null || echo none)"

if [ "$NEW_HASH" = "$OLD_HASH" ] && [ -f "$CORPUS/graphify-out/graph.json" ]; then
    echo "[$(ts)] corpus unchanged — skipping extract (no LLM spend)" >> "$LOG"
    exit 0
fi

echo "[$(ts)] corpus changed — running graphify extract" >> "$LOG"
GRAPHIFY_BACKEND="${GRAPHIFY_BACKEND:-claude-cli}" "$REPO/build.sh" >> "$LOG" 2>&1
echo "$NEW_HASH" > "$STAMP"
echo "[$(ts)] rebuild done" >> "$LOG"

# 3. if HQ deploy is live, push refreshed artifacts so the served graph stays current.
#    Marker file is created by deploy-hq.sh; absent until the L5 deploy lands.
if [ -f "$CACHE/.hq-deployed" ]; then
    HQ="${HQ_SSH:-hq}"
    rsync -az "$CORPUS/graphify-out/" "$HQ:~/.cache/agent-memory-graph/corpus/graphify-out/" >> "$LOG" 2>&1 || true
    rsync -az "$CACHE/manifest.json" "$HQ:~/.cache/agent-memory-graph/manifest.json" >> "$LOG" 2>&1 || true
    # graphify MCP hot-reloads graph.json inside tool handlers; no restart needed.
    echo "[$(ts)] synced artifacts to HQ" >> "$LOG"
fi
