import pytest
from kvcontinual.governance.sandbox import SandboxPolicy,HardenedSubprocessSandbox

def test_production_sandbox_fails_closed_without_backend(tmp_path):
    s=HardenedSubprocessSandbox(SandboxPolicy(allow_network=False),require_hardened=True,backend='none')
    with pytest.raises(RuntimeError):
        s.run(['true'],tmp_path)
