#!/usr/bin/env bash
# Deploy the memory graph services to HQ (Nico card #36, L5 — run only after the
# Approvals row is Approved). Run from the desktop build node; uses `ssh hq` + rsync.
#
#   ./scripts/deploy-hq.sh
#
# Idempotent. Builds nothing — expects a current graph from ./build.sh on desktop.
set -euo pipefail

HQ="${HQ_SSH:-hq}"
HQ_IP="100.85.55.57"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_OUT="$HOME/.cache/agent-memory-graph/corpus/graphify-out"
LOCAL_MANIFEST="$HOME/.cache/agent-memory-graph/manifest.json"

[ -f "$LOCAL_OUT/graph.json" ] || { echo "no local graph.json — run ./build.sh first"; exit 1; }

echo "[1/6] ensure repo on HQ…"
ssh "$HQ" 'set -e; mkdir -p ~/projects; cd ~/projects;
  [ -d agent-memory-graph ] || git clone https://github.com/traderza/agent-memory-graph.git;
  cd agent-memory-graph && git fetch -q origin && git checkout -q feat/agent-memory-ingest && git pull -q'

echo "[2/6] ensure graphify installed on HQ (uv venv)…"
ssh "$HQ" 'set -e; cd ~/projects/agent-memory-graph;
  command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh;
  ~/.local/bin/uv venv -q .venv 2>/dev/null || true;
  # [mcp] extra pulls mcp+starlette; uvicorn is needed by serve.py but not declared, so add it.
  ~/.local/bin/uv pip install -q --python .venv -e ".[mcp]" uvicorn pyyaml'

echo "[3/6] sync graph artifacts desktop -> HQ…"
ssh "$HQ" 'mkdir -p ~/.cache/agent-memory-graph/corpus/graphify-out'
rsync -az "$LOCAL_OUT/" "$HQ:~/.cache/agent-memory-graph/corpus/graphify-out/"
rsync -az "$LOCAL_MANIFEST" "$HQ:~/.cache/agent-memory-graph/manifest.json"

echo "[4/6] ensure API key on HQ (generated once, never in git)…"
ssh "$HQ" 'set -e; d=~/.config/agent-memory-graph; mkdir -p "$d";
  if [ ! -f "$d/env" ]; then
    echo "GRAPHIFY_API_KEY=amg-$(head -c24 /dev/urandom | base64 | tr -dc a-zA-Z0-9 | head -c32)" > "$d/env";
    chmod 600 "$d/env"; echo "  generated new API key"; else echo "  key exists"; fi'

echo "[5/6] install + start systemd --user units…"
scp -q "$REPO"/scripts/systemd/hq/agent-memory-{mcp,html}.service "$HQ:~/.config/systemd/user/" 2>/dev/null \
  || ssh "$HQ" 'mkdir -p ~/.config/systemd/user' && \
     scp -q "$REPO"/scripts/systemd/hq/agent-memory-{mcp,html}.service "$HQ:~/.config/systemd/user/"
ssh "$HQ" 'systemctl --user daemon-reload;
  systemctl --user enable --now agent-memory-mcp.service agent-memory-html.service;
  loginctl enable-linger $USER 2>/dev/null || true;
  sleep 2; systemctl --user --no-pager status agent-memory-mcp.service agent-memory-html.service | grep -E "Active:|●" | head'

echo "[6/6] healthcheck…"
ssh "$HQ" 'curl -s -o /dev/null -w "html :3310 -> %{http_code}\n" http://'"$HQ_IP"':3310/graph.html;
  curl -s -o /dev/null -w "mcp  :8770 -> %{http_code} (401/406 = up, key-gated)\n" http://'"$HQ_IP"':8770/mcp'
touch "$HOME/.cache/agent-memory-graph/.hq-deployed"   # tells rebuild.sh to sync HQ nightly
echo "done. API key: ssh $HQ 'cat ~/.config/agent-memory-graph/env'  (wire into agent MCP configs)"
