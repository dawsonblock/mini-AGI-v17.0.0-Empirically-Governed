from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import uuid


@dataclass
class SourceSegment:
    tokens: list[int]
    source_locator: str
    observed_from: str | None = None
    observed_until: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    semantic_refs: list[str] = field(default_factory=list)
    canonical_stream: str | None = None
    canonical_start: int | None = None
    canonical_end: int | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def token_digest(self) -> str:
        raw = json.dumps(self.tokens, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()


class SourceSegmentStore:
    """Durable source-of-truth tokens. No model-derived neural state is stored here."""

    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS source_segment (
                id TEXT PRIMARY KEY,
                tokens TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                observed_from TEXT,
                observed_until TEXT,
                evidence_ids TEXT NOT NULL,
                semantic_refs TEXT NOT NULL,
                canonical_stream TEXT,
                canonical_start INTEGER,
                canonical_end INTEGER,
                token_digest TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_source_stream ON source_segment(canonical_stream, canonical_start)")
        self.conn.commit()

    def put(self, s: SourceSegment) -> str:
        """Insert an immutable source segment.

        Reusing an existing ID is allowed only when the complete persisted source
        record is byte-for-byte equivalent. A caller cannot silently replace the
        authoritative token sequence underneath already-compiled neural artifacts.
        """
        existing = self.conn.execute("SELECT * FROM source_segment WHERE id=?", (s.id,)).fetchone()
        row = (s.id, json.dumps(s.tokens), s.source_locator, s.observed_from, s.observed_until,
               json.dumps(s.evidence_ids), json.dumps(s.semantic_refs), s.canonical_stream,
               s.canonical_start, s.canonical_end, s.token_digest, s.created_at)
        if existing is not None:
            persisted = tuple(existing[k] for k in (
                "id", "tokens", "source_locator", "observed_from", "observed_until",
                "evidence_ids", "semantic_refs", "canonical_stream", "canonical_start",
                "canonical_end", "token_digest", "created_at"
            ))
            if persisted != row:
                raise ValueError(f"immutable source segment conflict for id {s.id}")
            return s.id
        self.conn.execute("INSERT INTO source_segment VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", row)
        self.conn.commit()
        return s.id

    def get(self, segment_id: str) -> SourceSegment | None:
        row = self.conn.execute("SELECT * FROM source_segment WHERE id=?", (segment_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        persisted_digest = d.pop("token_digest")
        d["tokens"] = json.loads(d["tokens"])
        d["evidence_ids"] = json.loads(d["evidence_ids"])
        d["semantic_refs"] = json.loads(d["semantic_refs"])
        out = SourceSegment(**d)
        if out.token_digest != persisted_digest:
            raise ValueError(f"source segment token digest mismatch for id {segment_id}")
        return out

    def token_digest(self, segment_id: str) -> str | None:
        row = self.conn.execute("SELECT token_digest FROM source_segment WHERE id=?", (segment_id,)).fetchone()
        return None if row is None else str(row[0])

    def assembled_tokens(self, segment_ids: list[str]) -> list[int]:
        out: list[int] = []
        for sid in segment_ids:
            seg = self.get(sid)
            if seg is None:
                raise KeyError(f"unknown source segment: {sid}")
            out.extend(seg.tokens)
        return out

    def prefix_token_digest(self, segment_ids: list[str], token_position: int) -> str:
        if token_position < 0:
            raise ValueError("token_position must be >= 0")
        tokens = self.assembled_tokens(segment_ids)
        if token_position > len(tokens):
            raise ValueError("checkpoint token_position exceeds selected prefix length")
        raw = json.dumps(tokens[:token_position], separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def classify_topology(self, segment_ids: list[str]):
        from kvcontinual.rc1025.types import AssemblyTopology
        segments = [self.get(x) for x in segment_ids]
        if not segments or any(s is None for s in segments):
            return AssemblyTopology.UNKNOWN
        assert all(s is not None for s in segments)
        stream = segments[0].canonical_stream
        if stream is None or any(s.canonical_stream != stream for s in segments):
            return AssemblyTopology.ARBITRARY
        positions = [(s.canonical_start, s.canonical_end) for s in segments]
        if any(a is None or b is None for a, b in positions):
            return AssemblyTopology.ARBITRARY
        contiguous = all(positions[i][1] == positions[i+1][0] for i in range(len(positions)-1))
        monotone = all(positions[i][0] <= positions[i+1][0] for i in range(len(positions)-1))
        # A shared contiguous span is an exact *prefix* only when it begins at
        # canonical position zero. A middle-of-stream span such as D,E is not a
        # prefix and must not be allowed to reuse a prefix checkpoint.
        begins_at_zero = positions[0][0] == 0
        if contiguous and monotone and begins_at_zero:
            return AssemblyTopology.EXACT_PREFIX
        return AssemblyTopology.ARBITRARY
