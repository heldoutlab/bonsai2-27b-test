"""Brute-force / simulation solvers for reasoning_items.py.

Every solver recomputes its item's answer from the puzzle data by exhaustive
search or step-by-step simulation.  Run:

    python3 reasoning_solvers.py

It asserts every solver output equals the key in ITEMS, asserts uniqueness for
every constraint-style item, runs structural checks on the prompts, and prints
"OK 44/44".  Stdlib only; works on Python 3.9+.
"""
import os
import re
import sys
from collections import deque
from itertools import combinations, permutations, product

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------
# Kind 1: constraint / arrangement
# --------------------------------------------------------------------------
def _all_r01():
    names = ("Bascom", "Dunmore", "Ilka", "Oriel", "Thessaly", "Wren")
    out = []
    for perm in permutations(range(1, 7)):
        p = dict(zip(names, perm))
        if not p["Oriel"] < p["Bascom"]:
            continue
        if p["Thessaly"] != p["Wren"] + 1:
            continue
        if p["Dunmore"] in (1, 6):
            continue
        if abs(p["Ilka"] - p["Oriel"]) != 2:
            continue
        if abs(p["Bascom"] - p["Dunmore"]) == 1:
            continue
        if p["Wren"] % 2 != 0:
            continue
        if abs(p["Ilka"] - p["Wren"]) == 1:
            continue
        out.append(",".join(sorted(names, key=lambda n: p[n])))
    return out


def solve_r01():
    return _all_r01()[0]


def _all_r02():
    W = ("Glazing", "Knotwork", "Fermenting", "Mapmaking", "Whittling")
    T = ("Anselm", "Brisa", "Corwin", "Delphine", "Eskil")
    out = []
    for wp in permutations(range(5)):  # day index 0=Mon .. 4=Fri
        w = dict(zip(W, wp))
        day_to_w = {v: k for k, v in w.items()}
        for tp in permutations(range(5)):
            t = dict(zip(T, tp))
            ws = {n: day_to_w[t[n]] for n in T}  # tutor -> workshop
            if not (w["Glazing"] < w["Mapmaking"] < w["Whittling"]):
                continue
            if t["Brisa"] != t["Corwin"] + 1:
                continue
            if ws["Delphine"] in ("Glazing", "Fermenting"):
                continue
            if w["Knotwork"] not in (2, 4):
                continue
            if (t["Eskil"] == 0) == (ws["Eskil"] == "Whittling"):
                continue
            if t["Anselm"] != w["Fermenting"] + 2:
                continue
            if ws["Corwin"] == "Mapmaking":
                continue
            if not t["Delphine"] < t["Corwin"]:
                continue
            out.append(
                ",".join(sorted(T, key=lambda x: t[x]))
                + "|"
                + ",".join(sorted(W, key=lambda x: w[x]))
            )
    return out


def solve_r02():
    return _all_r02()[0].split("|")[0]


def _all_r03():
    N = ("Hask", "Ione", "Jorvik", "Kestrel", "Lumen", "Marit", "Nyle")

    def adj(a, b):
        return (a - b) % 7 in (1, 6)

    out = []
    for perm in permutations(range(7)):  # seat index 0..6 = seats 1..7 clockwise
        s = dict(zip(N, perm))
        if s["Hask"] != 0:
            continue
        if s["Jorvik"] != (s["Marit"] + 1) % 7:
            continue
        if adj(s["Kestrel"], s["Hask"]):
            continue
        if s["Lumen"] != (s["Ione"] + 3) % 7:
            continue
        if not adj(s["Nyle"], s["Kestrel"]):
            continue
        if adj(s["Ione"], s["Jorvik"]):
            continue
        if adj(s["Ione"], s["Hask"]):
            continue
        out.append(",".join(sorted(N, key=lambda x: s[x])))
    return out


def solve_r03():
    return _all_r03()[0]


def _all_r04():
    out = []
    for g in permutations(range(1, 10)):
        a, b, c, d, e, f, h, i, j = g  # rows: abc / def / hij
        if a + b + c != 13:
            continue
        if not (a < d < h):
            continue
        if h + i + j != 15:
            continue
        if e != a + j:
            continue
        pos = {v: k for k, v in enumerate(g)}
        if pos[2] != pos[8] + 3:  # 2 directly below 8
            continue
        if pos[1] % 3 != pos[3] % 3:  # 1 and 3 same column
            continue
        out.append(g)
    return out


def solve_r04():
    g = _all_r04()[0]
    return ",".join(str(x) for x in g[3:6])


