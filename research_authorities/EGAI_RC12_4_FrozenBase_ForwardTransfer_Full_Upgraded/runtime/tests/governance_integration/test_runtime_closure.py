from egai.common.canonical import digest
from kvcontinual.governance.runtime_closure import RuntimeClosure,verify_runtime_closure
def test_closure():
 d=[digest({'i':i}) for i in range(6)];c=RuntimeClosure('r',*d);assert verify_runtime_closure(c,expected_base=d[0],expected_governance=d[1],expected_execution=d[2],expected_hardware=d[3],expected_source=d[4],expected_artifact=d[5])
