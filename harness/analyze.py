#!/opt/homebrew/bin/python3.12
"""Score the runs and apply the pre-registered rule mechanically. Written before any model was run.

  analyze.py            # prints the report and writes results/report.json
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg

BOOT = 10000

# Items found broken after the run are dropped for every arm (PREREG.md, "Items"); listed in results/dropped_items.json.
_dropped_path = os.path.join(cfg.RESULTS_DIR, "dropped_items.json")
DROPPED = set(json.load(open(_dropped_path))) if os.path.exists(_dropped_path) else set()


def load(run, arm):
    path = os.path.join(cfg.RESULTS_DIR, run, "%s.jsonl" % arm)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return {r["id"]: r for r in map(json.loads, filter(str.strip, f)) if r["id"] not in DROPPED}


def score(rec, lenient=False):
    if lenient and rec["family"] == "tools":
        return 1.0 if rec.get("correct_lenient") else 0.0
    return 1.0 if rec["correct"] else 0.0


def pct(xs):
    return 100.0 * sum(xs) / len(xs) if xs else float("nan")


def acc(recs, ids, lenient=False):
    return pct([score(recs[i], lenient) for i in ids])


def by_family(recs, ids):
    out = {f: [i for i in ids if recs[i]["family"] == f] for f in cfg.FAMILIES}
    return {f: v for f, v in out.items() if v}


def paired_boot(x, y, ids, fams, lenient=False, seed=0):
    """Stratified paired bootstrap over items. Returns 95% intervals for x-y (points) and y/x (retention, %)."""
    rng = random.Random(seed)
    sx = {i: score(x[i], lenient) for i in ids}
    sy = {i: score(y[i], lenient) for i in ids}
    diffs, rets = [], []
    for _ in range(BOOT):
        sample = [rng.choice(members) for members in fams.values() for _ in members]
        ax, ay = pct([sx[i] for i in sample]), pct([sy[i] for i in sample])
        diffs.append(ax - ay)
        if ax > 0:
            rets.append(100.0 * ay / ax)
    q = lambda v, p: sorted(v)[min(len(v) - 1, max(0, int(p * len(v))))]
    return (q(diffs, 0.025), q(diffs, 0.975)), ((q(rets, 0.025), q(rets, 0.975)) if rets else (float("nan"),) * 2)


def compare(x, y, ids, lenient=False):
    fams = by_family(x, ids)
    ci, rci = paired_boot(x, y, ids, fams, lenient)
    ax, ay = acc(x, ids, lenient), acc(y, ids, lenient)
    out = {"n": len(ids), "x": ax, "y": ay, "diff": ax - ay, "diff_ci": ci,
           "retention": 100.0 * ay / ax if ax else float("nan"), "retention_ci": rci, "families": {}}
    for f, members in fams.items():
        fci, _ = paired_boot(x, y, members, {f: members}, lenient)
        fx, fy = acc(x, members, lenient), acc(y, members, lenient)
        out["families"][f] = {"n": len(members), "x": fx, "y": fy, "diff": fx - fy, "diff_ci": fci}
    return out


def noise_floor(main, noise):
    """Per arm: |accuracy(seed 1) - accuracy(seed 2)| on the re-run items. Floor = the larger of arms A and B."""
    out = {"overall": 0.0, "families": {f: 0.0 for f in cfg.FAMILIES}, "per_arm": {}}
    for arm in ("A", "B"):
        m, n = main.get(arm, {}), noise.get(arm, {})
        ids = [i for i in n if i in m]
        if not ids:
            continue
        fams = by_family(n, ids)
        d = {"n": len(ids), "overall": abs(acc(m, ids) - acc(n, ids)),
             "flips": sum(1 for i in ids if score(m[i]) != score(n[i])),
             "families": {f: abs(acc(m, v) - acc(n, v)) for f, v in fams.items()}}
        out["per_arm"][arm] = d
        out["overall"] = max(out["overall"], d["overall"])
        for f, v in d["families"].items():
            out["families"][f] = max(out["families"][f], v)
    return out


def verdict(ab, bc, floor):
    """The rule in PREREG.md, applied to strict scores."""
    fam_gaps = {f: v["diff"] for f, v in ab["families"].items()}
    if ab["diff"] >= 10 and ab["diff_ci"][0] > 0:
        headline = "NOT NEAR-LOSSLESS"
    elif ab["diff"] <= 5 and all(g <= 10 for g in fam_gaps.values()):
        headline = "NO LARGE LOSS FOUND"
    else:
        headline = "NOT RESOLVED"
    practical = None
    if bc:
        wins = [f for f, v in bc["families"].items() if v["diff"] > floor["families"].get(f, 0.0)]
        practical = {"families_where_B_beats_C_by_more_than_noise": wins, "worth_it": len(wins) >= 2}
    return {"headline": headline, "practical": practical}


def describe(recs):
    ids = list(recs)
    return {"n": len(ids), "accuracy": acc(recs, ids), "accuracy_lenient": acc(recs, ids, True),
            "families": {f: acc(recs, v) for f, v in by_family(recs, ids).items()},
            "tools_lenient": acc(recs, by_family(recs, ids).get("tools", []), True),
            "truncated": sum(1 for r in recs.values() if r.get("truncated")),
            "server_errors": sum(1 for r in recs.values() if r.get("server_error")),
            "tool_tasks_needing_repair": sum(1 for r in recs.values() if r.get("repairs")),
            "mean_tokens": sum(r["completion_tokens"] for r in recs.values()) / max(len(ids), 1),
            "hours": sum(r["wall_s"] for r in recs.values()) / 3600.0}


def main():
    main_runs = {a: load("main", a) for a in cfg.ARMS}
    noise = {a: load("noise", a) for a in ("A", "B")}
    xhigh = {a: load("xhigh", a) for a in ("A", "B")}
    report = {"arms": {a: describe(r) for a, r in main_runs.items() if r}}
    A, B, C = main_runs["A"], main_runs["B"], main_runs["C"]
    common = [i for i in A if i in B]
    if common:
        report["A_minus_B"] = compare(A, B, common)
        report["A_minus_B_lenient"] = compare(A, B, common, lenient=True)
    common_bc = [i for i in B if i in C]
    if common_bc:
        report["B_minus_C"] = compare(B, C, common_bc)
    report["noise_floor"] = noise_floor(main_runs, noise)
    xi = [i for i in xhigh["A"] if i in xhigh["B"]]
    if xi:
        report["xhigh_A_minus_B"] = compare(xhigh["A"], xhigh["B"], xi)
        report["medium_on_same_items"] = compare(A, B, [i for i in xi if i in A and i in B])
    if common:
        report["verdict"] = verdict(report["A_minus_B"], report.get("B_minus_C"), report["noise_floor"])
    with open(os.path.join(cfg.RESULTS_DIR, "report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
