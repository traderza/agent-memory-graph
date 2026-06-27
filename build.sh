#!/usr/bin/env bash
# Agent Memory Graph — full build pipeline (Nico card #36).
# Stage the four memory layers, then extract a graphify knowledge graph.
# Idempotent; safe to re-run (nightly + on-push). Stops short of the L5 HQ deploy.
set -euo pipefail

cd "$(dirname "$0")"
PY="${PY:-.venv/bin/python}"
GRAPHIFY="${GRAPHIFY:-.venv/bin/graphify}"
BACKEND="${GRAPHIFY_BACKEND:-claude-cli}"   # claude CLI binary = subscription, no API key (no OpenAI)

# Corpus path comes from ingest/config.yaml (a cache dir outside the gitignored repo).
CORPUS="$("$PY" - <<'PY'
import os, yaml
c = yaml.safe_load(open("ingest/config.yaml"))
print(os.path.expanduser(c["corpus_dir"]))
PY
)"

echo "[1/2] staging corpus (collect -> sanitize -> manifest)…"
"$PY" -m ingest.run

echo "[2/2] graphify extract ($BACKEND) over $CORPUS…"
# graphify writes <corpus>/graphify-out/{graph.json,graph.html,GRAPH_REPORT.md}
"$GRAPHIFY" extract "$CORPUS" --backend "$BACKEND" "$@"
# cluster-only generates GRAPH_REPORT.md + names communities (extract prints it as the next step)
"$GRAPHIFY" cluster-only "$CORPUS" 2>/dev/null || true

OUT="$CORPUS/graphify-out"
MANIFEST="$("$PY" -c "import os,yaml;print(os.path.expanduser(yaml.safe_load(open('ingest/config.yaml'))['manifest']))")"
echo "done:"
ls -1 "$OUT"/graph.json "$OUT"/graph.html "$OUT"/GRAPH_REPORT.md 2>/dev/null || true
echo "manifest: $MANIFEST ($("$PY" -c "import json;print(len(json.load(open('$MANIFEST'))))" 2>/dev/null) docs)"