def _all_r05():
    P = ("Pavel", "Quill", "Rosalind", "Soren", "Tamsin", "Ulrich")
    out = []
    for a in product(range(3), repeat=6):  # 0 dawn, 1 noon, 2 dusk
        if sorted(a) != [0, 0, 1, 1, 2, 2]:
            continue
        s = dict(zip(P, a))
        if s["Pavel"] == s["Quill"]:
            continue
        if not s["Rosalind"] < s["Soren"]:
            continue
        if s["Tamsin"] == 2 and s["Ulrich"] != 0:
            continue
        if s["Quill"] == 1:
            continue
        if s["Pavel"] == 0 and s["Rosalind"] != 1:
            continue
        if (s["Ulrich"] == s["Soren"]) == (s["Tamsin"] == s["Pavel"]):
            continue
        if s["Tamsin"] == 0:
            continue
        out.append(a)
    return out


def solve_r05():
    P = ("Pavel", "Quill", "Rosalind", "Soren", "Tamsin", "Ulrich")
    a = _all_r05()[0]
    return ",".join(sorted(n for n, x in zip(P, a) if x == 2))


# --------------------------------------------------------------------------
# Kind 2: state tracking
# --------------------------------------------------------------------------
def _extremes(b):
    vals = sorted(b.values())
    assert vals[0] != vals[1] and vals[-1] != vals[-2], ("tie", b)
    hi = max(b, key=lambda k: b[k])
    lo = min(b, key=lambda k: b[k])
    return hi, lo


def solve_r06():
    b = {"Amber": 17, "Cobalt": 8, "Slate": 23}
    m = b["Slate"] // 2  # 1
    b["Slate"] -= m
    b["Amber"] += m
    b["Amber"] -= 5  # 2
    b["Cobalt"] += 5
    hi, lo = _extremes(b)  # 3
    b[hi] -= 6
    b[lo] += 6
    b["Amber"], b["Cobalt"] = b["Cobalt"], b["Amber"]  # 4
    m = b["Cobalt"] // 3  # 5
    b["Cobalt"] -= m
    b["Slate"] += m
    hi, lo = _extremes(b)  # 6
    b[hi] -= b[lo]
    if b["Amber"] % 2 == 1:  # 7
        b["Amber"] -= 3
        b["Slate"] += 3
    else:
        b["Slate"] -= 4
        b["Amber"] += 4
    hi, lo = _extremes(b)  # 8
    m = b[hi] // 2
    b[hi] -= m
    b[lo] += m
    assert all(v >= 0 for v in b.values())
    return "%d,%d,%d" % (b["Amber"], b["Cobalt"], b["Slate"])


def solve_r07():
    r = {"P": 3, "Q": 14, "R": 0, "S": 1}
    line = 1
    steps = 0
    while True:
        steps += 1
        assert steps < 1000
        if line == 1:
            r["R"] += r["P"]
        elif line == 2:
            r["P"] += 2
        elif line == 3:
            r["S"] *= 3
        elif line == 4:
            if r["S"] > 20:
                r["S"] -= 20
        elif line == 5:
            r["Q"] -= 3
        elif line == 6:
            if r["Q"] > 0:
                line = 1
                continue
        elif line == 7:
            if r["R"] % 2 == 0:
                r["R"] //= 2
            else:
                r["R"] += r["S"]
        elif line == 8:
            r["P"] = r["P"] + r["R"] - r["Q"]
        elif line == 9:
            break
        line += 1
    return str(r["P"])


def solve_r08():
    row = list("FKMPTVZ")

    def swap(i, j):  # 1-indexed
        row[i - 1], row[j - 1] = row[j - 1], row[i - 1]

    swap(2, 6)  # 1
    row.append(row.pop(0))  # 2
    row[2:6] = row[2:6][::-1]  # 3 positions 3..6
    i = row.index("M") + 1  # 4
    swap(i, 1 if i == 7 else i + 1)
    row.insert(0, row.pop(4))  # 5
    i = row.index("T") + 1  # 6
    if i != 4:
        swap(i, 4)
    row[0:3] = row[0:3][::-1]  # 7
    i = row.index("K") + 1  # 8
    swap(i, 7 if i == 1 else i - 1)
    row.append(row.pop(1))  # 9 position 2 to the right end
    return ",".join(row)


def solve_r09():
    cards = [6, 3, 10, 7, 15, 4, 9, 12, 5, 16, 11, 8]
    assert len(set(cards)) == len(cards)
    tray = []
    tally = 0
    for c in cards:
        while True:
            if not tray:
                tray.append(c)
                break
            t = tray[-1]
            if c > t and (c - t) % 2 == 1:
                tray.pop()
                tally += t
                continue
            if c > t:
                tray.append(c)
                break
            if c % 2 == 0:
                tray.append(c)
                break
            tally += 1
            break
    return str(tally + sum(tray))


