"""Gate evidence for Nico card 35: planted secrets must never survive sanitization."""
from __future__ import annotations

import pytest

from ingest.collectors.base import Record
from ingest.sanitize import sanitize_record, scan_for_secrets

# Fake, structurally-valid-looking secrets. None are real.
PLANTED = [
    "sk-litellm-hq-FAKEKEY1234567890",
    "sk-ant-FAKE0000aaaabbbbccccddddee",
    "pk-lf-a1fc0b57c67b57dc394531c8e715cb48",
    "sk-lf-653ca068f18cbf9819259a92c293ea9c",
    "ghp_FAKEtoken0123456789abcdef0123456789",
    "AKIAIOSFODNN7FAKE000",
    "8286454982:FAKEAAEthisisaboteket_tokenABCDEFG",
    "password = hunter2supersecret",
    "https://bucket.s3.amazonaws.com/x?X-Amz-Signature=deadbeefcafef00d1234",
    "postgres://user:realpassword@db.internal:5432/app",
]


def _make(body: str, perm: str = "L1") -> Record:
    return Record(source="t", rel_path="t/x.md", title="t", body=body, permission_level=perm)


@pytest.mark.parametrize("secret", PLANTED)
def test_planted_secret_never_survives(secret):
    body = f"intro line\n{secret}\ntrailer line"
    res = sanitize_record(_make(body))
    # Either redacted to a surviving record with no secrets, or dropped fail-closed.
    if res.dropped:
        return
    assert scan_for_secrets(res.record.body) == [], f"leak: {secret}"
    assert secret not in res.record.body


def test_l4_and_above_dropped():
    for perm in ("L4", "L5", "L6"):
        res = sanitize_record(_make("anything", perm=perm))
        assert res.dropped and "permission" in res.reason


def test_full_label_formats_gate_correctly():
    # Nico stores full labels, not bare codes — these must still be dropped.
    for perm in ("L4 Destructive / Financial", "L5 PRODUCTION OPS", "L6 Human-only"):
        res = sanitize_record(_make("prod secret-ish content", perm=perm))
        assert res.dropped, f"{perm!r} should be dropped"
    # ...and lower labels must pass and be canonicalized in the manifest.
    res = sanitize_record(_make("note", perm="L2 SAFE STRUCTURED WRITE"))
    assert not res.dropped and res.record.permission_level == "L2"


def test_l3_and_below_pass():
    for perm in ("L0", "L1", "L2", "L3"):
        res = sanitize_record(_make("benign knowledge note", perm=perm))
        assert not res.dropped and res.record is not None


def test_clean_text_untouched():
    res = sanitize_record(_make("The finance-slip-api runs on desktop:8788 via MangoStickBot."))
    assert not res.dropped
    assert "finance-slip-api" in res.record.body
    assert res.redactions == 0
