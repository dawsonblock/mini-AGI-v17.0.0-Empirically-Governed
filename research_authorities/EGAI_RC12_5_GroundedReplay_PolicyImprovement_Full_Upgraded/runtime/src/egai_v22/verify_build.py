from pathlib import Path
from egai_v22.runtime.closure import runtime_closure_digest
def main():
    root=Path(__file__).resolve().parents[1]
    print({'runtime_closure_digest':runtime_closure_digest(root),'root':str(root)})
if __name__=='__main__': main()