def solve_r10():
    pos = {"R": 0, "B": 0}
    coins = {"R": 0, "B": 0}
    rolls = [3, 5, 4, 2, 6, 4, 2, 6, 5, 1, 4, 3]
    bounty = {2, 3, 5, 7}
    tax = {0, 4, 8}
    for i, r in enumerate(rolls):
        p = "R" if i % 2 == 0 else "B"
        o = "B" if p == "R" else "R"
        new = pos[p] + r
        if new >= 10:
            coins[p] += 4
        pos[p] = new % 10
        if pos[p] in bounty:
            coins[p] += pos[p]
        elif pos[p] in tax:
            coins[p] = max(0, coins[p] - 3)
        if pos[p] == pos[o]:
            t = min(2, coins[o])
            coins[o] -= t
            coins[p] += t
    return "%d,%d" % (coins["R"], coins["B"])


# --------------------------------------------------------------------------
# Kind 3: quantitative word problems
# --------------------------------------------------------------------------
def solve_r11():
    oil = 40
    d = 0
    while True:
        d += 1
        if d % 4 == 0:
            oil = min(40, oil + 20)
        need = 7 if d % 2 == 1 else 5
        if oil < need:
            return str(d)
        oil -= need


def solve_r12():
    months = ["Frostwane", "Budrise", "Highsun", "Reaptide", "Duskfall"]
    base = [31, 29, 33, 30, 28]
    week = ["Aln", "Bru", "Cey", "Dov", "Eth", "Fen"]
    wd = week.index("Cey")
    year = 412
    while True:
        for mi, m in enumerate(months):
            length = base[mi] + (1 if (m == "Duskfall" and year % 3 == 0) else 0)
            count = 0
            for day in range(1, length + 1):
                if year == 415 and m == "Reaptide" and week[wd] == "Eth":
                    count += 1
                    if count == 3:
                        return str(day)
                wd = (wd + 1) % 6
        year += 1
        assert year < 420


def solve_r13():
    carried = 0
    dep = 0
    t = 0
    while True:
        dep += 1
        arrived = 47 + t // 3  # carts that have reached the bank by time t (incl.)
        waiting = arrived - carried
        cap = 14 - (4 if dep % 3 == 0 else 0)
        load = min(cap, waiting)
        carried += load
        if waiting - load == 0:
            return "%d,%d" % (dep, load)
        t += 24
        assert dep < 100


def _r14_cost(n):
    c = 40
    for k in range(1, n + 1):
        c += 9 if k <= 20 else (7 if k <= 50 else 5)
    return c


def _all_r14():
    out = []
    for a in range(1, 96):
        b = 96 - a
        if a < b and _r14_cost(b) - _r14_cost(a) == 184:
            out.append(a)
    return out


def solve_r14():
    a = _all_r14()[0]
    saving = _r14_cost(a) + _r14_cost(96 - a) - _r14_cost(96)
    return "%d,%d" % (a, saving)


def solve_r15():
    total = 0
    d = 0
    while True:
        d += 1
        today = 24
        if d >= 4 and (d - 4) % 3 != 2:
            today += 30
        if d >= 7 and d % 2 == 0:
            today += 18
        if total + today >= 1000:
            return "%d,%d" % (d, 1000 - total)
        total += today


# --------------------------------------------------------------------------
# Kind 4: truth / lies / nested conditionals
# --------------------------------------------------------------------------
def _all_r16():
    P = ("Avel", "Brom", "Cass", "Dita", "Eddo")
    out = []
    for tr in product("ET", repeat=5):
        for morning in (True, False):
            t = dict(zip(P, tr))
            st = {
                "Avel": morning,
                "Brom": t["Avel"] == "T",
                "Cass": t["Dita"] != t["Brom"],
                "Dita": (not morning) and t["Cass"] == "E",
                "Eddo": t["Cass"] == "T",
            }
            if all(st[n] == ((t[n] == "E") == morning) for n in P):
                out.append((morning, ",".join(n for n in P if t[n] == "E")))
    return out


def solve_r16():
    return _all_r16()[0][1]


