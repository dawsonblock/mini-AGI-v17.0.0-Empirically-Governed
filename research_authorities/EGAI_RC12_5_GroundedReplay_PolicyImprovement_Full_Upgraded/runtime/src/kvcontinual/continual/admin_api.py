from __future__ import annotations

import hmac
import os
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from kvcontinual.continual.config import load_runtime_settings
from kvcontinual.continual.qualification import QualificationPolicy
from kvcontinual.continual.registry import AdapterRegistry

settings = load_runtime_settings()
app = FastAPI(title="KVContinual Admin Control API", version="0.10.1")
registry = AdapterRegistry(settings.registry_root)
qualifier = QualificationPolicy()


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("KVCONTINUAL_ADMIN_TOKEN")
    if not expected:
        raise HTTPException(503, "admin mutation API disabled: KVCONTINUAL_ADMIN_TOKEN is not configured")
    if x_admin_token is None or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "invalid admin token")


class QualificationIn(BaseModel):
    candidate_id: str
    target_gain: float
    general_regression: float
    critical_pass: bool
    cache_quality_pass: bool
    evaluation_digest: str = ""
    evaluator_digest: str = ""


@app.get("/health")
def health():
    return {"ok": True, "version": "0.10.1", "authority": "admin-control"}


@app.post("/qualification", dependencies=[Depends(require_admin)])
def qualify(x: QualificationIn):
    q = qualifier.evaluate(
        candidate_id=x.candidate_id,
        target_gain=x.target_gain,
        general_regression=x.general_regression,
        critical_pass=x.critical_pass,
        cache_quality_pass=x.cache_quality_pass,
    )
    q.evaluation_digest = x.evaluation_digest
    q.evaluator_digest = x.evaluator_digest
    try:
        registry.write_qualification(q)
    except FileNotFoundError:
        raise HTTPException(404, "candidate not found")
    except (RuntimeError, ValueError) as e:
        raise HTTPException(409, str(e))
    return {"decision": q.decision.value, "reason": q.reason, "adapter_digest": q.adapter_digest}


@app.post("/promotion/{candidate_id}", dependencies=[Depends(require_admin)])
def promote(candidate_id: str):
    try:
        path = registry.promote(candidate_id)
        return {"promoted": candidate_id, "path": str(path), "cache_policy": "REPLAY_REQUIRED"}
    except (RuntimeError, ValueError) as e:
        raise HTTPException(409, str(e))


@app.post("/rollback", dependencies=[Depends(require_admin)])
def rollback():
    try:
        restored = registry.rollback()
        return {"restored": restored, "cache_policy": "REPLAY_REQUIRED"}
    except (RuntimeError, ValueError) as e:
        raise HTTPException(409, str(e))
