from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json

from .seam_plan import SeamFirstAssemblyPlan


class SeamPhase(str, Enum):
    FRESH_SEAM = "fresh_seam"
    CACHED_TAIL = "cached_tail"


@dataclass(frozen=True)
class SeamExecutionEvent:
    source_segment_id: str
    phase: SeamPhase
    token_start: int
    token_end: int
    new_position_start: int
    new_position_end: int


@dataclass
class SeamExecutionTrace:
    """Auditable proof that a backend executed fresh-seam-before-cached-tail.

    This is intentionally backend-neutral. Metal/MLX/Transformers integrations can
    emit events while executing a plan; qualification rejects traces that skip,
    reorder, overlap or double-process token ranges.
    """

    plan_digest: str
    events: list[SeamExecutionEvent] = field(default_factory=list)

    @classmethod
    def for_plan(cls, plan: SeamFirstAssemblyPlan) -> "SeamExecutionTrace":
        return cls(plan_digest=plan.digest)

    def record(self, event: SeamExecutionEvent) -> None:
        self.events.append(event)

    def validate_against(self, plan: SeamFirstAssemblyPlan) -> None:
        if self.plan_digest != plan.digest:
            raise ValueError("seam execution trace/plan digest mismatch")
        expected: list[SeamExecutionEvent] = []
        for step in plan.steps:
            expected.append(SeamExecutionEvent(
                step.source_segment_id,
                SeamPhase.FRESH_SEAM,
                step.fresh_seam_start,
                step.fresh_seam_end,
                step.new_position_start,
                step.new_position_start + step.seam_width,
            ))
            expected.append(SeamExecutionEvent(
                step.source_segment_id,
                SeamPhase.CACHED_TAIL,
                step.cached_tail_start,
                step.cached_tail_end,
                step.new_position_start + step.seam_width,
                step.new_position_end,
            ))
        if self.events != expected:
            raise ValueError("backend did not execute exact seam-first token/position schedule")

    @property
    def digest(self) -> str:
        raw = json.dumps({
            "plan_digest": self.plan_digest,
            "events": [asdict(e) | {"phase": e.phase.value} for e in self.events],
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(raw).hexdigest()

    @property
    def complete(self) -> bool:
        return bool(self.events)