def _all_r17():
    Q = ("Fenn", "Gilda", "Horst", "Ines")
    out = []
    for roles in sorted(set(permutations("TLAA"))):
        r = dict(zip(Q, roles))
        st = {
            "Fenn": (r["Gilda"] == "L", r["Fenn"] != "L"),
            "Gilda": (r["Horst"] == "L", r["Fenn"] == "A"),
            "Horst": (r["Ines"] == "T", r["Gilda"] == "A"),
            "Ines": (r["Fenn"] == "T", r["Horst"] != "A"),
        }
        ok = True
        for n in Q:
            a, b = st[n]
            if r[n] == "T":
                ok = ok and a and b
            elif r[n] == "L":
                ok = ok and (not a) and (not b)
            else:
                ok = ok and (a != b)
        if ok:
            out.append(r)
    return out


def solve_r17():
    r = _all_r17()[0]
    return [n for n in r if r[n] == "L"][0]


def _all_r18():
    out = []
    for loc in range(1, 6):
        for v in product((False, True), repeat=5):
            V = dict(zip(range(1, 6), v))
            st = {
                1: loc in (2, 4),
                2: (loc != 1) and (not V[4]),
                3: loc % 2 == 1,
                4: (loc != 4) and V[1],
                5: (loc == 5) or (not V[3]),
            }
            if all(st[i] == V[i] for i in st) and sum(v) == 2:
                out.append((loc, v))
    return out


def solve_r18():
    return str(_all_r18()[0][0])


def _all_r19():
    out = []
    for bits in product((0, 1), repeat=6):
        A, B, C, D, E, F = bits
        ok = True
        if A and C:  # 1
            ok = False
        if B and not ((D == 1) == (A == 0)):  # 2
            ok = False
        if sum(bits) != 3:  # 3
            ok = False
        if not C and not (E != F):  # 4
            ok = False
        if not A and not B and F:  # 5
            ok = False
        if D and E:  # 6a
            ok = False
        if not D and not B:  # 6b
            ok = False
        if B and F:  # 7
            ok = False
        if C != E:  # 8
            ok = False
        if ok:
            out.append(",".join(n for n, b in zip("ABCDEF", bits) if b))
    return out


def solve_r19():
    return _all_r19()[0]


def _all_r20():
    L = ("Vane", "Wick", "Xanthe", "Yoren", "Zell")
    out = []
    for tv in product((True, False), repeat=5):
        t = dict(zip(L, tv))
        nl = 5 - sum(tv)
        st = {
            "Vane": nl == 1,
            "Wick": t["Xanthe"],
            "Xanthe": t["Wick"] != t["Yoren"],
            "Yoren": nl % 2 == 0,
            "Zell": nl >= 4,
        }
        if all(st[n] == t[n] for n in L):
            out.append(",".join(n for n in L if not t[n]))
    return out


def solve_r20():
    return _all_r20()[0]


# --------------------------------------------------------------------------
# Kind 5: counting
# --------------------------------------------------------------------------
def solve_r21():
    n = 0
    for c in product(range(1, 7), repeat=4):
        if any(c[i] == c[i + 1] for i in range(3)):
            continue
        if not c[0] > c[3]:
            continue
        if sum(c) % 2 != 0:
            continue
        n += 1
    return str(n)


def solve_r22():
    eng = ["Ostra", "E2", "E3", "E4", "E5"]
    pil = ["Penn", "P2", "P3", "P4"]
    med = ["Quay", "M2", "M3"]
    n = 0
    for crew in combinations(eng + pil + med, 5):
        ne = sum(x in eng for x in crew)
        np_ = sum(x in pil for x in crew)
        nm = sum(x in med for x in crew)
        if min(ne, np_, nm) < 1:
            continue
        if "Ostra" in crew and "Penn" in crew:
            continue
        if "Quay" in crew and np_ < 2:
            continue
        n += 1
    return str(n)


def solve_r23():
    closed = {(2, 2), (4, 1)}
    n = 0
    for east_idx in combinations(range(9), 5):
        moves = ["E" if i in east_idx else "N" for i in range(9)]
        if any(moves[i] == moves[i + 1] == moves[i + 2] for i in range(7)):
            continue
        x = y = 0
        ok = True
        for m in moves:
            if m == "E":
                x += 1
            else:
                y += 1
            if (x, y) in closed:
                ok = False
                break
        if ok:
            assert (x, y) == (5, 4)
            n += 1
    return str(n)


def solve_r24():
    n = 0
    for a, b, c, d in product(range(6), repeat=4):
        if a + b + c + d != 12:
            continue
        if a == b or b == c or c == d:
            continue
        if not a > d:
            continue
        n += 1
    return str(n)


def solve_r25():
    vols = ["A1", "A2", "A3", "D1", "D2", "L1", "L2"]
    n = 0
    for p in permutations(vols):
        if any(p[i][0] == "A" and p[i + 1][0] == "A" for i in range(6)):
            continue
        if abs(p.index("D1") - p.index("D2")) != 1:
            continue
        if not p.index("L1") < p.index("L2"):
            continue
        n += 1
    return str(n)


