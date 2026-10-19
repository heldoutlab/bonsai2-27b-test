#!/opt/homebrew/bin/python3.12
"""Run one arm on one item set against a local llama-server. Resumable: finished items are skipped.

  run.py --arm B --run pilot          # 10 throwaway items, timing only
  run.py --arm A --run main           # the test set, medium effort, seed 1001
  run.py --arm A --run noise          # 40-item re-run, seed 2002
  run.py --arm B --run xhigh          # 12-item subset at xhigh effort
"""
import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg
import grade

sys.path.insert(0, cfg.ITEMS_DIR)


def load_items():
    import coding_items
    import reasoning_items
    import tool_items
    fam = {}
    for it in reasoning_items.ITEMS:
        fam[it["id"]] = ("reasoning", it)
    for it in coding_items.ITEMS:
        fam[it["id"]] = ("coding", it)
    for it in tool_items.TASKS:
        fam[it["id"]] = ("tools", it)
    return fam, tool_items.ENVS


def is_pilot(item_id):
    return item_id[1] == "P"


def select(run, items, fallback90=False):
    by_family = {f: [] for f in cfg.FAMILIES}
    for item_id, (family, _) in items.items():
        if is_pilot(item_id) == (run == "pilot"):
            by_family[family].append(item_id)
    chosen = []
    for family in cfg.FAMILIES:
        ids = cfg.stable_order(by_family[family])
        if run != "pilot" and fallback90:
            ids = ids[: cfg.FALLBACK_PER_FAMILY]
        if run == "noise":
            ids = ids[: cfg.NOISE_PER_FAMILY[family]]
        elif run == "xhigh":
            n = cfg.XHIGH_PER_FAMILY
            ids = ids[: n[family] if isinstance(n, dict) else n]
        chosen += ids
    # interleave families so a partial run is still balanced
    order = cfg.stable_order(chosen)
    return order


# ---------- server ----------

def http(path, body=None, timeout=60):
    url = "http://127.0.0.1:%d%s" % (cfg.PORT, path)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def start_server(model_path, server_bin, sampler, log_path, context=None):
    cmd = [server_bin, "-m", model_path, "--host", "127.0.0.1", "--port", str(cfg.PORT),
           "-ngl", "99", "-fa", "on", "-c", str(context or cfg.CONTEXT), "-np", "1", "--jinja",
           "--temp", str(sampler["temperature"]), "--top-p", str(sampler["top_p"]), "--top-k", str(sampler["top_k"])]
    if "min_p" in sampler:
        cmd += ["--min-p", str(sampler["min_p"])]
    log = open(log_path, "a")
    log.write("\n# %s\n# %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), " ".join(cmd)))
    log.flush()
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.time() + 900
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit("llama-server exited during load; see " + log_path)
        try:
            if http("/health", timeout=5).get("status") == "ok":
                return proc, cmd
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(3)
    proc.terminate()
    raise SystemExit("llama-server did not become healthy in 15 minutes")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- one chat turn ----------

def chat(arm, messages, effort, seed, tools=None):
    body = {"model": "local", "messages": messages, "seed": seed, "max_tokens": cfg.MAX_TOKENS[effort], "stream": False}
    body.update(arm["sampler"])
    if arm.get("effort_field"):
        body["reasoning_effort"] = effort
    body.update(copy.deepcopy(arm.get("extra_body", {})))
    if tools:
        body["tools"] = tools
    t0 = time.time()
    try:
        resp = http("/v1/chat/completions", body, timeout=cfg.REQUEST_TIMEOUT_S)
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "error_body": e.read().decode(errors="replace")[:2000], "wall_s": round(time.time() - t0, 1)}
    choice = resp["choices"][0]
    msg = choice["message"]
    return {
        "content": msg.get("content") or "",
        "reasoning": msg.get("reasoning_content") or "",
        "tool_calls": msg.get("tool_calls") or [],
        "finish_reason": choice.get("finish_reason"),
        "usage": resp.get("usage", {}),
        "timings": resp.get("timings", {}),
        "wall_s": round(time.time() - t0, 1),
    }


def base_messages(prompt):
    return [{"role": "system", "content": cfg.SYSTEM_PROMPT}, {"role": "user", "content": prompt}]


def tokens(turns):
    return sum(t.get("usage", {}).get("completion_tokens", 0) for t in turns)


# ---------- families ----------

def run_single(arm, family, item, effort, seed):
    turn = chat(arm, base_messages(item["prompt"]), effort, seed)
    rec = {"turns": [turn], "truncated": turn.get("finish_reason") == "length", "server_error": "http_error" in turn}
    if rec["server_error"]:
        rec.update(correct=False, grader={"detail": "server error"})
        return rec
    grader = grade.grade_reasoning if family == "reasoning" else grade.grade_coding
    rec["correct"], rec["grader"] = grader(item, turn["content"])
    return rec


