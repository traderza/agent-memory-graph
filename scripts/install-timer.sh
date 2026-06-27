#!/usr/bin/env bash
# Install the nightly rebuild as a systemd --user timer on the build node (desktop).
# Idempotent. Run on the machine that has the four memory sources locally.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/systemd" && pwd)"
DEST="$HOME/.config/systemd/user"
mkdir -p "$DEST"
cp "$SRC/agent-memory-rebuild.service" "$SRC/agent-memory-rebuild.timer" "$DEST/"

systemctl --user daemon-reload
systemctl --user enable --now agent-memory-rebuild.timer
echo "installed. next runs:"
systemctl --user list-timers agent-memory-rebuild.timer --no-pager || true
echo "manual run: systemctl --user start agent-memory-rebuild.service ; tail -f ~/.cache/agent-memory-graph/rebuild.log"