# --------------------------------------------------------------------------
# Kind 6: follow an invented algorithm
# --------------------------------------------------------------------------
def solve_r26():
    w = "HARVEST"
    s = [chr((ord(ch) - 65 + i + 1) % 26 + 65) for i, ch in enumerate(w)]
    for i in range(0, len(s) - 1, 2):
        s[i], s[i + 1] = s[i + 1], s[i]
    s = [chr((ord(ch) - 65 + 1) % 26 + 65) if ch in "AEIOU" else ch for ch in s]
    return "".join(s)


def solve_r27():
    cells = [int(ch) for ch in "011010011100"]
    for _ in range(4):
        new = []
        for i in range(12):
            left = cells[i - 1] if i > 0 else 0
            right = cells[i + 1] if i < 11 else 0
            c = cells[i]
            flip = (left + right == 1)
            new.append(1 - c if flip else c)
        cells = new
    return "".join(str(x) for x in cells)


def solve_r28():
    nums = [47, 130, 58, 92, 205, 76, 311, 64, 9, 83]

    def ds(n):
        return sum(int(ch) for ch in str(n))

    s = sorted(nums, key=lambda n: (ds(n), -n))
    kept = [s[0]] + [s[i] for i in range(1, len(s)) if not s[i] < s[i - 1]]
    return ",".join(str(x) for x in kept)


def solve_r29():
    hand = [(4, "Moons"), (5, "Stars"), (5, "Suns"), (6, "Moons"), (9, "Stars"), (3, "Moons"), (8, "Suns")]
    score = 0
    for a, b in combinations(hand, 2):
        if a[0] == b[0]:
            score += 4
    ranks = {r for r, _ in hand}
    best = 0
    for r in ranks:
        length = 0
        while r + length in ranks:
            length += 1
        best = max(best, length)
    if best >= 3:
        score += 2 * best
    counts = {}
    for _, s in hand:
        counts[s] = counts.get(s, 0) + 1
    top = max(counts.values())
    if list(counts.values()).count(top) == 1:
        score += top
    score -= 2 * sum(1 for r, s in hand if s == "Stars" and r % 2 == 1)
    if sum(r for r, _ in hand) % 5 == 0:
        score *= 2
    return str(score)


def solve_r30():
    s = "AABABBABAB"
    rules = [("BB", "A"), ("AAA", "C"), ("AB", "BA"), ("CA", "AC")]
    steps = 0
    while True:
        for a, b in rules:
            i = s.find(a)
            if i >= 0:
                s = s[:i] + b + s[i + len(a):]
                steps += 1
                break
        else:
            return s
        assert steps < 500


# --------------------------------------------------------------------------
# Kind 7: graphs and paths
# --------------------------------------------------------------------------
def _simple_paths(adj, src, dst):
    """Yield (nodes, edge_attr_list) for every simple path src->dst."""
    stack = [(src, [src], [])]
    while stack:
        node, path, attrs = stack.pop()
        if node == dst:
            yield path, attrs
            continue
        for nxt, attr in adj.get(node, []):
            if nxt not in path:
                stack.append((nxt, path + [nxt], attrs + [attr]))


def solve_r31():
    E = [
        ("Alder", "Brack", 4), ("Alder", "Corrow", 7), ("Brack", "Corrow", 2),
        ("Brack", "Dellmoor", 9), ("Corrow", "Esk", 5), ("Corrow", "Dellmoor", 8),
        ("Dellmoor", "Esk", 2), ("Dellmoor", "Fenwick", 6), ("Esk", "Grange", 10),
        ("Fenwick", "Grange", 3), ("Esk", "Fenwick", 9),
    ]
    adj = {}
    for a, b, w in E:
        adj.setdefault(a, []).append((b, w))
        adj.setdefault(b, []).append((a, w))
    best = min(sum(ws) for p, ws in _simple_paths(adj, "Alder", "Grange") if "Dellmoor" in p)
    # revisiting towns cannot help: compare with the two-leg optimum
    leg1 = min(sum(ws) for p, ws in _simple_paths(adj, "Alder", "Dellmoor"))
    leg2 = min(sum(ws) for p, ws in _simple_paths(adj, "Dellmoor", "Grange"))
    assert best == leg1 + leg2
    free = min(sum(ws) for p, ws in _simple_paths(adj, "Alder", "Grange"))
    assert free < best  # the Dellmoor requirement actually matters
    return str(best)


