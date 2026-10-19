"""Brute-force / simulation solvers for the round-2 reasoning_items.py.

Every solver recomputes its item's answer from the puzzle data by exhaustive
search or step-by-step simulation.  Run:

    python3 reasoning_solvers.py            # asserts everything, prints OK 36/36
    python3 reasoning_solvers.py --dump     # print every recomputed answer

It asserts every solver output equals the key in ITEMS, asserts uniqueness for
every constraint-style item, checks that the data / clue text used by each
solver appears verbatim in the prompt, runs structural checks on the prompts,
and prints "OK 36/36".  Stdlib only; works on Python 3.9+.
"""
import datetime
import os
import re
import sys
from itertools import permutations, product

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------
# Kind 1: long simulations (R01-R05, RP1)
# --------------------------------------------------------------------------
R01_RULES = (("XX", "YZ"), ("ZYZ", "XYY"), ("ZZZ", "X"), ("YZ", "ZX"), ("XY", "ZZ"))
R01_START = "ZXYYZXXYYZY"


def trace_r01(start=R01_START, rules=R01_RULES):
    s, step, out = start, 0, [start]
    while True:
        for lhs, rhs in rules:
            if lhs in s:
                step += 1
                i = s.find(lhs) if step % 2 == 1 else s.rfind(lhs)
                s = s[:i] + rhs + s[i + len(lhs):]
                out.append(s)
                break
        else:
            return out
        assert step < 500


def solve_r01():
    return trace_r01()[-1]


R02_MOD = 9
R02_INIT = {"A": 5, "B": 11, "C": 1, "D": 0, "E": 30}


def trace_r02():
    r = dict(R02_INIT)
    pc, log, n = 1, [], 0
    while True:
        n += 1
        assert n < 1000
        nxt = pc + 1
        if pc == 1:
            r["D"] += r["A"]
        elif pc == 2:
            if r["D"] % 2 == 1:
                r["A"] += 3
            else:
                r["A"] -= 1
        elif pc == 3:
            r["C"] *= 2
        elif pc == 4:
            if r["C"] > 25:
                r["C"] -= 23
        elif pc == 5:
            r["E"] -= r["C"]
        elif pc == 6:
            if r["E"] < 10:
                r["E"] += 25
                r["D"] += 1
        elif pc == 7:
            r["B"] -= 1
        elif pc == 8:
            if r["B"] > 4:
                nxt = 1
        elif pc == 9:
            if r["D"] % R02_MOD == 0:
                nxt = 12
        elif pc == 10:
            r["D"] += r["C"]
            r["A"], r["E"] = r["E"], r["A"]
        elif pc == 11:
            r["C"] += 1
            nxt = 9
        elif pc == 12:
            log.append((pc, dict(r)))
            return log
        log.append((pc, dict(r)))
        pc = nxt


def solve_r02():
    r = trace_r02()[-1][1]
    return "%d,%d,%d" % (r["A"], r["D"], r["E"])


R03_DECK = (4, 7, 3, 4, 9, 2, 6, 5, 8, 1, 6, 3, 2, 9, 5, 4, 7, 7, 1, 8, 3, 6, 2, 5)


def trace_r03(deck=R03_DECK):
    score = [0, 0]  # Ysolde, Brannoch
    row, who, log = [], 0, []
    for card in deck:
        row.append(card)
        again = False
        if len(row) >= 2 and card == row[0]:
            score[who] += len(row)
            row, ev = [], "a"
        elif sum(row) % 5 == 0:
            taken = row[-2:]
            row = row[:-2]
            score[who] += sum(taken)
            ev = "b"
        elif len(row) >= 2 and abs(card - row[-2]) == 1:
            score[who] += 2
            again, ev = True, "c"
        else:
            ev = "-"
        log.append((card, "YB"[who], ev, tuple(row), tuple(score)))
        if not again:
            who = 1 - who
    score[0] -= 0
    return log, score, row


def solve_r03():
    log, score, row = trace_r03()
    return "%d,%d,%d" % (score[0], score[1], len(row))


R04_ROLLS = (5, 4, 6, 3, 2, 6, 5, 1, 4, 6, 3, 5, 2, 4, 6, 3, 1, 5)
R04_N = 14
R04_SLIDE = (3, 8, 11)
R04_TOLL = (5, 10)
R04_PRIZE = (2, 6, 12)


def trace_r04():
    pos = [0, 7]  # Garnet, Teal
    coins = [4, 4]
    log = []
    for i, roll in enumerate(R04_ROLLS):
        me, other = i % 2, 1 - i % 2
        new = pos[me] + roll
        ev = ""
        if new >= R04_N:
            new -= R04_N
            coins[me] += 5
            ev += "lap "
        if new in R04_SLIDE:
            new -= 2
            ev += "slide "
        elif new in R04_TOLL:
            coins[me] -= min(3, coins[me])
            ev += "toll "
        elif new in R04_PRIZE:
            coins[me] += roll
            ev += "prize "
        pos[me] = new
        if pos[me] == pos[other]:
            take = coins[other] // 2
            coins[other] -= take
            coins[me] += take
            pos[other] = (pos[other] + 1) % R04_N
            ev += "bump "
        log.append((roll, "GT"[me], ev, tuple(pos), tuple(coins)))
    return log, pos, coins


def solve_r04():
    log, pos, coins = trace_r04()
    return "%d,%d,%d,%d" % (pos[0], coins[0], pos[1], coins[1])


R05_START = "1020120021"
R05_GENS = 6


def r05_step(cells):
    n = len(cells)
    out = []
    for i, c in enumerate(cells):
        left = cells[i - 1] if i > 0 else 0
        right = cells[i + 1] if i < n - 1 else 0
        t = left + right
        if t == 0:
            v = c
        elif t == 1:
            v = (c + 1) % 3
        elif t == 2:
            v = 2 if c == 0 else 0
        elif t == 3:
            v = 1
        else:
            v = (c + 2) % 3
        out.append(v)
    return out


def trace_r05():
    cells = [int(ch) for ch in R05_START]
    out = ["".join(map(str, cells))]
    for _ in range(R05_GENS):
        cells = r05_step(cells)
        out.append("".join(map(str, cells)))
    return out


def solve_r05():
    return trace_r05()[-1]


RP1_QUEUE = (14, 8, 9, 5, 13, 11, 7, 4, 3, 6, 12, 10)


def trace_rp1(queue=RP1_QUEUE):
    q, stack, log, discarded = list(queue), [], [], 0
    while q:
        n = q.pop(0)
        if not stack or n > stack[-1]:
            stack.append(n)
            ev = "push"
        elif n == stack[-1]:
            stack.pop()
            discarded += 2
            ev = "cancel"
        else:
            t = stack.pop()
            q.append(t - n)
            stack.append(n)
            ev = "split"
        log.append((n, ev, tuple(q), tuple(stack)))
        assert len(log) < 2000
    return log, stack


def solve_rp1():
    log, stack = trace_rp1()
    return ",".join(str(v) for v in stack)


# --------------------------------------------------------------------------
# Kind 2: counting (R06-R10, RP2)
# --------------------------------------------------------------------------
def solve_r06():
    # 8 flags, each R / W / B
    n = 0
    for s in product("RWB", repeat=8):
        if any(s[i] == "R" and s[i + 1] == "R" for i in range(7)):
            continue
        if s.count("B") % 2 != 0:
            continue
        if any(s[i:i + 3] == ("W", "B", "W") for i in range(6)):
            continue
        if s[0] == "B":
            continue
        n += 1
    return str(n)


