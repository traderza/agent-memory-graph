"""Clearance-filter tests (Nico card #36): a low-clearance caller never sees high nodes."""
from __future__ import annotations

import json

from amg.filter import ClearanceFilter, caller_clearance


def _manifest(tmp_path):
    data = {
        "agent_core/CORE/USER.md": {"permission_level": "L1"},
        "nico/cards/row_25.md": {"permission_level": "L2"},
        "agent_memory/control-plane.md": {"permission_level": "L3"},
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(data))
    return ClearanceFilter(p)


def test_basename_and_rooted_paths_resolve(tmp_path):
    f = _manifest(tmp_path)
    assert f.level_for("agent_core/CORE/USER.md") == "L1"
    assert f.level_for("build/corpus/nico/cards/row_25.md") == "L2"
    assert f.level_for("control-plane.md") == "L3"
    assert f.level_for("unknown/whatever.md") == "L1"  # fail-safe shareable


def test_l1_caller_sees_only_l1(tmp_path):
    f = _manifest(tmp_path)
    nodes = [
        {"id": 1, "source_file": "agent_core/CORE/USER.md"},
        {"id": 2, "source_file": "nico/cards/row_25.md"},
        {"id": 3, "source_file": "agent_memory/control-plane.md"},
    ]
    got = {n["id"] for n in f.filter_nodes(nodes, "L1")}
    assert got == {1}


def test_l3_caller_sees_all_present(tmp_path):
    f = _manifest(tmp_path)
    nodes = [
        {"id": 1, "source_file": "agent_core/CORE/USER.md"},
        {"id": 3, "source_file": "agent_memory/control-plane.md"},
    ]
    assert len(f.filter_nodes(nodes, "L3")) == 2


def test_clearance_defaults(monkeypatch):
    monkeypatch.delenv("GRAPHIFY_CALLER_CLEARANCE", raising=False)
    monkeypatch.delenv("GRAPHIFY_CALLER_IDENTITY", raising=False)
    assert caller_clearance("san") == "L6"
    assert caller_clearance("pooniclaw") == "L1"
    assert caller_clearance("nobody") == "L1"  # fail-safe
