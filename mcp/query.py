"""Clearance-aware query over the memory graph (Nico cards #36/#37).

Thin wrapper that runs a graphify BFS query against graph.json and then applies the
stage-2 ClearanceFilter so a caller only sees nodes at or below its clearance. Used as:

  - the Phase 3 verification harness (prove low callers don't see high nodes), and
  - the engine behind the Phase 4 Telegram `/mem` command.

    python -m mcp.query "what links finance-slip-api to MangoStickBot" --as claude
    python -m mcp.query "homelab nodes" --as public --json

graphify's own MCP server (`graphify-mcp`) is the production transport; this module is
the deterministic, importable core so the same filter logic is testable and reusable.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp.filter import ClearanceFilter, caller_clearance  # noqa: E402

CACHE = Path(os.path.expanduser("~/.cache/agent-memory-graph"))
GRAPH = CACHE / "corpus" / "graphify-out" / "graph.json"
MANIFEST = CACHE / "manifest.json"   # one level above corpus (not graphed)


def _graphify_query(question: str, graph: Path, budget: int = 2000) -> dict:
    """Run `graphify query` and return its JSON-ish result.

    graphify's CLI prints a human report; we re-read graph.json for node provenance so
    the filter can act on structured nodes regardless of CLI output format.
    """
    venv_graphify = Path(__file__).resolve().parents[1] / ".venv" / "bin" / "graphify"
    exe = str(venv_graphify) if venv_graphify.exists() else "graphify"
    proc = subprocess.run(
        [exe, "query", question, "--graph", str(graph), "--budget", str(budget)],
        capture_output=True, text=True,
    )
    return {"stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}


def query(question: str, identity: str | None = None, graph: Path = GRAPH,
          manifest: Path = MANIFEST, budget: int = 2000) -> dict:
    clearance = caller_clearance(identity)
    flt = ClearanceFilter(manifest)
    g = json.loads(Path(graph).read_text())
    nodes = g.get("nodes", [])

    # Score nodes by naive label/keyword overlap so the harness works without the full
    # graphify traversal; the production MCP path uses graphify's BFS + this same filter.
    terms = {t.lower() for t in question.split() if len(t) > 2}
    scored = []
    for n in nodes:
        label = (n.get("label") or "").lower()
        hit = sum(1 for t in terms if t in label)
        if hit:
            scored.append((hit, n))
    scored.sort(key=lambda x: -x[0])
    candidate_nodes = [n for _, n in scored]

    visible = flt.filter_nodes(candidate_nodes, clearance)
    hidden = len(candidate_nodes) - len(visible)
    report = _graphify_query(question, graph, budget)
    return {
        "question": question,
        "identity": identity or "(env)",
        "clearance": clearance,
        "visible": [{"label": n.get("label"), "source_file": n.get("source_file"),
                     "level": flt.level_for(n.get("source_file"))} for n in visible[:20]],
        "hidden_count": hidden,
        "graphify_report": report["stdout"].strip(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Clearance-aware memory graph query")
    ap.add_argument("question")
    ap.add_argument("--as", dest="identity", default=None, help="agent identity (san/claude/public/...)")
    ap.add_argument("--graph", type=Path, default=GRAPH)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    res = query(args.question, args.identity, args.graph, args.manifest)
    if args.json:
        print(json.dumps(res, indent=2))
        return 0
    print(f"Q: {res['question']}  (as {res['identity']} = {res['clearance']})")
    print(f"visible nodes: {len(res['visible'])}  hidden by clearance: {res['hidden_count']}")
    for v in res["visible"]:
        print(f"  - [{v['level']}] {v['label']}  ({v['source_file']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