R07_BOOKS = (("a1", "Harrowgate"), ("a2", "Harrowgate"), ("a3", "Harrowgate"),
             ("b1", "Ilves"), ("b2", "Ilves"), ("c1", "Jorund"), ("c2", "Jorund"))


def solve_r07():
    # a1 = Harrowgate's atlas; c1 = Jorund's diary; b1 = Ilves's primer
    author = dict(R07_BOOKS)
    n = 0
    for perm in permutations([b for b, _ in R07_BOOKS]):
        if any(author[perm[i]] == author[perm[i + 1]] for i in range(6)):
            continue
        if perm[0] == "a1" or perm[6] == "a1":
            continue
        if not perm.index("c1") < perm.index("a1"):
            continue
        n += 1
    return str(n)


R08_CAPS = {"V": 4, "W": 4, "X": 4, "Y": 4, "Z": 4}
R08_TOTAL = 11


def solve_r08():
    n = 0
    for v, w, x, y, z in product(range(5), repeat=5):
        if v + w + x + y + z != R08_TOTAL:
            continue
        if not v > w:
            continue
        if x % 2 != 0:
            continue
        if y == z:
            continue
        n += 1
    return str(n)


R09_EDGES = ("AB", "BC", "CD", "DE", "EF", "FG", "GH", "AD", "BF", "CH", "EH")


def solve_r09():
    rooms = "ABCDEFGH"
    n = 0
    for cols in product("ROG", repeat=8):  # red, ochre, green
        c = dict(zip(rooms, cols))
        if any(c[e[0]] == c[e[1]] for e in R09_EDGES):
            continue
        if cols.count("R") != 3:
            continue
        n += 1
    return str(n)


# forbidden (row, column) squares, both numbered 1..6
R10_BLOCKED = ((1, 3), (2, 5), (3, 1), (3, 2), (3, 5), (4, 2), (4, 3), (6, 4))


def solve_r10():
    n = 0
    blocked = set(R10_BLOCKED)
    for perm in permutations(range(1, 7)):  # perm[r-1] = column of the lamp in row r
        if any((r + 1, c) in blocked for r, c in enumerate(perm)):
            continue
        # no two lamps diagonally touching: rows r, r+1 with columns differing by 1
        if any(abs(perm[r] - perm[r + 1]) == 1 for r in range(5)):
            continue
        n += 1
    return str(n)


# 4 rows x 6 columns; removed squares given as (row, column), 1-based
RP2_ROWS, RP2_COLS = 4, 7
RP2_REMOVED = ((2, 6), (3, 4))


def solve_rp2():
    free = {(r, c) for r in range(1, RP2_ROWS + 1) for c in range(1, RP2_COLS + 1)} - set(RP2_REMOVED)

    def count(free):
        if not free:
            return 1
        r, c = min(free)
        total = 0
        for other in ((r, c + 1), (r + 1, c)):
            if other in free:
                total += count(free - {(r, c), other})
        return total

    return str(count(frozenset(free)))


# --------------------------------------------------------------------------
# Kind 3: constraint puzzles (R11-R15, RP3)
# Each clue is (English text exactly as numbered in the prompt, predicate).
# --------------------------------------------------------------------------
def _adj8(x, y):
    return (x - y) % 8 in (1, 7)


def _opp8(x, y):
    return (x - y) % 8 == 4


R15_WEIGHT = {"a": 9, "b": 4, "c": 6, "d": 7, "e": 11, "f": 2, "g": 8, "h": 3}


def _load(t, k):
    return sum(R15_WEIGHT[c] for c in t if t[c] == k)


def _cnt(t, k):
    return sum(1 for c in t if t[c] == k)


R11_CLUES = (
    ("Exactly two cottages stand between Esme's cottage and Aldric's cottage.",
     lambda A, B, C, D, E, F, G: abs(E - A) == 3),
    ('Exactly one of these two statements is true: "Dorrit lives in cottage 3"; "Dorrit\'s cottage is adjacent to Fenwick\'s".',
     lambda A, B, C, D, E, F, G: (D == 3) != (abs(D - F) == 1)),
    ('Exactly two of the four keepers Aldric, Caius, Esme and Gilda live in even-numbered cottages.',
     lambda A, B, C, D, E, F, G: sum(v % 2 == 0 for v in (A, C, E, G)) == 2),
    ('Caius lives somewhere west of Dorrit.',
     lambda A, B, C, D, E, F, G: C < D),
    ("Exactly one of Dorrit, Fenwick and Gilda lives in a cottage numbered lower than Aldric's.",
     lambda A, B, C, D, E, F, G: sum(v < A for v in (D, F, G)) == 1),
    ('If Caius lives west of Aldric, then Fenwick lives east of Dorrit.',
     lambda A, B, C, D, E, F, G: (not C < A) or F > D),
    ("Esme's cottage is adjacent to neither Dorrit's nor Fenwick's.",
     lambda A, B, C, D, E, F, G: abs(E - D) != 1 and abs(E - F) != 1),
    ('Fenwick does not live in cottage 1, cottage 2 or cottage 7.',
     lambda A, B, C, D, E, F, G: F not in (1, 2, 7)),
    ("Gilda's cottage is adjacent to exactly one of these two cottages: Caius's, Bettony's.",
     lambda A, B, C, D, E, F, G: (abs(G - C) == 1) != (abs(G - B) == 1)),
    ('If Esme lives in cottage 1, then Gilda does not live in cottage 2.',
     lambda A, B, C, D, E, F, G: E != 1 or G != 2),
    ('If Gilda lives in an odd-numbered cottage, then Bettony also lives in an odd-numbered cottage.',
     lambda A, B, C, D, E, F, G: G % 2 == 0 or B % 2 == 1),
)

R12_CLUES = (
    ('Exactly two of the four guests Isaura, Jocasta, Mirren and Odalys have a seat number greater than 4.',
     lambda H, I, J, K, L, M, N, O: sum(v > 4 for v in (I, J, M, O)) == 2),
    ('If Kell is adjacent to Mirren, then Lysander is adjacent to Njal.',
     lambda H, I, J, K, L, M, N, O: (not _adj8(K, M)) or _adj8(L, N)),
    ('Mirren is in neither seat 4 nor seat 6.',
     lambda H, I, J, K, L, M, N, O: M not in (4, 6)),
    ('Exactly one of the three guests Isaura, Kell and Odalys is adjacent to Lysander.',
     lambda H, I, J, K, L, M, N, O: sum(_adj8(v, L) for v in (I, K, O)) == 1),
    ('Jocasta is in an even-numbered seat.',
     lambda H, I, J, K, L, M, N, O: J % 2 == 0),
    ("Kell's seat number is higher than Mirren's and lower than Isaura's.",
     lambda H, I, J, K, L, M, N, O: M < K < I),
    ('If Njal is in an odd-numbered seat, then Mirren is in an even-numbered seat.',
     lambda H, I, J, K, L, M, N, O: N % 2 == 0 or M % 2 == 0),
    ('Halvard sits directly opposite Isaura.',
     lambda H, I, J, K, L, M, N, O: _opp8(H, I)),
    ('Odalys is not adjacent to Halvard.',
     lambda H, I, J, K, L, M, N, O: not _adj8(O, H)),
    ('Njal is adjacent to Jocasta.',
     lambda H, I, J, K, L, M, N, O: _adj8(N, J)),
    ('If Halvard is adjacent to Jocasta, then Kell is in an odd-numbered seat.',
     lambda H, I, J, K, L, M, N, O: (not _adj8(H, J)) or K % 2 == 1),
)