def run_tools(arm, task, envs, effort, seed):
    """One trajectory. `correct` is the strict score (no repair was ever needed); `correct_lenient`
    is the final-state check regardless of repairs. Reasoning is never echoed back (vendor guidance)."""
    env = envs[task["env"]](copy.deepcopy(task["init"]))
    tool_names = {t["function"]["name"] for t in env.TOOLS}
    messages = base_messages(task["prompt"])
    turns, repairs, truncated, server_error = [], [], False, False
    for n in range(cfg.MAX_TOOL_TURNS):
        turn = chat(arm, messages, effort, seed + n, tools=env.TOOLS)
        if "http_error" in turn:  # known failure mode: server rejects a malformed call. Lenient: one retry.
            turns.append(turn)
            repairs.append("http_%s_retry" % turn["http_error"])
            turn = chat(arm, messages, effort, seed + n + 5000, tools=env.TOOLS)
            if "http_error" in turn:
                turns.append(turn)
                server_error = True
                break
        turns.append(turn)
        truncated = truncated or turn["finish_reason"] == "length"
        calls = []
        for i, tc in enumerate(turn["tool_calls"]):
            fn = tc.get("function", {})
            args, repaired = grade.parse_arguments(fn.get("arguments"))
            if repaired:
                repairs.append("arguments_repaired")
            calls.append({"id": tc.get("id") or "call_%d_%d" % (n, i), "name": fn.get("name"), "arguments": args, "raw": fn.get("arguments")})
        if not calls:
            recovered = grade.calls_from_text(turn["content"], tool_names)
            if recovered:
                repairs.append("call_recovered_from_text")
                calls = [{"id": "call_%d_%d" % (n, i), "name": c["name"], "arguments": c["arguments"], "raw": None} for i, c in enumerate(recovered)]
        if not calls:
            break
        messages.append({"role": "assistant", "content": turn["content"], "tool_calls": [
            {"id": c["id"], "type": "function", "function": {"name": c["name"] or "", "arguments": json.dumps(c["arguments"] if c["arguments"] is not None else {})}}
            for c in calls]})
        for c in calls:
            if c["arguments"] is None:
                result = {"error": "arguments were not valid JSON"}
            else:
                try:
                    result = env.call(c["name"], c["arguments"])
                except Exception as e:  # envs are fuzzed never to raise; belt and braces
                    result = {"error": "tool failed: %s" % type(e).__name__}
            c["result"] = result
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)})
        turn["executed"] = calls
    try:
        state_ok = bool(task["check"](env.state))
    except Exception as e:
        state_ok = False
        repairs.append("check_raised_%s" % type(e).__name__)
    return {"turns": turns, "truncated": truncated, "server_error": server_error, "repairs": repairs,
            "correct": state_ok and not repairs, "correct_lenient": state_ok,
            "grader": {"final_state": env.state}}


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(cfg.ARMS))
    ap.add_argument("--run", required=True, choices=["pilot", "main", "noise", "xhigh"])
    ap.add_argument("--fallback90", action="store_true", help="use the pre-registered 90-item fallback set")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-name", default="", help="results subfolder (default: the run name)")
    ap.add_argument("--model-path", default="", help="smoke tests only: override the arm's model file")
    ap.add_argument("--server-bin", default="", help="smoke tests only: override the server binary")
    ap.add_argument("--skip-hash", action="store_true")
    args = ap.parse_args()

    arm = cfg.ARMS[args.arm]
    effort = "xhigh" if args.run == "xhigh" else "medium"
    seed = cfg.SEEDS[args.run]
    items, envs = load_items()
    order = select(args.run, items, args.fallback90)
    if args.limit:
        order = order[: args.limit]

    out_dir = os.path.join(cfg.RESULTS_DIR, args.out_name or args.run)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s.jsonl" % args.arm)
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            done = {json.loads(line)["id"] for line in f if line.strip()}
    todo = [i for i in order if i not in done]
    print("%s / %s: %d items, %d already done" % (args.arm, args.run, len(order), len(order) - len(todo)), flush=True)
    if not todo:
        return

    model_path = args.model_path or os.path.join(cfg.MODELS_DIR, arm["file"])
    server_bin = args.server_bin or cfg.SERVER_BIN
    manifest = {"arm": args.arm, "label": arm["label"], "run": args.run, "effort": effort, "seed": seed,
                "model_path": model_path, "server_bin": server_bin, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not args.skip_hash:
        manifest["model_sha256"] = sha256_file(model_path)
        if not args.model_path and manifest["model_sha256"] != arm["sha256"]:
            raise SystemExit("model file hash does not match the pre-registered hash: " + model_path)
        manifest["server_sha256"] = sha256_file(server_bin)
    proc, cmd = start_server(model_path, server_bin, arm["sampler"], os.path.join(out_dir, "%s.server.log" % args.arm),
                              cfg.CONTEXT_BY_RUN.get(args.run))
    manifest["server_cmd"] = cmd
    try:
        manifest["props"] = {k: v for k, v in http("/props").items() if k in ("build_info", "model_path", "default_generation_settings")}
    except Exception:
        pass
    with open(os.path.join(out_dir, "%s.manifest.jsonl" % args.arm), "a") as f:
        f.write(json.dumps(manifest) + "\n")

    try:
        for k, item_id in enumerate(todo, 1):
            family, item = items[item_id]
            t0 = time.time()
            if family == "tools":
                rec = run_tools(arm, item, envs, effort, seed)
            else:
                rec = run_single(arm, family, item, effort, seed)
            rec.update(id=item_id, family=family, arm=args.arm, run=args.run, effort=effort, seed=seed,
                       completion_tokens=tokens(rec["turns"]), wall_s=round(time.time() - t0, 1))
            with open(out_path, "a") as f:
                f.write(json.dumps(rec, default=str) + "\n")
            print("[%d/%d] %s %s correct=%s tokens=%d %.0fs%s" % (
                k, len(todo), item_id, family, rec["correct"], rec["completion_tokens"], rec["wall_s"],
                " TRUNCATED" if rec["truncated"] else ""), flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