def solve_r32():
    dur = {"A": 4, "B": 6, "C": 3, "D": 5, "E": 2, "F": 7, "G": 4, "H": 3, "I": 5, "J": 2}
    pre = {"A": "", "B": "", "C": "A", "D": "A", "E": "BC", "F": "C", "G": "DE", "H": "FGJ", "I": "B", "J": "DI"}
    t = 0
    done = set()
    started = set()
    running = []
    free = 2
    while len(done) < len(dur):
        avail = sorted(x for x in dur if x not in started and all(p in done for p in pre[x]))
        while free and avail:
            x = avail.pop(0)
            started.add(x)
            running.append((t + dur[x], x))
            free -= 1
        t = min(f for f, _ in running)
        for f, x in list(running):
            if f == t:
                done.add(x)
                running.remove((f, x))
                free += 1
    return str(t)


def solve_r33():
    E = [
        ("Ashford", "Birle", 6, 0), ("Ashford", "Cranmer", 3, 1), ("Birle", "Dove", 7, 0),
        ("Cranmer", "Dove", 4, 0), ("Cranmer", "Elst", 11, 0), ("Dove", "Farrow", 2, 1),
        ("Dove", "Elst", 8, 0), ("Elst", "Gault", 5, 0), ("Farrow", "Gault", 9, 0),
        ("Farrow", "Holm", 14, 0), ("Gault", "Holm", 3, 1), ("Elst", "Holm", 10, 0),
    ]
    adj = {}
    for a, b, w, f in E:
        adj.setdefault(a, []).append((b, (w, f)))
        adj.setdefault(b, []).append((a, (w, f)))
    best = None
    for p, attrs in _simple_paths(adj, "Ashford", "Holm"):
        if sum(f for _, f in attrs) > 1:
            continue
        tot = sum(w for w, _ in attrs)
        if best is None or tot < best:
            best = tot
    free = min(sum(w for w, _ in attrs) for p, attrs in _simple_paths(adj, "Ashford", "Holm"))
    assert free < best
    return str(best)


def solve_r34():
    E = [
        ("Atrium", "Buttery", None), ("Atrium", "Hall", None), ("Buttery", "Cellar", None),
        ("Hall", "Library", "red"), ("Hall", "Gallery", None), ("Gallery", "Dormitory", "blue"),
        ("Cellar", "Library", None), ("Library", "Vault", "green"),
    ]
    oneway = [("Dormitory", "Cellar")]
    keys = {"Cellar": "red", "Library": "blue", "Dormitory": "green"}
    start = ("Atrium", frozenset())
    dq = deque([(start, 0)])
    seen = {start}
    while dq:
        (room, ks), d = dq.popleft()
        if room == "Vault":
            return str(d)
        nxt = []
        for a, b, k in E:
            for x, y in ((a, b), (b, a)):
                if x == room and (k is None or k in ks):
                    nxt.append(y)
        for x, y in oneway:
            if x == room:
                nxt.append(y)
        for y in nxt:
            nk = frozenset(ks | ({keys[y]} if y in keys else set()))
            if (y, nk) not in seen:
                seen.add((y, nk))
                dq.append(((y, nk), d + 1))
    raise AssertionError("vault unreachable")


def _r35_days():
    contacts = {
        "Arden": ["Bex", "Cole"], "Bex": ["Dara"], "Cole": ["Dara", "Emrys"],
        "Dara": ["Finn"], "Emrys": ["Finn", "Gwyn"], "Finn": ["Hale"],
        "Gwyn": ["Hale", "Bex"], "Hale": ["Ivo"], "Ivo": [],
    }
    slow = {"Cole", "Finn", "Gwyn"}
    hear = {"Arden": 1}
    for day in range(2, 40):
        tellers = [p for p, h in hear.items() if h + (2 if p in slow else 1) == day]
        new = set()
        for p in tellers:
            for c in contacts[p]:
                if c not in hear:
                    new.add(c)
        for c in new:
            hear[c] = day
    assert len(hear) == len(contacts)
    return hear


def solve_r35():
    return str(_r35_days()["Ivo"])


# --------------------------------------------------------------------------
# Kind 8: narrative deduction
# --------------------------------------------------------------------------
def _all_r36():
    # minutes after 2:00; intervals are [enter, leave)
    present = {
        "Halvard": [(0, 25)],
        "Isolde": [(10, 22), (40, 46)],
        "Jarrah": [(20, 32)],
        "Kelda": [(29, 43)],
        "Lorcan": [(42, 53)],
        "Mirren": [(36, 37)],  # steps in, sees the ledger still in place, leaves
    }
    last_seen = 36  # ledger seen intact at 2:36 while two people were present
    out = []
    for name in present:
        run = best = 0
        for m in range(last_seen, 60):
            here = [n for n, iv in present.items() if any(a <= m < b for a, b in iv)]
            if here == [name]:
                run += 1
                best = max(best, run)
            else:
                run = 0
        if best >= 5:
            out.append(name)
    return out


