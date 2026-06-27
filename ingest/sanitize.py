"""Security gate for the memory graph (Nico card 35).

Every Record passes through `sanitize_record` before it reaches the staging corpus.
Two guarantees:

  1. Secrets are redacted. Known credential shapes (API keys, bearer tokens,
     passwords, presigned URLs, private keys) are replaced with [REDACTED:<kind>].
  2. L4+ never enters the graph. Records at or above `drop_at` (default L4) are
     dropped entirely and logged to excluded.log with a reason but NO content.

A record whose body still matches a secret pattern after redaction is dropped
(fail-closed) rather than risk a leak. Tests plant fake secrets and assert zero
survive — that test output is the evidence for the gate card.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .collectors.base import Record, perm_rank, normalize_level

# --- secret patterns -------------------------------------------------------
# (kind, compiled regex). Order matters: most specific first.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("openai_key",      re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b")),
    ("anthropic_key",   re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}\b")),
    ("litellm_key",     re.compile(r"\bsk-litellm-[A-Za-z0-9_\-]+\b")),
    ("langfuse_key",    re.compile(r"\b[ps]k-lf-[A-Za-z0-9]{8,}\b")),
    ("github_token",    re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b")),
    ("slack_token",     re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("aws_key",         re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("telegram_token",  re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{30,}\b")),
    ("private_key",     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt",             re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("bearer",          re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}\b")),
    ("presigned_url",   re.compile(r"https?://\S+[?&](X-Amz-Signature|Signature|sig)=[A-Za-z0-9%._\-]+")),
    ("url_userinfo",    re.compile(r"\b[a-z]+://[^/\s:@]+:[^/\s@]+@")),
    # key:value style assignments naming a secret (password=..., token: ...)
    ("named_secret",    re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token|access[_-]?key)\b\s*[:=]\s*[\"']?([^\s\"',]{6,})")),
]


@dataclass
class Result:
    record: Record | None        # sanitized Record, or None if dropped
    dropped: bool
    reason: str = ""
    redactions: int = 0


def _redact(text: str) -> tuple[str, int]:
    count = 0
    for kind, pat in _PATTERNS:
        if kind == "named_secret":
            def _sub(m):
                nonlocal count
                count += 1
                # No ':'/'=' separator in the replacement, so the placeholder
                # cannot re-match the key:value pattern on a rescan.
                return f"{m.group(1)} [REDACTED:{kind}]"
            text = pat.sub(_sub, text)
        else:
            text, n = pat.subn(f"[REDACTED:{kind}]", text)
            count += n
    return text, count


def _residual_secret(text: str) -> str | None:
    """Return the kind of any secret pattern still present (post-redaction)."""
    for kind, pat in _PATTERNS:
        if kind == "named_secret":
            continue  # handled by substitution; value already replaced
        if pat.search(text):
            return kind
    return None


def sanitize_record(rec: Record, drop_at: str = "L4") -> Result:
    # 0. canonicalize the level so labels like "L5 PRODUCTION OPS" gate correctly
    rec.permission_level = normalize_level(rec.permission_level)

    # 1. permission gate — L4+ never enters the graph
    if perm_rank(rec.permission_level) >= perm_rank(drop_at):
        return Result(None, True, reason=f"permission>={drop_at} ({rec.permission_level})")

    # 2. redact secrets in body and title
    body, n_body = _redact(rec.body)
    title, n_title = _redact(rec.title)

    # 3. fail-closed: if anything still looks like a secret, drop the record
    residual = _residual_secret(body) or _residual_secret(title)
    if residual:
        return Result(None, True, reason=f"residual_secret:{residual}")

    rec.body = body
    rec.title = title
    return Result(rec, False, redactions=n_body + n_title)


def scan_for_secrets(text: str) -> list[str]:
    """Convenience for tests/CI: list secret kinds present in raw text."""
    return [kind for kind, pat in _PATTERNS if pat.search(text)]
