"""/mem handler tests (card #37): mobile formatting + clearance in the rendered reply."""
from __future__ import annotations

from bot.mem_command import _format


def _res(visible, hidden, clearance="L1"):
    return {"question": "q", "identity": "x", "clearance": clearance,
            "visible": visible, "hidden_count": hidden}


def test_empty_result_message():
    out = _format(_res([], 0, clearance="L1"))
    assert "No matching memory" in out and "L1" in out


def test_renders_citations_and_hidden_count():
    vis = [{"label": "Homelab Inventory", "source_file": "agent_memory/x.md", "level": "L2"}]
    out = _format(_res(vis, 14, clearance="L1"))
    assert "Homelab Inventory" in out
    assert "[L2·agent_memory]" in out
    assert "14 more hidden" in out
    assert "graph.html" in out
    # mobile pref: no markdown tables / pipe-alignment
    assert "|" not in out


def test_usage_on_blank():
    from bot.mem_command import handle_mem
    assert "Usage:" in handle_mem("   ")
