from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest_obj(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(_canon(obj)).hexdigest()


def digest_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def digest_tree(path: str | Path) -> str:
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    rows: list[dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(part in {"__pycache__", ".pytest_cache", ".git"} for part in p.relative_to(root).parts):
            continue
        rows.append({"path": rel, "sha256": digest_file(p), "bytes": p.stat().st_size})
    return digest_obj(rows)


@dataclass(frozen=True)
class TargetMacRuntimeIdentity:
    model_digest: str
    tokenizer_digest: str
    source_closure_digest: str
    hardware_profile_digest: str
    backend: str
    precision: str
    quantization: str
    adapter_digest: str = "sha256:" + "0" * 64
    execution_policy_digest: str = "sha256:" + "0" * 64

    @property
    def digest(self) -> str:
        return digest_obj(asdict(self))


@dataclass(frozen=True)
class EquivalenceThresholds:
    min_cases: int = 32
    exact_text_fraction: float = 1.0
    exact_token_fraction: float = 1.0
    require_token_ids: bool = False
    require_intermediate_metrics: bool = False
    max_state_abs_error: float = 1e-5
    max_logit_abs_error: float = 1e-4
    max_ttft_ratio: float = 1.0
    min_decode_speedup: float = 1.0

    def validate(self) -> None:
        if self.min_cases <= 0:
            raise ValueError("min_cases must be positive")
        if not 0.0 <= self.exact_text_fraction <= 1.0:
            raise ValueError("exact_text_fraction must be in [0,1]")
        if not 0.0 <= self.exact_token_fraction <= 1.0:
            raise ValueError("exact_token_fraction must be in [0,1]")
        if self.max_state_abs_error < 0 or self.max_logit_abs_error < 0:
            raise ValueError("error tolerances must be non-negative")
        if self.max_ttft_ratio <= 0 or self.min_decode_speedup <= 0:
            raise ValueError("performance thresholds must be positive")


def _cases(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = bundle.get("cases")
    if not isinstance(rows, list):
        raise ValueError("differential bundle requires cases list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("case must be an object")
        cid = str(row.get("case_id") or "")
        if not cid or cid in seen:
            raise ValueError("case_id must be non-empty and unique")
        seen.add(cid)
        out.append(row)
    return out


def _safe_ratio(num: float, den: float) -> float | None:
    if not math.isfinite(num) or not math.isfinite(den) or den <= 0:
        return None
    return num / den


def compare_differential_runs(baseline: dict[str, Any], accelerated: dict[str, Any]) -> dict[str, Any]:
    """Compare exact/baseline and accelerated execution bundles by case ID.

    This function is intentionally strict about case membership and prompt binding.
    Text/token equality is treated separately from intermediate-state/logit metrics.
    """
    b_rows = _cases(baseline)
    a_rows = _cases(accelerated)
    b = {str(x["case_id"]): x for x in b_rows}
    a = {str(x["case_id"]): x for x in a_rows}
    ids = sorted(set(b) | set(a))
    aligned = []
    for cid in ids:
        br = b.get(cid)
        ar = a.get(cid)
        present = br is not None and ar is not None
        prompt_ok = bool(present and br.get("prompt_digest") == ar.get("prompt_digest"))
        b_text = str(br.get("assistant_text", "")) if br else ""
        a_text = str(ar.get("assistant_text", "")) if ar else ""
        text_equal = bool(present and b_text == a_text)
        bt = br.get("output_token_ids") if br else None
        at = ar.get("output_token_ids") if ar else None
        token_ids_present = isinstance(bt, list) and isinstance(at, list)
        token_equal = bool(token_ids_present and bt == at)
        exact_ttft = float(br.get("ttft_s", 0.0)) if br else 0.0
        accel_ttft = float(ar.get("ttft_s", 0.0)) if ar else 0.0
        exact_tps = float(br.get("decode_tps", 0.0)) if br else 0.0
        accel_tps = float(ar.get("decode_tps", 0.0)) if ar else 0.0
        state_error = ar.get("state_max_abs_error") if ar else None
        logit_error = ar.get("logit_max_abs_error") if ar else None
        aligned.append({
            "case_id": cid,
            "present_in_both": present,
            "prompt_binding_ok": prompt_ok,
            "text_equal": text_equal,
            "token_ids_present": token_ids_present,
            "token_equal": token_equal,
            "state_max_abs_error": None if state_error is None else float(state_error),
            "logit_max_abs_error": None if logit_error is None else float(logit_error),
            "ttft_ratio": _safe_ratio(accel_ttft, exact_ttft),
            "decode_speedup": _safe_ratio(accel_tps, exact_tps),
        })
    n = len(aligned)
    present = [x for x in aligned if x["present_in_both"]]
    valid_ttft = [x["ttft_ratio"] for x in present if x["ttft_ratio"] is not None]
    valid_decode = [x["decode_speedup"] for x in present if x["decode_speedup"] is not None]
    state = [x["state_max_abs_error"] for x in present if x["state_max_abs_error"] is not None]
    logits = [x["logit_max_abs_error"] for x in present if x["logit_max_abs_error"] is not None]
    return {
        "cases": n,
        "paired_cases": len(present),
        "same_case_set": set(b) == set(a),
        "prompt_binding_fraction": (sum(x["prompt_binding_ok"] for x in present) / len(present)) if present else 0.0,
        "exact_text_fraction": (sum(x["text_equal"] for x in present) / len(present)) if present else 0.0,
        "token_ids_present_fraction": (sum(x["token_ids_present"] for x in present) / len(present)) if present else 0.0,
        "exact_token_fraction": (sum(x["token_equal"] for x in present if x["token_ids_present"]) / sum(x["token_ids_present"] for x in present)) if any(x["token_ids_present"] for x in present) else 0.0,
        "intermediate_state_fraction": len(state) / len(present) if present else 0.0,
        "logit_metric_fraction": len(logits) / len(present) if present else 0.0,
        "max_state_abs_error": max(state) if state else None,
        "max_logit_abs_error": max(logits) if logits else None,
        "median_ttft_ratio": statistics.median(valid_ttft) if valid_ttft else None,
        "median_decode_speedup": statistics.median(valid_decode) if valid_decode else None,
        "case_details_digest": digest_obj(aligned),
    }


def evaluate_summary(summary: dict[str, Any], thresholds: EquivalenceThresholds) -> dict[str, bool]:
    thresholds.validate()
    paired = int(summary.get("paired_cases", 0))
    token_present = float(summary.get("token_ids_present_fraction", 0.0))
    state_fraction = float(summary.get("intermediate_state_fraction", 0.0))
    logit_fraction = float(summary.get("logit_metric_fraction", 0.0))
    state_max = summary.get("max_state_abs_error")
    logit_max = summary.get("max_logit_abs_error")
    ttft_ratio = summary.get("median_ttft_ratio")
    decode_speedup = summary.get("median_decode_speedup")
    return {
        "case_count_ok": paired >= thresholds.min_cases and bool(summary.get("same_case_set")),
        "prompt_binding_ok": float(summary.get("prompt_binding_fraction", 0.0)) >= 1.0,
        "exact_text_ok": float(summary.get("exact_text_fraction", 0.0)) >= thresholds.exact_text_fraction,
        "exact_tokens_ok": (
            (not thresholds.require_token_ids and token_present == 0.0)
            or (token_present >= 1.0 and float(summary.get("exact_token_fraction", 0.0)) >= thresholds.exact_token_fraction)
        ),
        "intermediate_state_ok": (
            (not thresholds.require_intermediate_metrics and state_fraction == 0.0)
            or (state_fraction >= 1.0 and state_max is not None and float(state_max) <= thresholds.max_state_abs_error)
        ),
        "logit_equivalence_ok": (
            (not thresholds.require_intermediate_metrics and logit_fraction == 0.0)
            or (logit_fraction >= 1.0 and logit_max is not None and float(logit_max) <= thresholds.max_logit_abs_error)
        ),
        "ttft_ok": ttft_ratio is not None and float(ttft_ratio) <= thresholds.max_ttft_ratio,
        "decode_ok": decode_speedup is not None and float(decode_speedup) >= thresholds.min_decode_speedup,
    }


def build_target_mac_evidence(
    *,
    identity: TargetMacRuntimeIdentity,
    baseline: dict[str, Any],
    accelerated: dict[str, Any],
    thresholds: EquivalenceThresholds | None = None,
    hardware_profile: dict[str, Any] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    t = thresholds or EquivalenceThresholds()
    summary = compare_differential_runs(baseline, accelerated)
    gates = evaluate_summary(summary, t)
    body: dict[str, Any] = {
        "schema": "egai.apple.target-mac-qualification.v1",
        "authoritative_promotion": False,
        "release_version": "12.4.0",
        "identity": asdict(identity),
        "identity_digest": identity.digest,
        "hardware_profile": hardware_profile or {},
        "hardware_profile_digest": digest_obj(hardware_profile or {}),
        "thresholds": asdict(t),
        "summary": summary,
        "gates": gates,
        "passed_local_differential_gates": all(gates.values()),
        "baseline_bundle_digest": str(baseline.get("bundle_digest") or digest_obj(baseline)),
        "accelerated_bundle_digest": str(accelerated.get("bundle_digest") or digest_obj(accelerated)),
        "notes": notes,
        "promotion_note": "Evidence only. Independent qualification/promotion authority must bind and sign the exact runtime closure before accelerated execution is authorized.",
    }
    body["evidence_digest"] = digest_obj(body)
    return body


def verify_target_mac_evidence(raw: dict[str, Any]) -> bool:
    try:
        if not isinstance(raw, dict):
            return False
        body = dict(raw)
        observed_digest = str(body.pop("evidence_digest"))
        if observed_digest != digest_obj(body):
            return False
        if body.get("schema") != "egai.apple.target-mac-qualification.v1":
            return False
        if body.get("authoritative_promotion") is not False:
            return False
        ident = TargetMacRuntimeIdentity(**body["identity"])
        if body.get("identity_digest") != ident.digest:
            return False
        if body.get("hardware_profile_digest") != digest_obj(body.get("hardware_profile") or {}):
            return False
        thresholds = EquivalenceThresholds(**body["thresholds"])
        recomputed_gates = evaluate_summary(body["summary"], thresholds)
        if body.get("gates") != recomputed_gates:
            return False
        if body.get("passed_local_differential_gates") is not all(recomputed_gates.values()):
            return False
        return True
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
