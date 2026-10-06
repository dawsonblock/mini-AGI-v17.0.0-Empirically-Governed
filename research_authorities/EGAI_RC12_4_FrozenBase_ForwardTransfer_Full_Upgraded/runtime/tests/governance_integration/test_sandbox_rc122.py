import sys
import pytest
from kvcontinual.governance.sandbox import *

def test_sandbox_network_capability_and_basic_execution(tmp_path):
    s=LocalSubprocessSandbox(SandboxPolicy(timeout_s=3,max_cpu_s=2,max_memory_bytes=1024*1024*1024))
    with pytest.raises(PermissionError):s.run([sys.executable,'-c','print(1)'],tmp_path,network_requested=True)
    r=s.run([sys.executable,'-c','print("ok")'],tmp_path);assert r.returncode==0 and 'ok' in r.stdout