def solve_r36():
    return _all_r36()[0]


def _all_r37():
    wells = ["Abbey", "Mill", "North", "Quarry", "Sedge"]
    # (name, wells drunk from, ate bitterroot, fell ill)
    people = [
        ("Tobin", {"North", "Mill"}, False, True),
        ("Verrin", {"Mill", "Quarry"}, False, False),
        ("Ursa", {"Abbey", "Sedge"}, True, False),
        ("Wyn", {"Abbey", "Quarry"}, False, True),
        ("Zeb", {"North", "Sedge"}, True, False),
    ]
    out = []
    for pair in combinations(wells, 2):
        bad = set(pair)
        ok = True
        for _, drank, root, ill in people:
            expect = bool(drank & bad) and not root
            if expect != ill:
                ok = False
        if ok:
            out.append(",".join(sorted(pair)))
    return out


def solve_r37():
    return _all_r37()[0]


def _all_r38():
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    out = []
    for fire_wd in (2, 5):  # market days: Wednesday, Saturday
        def wd(day):
            return (fire_wd + day) % 7

        unload = 3
        deliver = unload + 1
        while wd(deliver) in (6, 0):  # guild closed Sunday and Monday
            deliver += 1
        exam = deliver + 1
        while wd(exam) not in (1, 3, 4):  # examiner: Tuesday, Thursday, Friday
            exam += 1
        if not exam > 7:  # "more than seven days after the firing"
            continue
        day = exam
        opened = 0
        while opened < 3:
            day += 1
            if wd(day) not in (6, 0):
                opened += 1
        out.append(names[wd(day)])
    return out


def solve_r38():
    return _all_r38()[0]


def _all_r39():
    completed_years = {"Odo": 4, "Perrin": 2, "Quenby": 1, "Runa": 2, "Stellan": 3}
    right_handed = {"Perrin"}
    # bakery presence as (from, to) in minutes after 6:00 pm; flour spilled at 8:00 (=120)
    bakery = {"Odo": (0, 90), "Runa": (60, 180), "Stellan": (60, 180), "Quenby": (135, 150)}
    needs_ladder = {"Stellan"}
    out = []
    for n in completed_years:
        if completed_years[n] < 2:
            continue
        if n in right_handed:
            continue
        if n not in bakery or bakery[n][1] <= 120:
            continue
        if n in needs_ladder:
            continue
        out.append(n)
    return out


def solve_r39():
    return _all_r39()[0]


def _r40_arrivals():
    barges = {"Heron": (2, 9), "Kite": (1, 7), "Lark": (4, 20), "Marten": (3, 12)}
    arr = {}
    for name, (dep, speed) in barges.items():
        dist = 0
        day = dep
        while True:
            if day != 5:
                dist += speed
            if dist >= 60:
                arr[name] = day
                break
            day += 1
    return arr


def _all_r40():
    arr = _r40_arrivals()
    assert len(set(arr.values())) == 4
    last = max(arr.values())
    salt = "Marten"
    return [n for n in arr if arr[n] > arr[salt] and arr[n] != last]


def solve_r40():
    return _all_r40()[0]


# --------------------------------------------------------------------------
# Pilot items
# --------------------------------------------------------------------------
def solve_rp1():
    b = {"Red": 9, "Green": 4, "Blue": 12}
    b["Red"] -= 3
    b["Green"] += 3
    m = b["Blue"] // 2
    b["Blue"] -= m
    b["Red"] += m
    b["Green"], b["Blue"] = b["Blue"], b["Green"]
    hi, lo = _extremes(b)
    b[hi] -= 2
    b[lo] += 2
    m = b["Green"] // 3
    b["Green"] -= m
    b["Blue"] += m
    return "%d,%d,%d" % (b["Red"], b["Green"], b["Blue"])


def solve_rp2():
    picked = {1: 45, 2: 45, 3: 45, 4: 20, 5: 45, 6: 45}
    waiting = 0
    carts = 0
    for d in range(1, 7):
        waiting += picked[d]
        carts += waiting // 32
        waiting %= 32
        if d < 6:
            waiting -= min(3, waiting)  # overnight spoilage
    return "%d,%d" % (carts, waiting)


