from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'runtime/src'))
from kvcontinual.governance.source_closure import verify_source_closure
p=ROOT/'release/RC12_3_1_TARGET_MAC_SOURCE_CLOSURE.json'
if not verify_source_closure(ROOT,p):
    raise SystemExit('RC12.3.1 source closure verification failed')
print('RC12.3.1 target-Mac source closure: OK')
