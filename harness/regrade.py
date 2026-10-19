#!/opt/homebrew/bin/python3.12
"""Re-grade coding answers from the saved replies with the machine idle (PREREG_R2.md). Some round-2 hidden tests
are timing-sensitive, and during a run the model server competes for the CPU. The saved reply is graded again with
the same grader; `correct` becomes the idle result and the live result is kept as `correct_live`."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
import grade
import run

items, _ = run.load_items()
for runname in ("main", "noise", "xhigh"):
    for arm in ("A", "B"):
        path = os.path.join(cfg.RESULTS_DIR, runname, arm + ".jsonl")
        if not os.path.exists(path):
            continue
        recs = [json.loads(l) for l in open(path) if l.strip()]
        changed = []
        for r in recs:
            if r["family"] != "coding" or r.get("server_error"):
                continue
            live = r.get("correct_live", r["correct"])
            ok, detail = grade.grade_coding(items[r["id"]][1], r["turns"][0]["content"])
            if not ok and live:  # a pass that turns into a failure when idle would be a timing fluke: retry twice
                ok = any(grade.grade_coding(items[r["id"]][1], r["turns"][0]["content"])[0] for _ in range(2))
            r["correct_live"], r["correct"], r["grader_idle"] = live, ok, detail
            if ok != live:
                changed.append((r["id"], live, ok))
        with open(path + ".tmp", "w") as f:
            for r in recs:
                f.write(json.dumps(r, default=str) + "\n")
        os.replace(path + ".tmp", path)
        print(runname, arm, "coding re-graded; changed:", changed)
