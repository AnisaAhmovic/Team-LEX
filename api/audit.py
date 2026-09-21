"""S4-10: local SQLite audit records with explicit fields and bounded redaction.

This is an inspectable prototype trail, not an immutable compliance ledger.
No request headers, identity, IP address, credentials or environment dumps enter it.
"""

import json
import math
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = "lex-interaction-v1"
DEFAULT_AUDIT_PATH = Path(__file__).resolve().parent.parent / "var/audit/interactions.sqlite3"
REDACTION_VERSION = "best-effort-v1"
_PATTERNS = [
    re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)", re.S),
    re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=:-]+", re.I),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16})\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    # Redact the rest of the line, including quoted or multiword secret values.
    re.compile(r"\b(?:password|passwd|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|secret(?:[_ -]?key)?|authorization|cookie)\b[\"']?\s*(?:[:=]|\bis\b)\s*[^\r\n]+", re.I),
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I),
    re.compile(r"\b(?:student|staff)\s*(?:id|number|no\.?)\s*[:=#]?\s*\d+", re.I),
    re.compile(r"(?<!\w)(?:\+61[\s-]?|0)[23478](?:[\s()-]*\d){8}(?!\d)"),
    re.compile(r"(?<!\w)\d{7,19}(?!\w)"),
    re.compile(r"(?i)https?://[^\s/@:]+:[^\s/@]+@[^\s]+"),
]


def new_record(endpoint):
    return {
        "schema_version": SCHEMA_VERSION,
        "interaction_id": str(uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "question": None,
        "retrieval": {"outcome": "not_started", "config": None, "candidates": []},
        "selection": {"selected_context": [], "excluded": [], "source_evidence": []},
        "generation": {"attempted": False},
    }


def sanitise_record(record):
    """Best-effort defence for free text. This is not guaranteed anonymisation."""
    redacted, truncated = [], []

    def clean(value, path):
        if isinstance(value, str):
            # Server-generated correlation fields must remain stable for lookup.
            if path in {"interaction_id", "timestamp_utc"}:
                return value
            cleaned = value.encode("utf-8", errors="replace").decode("utf-8")
            for pattern in _PATTERNS:
                cleaned = pattern.sub("[REDACTED]", cleaned)
            if cleaned != value:
                redacted.append(path)
            limit = 500 if path == "question" else 30000
            if len(cleaned) > limit:
                cleaned = cleaned[:limit]
                truncated.append(path)
            return cleaned
        if isinstance(value, dict):
            return {key: clean(item, f"{path}.{key}" if path else key) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item, f"{path}[{i}]") for i, item in enumerate(value)]
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        # Never stringify unexpected objects, which could reveal internals.
        return None

    safe = clean(record, "")
    safe["privacy"] = {
        "redaction_version": REDACTION_VERSION,
        "redacted_fields": redacted, "truncated_fields": truncated,
    }
    return safe


class AuditStore:
    """One committed JSON record per completed request, safe for concurrent writers."""

    def __init__(self, path=DEFAULT_AUDIT_PATH, retention_days=30):
        self.path = Path(path)
        self.retention_days = int(retention_days)
        if self.retention_days < 1:
            raise ValueError("Audit retention must be at least one day.")

    def append(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        payload = json.dumps(sanitise_record(record), ensure_ascii=False, allow_nan=False)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        with closing(sqlite3.connect(self.path, timeout=10)) as connection:
            connection.execute("PRAGMA secure_delete=ON")
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS interactions (
                    interaction_id TEXT PRIMARY KEY, timestamp_utc TEXT NOT NULL,
                    outcome TEXT NOT NULL, record_json TEXT NOT NULL
                )""")
                connection.execute("CREATE INDEX IF NOT EXISTS audit_time ON interactions(timestamp_utc)")
                connection.execute("DELETE FROM interactions WHERE timestamp_utc < ?", (cutoff,))
                connection.execute("INSERT INTO interactions VALUES (?, ?, ?, ?)", (
                    record["interaction_id"], record["timestamp_utc"], record["outcome"], payload,
                ))
        return record["interaction_id"]

    def read(self, interaction_id=None, limit=20):
        """Local operator access only. There is deliberately no public audit API."""
        if not self.path.exists():
            return []
        uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            if interaction_id:
                rows = connection.execute(
                    "SELECT record_json FROM interactions WHERE interaction_id = ?", (interaction_id,),
                )
            else:
                rows = connection.execute(
                    "SELECT record_json FROM interactions ORDER BY timestamp_utc DESC LIMIT ?",
                    (max(1, min(int(limit), 1000)),),
                )
            return [json.loads(row[0]) for row in rows]

    def purge_expired(self):
        if not self.path.exists():
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA secure_delete=ON")
            with connection:
                return connection.execute("DELETE FROM interactions WHERE timestamp_utc < ?", (cutoff,)).rowcount
