#!/opt/homebrew/bin/python3.12
"""Resumable ranged downloader for the pre-registered model files. Each 32 MB segment is written at its own
offset and recorded only when complete, so retries can never duplicate or shift bytes. Verifies sha256."""
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "harness"))
import config as cfg

SEG = 32 << 20
THREADS = 8


def remote_size(url):
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Range"].split("/")[1])


def fetch(arm):
    name = arm["file"]
    url = "https://huggingface.co/%s/resolve/main/%s" % (arm["repo"], name)
    path = os.path.join(cfg.MODELS_DIR, name)
    state_path = path + ".segments.json"
    if os.path.exists(path) and not os.path.exists(state_path):
        if sha256(path) == arm["sha256"]:
            print("OK   %s (already present)" % name, flush=True)
            return True
        os.remove(path)
    size = None
    while size is None:
        try:
            size = remote_size(url)
        except Exception as e:
            print("size lookup failed (%s); retrying" % e, flush=True)
            time.sleep(10)
    done = set()
    if os.path.exists(state_path) and os.path.exists(path):
        done = set(json.load(open(state_path)))
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    os.ftruncate(fd, size)
    todo = [i for i in range((size + SEG - 1) // SEG) if i not in done]
    lock = threading.Lock()

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                i = todo.pop(0)
            start, end = i * SEG, min(size, (i + 1) * SEG) - 1
            while True:
                try:
                    req = urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % (start, end)})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        if r.status != 206:
                            raise IOError("status %s" % r.status)
                        buf = bytearray()
                        while True:
                            chunk = r.read(1 << 20)
                            if not chunk:
                                break
                            buf += chunk
                    if len(buf) != end - start + 1:
                        raise IOError("short read")
                    os.pwrite(fd, bytes(buf), start)
                    break
                except Exception:
                    time.sleep(5)
            with lock:
                done.add(i)
                with open(state_path + ".tmp", "w") as f:
                    json.dump(sorted(done), f)
                os.replace(state_path + ".tmp", state_path)
                if len(done) % 16 == 0:
                    print("%s  %.1f / %.1f GB" % (name, len(done) * SEG / 1e9, size / 1e9), flush=True)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(THREADS)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    os.fsync(fd)
    os.close(fd)
    ok = sha256(path) == arm["sha256"]
    if ok:
        os.remove(state_path)
    print(("OK   " if ok else "BAD  ") + name, flush=True)
    return ok


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    os.makedirs(cfg.MODELS_DIR, exist_ok=True)
    results = [fetch(cfg.ARMS[a]) for a in (sys.argv[1:] or ["B", "C", "A"])]
    print("ALL OK" if all(results) else "SOME FAILED", flush=True)