def _all_rp3():
    N = ("Aldis", "Bryn", "Cato", "Dru", "Elke")
    out = []
    for perm in permutations(range(1, 6)):
        p = dict(zip(N, perm))
        if not p["Aldis"] < p["Cato"]:
            continue
        if abs(p["Bryn"] - p["Dru"]) != 1:
            continue
        if p["Elke"] in (1, 5):
            continue
        if p["Cato"] != p["Elke"] + 2:
            continue
        if p["Dru"] == 1:
            continue
        out.append(",".join(sorted(N, key=lambda n: p[n])))
    return out


def solve_rp3():
    return _all_rp3()[0]


def solve_rp4():
    serial = "480593"
    total = 0
    for i, ch in enumerate(serial, start=1):
        d = int(ch)
        total += d * 3 if i % 2 == 1 else d
    total += sum(1 for ch in serial if int(ch) > 5)
    return str((10 - total % 10) % 10)


# --------------------------------------------------------------------------
SOLVERS = {
    "R01": solve_r01, "R02": solve_r02, "R03": solve_r03, "R04": solve_r04, "R05": solve_r05,
    "R06": solve_r06, "R07": solve_r07, "R08": solve_r08, "R09": solve_r09, "R10": solve_r10,
    "R11": solve_r11, "R12": solve_r12, "R13": solve_r13, "R14": solve_r14, "R15": solve_r15,
    "R16": solve_r16, "R17": solve_r17, "R18": solve_r18, "R19": solve_r19, "R20": solve_r20,
    "R21": solve_r21, "R22": solve_r22, "R23": solve_r23, "R24": solve_r24, "R25": solve_r25,
    "R26": solve_r26, "R27": solve_r27, "R28": solve_r28, "R29": solve_r29, "R30": solve_r30,
    "R31": solve_r31, "R32": solve_r32, "R33": solve_r33, "R34": solve_r34, "R35": solve_r35,
    "R36": solve_r36, "R37": solve_r37, "R38": solve_r38, "R39": solve_r39, "R40": solve_r40,
    "RP1": solve_rp1, "RP2": solve_rp2, "RP3": solve_rp3, "RP4": solve_rp4,
}

# Items whose answer is "the one consistent solution": the full solution set
# must have exactly one member.
UNIQUE = {
    "R01": _all_r01, "R02": _all_r02, "R03": _all_r03, "R04": _all_r04, "R05": _all_r05,
    "R14": _all_r14,
    "R16": _all_r16, "R17": _all_r17, "R18": _all_r18, "R19": _all_r19, "R20": _all_r20,
    "R36": _all_r36, "R37": _all_r37, "R38": _all_r38, "R39": _all_r39, "R40": _all_r40,
    "RP3": _all_rp3,
}

_TAIL = re.compile(r'Finish with a final line of the form "ANSWER: <[^<>"\n]+>"$')


def main(argv):
    if "--dump" in argv:
        for k, f in SOLVERS.items():
            extra = ""
            if k in UNIQUE:
                extra = "   [solutions: %d]" % len(UNIQUE[k]())
            print(k, f(), extra)
        return 0
    from reasoning_items import ITEMS

    expected_ids = ["R%02d" % i for i in range(1, 41)] + ["RP%d" % i for i in range(1, 5)]
    assert [it["id"] for it in ITEMS] == expected_ids, "ids / order wrong"
    assert set(SOLVERS) == set(expected_ids)
    ok = 0
    for it in ITEMS:
        iid = it["id"]
        assert set(it) == {"id", "prompt", "answer", "answer_type"}, iid
        assert isinstance(it["answer"], str) and it["answer"] == it["answer"].strip(), iid
        assert it["answer_type"] in ("int", "str", "list"), iid
        if it["answer_type"] == "int":
            assert re.fullmatch(r"-?\d+", it["answer"]), iid
        elif it["answer_type"] == "str":
            assert re.fullmatch(r"[A-Za-z0-9/]+", it["answer"]), iid
        else:
            assert re.fullmatch(r"[A-Za-z0-9]+(,[A-Za-z0-9]+)*", it["answer"]), iid
        prompt = it["prompt"]
        assert prompt == prompt.strip(), iid
        assert _TAIL.search(prompt), "bad final line: " + iid
        words = len(prompt.split())
        assert 60 <= words <= 250, "%s has %d words" % (iid, words)
        got = SOLVERS[iid]()
        assert got == it["answer"], "%s: solver=%r key=%r" % (iid, got, it["answer"])
        if iid in UNIQUE:
            sols = UNIQUE[iid]()
            assert len(sols) == 1, "%s: %d solutions" % (iid, len(sols))
        ok += 1
    print("OK %d/%d" % (ok, len(ITEMS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