R13_CLUES = (
    ('Pernille plays neither the bassoon nor the cittern.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: P not in (ba, ci)),
    ('If Pernille performs before Thursday, then the flute recital is before Wednesday.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: P >= 4 or fl < 3),
    ('Exactly one of these two statements is true: "Torvald plays the harp"; "Torvald performs on Thursday".',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: (T == ha) != (T == 4)),
    ('Rasmus does not perform on Wednesday, Thursday or Saturday.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: R not in (3, 4, 6)),
    ('Quentin performs later in the week than the bassoon player.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: Q > ba),
    ('Exactly two days lie between the day of the flute recital and the day of the cittern recital.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: abs(fl - ci) == 3),
    ('Sunniva performs on the day immediately after the oboe recital.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: S == ob + 1),
    ('Quentin plays none of these three instruments: bassoon, flute, oboe.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: Q not in (ba, fl, ob)),
    ("The harp recital is on the day immediately before Pernille's recital.",
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: ha + 1 == P),
    ('Torvald performs earlier in the week than the oboe player.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: T < ob),
    ('Rasmus performs earlier in the week than Sunniva.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: R < S),
    ('Exactly one of the bassoon, dulcimer and harp recitals falls on a Monday, Wednesday or Friday.',
     lambda P, Q, R, S, T, U, ba, ci, du, fl, ha, ob: sum(v in (1, 3, 5) for v in (ba, du, ha)) == 1),
)

R14_CLUES = (
    ("If Vesna's number is greater than Yorick's, then Briar's number is odd.",
     lambda V, W, X, Y, Z, A, B: V <= Y or B % 2 == 1),
    ('Exactly one of these two statements is true: "Wystan\'s number is greater than Ambrose\'s"; "Briar\'s number is greater than Vesna\'s".',
     lambda V, W, X, Y, Z, A, B: (W > A) != (B > V)),
    ("Briar's number is not a multiple of 3.",
     lambda V, W, X, Y, Z, A, B: B % 3 != 0),
    ('Exactly three of the seven members hold even numbers.',
     lambda V, W, X, Y, Z, A, B: sum(v % 2 == 0 for v in (V, W, X, Y, Z, A, B)) == 3),
    ('Exactly two of the four members Wystan, Yorick, Ambrose and Briar hold numbers less than 3.',
     lambda V, W, X, Y, Z, A, B: sum(v < 3 for v in (W, Y, A, B)) == 2),
    ('The number 8 is not held by Vesna, Xanthe or Zelda.',
     lambda V, W, X, Y, Z, A, B: 8 not in (V, X, Z)),
    ('The largest of the seven numbers is held by Xanthe or by Zelda.',
     lambda V, W, X, Y, Z, A, B: max(V, W, X, Y, Z, A, B) in (X, Z)),
    ("Ambrose's number is odd.",
     lambda V, W, X, Y, Z, A, B: A % 2 == 1),
    ('Exactly one of these two statements is true: "Vesna\'s number is a multiple of 3"; "Zelda\'s number is a multiple of 3".',
     lambda V, W, X, Y, Z, A, B: (V % 3 == 0) != (Z % 3 == 0)),
    ("Zelda's number is greater than Vesna's.",
     lambda V, W, X, Y, Z, A, B: Z > V),
    ("Xanthe's number is larger than Zelda's.",
     lambda V, W, X, Y, Z, A, B: X > Z),
    ("Vesna's number plus Wystan's number equals twice Yorick's number.",
     lambda V, W, X, Y, Z, A, B: V + W == 2 * Y),
)

R15_CLUES = (
    ('Exactly one of these two statements is true: "the drum and the girder are on the same truck"; "the drum and the anvil are on the same truck".',
     lambda t: (t['d'] == t['g']) != (t['d'] == t['a'])),
    ('The drum is not on the Tan truck.',
     lambda t: t['d'] != 'T'),
    ('The truck carrying the cable has a total load of less than 15.',
     lambda t: _load(t, t['c']) < 15),
    ('The fleece and the cable are on different trucks.',
     lambda t: t['f'] != t['c']),
    ('The barrel is not on the Red truck.',
     lambda t: t['b'] != 'R'),
    ('The engine is not on the Red truck.',
     lambda t: t['e'] != 'R'),
    ("The Red truck's total load is an even number.",
     lambda t: _load(t, 'R') % 2 == 0),
    ('The girder shares its truck with exactly one other crate.',
     lambda t: _cnt(t, t['g']) == 2),
    ('If the cable is on the Tan truck, then the girder is on the Red truck.',
     lambda t: t['c'] != 'T' or t['g'] == 'R'),
    ('The fleece and the hawser are on different trucks.',
     lambda t: t['f'] != t['h']),
    ('The Violet truck carries exactly two crates.',
     lambda t: _cnt(t, 'V') == 2),
)

RP3_CLUES = (
    ('If Eluned keeps a dog, then Greta keeps a dog.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: e != 'dog' or g == 'dog'),
    ('Fabian and Corvin keep the same kind of pet.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: f == c),
    ('The resident of floor 1 keeps a dog.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: dict(zip((C, D, E, F, G, H), (c, d, e, f, g, h)))[1] == 'dog'),
    ("Delwyn lives on the floor directly above Hesper's.",
     lambda C, D, E, F, G, H, c, d, e, f, g, h: D == H + 1),
    ('The residents of floor 2 and floor 4 keep the same kind of pet.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: dict(zip((C, D, E, F, G, H), (c, d, e, f, g, h)))[2] == dict(zip((C, D, E, F, G, H), (c, d, e, f, g, h)))[4]),
    ('Corvin lives on neither floor 1 nor floor 3.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: C not in (1, 3)),
    ('If Hesper keeps a cat, then Delwyn does not keep a dog.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: h != 'cat' or d != 'dog'),
    ('Exactly three of the six residents keep a cat.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: (c, d, e, f, g, h).count('cat') == 3),
    ('No two residents living on consecutive floors both keep dogs.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: all(not (x == 'dog' and y == 'dog' and abs(m - n) == 1) for m, x in zip((C, D, E, F, G, H), (c, d, e, f, g, h)) for n, y in zip((C, D, E, F, G, H), (c, d, e, f, g, h)))),
    ('Exactly one of these two statements is true: "Fabian lives on floor 6"; "Fabian keeps a dog".',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: (F == 6) != (f == 'dog')),
    ('Corvin lives on a lower floor than Greta.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: C < G),
    ('Delwyn lives on a higher floor than Greta.',
     lambda C, D, E, F, G, H, c, d, e, f, g, h: D > G),
)


def _clue_search(worlds, clues):
    fs = [f for _, f in clues]
    return [w for w in worlds if all(f(*w) for f in fs)]


R11_NAMES = ("Aldric", "Bettony", "Caius", "Dorrit", "Esme", "Fenwick", "Gilda")


def _all_r11():
    return _clue_search(permutations(range(1, 8)), R11_CLUES)


def solve_r11():
    w = _all_r11()[0]
    return ",".join(sorted(R11_NAMES, key=lambda n: w[R11_NAMES.index(n)]))


R12_NAMES = ("Halvard", "Isaura", "Jocasta", "Kell", "Lysander", "Mirren", "Njal", "Odalys")


def _all_r12():
    return _clue_search(permutations(range(1, 9)), R12_CLUES)


def solve_r12():
    w = _all_r12()[0]
    return ",".join(sorted(R12_NAMES, key=lambda n: w[R12_NAMES.index(n)]))


R13_NAMES = ("Pernille", "Quentin", "Rasmus", "Sunniva", "Torvald", "Ursa")
R13_INSTR = ("bassoon", "cittern", "dulcimer", "flute", "harp", "oboe")


def _all_r13():
    worlds = (a + b for a in permutations(range(1, 7)) for b in permutations(range(1, 7)))
    return _clue_search(worlds, R13_CLUES)


def solve_r13():
    # instruments in day order Monday..Saturday
    w = _all_r13()[0]
    return ",".join(sorted(R13_INSTR, key=lambda n: w[6 + R13_INSTR.index(n)]))


R14_NAMES = ("Vesna", "Wystan", "Xanthe", "Yorick", "Zelda", "Ambrose", "Briar")


def _all_r14():
    return _clue_search(permutations(range(1, 10), 7), R14_CLUES)


def solve_r14():
    return ",".join(str(v) for v in _all_r14()[0])


R15_CRATES = ("anvil", "barrel", "cable", "drum", "engine", "fleece", "girder", "hawser")


def _all_r15():
    worlds = []
    for tr in product("RTV", repeat=8):
        if min(tr.count(k) for k in "RTV") >= 2:  # every truck carries at least two crates
            worlds.append((dict(zip("abcdefgh", tr)),))
    return _clue_search(worlds, R15_CLUES)


def solve_r15():
    t = _all_r15()[0][0]
    return ",".join(t[c] for c in "abcdefgh")


RP3_NAMES = ("Corvin", "Delwyn", "Eluned", "Fabian", "Greta", "Hesper")


def _all_rp3():
    worlds = (a + b for a in permutations(range(1, 7)) for b in product(("cat", "dog", "finch"), repeat=6))
    return _clue_search(worlds, RP3_CLUES)


def solve_rp3():
    w = _all_rp3()[0]
    return ",".join(sorted(RP3_NAMES, key=lambda n: w[RP3_NAMES.index(n)]))


# --------------------------------------------------------------------------
# Kind 4: graphs and scheduling (R16-R20, RP4)
# --------------------------------------------------------------------------
# (from, to, first departure minute, minutes between departures, sailing minutes); one-way
R16_FERRIES = (
    ("Arrow", "Brine", 22, 45, 17), ("Arrow", "Dune", 12, 25, 14), ("Arrow", "Gull", 32, 40, 21),
    ("Brine", "Haven", 11, 40, 28), ("Cask", "Brine", 13, 40, 12), ("Cask", "Dune", 10, 20, 19),
    ("Cask", "Haven", 33, 45, 28), ("Cask", "Jetty", 17, 60, 14), ("Dune", "Flint", 23, 40, 19),
    ("Dune", "Gull", 11, 35, 26), ("Dune", "Haven", 19, 20, 14), ("Flint", "Ember", 15, 60, 23),
    ("Gull", "Ember", 14, 40, 21), ("Gull", "Haven", 39, 50, 34), ("Gull", "Jetty", 39, 50, 23),
    ("Haven", "Islet", 18, 35, 12), ("Islet", "Jetty", 16, 25, 31),
)
R16_START, R16_GOAL = "Arrow", "Jetty"


def r16_arrivals(ferries=None, start=None, horizon=600):
    ferries = R16_FERRIES if ferries is None else ferries
    start = R16_START if start is None else start
    best = {start: 0}
    for t in range(horizon):  # sweep minute by minute; sailing times are positive
        for a, b, first, every, dur in ferries:
            if t >= first and (t - first) % every == 0 and a in best and best[a] <= t:
                if b not in best or t + dur < best[b]:
                    best[b] = t + dur
    return best


def solve_r16():
    return str(r16_arrivals()[R16_GOAL])


# road lengths in km (two-way)
R17_ROADS = (
    ("A", "J", 17), ("B", "F", 7), ("B", "G", 10), ("B", "J", 10), ("B", "K", 7), ("C", "G", 17),
    ("C", "H", 12), ("C", "J", 15), ("C", "K", 17), ("C", "L", 17), ("D", "H", 7), ("D", "K", 10),
    ("E", "H", 8), ("F", "G", 19), ("F", "J", 19), ("F", "K", 13), ("G", "K", 10), ("H", "L", 18),
    ("J", "K", 7),
)
R17_CHARGERS = ("B", "C", "G")
R17_RANGE = 30
R17_START, R17_GOAL = "A", "L"


def r17_best(roads=None, chargers=None, rng=None, start=None, goal=None):
    roads = R17_ROADS if roads is None else roads
    chargers = R17_CHARGERS if chargers is None else chargers
    rng = R17_RANGE if rng is None else rng
    start = R17_START if start is None else start
    goal = R17_GOAL if goal is None else goal
    adj = {}
    for a, b, d in roads:
        adj.setdefault(a, []).append((b, d))
        adj.setdefault(b, []).append((a, d))
    # Bellman-Ford style relaxation over states (town, km of range left)
    dist = {(start, rng): 0}
    changed = True
    while changed:
        changed = False
        for (u, left), du in list(dist.items()):
            for v, d in adj.get(u, ()):
                if d > left:
                    continue
                nl = rng if v in chargers else left - d
                if dist.get((v, nl), 10 ** 9) > du + d:
                    dist[(v, nl)] = du + d
                    changed = True
    cands = [d for (u, _), d in dist.items() if u == goal]
    return min(cands) if cands else None


def solve_r17():
    return str(r17_best())


R18_ROADS = (
    ("A", "F", 20), ("A", "H", 23), ("A", "K", 30), ("B", "D", 24), ("C", "E", 14), ("C", "J", 10),
    ("C", "K", 8), ("D", "F", 37), ("D", "H", 33), ("D", "M", 17), ("E", "G", 4), ("F", "G", 16),
    ("F", "J", 11), ("G", "K", 25), ("G", "L", 22), ("G", "M", 27), ("H", "J", 5), ("H", "L", 39),
    ("K", "L", 35), ("L", "M", 29),
)
R18_START = "A"


def trace_r18(roads=None, start=None):
    roads = R18_ROADS if roads is None else roads
    start = R18_START if start is None else start
    adj = {}
    for a, b, d in roads:
        adj.setdefault(a, {})[b] = d
        adj.setdefault(b, {})[a] = d
    order, came_from, cur, total, log = [start], {}, start, 0, []
    while len(order) < len(adj):
        opts = [(d, v) for v, d in adj[cur].items() if v not in order]
        if opts:
            if len(order) % 3 == 0:
                d, v = min(opts, key=lambda o: (-o[0], o[1]))  # longest, ties alphabetical
            else:
                d, v = min(opts)  # shortest, ties alphabetical
            came_from[v] = cur
            order.append(v)
            log.append(("go", cur, v, d))
        else:
            v = came_from[cur]
            d = adj[cur][v]
            log.append(("back", cur, v, d))
        total += d
        cur = v
    return order, total, log


def solve_r18():
    order, total, _ = trace_r18()
    return "%d,%s" % (total, order[-1])


# candidate links: (hub, hub, cost); all costs distinct
R19_LINKS = (
    ("A", "B", 58), ("A", "K", 46), ("B", "C", 44), ("B", "E", 35), ("B", "G", 29), ("C", "D", 73),
    ("C", "E", 38), ("C", "J", 18), ("D", "E", 27), ("D", "G", 76), ("D", "J", 26), ("D", "K", 28),
    ("E", "F", 51), ("E", "J", 11), ("E", "K", 63), ("E", "M", 66), ("F", "H", 53), ("F", "J", 39),
    ("F", "L", 12), ("G", "J", 48), ("H", "K", 49), ("H", "L", 69), ("H", "M", 59), ("L", "M", 23),
)
R19_CAP = 2


def trace_r19(links=None):
    links = R19_LINKS if links is None else links
    hubs = sorted({h for l in links for h in l[:2]})
    comp = {h: h for h in hubs}
    deg = {h: 0 for h in hubs}
    total, log = 0, []
    for a, b, c in sorted(links, key=lambda l: l[2]):
        if comp[a] == comp[b]:
            log.append((a, b, c, "loop"))
            continue
        if deg[a] >= R19_CAP or deg[b] >= R19_CAP:
            log.append((a, b, c, "full"))
            continue
        old = comp[b]
        for h in hubs:
            if comp[h] == old:
                comp[h] = comp[a]
        deg[a] += 1
        deg[b] += 1
        total += c
        log.append((a, b, c, "built"))
    return total, len(set(comp.values())), log


def solve_r19():
    total, groups, _ = trace_r19()
    return "%d,%d" % (total, groups)


# task: (days, crew needed, prerequisites)
R20_TASKS = {
    "A": (6, 2, ()), "B": (5, 5, ()), "C": (2, 5, ("A", "B")), "D": (5, 5, ()),
    "E": (5, 4, ("A", "C")), "F": (2, 4, ("E",)), "G": (2, 2, ()), "H": (7, 3, ("A", "D")),
    "I": (3, 5, ("A", "E")), "J": (4, 3, ("D", "I")), "K": (4, 2, ("H",)),
}
R20_CREW = 7


def trace_r20(tasks=None, crew=None):
    tasks = R20_TASKS if tasks is None else tasks
    crew = R20_CREW if crew is None else crew
    start, finish, running, free, t = {}, {}, {}, crew, 0
    while len(finish) < len(tasks):
        for k in sorted(tasks):
            days, need, pre = tasks[k]
            if k not in start and all(p in finish for p in pre) and need <= free:
                start[k] = t
                running[k] = t + days
                free -= need
        t = min(running.values())
        for k in [k for k, e in running.items() if e == t]:
            finish[k] = t
            free += tasks[k][1]
            del running[k]
    return start, finish


def solve_r20():
    start, finish = trace_r20()
    return "%d,%d" % (max(finish.values()), start["K"])


# job: (hours, prerequisites, needs_kiln)
RP4_JOBS = {
    "A": (4, (), False), "B": (2, (), False), "C": (5, (), False), "D": (8, ("A", "C"), True),
    "E": (5, (), False), "F": (9, ("B", "E"), True), "G": (9, ("C", "E"), True),
    "H": (4, ("A", "C"), True), "I": (7, ("C",), False), "J": (8, ("B",), False),
    "K": (9, ("I",), False),
}


def trace_rp4(jobs=None):
    jobs = RP4_JOBS if jobs is None else jobs
    start, finish, who = {}, {}, {}
    busy = {"Wren": None, "Pike": None}  # worker -> (job, end time)
    t = 0
    while len(finish) < len(jobs):
        for w in ("Wren", "Pike"):
            if busy[w] is not None:
                continue
            ready = [k for k in jobs if k not in start and all(p in finish for p in jobs[k][1])
                     and (w == "Wren" or not jobs[k][2])]
            if ready:
                k = min(ready, key=lambda j: (-jobs[j][0], j))  # longest first, ties alphabetical
                start[k], who[k] = t, w
                busy[w] = (k, t + jobs[k][0])
        t = min(b[1] for b in busy.values() if b is not None)
        for w in busy:
            if busy[w] is not None and busy[w][1] == t:
                finish[busy[w][0]] = t
                busy[w] = None
    return start, finish, who


def solve_rp4():
    start, finish, who = trace_rp4()
    return "%d,%d" % (max(finish.values()), sum(1 for k in who if who[k] == "Pike"))


# --------------------------------------------------------------------------
# Kind 5: truth-tellers, liars and self-reference (R21-R25, RP5)
# A statement is (speaker, English text exactly as in the prompt, is_reference,
# predicate(t, x, s)) where t maps name -> kind letter, x is the hidden fact
# (thief / number) if any, and s maps (speaker, ordinal) -> truth value of the
# non-reference statements.
# --------------------------------------------------------------------------
def _is_prime(n):
    return n > 1 and all(n % d for d in range(2, int(n ** 0.5) + 1))


def _liar_solutions(names, kinds, stmts, mode, extras=(None,)):
    """kinds[0] always tells the truth, kinds[1] always lies, kinds[2] is the
    special kind: mode "ONE_OF_TWO" (exactly one of two statements true),
    "ALTERNATE" (truth values alternate) or "CONTRARY" (statement true exactly
    when the previous speaker's statement is false; first follows last)."""
    sols = []
    for combo in product(kinds, repeat=len(names)):
        t = dict(zip(names, combo))
        for x in extras:
            s, vals, ordn = {}, [None] * len(stmts), {}
            for i, (sp, _txt, is_ref, f) in enumerate(stmts):
                ordn[sp] = ordn.get(sp, 0) + 1
                if not is_ref:
                    vals[i] = bool(f(t, x, s))
                    s[(sp, ordn[sp])] = vals[i]
            for i, (sp, _txt, is_ref, f) in enumerate(stmts):
                if is_ref:
                    vals[i] = bool(f(t, x, s))
            ok = True
            if mode == "CONTRARY":
                for i, st in enumerate(stmts):
                    k = t[st[0]]
                    if k == kinds[0]:
                        good = vals[i]
                    elif k == kinds[1]:
                        good = not vals[i]
                    else:
                        good = vals[i] != vals[i - 1]  # i = 0 looks at the last speaker
                    ok = ok and good
            else:
                for n in names:
                    v = [vals[i] for i, st in enumerate(stmts) if st[0] == n]
                    k = t[n]
                    if k == kinds[0]:
                        good = all(v)
                    elif k == kinds[1]:
                        good = not any(v)
                    elif mode == "ONE_OF_TWO":
                        good = len(v) == 2 and sum(v) == 1
                    else:
                        good = all(v[j] != v[j + 1] for j in range(len(v) - 1))
                    ok = ok and good
            if ok:
                sols.append((combo, x))
    return sols


R21_NAMES = ("Brannick", "Cosima", "Dagny", "Evander", "Fliss", "Gorran")
R21_KINDS = "STD"
R21_STATEMENTS = (
    ('Brannick', 'Fliss is not a Steadfast.', False,
     lambda t, x, s: t['Fliss'] != 'S'),
    ('Brannick', 'At least one of Evander and Gorran is a Drifter.', False,
     lambda t, x, s: 'D' in (t['Evander'], t['Gorran'])),
    ('Cosima', 'Brannick is a Steadfast and Gorran is a Twister.', False,
     lambda t, x, s: t['Brannick'] == 'S' and t['Gorran'] == 'T'),
    ('Cosima', 'At most one of the six of us is a Twister.', False,
     lambda t, x, s: list(t.values()).count('T') <= 1),
    ('Dagny', 'At most two of the six of us are Steadfasts.', False,
     lambda t, x, s: list(t.values()).count('S') <= 2),
    ('Dagny', 'Fliss is a Drifter.', False,
     lambda t, x, s: t['Fliss'] == 'D'),
    ('Evander', 'Gorran is a Drifter.', False,
     lambda t, x, s: t['Gorran'] == 'D'),
    ('Evander', 'Dagny and Gorran are of the same kind.', False,
     lambda t, x, s: t['Dagny'] == t['Gorran']),
    ('Fliss', 'Evander is a Twister.', False,
     lambda t, x, s: t['Evander'] == 'T'),
    ('Fliss', 'Cosima is a Drifter.', False,
     lambda t, x, s: t['Cosima'] == 'D'),
    ('Gorran', "Evander's second statement is true.", True,
     lambda t, x, s: s[('Evander', 2)]),
    ('Gorran', 'Evander and I are of different kinds.', False,
     lambda t, x, s: t['Evander'] != t['Gorran']),
)

R22_NAMES = ("Hesketh", "Imre", "Juno", "Kasimir", "Leda")
R22_KINDS = "VFA"
R22_STATEMENTS = (
    ('Hesketh', 'Leda is a Verity and Kasimir is an Alternator.', False,
     lambda t, x, s: t['Leda'] == 'V' and t['Kasimir'] == 'A'),
    ('Hesketh', 'At least one of Juno and Kasimir is an Alternator.', False,
     lambda t, x, s: 'A' in (t['Juno'], t['Kasimir'])),
    ('Hesketh', 'Kasimir and Imre are of the same kind.', False,
     lambda t, x, s: t['Kasimir'] == t['Imre']),
    ('Imre', "Leda's second statement is true.", True,
     lambda t, x, s: s[('Leda', 2)]),
    ('Imre', 'The sextant was taken by Hesketh or by Juno.', False,
     lambda t, x, s: x in ('Hesketh', 'Juno')),
    ('Imre', 'At most one of the five of us is a Falsifier.', False,
     lambda t, x, s: list(t.values()).count('F') <= 1),
    ('Juno', 'Neither Leda nor Imre took the sextant.', False,
     lambda t, x, s: x not in ('Leda', 'Imre')),
    ('Juno', 'Leda and I are of different kinds.', False,
     lambda t, x, s: t['Leda'] != t['Juno']),
    ('Juno', 'Imre is an Alternator and Leda is an Alternator.', False,
     lambda t, x, s: t['Imre'] == 'A' and t['Leda'] == 'A'),
    ('Kasimir', 'The person who took the sextant is not a Verity.', False,
     lambda t, x, s: t[x] != 'V'),
    ('Kasimir', 'The sextant was taken by Imre or by Leda.', False,
     lambda t, x, s: x in ('Imre', 'Leda')),
    ('Kasimir', 'Juno is not a Falsifier.', False,
     lambda t, x, s: t['Juno'] != 'F'),
    ('Leda', 'Juno took the sextant.', False,
     lambda t, x, s: x == 'Juno'),
    ('Leda', 'The person who took the sextant is an Alternator.', False,
     lambda t, x, s: t[x] == 'A'),
    ('Leda', 'The sextant was taken by Imre or by Juno.', False,
     lambda t, x, s: x in ('Imre', 'Juno')),
)

R24_NAMES = ("Maelis", "Nico", "Oswin", "Petra", "Quillon", "Runa")
R24_KINDS = "CGH"
R24_STATEMENTS = (
    ('Maelis', 'I am not a Halfling.', False,
     lambda t, x, s: t['Maelis'] != 'H'),
    ('Maelis', 'Runa is a Candid.', False,
     lambda t, x, s: t['Runa'] == 'C'),
    ('Nico', 'Petra is a Candid.', False,
     lambda t, x, s: t['Petra'] == 'C'),
    ('Nico', 'The number of steps is a prime number.', False,
     lambda t, x, s: _is_prime(x)),
    ('Oswin', 'The number of steps is even.', False,
     lambda t, x, s: x % 2 == 0),
    ('Oswin', 'The number of steps is not a multiple of 5.', False,
     lambda t, x, s: x % 5 != 0),
    ('Petra', 'At most two of the six of us are Candids.', False,
     lambda t, x, s: list(t.values()).count('C') <= 2),
    ('Petra', 'The two digits of the number of steps differ by exactly 1.', False,
     lambda t, x, s: abs(x // 10 - x % 10) == 1),
    ('Quillon', 'The number of steps is a multiple of 3.', False,
     lambda t, x, s: x % 3 == 0),
    ('Quillon', 'Among the six of us there are more Candids than Guilers.', False,
     lambda t, x, s: list(t.values()).count('C') > list(t.values()).count('G')),
    ('Runa', 'The number of steps is less than 12.', False,
     lambda t, x, s: x < 12),
    ('Runa', 'Quillon is not a Halfling.', False,
     lambda t, x, s: t['Quillon'] != 'H'),
)

R25_NAMES = ("Sable", "Tiernan", "Ulla", "Vance", "Wilhelmina", "Xavi", "Yseult")
R25_KINDS = "PDC"
R25_STATEMENTS = (
    ('Sable', 'Wilhelmina and I are of different kinds.', False,
     lambda t, x, s: t['Wilhelmina'] != t['Sable']),
    ('Tiernan', 'At most two of the seven of us are Contraries.', False,
     lambda t, x, s: list(t.values()).count('C') <= 2),
    ('Ulla', 'Xavi and Sable are of the same kind.', False,
     lambda t, x, s: t['Xavi'] == t['Sable']),
    ('Vance', 'Tiernan and I are of different kinds.', False,
     lambda t, x, s: t['Tiernan'] != t['Vance']),
    ('Wilhelmina', 'At least one of Xavi and Vance is a Deceiver.', False,
     lambda t, x, s: 'D' in (t['Xavi'], t['Vance'])),
    ('Xavi', 'Vance is a Deceiver and Tiernan is a Deceiver.', False,
     lambda t, x, s: t['Vance'] == 'D' and t['Tiernan'] == 'D'),
    ('Yseult', 'Wilhelmina is a Plainspeaker and Vance is a Contrary.', False,
     lambda t, x, s: t['Wilhelmina'] == 'P' and t['Vance'] == 'C'),
)

RP5_NAMES = ("Anwen", "Bede", "Calla", "Dov", "Edda")
RP5_KINDS = "KBF"
RP5_STATEMENTS = (
    ('Anwen', "Bede's first statement is true.", True,
     lambda t, x, s: s[('Bede', 1)]),
    ('Anwen', 'Edda is a Bender and Dov is a Keeper.', False,
     lambda t, x, s: t['Edda'] == 'B' and t['Dov'] == 'K'),
    ('Anwen', 'Exactly two of the five of us are Flippers.', False,
     lambda t, x, s: list(t.values()).count('F') == 2),
    ('Bede', 'Exactly two of the five of us are Keepers.', False,
     lambda t, x, s: list(t.values()).count('K') == 2),
    ('Bede', 'At least one of these is the case: Anwen is a Bender; Edda is a Keeper.', False,
     lambda t, x, s: t['Anwen'] == 'B' or t['Edda'] == 'K'),
    ('Bede', 'At least one of these is the case: Dov is a Keeper; Edda is a Flipper.', False,
     lambda t, x, s: t['Dov'] == 'K' or t['Edda'] == 'F'),
    ('Calla', 'Among the five of us there are more Flippers than Benders.', False,
     lambda t, x, s: list(t.values()).count('F') > list(t.values()).count('B')),
    ('Calla', 'Bede is a Bender.', False,
     lambda t, x, s: t['Bede'] == 'B'),
    ('Calla', 'Bede and Edda are of the same kind.', False,
     lambda t, x, s: t['Bede'] == t['Edda']),
    ('Dov', 'Calla is a Keeper and Anwen is a Bender.', False,
     lambda t, x, s: t['Calla'] == 'K' and t['Anwen'] == 'B'),
    ('Dov', 'Exactly three of the five of us are Keepers.', False,
     lambda t, x, s: list(t.values()).count('K') == 3),
    ('Dov', 'Edda is a Flipper.', False,
     lambda t, x, s: t['Edda'] == 'F'),
    ('Edda', 'Calla and I are of different kinds.', False,
     lambda t, x, s: t['Calla'] != t['Edda']),
    ('Edda', 'I am not a Flipper.', False,
     lambda t, x, s: t['Edda'] != 'F'),
    ('Edda', 'Dov and I are of different kinds.', False,
     lambda t, x, s: t['Dov'] != t['Edda']),
)


def _all_r21():
    return _liar_solutions(R21_NAMES, R21_KINDS, R21_STATEMENTS, "ONE_OF_TWO")


def solve_r21():
    return ",".join(_all_r21()[0][0])


def _all_r22():
    return _liar_solutions(R22_NAMES, R22_KINDS, R22_STATEMENTS, "ALTERNATE", R22_NAMES)


def solve_r22():
    combo, thief = _all_r22()[0]
    return thief + "," + ",".join(combo)


R23_STATEMENTS = (
    ("The number of true statements among these nine is even.", lambda v: sum(v[1:]) % 2 == 0),
    ("Exactly two of the odd-numbered statements (1, 3, 5, 7, 9) are true.", lambda v: sum(v[1::2]) == 2),
    ("At least two of statements 1, 2, 3 and 4 are true.", lambda v: sum(v[1:5]) >= 2),
    ("Statement 3 and statement 5 have the same truth value (both true or both false).", lambda v: v[3] == v[5]),
    ("Exactly five of these nine statements are true.", lambda v: sum(v[1:]) == 5),
    ("Statement 9 is false.", lambda v: not v[9]),
    ("Statement 1 is false.", lambda v: not v[1]),
    ("Statement 7 and statement 9 have the same truth value (both true or both false).", lambda v: v[7] == v[9]),
    ("Exactly one of statements 4 and 5 is true.", lambda v: v[4] != v[5]),
)


def _all_r23():
    out = []
    for bits in product((False, True), repeat=9):
        v = (None,) + bits  # v[i] = truth value of statement i
        if all(bool(f(v)) == v[i + 1] for i, (_txt, f) in enumerate(R23_STATEMENTS)):
            out.append(bits)
    return out


def solve_r23():
    bits = _all_r23()[0]
    return ",".join(str(i + 1) for i, b in enumerate(bits) if b)


R24_RANGE = tuple(range(10, 41))


def _all_r24():
    return _liar_solutions(R24_NAMES, R24_KINDS, R24_STATEMENTS, "ONE_OF_TWO", R24_RANGE)


def solve_r24():
    return str(_all_r24()[0][1])


def _all_r25():
    return _liar_solutions(R25_NAMES, R25_KINDS, R25_STATEMENTS, "CONTRARY")


def solve_r25():
    return ",".join(_all_r25()[0][0])


def _all_rp5():
    return _liar_solutions(RP5_NAMES, RP5_KINDS, RP5_STATEMENTS, "ALTERNATE")


def solve_rp5():
    return ",".join(_all_rp5()[0][0])


# --------------------------------------------------------------------------
# Kind 6: multi-stage quantitative (R26-R30, RP6)
# --------------------------------------------------------------------------
R26_YEAR = 2027
R26_JOBS = {"prune": ((1, 5), 9), "spray": ((1, 11), 14)}  # first date (month, day), interval in days


def r26_done_dates(first, every):
    d = datetime.date(R26_YEAR, first[0], first[1])
    out = set()
    while d.year == R26_YEAR:
        actual = d + datetime.timedelta(days=1) if d.weekday() == 6 else d  # Sunday -> Monday
        if actual.year == R26_YEAR and actual.month != 8:  # nothing is done in August
            out.add(actual)
        d += datetime.timedelta(days=every)  # always counted from the planned date
    return out


def r26_both():
    a = r26_done_dates(*R26_JOBS["prune"])
    b = r26_done_dates(*R26_JOBS["spray"])
    return sorted(a & b)


def solve_r26():
    d = r26_both()[2]
    return "%d,%d" % (d.day, d.month)


# draw-off in litres per minute for [start, end) minutes after 06:00
R27_DRAW = ((0, 90, 6), (90, 180, 14), (180, 300, 9), (300, 360, 17))
R27_START_LEVEL, R27_PUMP, R27_LOW, R27_HIGH = 420, 25, 300, 800


def trace_r27():
    level, on, on_minutes, events = R27_START_LEVEL, False, 0, []
    for m in range(360):
        if not on and level < R27_LOW:
            on = True
            events.append((m, "on", level))
        elif on and level >= R27_HIGH:
            on = False
            events.append((m, "off", level))
        draw = [r for a, b, r in R27_DRAW if a <= m < b][0]
        level += (R27_PUMP if on else 0) - draw
        on_minutes += on
    return level, on_minutes, events


def solve_r27():
    level, on_minutes, _ = trace_r27()
    return "%d,%d" % (level, on_minutes)


R28_USE = (1340, 870, 610, 1515)
R28_DAYS = (90, 91, 92, 92)
R28_EXPORT = (120, 900, 1100, 200)


def trace_r28():
    carry, total, prev_use, rows = 0, 0, None, []
    for use, days, exp in zip(R28_USE, R28_DAYS, R28_EXPORT):
        energy = 21 * min(use, 400) + 17 * min(max(use - 400, 0), 600) + 26 * max(use - 1000, 0)
        standing = 43 * days
        avail = carry + 9 * exp
        used = min(avail, energy // 2)
        carry = avail - used
        sub = energy + standing - used
        levy = sub * 5 // 100
        bill = sub + levy
        if prev_use is not None and use < prev_use:
            bill -= 250
        rows.append((energy, standing, avail, used, carry, sub, levy, bill))
        total += bill
        prev_use = use
    return total, rows


def solve_r28():
    return str(trace_r28()[0])


# reaches: (km, km/h); locks: (first cycle start, minutes between cycle starts), minutes after 07:00
R29_REACHES = ((6, 8), (4, 6), (9, 12), (5, 10), (7, 6))
R29_LOCKS = ((0, 20), (10, 35), (5, 25), (15, 30))
R29_DEPART, R29_LOCK_MIN, R29_REST_AFTER, R29_REST = 10, 12, 80, 15
R29_CLOSED = (280, 325)  # no cycle may start at a time t with 280 <= t < 325


def trace_r29():
    t, engine, log = R29_DEPART, 0, []
    for i, (km, speed) in enumerate(R29_REACHES):
        mins = 60 * km // speed
        assert 60 * km % speed == 0
        t += mins
        engine += mins
        log.append(("reach %d end" % (i + 1), t, engine))
        if i == len(R29_REACHES) - 1:
            break
        if engine >= R29_REST_AFTER:
            t += R29_REST
            engine = 0
            log.append(("rested", t, engine))
        first, every = R29_LOCKS[i]
        c = first
        while c < t or R29_CLOSED[0] <= c < R29_CLOSED[1]:
            c += every
        t = c + R29_LOCK_MIN
        log.append(("lock %d out" % (i + 1), t, c))
    return t, log


def solve_r29():
    t, _ = trace_r29()
    t += 7 * 60
    return "%02d%02d" % (t // 60, t % 60)


R30_LOAN = 4800


def trace_r30():
    bal, month, rows = R30_LOAN, 0, []
    while True:
        month += 1
        interest = bal * (2 if bal >= 3000 else 1) // 100
        bal += interest
        due = 200 if month % 4 == 0 else 450
        pay = min(due, bal)
        bal -= pay
        if bal > 0 and month % 6 == 0:
            bal += 25
        rows.append((month, interest, pay, bal))
        if bal == 0:
            return month, pay, rows
        assert month < 200


def solve_r30():
    month, pay, _ = trace_r30()
    return "%d,%d" % (month, pay)


RP6_FLOUR0, RP6_EGGS0 = 26, 45
RP6_FLOUR_IN = (0, 30, 0, 20, 0, 36, 0)   # kg delivered each morning, days 1..7
RP6_EGGS_IN = (40, 40, 20, 20, 40, 60, 80)
RP6_OVEN = (5, 5, 5, 5, 5, 7, 3)          # most batches the oven can take that day
RP6_DEMAND = (53, 77, 20, 20, 35, 59, 26)
RP6_FLOUR_PER, RP6_EGGS_PER, RP6_LOAVES_PER = 4, 10, 12


def trace_rp6():
    flour, eggs, old, sold_total, dumped, rows = RP6_FLOUR0, RP6_EGGS0, 0, 0, 0, []
    for d in range(7):
        flour += RP6_FLOUR_IN[d]
        eggs += RP6_EGGS_IN[d]
        batches = min(flour // RP6_FLOUR_PER, eggs // RP6_EGGS_PER, RP6_OVEN[d])
        flour -= batches * RP6_FLOUR_PER
        eggs -= batches * RP6_EGGS_PER
        fresh = batches * RP6_LOAVES_PER
        demand = RP6_DEMAND[d]
        s_old = min(old, demand)          # yesterday's loaves are sold first
        s_new = min(fresh, demand - s_old)
        dumped += old - s_old             # unsold day-old loaves are thrown away
        sold_total += s_old + s_new
        old = fresh - s_new
        rows.append((d + 1, batches, flour, eggs, s_old, s_new, old, dumped))
    return sold_total, dumped, rows


def solve_rp6():
    sold, dumped, rows = trace_rp6()
    return "%d,%d,%d" % (sold, dumped, rows[-1][3])


# --------------------------------------------------------------------------
# Text fragments that must appear verbatim in the prompts (data <-> prompt)
# --------------------------------------------------------------------------
def _numbered(texts):
    return ["%d. %s" % (i + 1, t) for i, t in enumerate(texts)]


def _spoken(names, stmts):
    out = []
    for n in names:
        mine = [st[1] for st in stmts if st[0] == n]
        out.append("%s: %s" % (n, " ".join('(%d) "%s"' % (i + 1, t) for i, t in enumerate(mine))))
    return out


def _prereq(pre):
    return "none" if not pre else " and ".join(pre)


def fragments(iid):
    if iid == "R01":
        return ["Rule %d: %s becomes %s" % (i + 1, a, b) for i, (a, b) in enumerate(R01_RULES)] + [
            "The starting string is %s." % R01_START]
    if iid == "R02":
        return ["A = %(A)d, B = %(B)d, C = %(C)d, D = %(D)d and E = %(E)d" % R02_INIT,
                "If D is divisible by %d, jump to line 12." % R02_MOD]
    if iid == "R03":
        return [", ".join(str(c) for c in R03_DECK) + "."]
    if iid == "R04":
        return [", ".join(str(c) for c in R04_ROLLS) + "."]
    if iid == "R05":
        return [" ".join(R05_START) + "."]
    if iid == "RP1":
        return [", ".join(str(c) for c in RP1_QUEUE) + "."]
    if iid == "R09":
        return [", ".join("%s-%s" % (e[0], e[1]) for e in R09_EDGES)]
    if iid == "R10":
        return [", ".join("(%d, %d)" % b for b in R10_BLOCKED)]
    if iid == "RP2":
        return [" and ".join("(row %d, column %d)" % b for b in RP2_REMOVED)]
    if iid in ("R11", "R12", "R13", "R14", "R15", "RP3"):
        return _numbered([t for t, _ in globals()[iid + "_CLUES"]])
    if iid == "R16":
        return ["%s to %s: first %d, every %d, takes %d" % f for f in R16_FERRIES]
    if iid == "R17":
        return ["; ".join("%s-%s %d" % r for r in R17_ROADS) + ".",
                "Only depots %s and %s have chargers" % (", ".join(R17_CHARGERS[:-1]), R17_CHARGERS[-1]),
                "exactly %d km" % R17_RANGE]
    if iid == "R18":
        return ["; ".join("%s-%s %d" % r for r in R18_ROADS) + "."]
    if iid == "R19":
        return ["; ".join("%s-%s %d" % r for r in R19_LINKS) + "."]
    if iid == "R20":
        return ["%s: %d days, %d workers, prerequisites %s" % (k, v[0], v[1], _prereq(v[2]))
                for k, v in sorted(R20_TASKS.items())]
    if iid == "RP4":
        return ["%s: %d hours, prerequisites %s%s" % (k, v[0], _prereq(v[1]), ", kiln" if v[2] else "")
                for k, v in sorted(RP4_JOBS.items())]
    if iid == "R21":
        return _spoken(R21_NAMES, R21_STATEMENTS)
    if iid == "R22":
        return _spoken(R22_NAMES, R22_STATEMENTS)
    if iid == "R23":
        return _numbered([t for t, _ in R23_STATEMENTS])
    if iid == "R24":
        return _spoken(R24_NAMES, R24_STATEMENTS)
    if iid == "R25":
        return ['%s: "%s"' % (st[0], st[1]) for st in R25_STATEMENTS]
    if iid == "RP5":
        return _spoken(RP5_NAMES, RP5_STATEMENTS)
    if iid == "R27":
        return ["%d litres" % R27_START_LEVEL]
    if iid == "RP6":
        return [", ".join(map(str, RP6_FLOUR_IN)), ", ".join(map(str, RP6_EGGS_IN)), ", ".join(map(str, RP6_DEMAND))]
    return []


# --------------------------------------------------------------------------
SOLVERS = {
    "R01": solve_r01, "R02": solve_r02, "R03": solve_r03, "R04": solve_r04, "R05": solve_r05,
    "R06": solve_r06, "R07": solve_r07, "R08": solve_r08, "R09": solve_r09, "R10": solve_r10,
    "R11": solve_r11, "R12": solve_r12, "R13": solve_r13, "R14": solve_r14, "R15": solve_r15,
    "R16": solve_r16, "R17": solve_r17, "R18": solve_r18, "R19": solve_r19, "R20": solve_r20,
    "R21": solve_r21, "R22": solve_r22, "R23": solve_r23, "R24": solve_r24, "R25": solve_r25,
    "R26": solve_r26, "R27": solve_r27, "R28": solve_r28, "R29": solve_r29, "R30": solve_r30,
    "RP1": solve_rp1, "RP2": solve_rp2, "RP3": solve_rp3, "RP4": solve_rp4, "RP5": solve_rp5,
    "RP6": solve_rp6,
}

# Items whose answer is "the one consistent solution": the full solution set
# (over the whole hidden state, not just the part asked for) must have exactly
# one member.
UNIQUE = {
    "R11": _all_r11, "R12": _all_r12, "R13": _all_r13, "R14": _all_r14, "R15": _all_r15,
    "R21": _all_r21, "R22": _all_r22, "R23": _all_r23, "R24": _all_r24, "R25": _all_r25,
    "RP3": _all_rp3, "RP5": _all_rp5,
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

    expected_ids = ["R%02d" % i for i in range(1, 31)] + ["RP%d" % i for i in range(1, 7)]
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
        assert prompt.count("ANSWER:") == 1, iid
        words = len(prompt.split())
        assert 60 <= words <= 350, "%s has %d words" % (iid, words)
        for frag in fragments(iid):
            assert frag in prompt, "%s: prompt lacks %r" % (iid, frag)
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
