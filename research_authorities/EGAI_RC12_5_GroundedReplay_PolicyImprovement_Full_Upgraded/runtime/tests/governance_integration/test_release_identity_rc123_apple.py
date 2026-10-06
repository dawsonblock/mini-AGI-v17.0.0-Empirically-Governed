from pathlib import Path
import tomllib
from kvcontinual import __version__
from kvcontinual.governance.release_identity import RELEASE_VERSION,RELEASE_NAME
def test_runtime_release_identity_is_canonical():
    root=Path(__file__).resolve().parents[2]
    d=tomllib.loads((root/"pyproject.toml").read_text())
    assert RELEASE_VERSION==__version__==d["project"]["version"]=="12.5.0"
    assert RELEASE_NAME=="EGAI_RC12_3_1_TargetMac_Qualification_Full_Upgraded"
