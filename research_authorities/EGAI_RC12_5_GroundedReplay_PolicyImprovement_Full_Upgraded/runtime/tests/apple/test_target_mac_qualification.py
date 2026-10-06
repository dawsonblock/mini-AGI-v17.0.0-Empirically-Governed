from kvcontinual.execution.platforms.target_mac_qualification import *
def bundle(mode,text="ok",ttft=.2,tps=20,prompt="sha256:p",tokens=None,state=None,logit=None,n=4):
    rows=[]
    for i in range(n):
        r={"case_id":f"c{i}","prompt_digest":prompt,"assistant_text":text,"ttft_s":ttft,"decode_tps":tps}
        if tokens is not None:r["output_token_ids"]=tokens
        if state is not None:r["state_max_abs_error"]=state
        if logit is not None:r["logit_max_abs_error"]=logit
        rows.append(r)
    return {"mode":mode,"cases":rows}
def ident():return TargetMacRuntimeIdentity("sha256:m","sha256:t","sha256:s","sha256:h","native-metal","fp16","none")
def test_exact_pass():
    s=compare_differential_runs(bundle("baseline",tokens=[1,2]),bundle("accelerated",ttft=.1,tps=40,tokens=[1,2],state=1e-7,logit=1e-7)); assert all(evaluate_summary(s,EquivalenceThresholds(min_cases=4,require_token_ids=True,require_intermediate_metrics=True)).values())
def test_prompt_mismatch_fails(): assert not evaluate_summary(compare_differential_runs(bundle("b"),bundle("a",prompt="sha256:x")),EquivalenceThresholds(min_cases=4))["prompt_binding_ok"]
def test_text_mismatch_fails(): assert not evaluate_summary(compare_differential_runs(bundle("b",text="x"),bundle("a",text="y")),EquivalenceThresholds(min_cases=4))["exact_text_ok"]
def test_missing_intermediate_fails_when_required():
    g=evaluate_summary(compare_differential_runs(bundle("b"),bundle("a")),EquivalenceThresholds(min_cases=4,require_intermediate_metrics=True)); assert not g["intermediate_state_ok"] and not g["logit_equivalence_ok"]
def test_digest_tamper_detected():
    e=build_target_mac_evidence(identity=ident(),baseline=bundle("b"),accelerated=bundle("a",ttft=.1,tps=40),thresholds=EquivalenceThresholds(min_cases=4),hardware_profile={"chip":"M"}); assert verify_target_mac_evidence(e); e["summary"]["cases"]=9; assert not verify_target_mac_evidence(e)
