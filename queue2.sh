#!/bin/bash
# Runs everything that remains (resumable) with no decisions left to a person. All rules are from PREREG.md.
cd "$(dirname "$0")/harness"
PY=/opt/homebrew/bin/python3.12
R=../results
LOG=$R/queue2.log
say() { echo "$(date '+%m-%d %H:%M') $*" | tee -a $LOG; }
step() { # arm run [extra args]; resumable, so retry up to 3 times after a crash
  local arm=$1 run=$2; shift 2
  for try in 1 2 3; do
    say "start $run $arm (try $try) $*"
    $PY run.py --arm $arm --run $run "$@" 2>&1 | tee -a $R/${run}_$arm.log
    if $PY - "$arm" "$run" "$@" <<'PYEOF'
import sys, json, os
sys.path.insert(0, ".")
import run, config as cfg
arm, runname = sys.argv[1], sys.argv[2]
items, _ = run.load_items()
order = run.select(runname, items, "--fallback90" in sys.argv)
path = os.path.join(cfg.RESULTS_DIR, runname, arm + ".jsonl")
done = {json.loads(l)["id"] for l in open(path)} if os.path.exists(path) else set()
sys.exit(0 if all(i in done for i in order) else 1)
PYEOF
    then say "done $run $arm"; return 0; fi
    sleep 30
  done
  say "FAILED $run $arm after 3 tries"; return 1
}
step B main
say "start pilot A on the fork"
$PY run.py --arm A --run pilot 2>&1 | tee -a $R/pilot_A.log
# Arm A pilot must have run on the fork; if it did not complete, arm A uses stock llama.cpp (PREREG: recorded fallback).
ABIN=""
n=$( [ -f $R/pilot/A.jsonl ] && wc -l < $R/pilot/A.jsonl || echo 0 )
if [ "$n" -lt 10 ]; then
  say "pilot A incomplete on the fork ($n/10): retrying pilot A on stock llama.cpp"
  ABIN="--server-bin /opt/homebrew/bin/llama-server"
  rm -f $R/pilot/A.jsonl
  step A pilot $ABIN || { say "ARM A CANNOT RUN - STOPPING"; exit 1; }
fi
# 60-hour rule: project total hours from pilot seconds per item; above 60 h, arms A and C use the 90-item fallback.
FB=$($PY - <<'PYEOF'
import json
def mean(p):
    rs = [json.loads(l) for l in open(p)]
    return sum(r["wall_s"] for r in rs) / len(rs)
a = mean("../results/pilot/A.jsonl"); c = mean("../results/pilot/C.jsonl")
b = mean("../results/main/B.jsonl")
# pilot items ran about half as long as test items on arm B; scale A and C the same way
scale = b / mean("../results/pilot/B.jsonl")
hours = (120 * b + 120 * a * scale + 120 * c * scale + 40 * (a * scale + b) + 12 * 2 * (a * scale + b)) / 3600
open("../results/projection.txt", "w").write("projected total hours: %.1f (A %.0f s/item pilot, scale %.2f)\n" % (hours, a, scale))
print("--fallback90" if hours > 60 else "")
PYEOF
)
say "projection: $(cat $R/projection.txt) fallback='$FB'"
step A main $ABIN $FB
step C main $FB
step A noise $ABIN
step B noise
step A xhigh $ABIN
step B xhigh
$PY analyze.py > $R/report.txt 2>&1
say "ALL DONE - report in results/report.txt"
