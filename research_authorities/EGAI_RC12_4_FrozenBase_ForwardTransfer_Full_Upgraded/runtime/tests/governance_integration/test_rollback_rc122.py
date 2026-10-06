from egai.common.canonical import digest
from kvcontinual.governance.rollback import RuntimeState,AtomicRuntimePointer

def test_atomic_runtime_pointer(tmp_path):
    ds=[digest({'i':i}) for i in range(8)];s=RuntimeState(ds[0],ds[1],(ds[2],),ds[3],ds[4],ds[5],ds[6],ds[7]);p=AtomicRuntimePointer(tmp_path/'active.json');p.activate(s);assert p.current()['runtime_digest']==ds[0]
