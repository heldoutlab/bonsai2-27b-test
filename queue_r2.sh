#!/bin/bash
# Round 2, unattended: main A, main B, noise A, noise B, xhigh A, xhigh B, idle re-grade, analysis. Resumable.
export BONSAI_ROUND=2
cd "$(dirname "$0")/harness"
PY=/opt/homebrew/bin/python3.12
R=../results_r2
LOG=$R/queue.log
say() { echo "$(date '+%m-%d %H:%M') $*" | tee -a $LOG; }
step() {
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
FB="${1:-}"
step A main $FB
step B main $FB
step A noise
step B noise
step A xhigh
step B xhigh
say "re-grading coding answers with the machine idle"
$PY regrade.py 2>&1 | tee -a $LOG
$PY analyze.py > $R/report.txt 2>&1
say "ALL DONE - report in results_r2/report.txt"
