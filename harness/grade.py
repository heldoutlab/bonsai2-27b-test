"""Graders. Deterministic; no model in the loop. Written before any model was run."""
import json
import os
import re
import subprocess
import tempfile

from config import CODE_TIMEOUT_S, PYTHON_FOR_TESTS

# ---------- reasoning ----------

ANSWER_RE = re.compile(r"ANSWER\s*:\s*(.+)", re.IGNORECASE)


def _clean(s):
    s = s.strip()
    s = re.sub(r"^[\s*_`\"'\[(<]+", "", s)
    s = re.sub(r"[\s*_`\"'\])>.]+$", "", s)
    return s.strip()


def extract_answer(content):
    """Last 'ANSWER: ...' line of the visible reply (never the reasoning trace). None if absent."""
    found = ANSWER_RE.findall(content or "")
    return _clean(found[-1]) if found else None


def grade_reasoning(item, content):
    got = extract_answer(content)
    if got is None:
        return False, {"extracted": None}
    key, kind = item["answer"], item["answer_type"]
    ok = False
    if kind == "int":
        digits = re.sub(r"[,\s_]", "", got)
        ok = bool(re.fullmatch(r"-?\d+", digits)) and int(digits) == int(key)
    elif kind == "list":
        norm = lambda s: [_clean(p).casefold() for p in s.split(",")]
        ok = norm(got) == norm(key)
    else:
        norm = lambda s: re.sub(r"\s+", " ", s).casefold()
        ok = norm(got) == norm(_clean(key))
    return ok, {"extracted": got}


# ---------- coding ----------

FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", re.DOTALL)
SANDBOX = '(version 1)(allow default)(deny network*)(deny file-write* (subpath "/Users"))'


def extract_code(content):
    """Last fenced block tagged python/py; else the last fenced block of any kind. None if there is none."""
    blocks = FENCE_RE.findall(content or "")
    if not blocks:
        return None
    tagged = [body for lang, body in blocks if lang.lower() in ("python", "py", "python3")]
    return (tagged or [body for _, body in blocks])[-1]


def run_tests(solution, tests):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "candidate.py")
        with open(path, "w") as f:
            f.write(solution + "\n\n# ---- hidden tests ----\n" + tests + "\n")
        try:
            p = subprocess.run(
                ["/usr/bin/sandbox-exec", "-p", SANDBOX, PYTHON_FOR_TESTS, "-I", path],
                cwd=tmp, capture_output=True, text=True, timeout=CODE_TIMEOUT_S, stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return False, "timeout"
        if p.returncode == 0:
            return True, "pass"
        return False, (p.stderr or p.stdout).strip()[-600:]


def grade_coding(item, content):
    code = extract_code(content)
    if code is None:
        return False, {"detail": "no code block"}
    ok, detail = run_tests(code, item["tests"])
    return ok, {"detail": detail}


# ---------- tool calls: argument repair for the lenient score ----------

def parse_arguments(raw):
    """Returns (args_dict_or_None, repaired: bool). Strict path is plain json.loads to a dict."""
    if isinstance(raw, dict):
        return raw, False
    try:
        val = json.loads(raw)
        if isinstance(val, dict):
            return val, False
        if isinstance(val, str):  # double-encoded
            val2 = json.loads(val)
            if isinstance(val2, dict):
                return val2, True
    except (TypeError, ValueError):
        pass
    if not isinstance(raw, str):
        return None, False
    s = raw.strip()
    s = re.sub(r"^```(?:json)?|```$", "", s).strip()
    start = s.find("{")
    if start == -1:
        return None, False
    s = s[start:]
    candidates = [s, re.sub(r",\s*([}\]])", r"\1", s)]
    candidates.append(candidates[-1].replace("'", '"'))
    for c in list(candidates):
        opened = c.count("{") - c.count("}")
        sq = c.count("[") - c.count("]")
        if opened > 0 or sq > 0:
            candidates.append(c + "]" * max(sq, 0) + "}" * max(opened, 0))
        end = c.rfind("}")
        if end != -1:
            candidates.append(c[: end + 1])
    for c in candidates:
        try:
            val = json.loads(c)
            if isinstance(val, dict):
                return val, True
        except ValueError:
            continue
    return None, False


TEXT_CALL_RES = [
    re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL),
    re.compile(r"```(?:json|tool_call)?\s*(\{\s*\"name\".*?\})\s*```", re.DOTALL),
]


def calls_from_text(content, tool_names):
    """Lenient only: recover tool calls the server failed to parse out of the visible reply."""
    out = []
    for rx in TEXT_CALL_RES:
        for blob in rx.findall(content or ""):
            obj, _ = parse_arguments(blob)
            if not obj or obj.get("name") not in tool_names:
                continue
            args = obj.get("arguments", obj.get("parameters", {}))
            if isinstance(args, str):
                args, _ = parse_arguments(args)
            if isinstance(args, dict):
                out.append({"name": obj["name"], "arguments": args})
        if out:
            break
    return out
