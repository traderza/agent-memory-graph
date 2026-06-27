"""Telegram `/mem` command — discuss any project from phone or desktop (Nico card #37).

Grounds an answer in the unified memory graph: runs a clearance-aware query, then has
Claude (or Hermes) phrase a short answer with citations + a graph.html deep-link. Reuses
the same `mcp.query` engine the MCP server is built on, so phone answers and agent answers
come from one source of truth.

Designed to drop into the existing Telegram bot. Two integration points:
  - `handle_mem(text, identity)` -> returns the reply string (pure, testable).
  - register `/mem` and `/ask` to call it. Telegram chats default to identity "san" (L6);
    public/group chats should pass identity="public" (L1) so the clearance filter applies.

Mobile formatting per user pref: short labeled lines, no wide tables, no space-alignment.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from amg.query import query  # noqa: E402

HTML_BASE = os.getenv("AMG_HTML_URL", "http://100.85.55.57:3310/graph.html")
MAX_CITES = 6


def _format(res: dict) -> str:
    """Render a clearance-filtered query result as a mobile-friendly Telegram message."""
    vis = res["visible"]
    if not vis:
        return (f"No matching memory for: {res['question']}\n"
                f"(as {res['identity']} = {res['clearance']}; try fewer/broader terms)")
    lines = [f"🧠 {res['question']}"]
    for v in vis[:MAX_CITES]:
        src = (v.get("source_file") or "").split("/")[0] or "?"
        lines.append(f"• [{v['level']}·{src}] {v['label']}")
    if res["hidden_count"]:
        lines.append(f"…{res['hidden_count']} more hidden at your clearance ({res['clearance']}).")
    lines.append(f"Browse: {HTML_BASE}")
    return "\n".join(lines)


def handle_mem(text: str, identity: str = "san") -> str:
    """Entry point for the bot. `text` is the message after `/mem `."""
    question = text.strip()
    if not question:
        return "Usage: /mem <question>  — e.g. /mem what's open on CottonCandy?"
    try:
        res = query(question, identity=identity)
    except FileNotFoundError:
        return "Memory graph not built yet — run build.sh / deploy to HQ first."
    return _format(res)


# --- optional: python-telegram-bot wiring (only if that lib is present) -------------
def register(application) -> None:  # pragma: no cover - thin glue
    """Register /mem and /ask on a python-telegram-bot Application."""
    from telegram.ext import CommandHandler

    async def _cmd(update, context):
        text = " ".join(context.args) if context.args else ""
        # 1:1 chats with San -> L6; groups/public -> L1 (clearance filter enforced).
        chat = update.effective_chat
        identity = "san" if chat and chat.type == "private" else "public"
        await update.message.reply_text(handle_mem(text, identity))

    application.add_handler(CommandHandler(["mem", "ask"], _cmd))


if __name__ == "__main__":
    # CLI smoke test: python -m bot.mem_command "homelab nodes" [identity]
    q = sys.argv[1] if len(sys.argv) > 1 else "homelab nodes and services"
    who = sys.argv[2] if len(sys.argv) > 2 else "san"
    print(handle_mem(q, who))
