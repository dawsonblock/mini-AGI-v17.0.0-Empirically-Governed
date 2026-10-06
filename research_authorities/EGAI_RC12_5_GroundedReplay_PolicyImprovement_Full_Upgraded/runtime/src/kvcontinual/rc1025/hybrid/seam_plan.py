from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from kvcontinual.rc1025.cache.block import ExecutionArtifact
from kvcontinual.rc1025.source import SourceSegmentStore


@dataclass(frozen=True)
class SeamFirstSegmentPlan:
    source_segment_id: str
    source_token_digest: str
    artifact_content_digest: str
    execution_identity_digest: str
    source_token_count: int
    seam_width: int
    fresh_seam_start: int
    fresh_seam_end: int
    cached_tail_start: int
    cached_tail_end: int
    new_position_start: int
    new_position_end: int

    @property
    def tail_token_count(self) -> int:
        return self.cached_tail_end - self.cached_tail_start


@dataclass(frozen=True)
class SeamFirstAssemblyPlan:
    steps: tuple[SeamFirstSegmentPlan, ...]
    total_tokens: int
    fixed_seam_width: int

    @property
    def digest(self) -> str:
        raw = json.dumps({
            "steps": [asdict(x) for x in self.steps],
            "total_tokens": self.total_tokens,
            "fixed_seam_width": self.fixed_seam_width,
        }, sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    def validate(self) -> None:
        cursor = 0
        for step in self.steps:
            if not step.source_token_digest.startswith("sha256:"):
                raise ValueError("seam plan source digest is missing or invalid")
            if not step.artifact_content_digest.startswith("sha256:"):
                raise ValueError("seam plan artifact digest is missing or invalid")
            if not step.execution_identity_digest.startswith("sha256:"):
                raise ValueError("seam plan execution identity digest is missing or invalid")
            if step.seam_width != self.fixed_seam_width:
                raise ValueError("mixed seam widths are not allowed")
            if step.source_token_count <= step.seam_width:
                raise ValueError("segment is too short to have a reusable cached tail")
            if step.fresh_seam_start != 0 or step.fresh_seam_end != step.seam_width:
                raise ValueError("fresh seam must be the leading source range")
            if step.cached_tail_start != step.seam_width or step.cached_tail_end != step.source_token_count:
                raise ValueError("cached tail must begin exactly after the fresh seam")
            if step.new_position_start != cursor:
                raise ValueError("assembled positions must be contiguous")
            if step.new_position_end != cursor + step.source_token_count:
                raise ValueError("assembled position extent does not match source segment")
            cursor = step.new_position_end
        if cursor != self.total_tokens:
            raise ValueError("plan total_tokens mismatch")


def build_seam_first_plan(
    source_store: SourceSegmentStore,
    source_segment_ids: list[str],
    artifacts: list[ExecutionArtifact],
    *,
    seam_width: int = 8,
) -> SeamFirstAssemblyPlan:
    if len(source_segment_ids) != len(artifacts):
        raise ValueError("segment/artifact counts differ")
    cursor = 0
    steps: list[SeamFirstSegmentPlan] = []
    for sid, art in zip(source_segment_ids, artifacts):
        if art.source_segment_id != sid:
            raise ValueError("artifact order does not match selected source order")
        if art.fixed_seam_width != seam_width:
            raise ValueError("artifact seam width does not match planner seam width")
        seg = source_store.get(sid)
        if seg is None:
            raise KeyError(f"unknown source segment: {sid}")
        n = len(seg.tokens)
        if not art.source_token_digest:
            raise ValueError("artifact is not bound to authoritative source tokens")
        if art.source_token_digest != seg.token_digest:
            raise ValueError("artifact/source token digest mismatch")
        step = SeamFirstSegmentPlan(
            source_segment_id=sid,
            source_token_digest=seg.token_digest,
            artifact_content_digest=art.content_digest,
            execution_identity_digest=art.identity.digest,
            source_token_count=n,
            seam_width=seam_width,
            fresh_seam_start=0,
            fresh_seam_end=seam_width,
            cached_tail_start=seam_width,
            cached_tail_end=n,
            new_position_start=cursor,
            new_position_end=cursor+n,
        )
        steps.append(step)
        cursor += n
    plan = SeamFirstAssemblyPlan(tuple(steps), cursor, seam_width)
    plan.validate()
    return plan
