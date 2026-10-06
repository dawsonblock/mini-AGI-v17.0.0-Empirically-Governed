from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3
from . import __version__


def _sqlite_row(path: Path, sql: str):
    if not path.exists():
        return None
    try:
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        try:
            row = c.execute(sql).fetchone()
            return None if row is None else dict(row)
        finally:
            c.close()
    except sqlite3.Error:
        return {"error": "unreadable sqlite state"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="egai", description="EGAI RC14 canonical converged governed continual runtime CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("version")
    info = sub.add_parser("inspect-root")
    info.add_argument("root")
    rc14 = sub.add_parser("rc14-inspect", help="inspect RC14 candidate/StateEpoch control heads")
    rc14.add_argument("root")
    args = p.parse_args(argv)
    if args.cmd == "version":
        print(__version__)
        return 0
    root = Path(args.root)
    if args.cmd == "inspect-root":
        result = {
            "version": __version__,
            "root": str(root),
            "evidence_db": (root / "evidence" / "ledger.sqlite3").exists(),
            "skill_db": (root / "skills" / "skills.sqlite3").exists(),
            "belief_db": (root / "beliefs" / "beliefs.sqlite3").exists(),
            "runtime_activation_db": (root / "runtime_activation" / "activation.sqlite3").exists(),
            "legacy_state_epoch_db": (root / "state_epochs" / "epochs.sqlite3").exists(),
            "rc14_candidate_state_db": (root / "rc14_candidates" / "candidate_state.sqlite3").exists(),
            "rc14_state_epoch_db": (root / "state_epochs_rc14" / "epochs.sqlite3").exists(),
            "rc14_fresh_task_db": (root / "rc14_fresh_tasks" / "fresh_tasks.sqlite3").exists(),
            "rc14_continual_experiment_db": (root / "rc14_science" / "experiments" / "experiments.sqlite3").exists(),
            "rc14_experiment_protocol_db": (root / "rc14_science" / "protocol" / "protocol.sqlite3").exists(),
        }
    else:
        result = {
            "version": __version__,
            "root": str(root),
            "candidate_count": None,
            "candidate_states": None,
            "epoch_control": _sqlite_row(root / "state_epochs_rc14" / "epochs.sqlite3", "SELECT * FROM control_state WHERE singleton=1"),
            "continual_experiment_head": _sqlite_row(root / "rc14_science" / "experiments" / "experiments.sqlite3", "SELECT * FROM state WHERE singleton=1"),
            "experiment_protocol_head": _sqlite_row(root / "rc14_science" / "protocol" / "protocol.sqlite3", "SELECT * FROM state WHERE singleton=1"),
        }
        cpath = root / "rc14_candidates" / "candidate_state.sqlite3"
        if cpath.exists():
            try:
                c = sqlite3.connect(cpath)
                try:
                    result["candidate_count"] = int(c.execute("SELECT COUNT(*) FROM candidate_state").fetchone()[0])
                    result["candidate_states"] = {row[0]: int(row[1]) for row in c.execute("SELECT state,COUNT(*) FROM candidate_state GROUP BY state ORDER BY state")}
                finally:
                    c.close()
            except sqlite3.Error:
                result["candidate_states"] = {"error": 1}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
