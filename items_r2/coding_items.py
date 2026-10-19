"""Bonsai-2 coding items, ROUND 2: 30 test tasks (C01..C30) + 6 calibration tasks (CP1..CP6).

Fresh, never-published tasks written for a pre-registered local-LLM comparison.
Round 1 was too easy (the 4-bit model passed 95%); these are deliberately harder:
deeper specifications, real algorithmic demand, exact error behaviour and, for
some items, input sizes on which a naive approach exceeds the 10-second limit.

Each item: id, kind, difficulty, entry_point, prompt, reference, tests, wrong.
  - prompt     : full task statement shown to the model
  - reference  : complete solution (verified to pass `tests`)
  - tests      : plain asserts, exec'd in the namespace the solution defined
  - wrong      : plausible-but-wrong solution that `tests` must reject
Run `python coding_items.py` to self-check (prints "OK 36/36").
Stdlib only. The module imports on Python 3.9+; references/tests target 3.12.
"""

_TAIL = "\n\nReply with one Python code block containing the complete solution. Standard library only.\n"

# Helper prepended to test sources that check for exceptions.
_RAISES = '''
def _raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    except Exception:
        return False
    return False
'''


def _mut(src, old, new):
    """Build a 'wrong' solution by editing one fragment of a reference."""
    if src.count(old) != 1:
        raise AssertionError("mutation target must occur exactly once: %r" % (old,))
    return src.replace(old, new)


ITEMS = []

# ---------------------------------------------------------------------------
# Kind 1: parsing / evaluating invented mini-languages (C01-C06)
# ---------------------------------------------------------------------------

_REF_C01 = r'''
def eval_tally(src, env):
    digits = "0123456789"
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
    toks = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == " ":
            i += 1
        elif c in digits:
            j = i
            while j < n and src[j] in digits:
                j += 1
            toks.append(("num", src[i:j], i))
            i = j
        elif c in letters:
            j = i
            while j < n and (src[j] in letters or src[j] in digits):
                j += 1
            toks.append(("name", src[i:j], i))
            i = j
        elif src[i:i + 2] in ("<=", ">=", "==", "!="):
            toks.append(("op", src[i:i + 2], i))
            i += 2
        elif c in "+-*/%^()<>?:!&|":
            toks.append(("op", c, i))
            i += 1
        else:
            toks.append(("bad", c, i))
            i += 1
    toks.append(("end", "", n))
    pos = [0]

    def isop(*ops):
        t = toks[pos[0]]
        return t[0] == "op" and t[1] in ops

    def adv():
        t = toks[pos[0]]
        pos[0] += 1
        return t

    def fail():
        raise ValueError("syntax", toks[pos[0]][2])

    def expr():
        c = or_()
        if isop("?"):
            adv()
            a = expr()
            if not isop(":"):
                fail()
            adv()
            b = expr()
            return ("?", c, a, b)
        return c

    def or_():
        left = and_()
        while isop("|"):
            adv()
            left = ("|", left, and_())
        return left

    def and_():
        left = cmp_()
        while isop("&"):
            adv()
            left = ("&", left, cmp_())
        return left

    def cmp_():
        left = add()
        if isop("<", "<=", ">", ">=", "==", "!="):
            op = adv()
            left = ("bin", op[1], op[2], left, add())
        return left

    def add():
        left = mul()
        while isop("+", "-"):
            op = adv()
            left = ("bin", op[1], op[2], left, mul())
        return left

    def mul():
        left = unary()
        while isop("*", "/", "%"):
            op = adv()
            left = ("bin", op[1], op[2], left, unary())
        return left

    def unary():
        if isop("-", "!"):
            op = adv()
            return ("un", op[1], unary())
        return power()

    def power():
        base = atom()
        if isop("^"):
            op = adv()
            return ("bin", "^", op[2], base, unary())
        return base

    def atom():
        t = toks[pos[0]]
        if t[0] == "num":
            adv()
            return ("num", int(t[1]))
        if t[0] == "name":
            adv()
            return ("name", t[1], t[2])
        if isop("("):
            adv()
            e = expr()
            if not isop(")"):
                fail()
            adv()
            return e
        fail()

    tree = expr()
    if toks[pos[0]][0] != "end":
        fail()

    def ev(node):
        kind = node[0]
        if kind == "num":
            return node[1]
        if kind == "name":
            if node[1] not in env:
                raise ValueError("name", node[2])
            return env[node[1]]
        if kind == "?":
            return ev(node[2]) if ev(node[1]) != 0 else ev(node[3])
        if kind == "|":
            if ev(node[1]) != 0:
                return 1
            return 1 if ev(node[2]) != 0 else 0
        if kind == "&":
            if ev(node[1]) == 0:
                return 0
            return 1 if ev(node[2]) != 0 else 0
        if kind == "un":
            v = ev(node[2])
            return -v if node[1] == "-" else (1 if v == 0 else 0)
        op, at = node[1], node[2]
        a = ev(node[3])
        b = ev(node[4])
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op in "/%":
            if b == 0:
                raise ValueError("div", at)
            q = abs(a) // abs(b)
            if (a < 0) != (b < 0):
                q = -q
            return q if op == "/" else a - b * q
        if op == "^":
            if b < 0:
                raise ValueError("exp", at)
            return a ** b
        return int({"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b,
                    "==": a == b, "!=": a != b}[op])

    return ev(tree)
'''

ITEMS.append({
    "id": "C01",
    "kind": "parsing",
    "difficulty": "very hard",
    "entry_point": "eval_tally",
    "prompt": r"""Write a Python function `eval_tally(src: str, env: dict) -> int` that evaluates an expression of the "Tally" language. All values are integers (arbitrary size). `env` maps variable names to integers.

Tokens: integer literals (one or more digits 0-9); names (a letter or `_`, then letters, digits or `_`); the operators `+ - * / % ^ ( ) < <= > >= == != ? : ! & |` (two-character operators are matched first). Space characters may separate tokens. Every other character (tabs, newlines, `=` alone, `$`, ...) is an illegal token one character long.

Grammar, from lowest to highest precedence:
1. `c ? a : b` - conditional. `c` is a level-2 expression; `a` and `b` are full expressions (so it nests to the right).
2. `|` - left-associative.
3. `&` - left-associative.
4. `< <= > >= == !=` - NOT associative: at most one comparison per level, so `1 < 2 < 3` is a syntax error (parentheses make `(1 < 2) < 3` legal).
5. `+ -` binary, left-associative.
6. `* / %` left-associative.
7. unary prefix `-` and `!` (may be repeated: `- - 3`, `!-x`).
8. `^` power: `atom ^ operand`, where the right operand is a level-7 expression. So `2^3^2` is `2^(3^2)`, `-2^2` is `-(2^2)`, and `2^-1` parses.
9. atoms: literal, name, `( expression )`.

Evaluation:
- `/` divides and truncates toward zero (`-7 / 2` is `-3`); `a % b` is `a - b * (a / b)` with that same division. A zero right operand is the error `"div"`.
- `^` with a negative exponent is the error `"exp"`; `0^0` is 1.
- Comparisons give 1 or 0. `!x` is 1 if x is 0, else 0.
- `a & b` is 0 if a is 0 (b is then NOT evaluated), otherwise 1 if b is non-zero else 0. `a | b` is 1 if a is non-zero (b NOT evaluated), otherwise 1 if b is non-zero else 0. The result is always 0 or 1.
- `c ? a : b` evaluates c, then only one of a, b (a if c is non-zero).
- A name that is evaluated but missing from `env` is the error `"name"`. Names in parts that are never evaluated cause no error.
- Otherwise operands are evaluated left to right, and the first error encountered is the one reported.

Errors: always `raise ValueError(kind, pos)` - two arguments, so `exc.args == (kind, pos)`.
- `"syntax"`: the text is not a valid expression. `pos` is the index in `src` of the first character of the first token that cannot continue a valid expression when reading left to right; if the text ends too early, `pos` is `len(src)`. An illegal token counts as a token that fits nowhere. The whole text is checked for syntax before anything is evaluated, so a syntax error wins over any evaluation error.
- `"div"`, `"exp"`: `pos` is the index of the operator. `"name"`: `pos` is the index of the name's first character.

Examples:
- `eval_tally("1 + 2 * 3", {})` returns 7; `eval_tally("a > 3 ? a * 2 : b", {"a": 5})` returns 10.
- `eval_tally("0 & 1/0", {})` returns 0.
- `eval_tally("1 + * 2 $", {})` raises `ValueError("syntax", 4)`; `eval_tally("4 / (2 - 2)", {})` raises `ValueError("div", 2)`.""" + _TAIL,
    "reference": _REF_C01,
    "tests": r'''
def _err(src, env=None):
    try:
        eval_tally(src, env or {})
    except ValueError as e:
        return e.args
    return None

assert eval_tally("1 + 2 * 3", {}) == 7 and eval_tally("1 - 2 - 3", {}) == -4 and eval_tally("100 / 7 / 2", {}) == 7
assert eval_tally("-2^2", {}) == -4 and eval_tally("2^3^2", {}) == 512 and eval_tally("(-2)^2", {}) == 4
assert eval_tally("-3 ^ 2 * 2", {}) == -18 and eval_tally("2 ^ !0", {}) == 2 and eval_tally("0^0", {}) == 1
assert [eval_tally(s, {}) for s in ("7 / -2", "-7 / 2", "-7 % 3", "7 % -3", "-8 / 2")] == [-3, -3, -1, 1, -4]
assert eval_tally("1 < 2 & 2 < 3", {}) == 1 and eval_tally("5 & 7", {}) == 1 and eval_tally("0 | 9", {}) == 1
assert eval_tally("!5", {}) == 0 and eval_tally("!0 + 1", {}) == 2 and eval_tally("- - 3", {}) == 3 and eval_tally("!-0", {}) == 1
assert eval_tally("a > 3 ? a * 2 : b", {"a": 5}) == 10 and eval_tally("a_1+B2", {"a_1": 2, "B2": 40}) == 42
assert eval_tally("0 & 1/0", {}) == 0 and eval_tally("1 | zz", {}) == 1 and eval_tally("0 ? 1/0 : 4", {}) == 4
assert eval_tally("1 ? 2 : 0 ? 3 : 4", {}) == 2 and eval_tally("0 ? 2 : 0 ? 3 : 4", {}) == 4
assert eval_tally("1 | 0 ? 5 : 6", {}) == 5 and eval_tally("2 + 3 == 5 & 1", {}) == 1 and eval_tally("(1 < 2) < 3", {}) == 1
assert eval_tally("1 ? 0 ? 7 : 8 : 9", {}) == 8 and eval_tally("3 * (2 + 4) % 5", {}) == 3
assert eval_tally("2^100 / 2^98", {}) == 4 and eval_tally("x*x - 1 == (x-1)*(x+1)", {"x": 10**20}) == 1
assert _err("1 +") == ("syntax", 3) and _err("") == ("syntax", 0) and _err("   ") == ("syntax", 3)
assert _err("1 < 2 < 3") == ("syntax", 6) and _err("(1 + 2") == ("syntax", 6) and _err("1 2") == ("syntax", 2)
assert _err("1 $ 2") == ("syntax", 2) and _err("1 + * 2 $") == ("syntax", 4) and _err("3 = 3") == ("syntax", 2)
assert _err("12ab") == ("syntax", 2) and _err("1 ! = 2") == ("syntax", 2) and _err("1 ? 2") == ("syntax", 5)
assert _err("1/0 + )") == ("syntax", 6) and _err("zz + (") == ("syntax", 6) and _err("1\t+ 2") == ("syntax", 1)
assert _err("4 / (2 - 2)") == ("div", 2) and _err("10 % 0") == ("div", 3) and _err("2 ^ -1") == ("exp", 2)
assert _err("x + 1/0") == ("name", 0) and _err("1/0 + x") == ("div", 1) and _err("1 & (2 ^ (0 - 1))") == ("exp", 7)
assert _err("0 | 1/0") == ("div", 5) and _err("1 ? yy : 1/0") == ("name", 4) and _err("()") == ("syntax", 1)
''',
    "wrong": _mut(_REF_C01, "            q = abs(a) // abs(b)\n            if (a < 0) != (b < 0):\n                q = -q\n", "            q = a // b\n"),
})


_REF_C02 = r'''
def reflow(src, width):
    # ---- parse ----
    stack = [[]]
    opens = []
    i, n = 0, len(src)
    special = '()[]";'
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
        elif c == ";":
            while i < n and src[i] != "\n":
                i += 1
        elif c in "([":
            opens.append(c)
            stack.append([])
            i += 1
        elif c in ")]":
            items = stack.pop()
            stack[-1].append(("list", opens.pop(), items))
            i += 1
        elif c == '"':
            j = i + 1
            while src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            stack[-1].append(("str", src[i:j + 1]))
            i = j + 1
        else:
            j = i
            while j < n and not src[j].isspace() and src[j] not in special:
                j += 1
            stack[-1].append(("atom", src[i:j]))
            i = j

    close = {"(": ")", "[": "]"}

    def flat(node):
        if node[0] != "list":
            return node[1]
        return node[1] + " ".join(flat(x) for x in node[2]) + close[node[1]]

    def render(node, col, trail):
        """Lines of the node; the first line has no indentation prefix."""
        if node[0] != "list":
            return [node[1]]
        f = flat(node)
        items = node[2]
        if not items or col + len(f) + trail <= width:
            return [f]
        op = node[1]
        last = len(items) - 1
        if op == "(" and items[0][0] == "atom" and len(items) >= 2:
            lines = [op + items[0][1]]
            ind = col + 2
            start = 1
        else:
            first = render(items[0], col + 1, trail + 1 if last == 0 else 0)
            lines = [op + first[0]] + first[1:]
            ind = col + 1
            start = 1
        for k in range(start, len(items)):
            sub = render(items[k], ind, trail + 1 if k == last else 0)
            lines.append(" " * ind + sub[0])
            lines.extend(sub[1:])
        lines[-1] += close[op]
        return lines

    out = []
    for form in stack[0]:
        out.extend(render(form, 0, 0))
    return "\n".join(out)
'''

ITEMS.append({
    "id": "C02",
    "kind": "parsing",
    "difficulty": "very hard",
    "entry_point": "reflow",
    "prompt": r"""Write a Python function `reflow(src: str, width: int) -> str` that parses text in the "Lath" notation and prints it back in a canonical layout that tries to keep lines within `width` columns.

Notation (the input is always well-formed: brackets balanced and correctly matched, strings terminated):
- A string starts with `"` and runs to the next `"` that is not escaped; inside a string a backslash escapes the following character (so `\"` and `\\` do not end it). Strings are kept verbatim, quotes and backslashes included. Anything may appear inside a string.
- Outside strings, `;` starts a comment that runs to the end of the line; comments are dropped.
- `(` ... `)` and `[` ... `]` are lists of zero or more items.
- An atom is a maximal run of characters that are not whitespace and not one of `( ) [ ] " ;`.
- Whitespace (including newlines) only separates items. `a(b)"c"d` is four items: atom, list, string, atom.
- The text is a sequence of zero or more top-level items.

Layout. Define the FLAT form of an item: an atom or string is its own text; a list is its opening bracket, the flat forms of its items joined by single spaces, and its closing bracket (`()` and `[]` when empty).

To render an item starting at column `col` (0-based) when `trail` closing brackets of enclosing lists will follow it on its last line:
1. An atom or string is always written as is, even if too long.
2. A list is written in flat form if it is empty or if `col + len(flat) + trail <= width`.
3. Otherwise it is BROKEN over several lines:
   - HEAD STYLE - used when the opening bracket is `(`, the first item is an atom, and the list has at least two items: the first line is `(` immediately followed by the first item; every other item starts on its own new line at column `col + 2`.
   - BLOCK STYLE - every other broken list: the first item is rendered directly after the opening bracket (so at column `col + 1`); every other item starts on its own new line at column `col + 1`.
   - The closing bracket is written directly after the list's last item, on that item's last line. So the last item is rendered with `trail + 1`; all other items are rendered with `trail` 0.
   Items are rendered recursively by these same rules at their own column.

Each top-level item is rendered at column 0 with `trail` 0; top-level items are joined with `"\n"`. Indentation uses spaces; there is never trailing whitespace and no final newline. No items gives `""`.

Examples:
- `reflow("(define (square x) (times x x))", 20)` returns

      (define
        (square x)
        (times x x))

- `reflow("(a (b (c d e f)))", 14)` returns `"(a\n  (b\n    (c\n      d\n      e\n      f)))"`: at column 4 the flat `(c d e f)` is 9 long and two closing brackets follow, 4 + 9 + 2 = 15 > 14. With `width` 15 the result is `"(a\n  (b\n    (c d e f)))"`.
- `reflow("[alpha beta gamma]", 10)` returns `"[alpha\n beta\n gamma]"`.""" + _TAIL,
    "reference": _REF_C02,
    "tests": r'''
assert reflow("(a b c)", 80) == "(a b c)"
assert reflow("  ( a   b\n c )  ", 80) == "(a b c)"
assert reflow("(define (square x) (times x x))", 20) == "(define\n  (square x)\n  (times x x))"
assert reflow("(a (b (c d e f)))", 14) == "(a\n  (b\n    (c\n      d\n      e\n      f)))"
assert reflow("(a (b (c d e f)))", 15) == "(a\n  (b\n    (c d e f)))"
assert reflow("(a (b (c d e f)))", 17) == "(a (b (c d e f)))" and reflow("(a (b (c d e f)))", 16) == "(a\n  (b (c d e f)))"
assert reflow("[alpha beta gamma]", 10) == "[alpha\n beta\n gamma]"
assert reflow('("x y" bb cc)', 8) == '("x y"\n bb\n cc)'
assert reflow("(abcdefghij)", 5) == "(abcdefghij)"
assert reflow("((a b c))", 6) == "((a\n   b\n   c))"
assert reflow("(let [x 1 y 2] (add x y))", 16) == "(let\n  [x 1 y 2]\n  (add x y))"
assert reflow("(let [x 1 y 2] (add x y))", 10) == "(let\n  [x\n   1\n   y\n   2]\n  (add\n    x\n    y))"
assert reflow('(say "a;b (c" ; note )\n more)', 80) == '(say "a;b (c" more)'
assert reflow('(q "a\\"b" z "\\\\")', 80) == '(q "a\\"b" z "\\\\")'
assert reflow("a (b c)\n[d]", 80) == "a\n(b c)\n[d]" and reflow("", 10) == "" and reflow("; only\n", 10) == ""
assert reflow("( ) [ ]", 1) == "()\n[]" and reflow("(f () [])", 4) == "(f\n  ()\n  [])"
assert reflow('a(b)"c"d', 80) == 'a\n(b)\n"c"\nd'
assert reflow("(aa bb)", 7) == "(aa bb)" and reflow("(aa bb)", 6) == "(aa\n  bb)"
assert reflow("[[[a b]]]", 8) == "[[[a\n   b]]]" and reflow("[[[a b]]]", 9) == "[[[a b]]]"
assert reflow("[(k v) (k2 [1 2 3])]", 12) == "[(k v)\n (k2\n   [1 2 3])]"
assert reflow("[(k v) (k2 [1 2 3])]", 11) == "[(k v)\n (k2\n   [1\n    2\n    3])]"
''',
    "wrong": _mut(_REF_C02, "        if not items or col + len(f) + trail <= width:", "        if not items or col + len(f) <= width:"),
})


_REF_C03 = r'''
import re

def match_route(pattern, path):
    if not pattern.startswith("/") or not path.startswith("/"):
        raise ValueError("must start with /")
    segs = []
    names = set()
    for raw in pattern[1:].split("/"):
        kind, name = "lit", raw
        if raw[:1] == ":":
            if raw.endswith("?"):
                kind, name = "opt", raw[1:-1]
            else:
                kind, name = "one", raw[1:]
        elif raw[:1] == "#":
            kind, name = "num", raw[1:]
        elif raw[:1] == "*":
            kind, name = "star", raw[1:]
        if kind != "lit":
            if not re.fullmatch(r"[A-Za-z0-9_]+", name) or name in names:
                raise ValueError("bad name")
            names.add(name)
        segs.append((kind, name))
    parts = path[1:].split("/")
    P, M = len(segs), len(parts)

    def single(kind, name, part):
        if kind == "lit":
            return part == name
        if kind == "num":
            return re.fullmatch(r"[0-9]+", part) is not None
        return part != ""

    ok = [[False] * (M + 1) for _ in range(P + 1)]
    ok[P][M] = True
    for i in range(P - 1, -1, -1):
        kind, name = segs[i]
        for j in range(M, -1, -1):
            if kind == "star":
                ok[i][j] = ok[i + 1][j] or (j < M and ok[i][j + 1])
            else:
                take = j < M and single(kind, name, parts[j]) and ok[i + 1][j + 1]
                ok[i][j] = take or (kind == "opt" and ok[i + 1][j])
    if not ok[0][0]:
        return None
    out = {}
    j = 0
    for i, (kind, name) in enumerate(segs):
        if kind == "lit":
            j += 1
        elif kind == "one":
            out[name] = parts[j]
            j += 1
        elif kind == "num":
            out[name] = int(parts[j])
            j += 1
        elif kind == "opt":
            if ok[i + 1][j]:
                out[name] = None
            else:
                out[name] = parts[j]
                j += 1
        else:
            k = j
            while not ok[i + 1][k]:
                k += 1
            out[name] = parts[j:k]
            j = k
    return out
'''

ITEMS.append({
    "id": "C03",
    "kind": "parsing",
    "difficulty": "very hard",
    "entry_point": "match_route",
    "prompt": r"""Write a Python function `match_route(pattern: str, path: str)` that matches a URL-like path against a route pattern and returns a dict of captured values, or `None` if the path does not match.

Both `pattern` and `path` must start with `/` (otherwise raise `ValueError`). Remove that first `/` and split the rest on `/` to get the list of segments. Segments may be empty: `"/"` is one empty segment, `"/a/"` is `["a", ""]`, `"/a//b"` is `["a", "", "b"]`.

Each pattern segment is one of:
- `:name` - matches exactly one path segment, which must be non-empty. Captures it as a `str`.
- `:name?` - matches either one non-empty path segment (captured as a `str`) or no path segment at all (captures `None`).
- `#name` - matches exactly one path segment consisting only of digits 0-9 (at least one). Captures it as an `int`.
- `*name` - matches any number of consecutive path segments, including none; the segments may be anything, even empty. Captures the `list` of matched segments.
- anything else is a literal: it matches exactly one path segment equal to it (the literal may be the empty string).

A `name` must be one or more characters from `A-Z a-z 0-9 _`, and no name may be used twice in a pattern. A pattern that breaks this (for example `/:`, `/:?`, `/*a-b`, `/:id/#id`) raises `ValueError` regardless of the path.

The pattern matches when its segments, in order, account for ALL path segments. The returned dict has one key per named pattern segment.

If there are several ways to match, pick this one: look at the flexible pattern segments (`:name?` and `*name`) in pattern order. The first one must match as FEW path segments as possible; given that, the second one as few as possible; and so on.

Patterns have up to 40 segments and paths up to 400 segments; your function must stay fast (well under a second) even for patterns with many `*name` segments on paths that only fail at the very end - plain backtracking is exponential there.

Examples:
- `match_route("/users/#id", "/users/42")` returns `{"id": 42}`; with path `"/users/4x"` it returns `None`.
- `match_route("/a/:x?/b", "/a/b")` returns `{"x": None}`.
- `match_route("/*a/x/*b", "/x/x/x")` returns `{"a": [], "b": ["x", "x"]}`.
- `match_route("/files/*rest", "/files/")` returns `{"rest": [""]}` and `match_route("/files/*rest", "/files")` returns `{"rest": []}`.""" + _TAIL,
    "reference": _REF_C03,
    "tests": _RAISES + r'''
assert match_route("/users/:id", "/users/42") == {"id": "42"}
assert match_route("/users/#id", "/users/42") == {"id": 42} and match_route("/users/#id", "/users/007") == {"id": 7}
assert match_route("/users/#id", "/users/4x") is None and match_route("/users/#id", "/users/") is None and match_route("/users/#id", "/users/-4") is None
assert match_route("/a/:x?/b", "/a/b") == {"x": None} and match_route("/a/:x?/b", "/a/q/b") == {"x": "q"}
assert match_route("/a/:x?/b", "/a/b/b") == {"x": "b"} and match_route("/a/:x?/b", "/a//b") is None
assert match_route("/:x?/:y?", "/a") == {"x": None, "y": "a"} and match_route("/:x?/:y?", "/a/b") == {"x": "a", "y": "b"}
assert match_route("/*a/*b", "/1/2") == {"a": [], "b": ["1", "2"]}
assert match_route("/*a/x/*b", "/x/x/x") == {"a": [], "b": ["x", "x"]} and match_route("/*a/x/*b", "/p/q") is None
assert match_route("/*a/:last", "/p/q/r") == {"a": ["p", "q"], "last": "r"} and match_route("/*a/:last", "/p/q/") is None
assert match_route("/files/*rest", "/files") == {"rest": []} and match_route("/files/*rest", "/files/") == {"rest": [""]}
assert match_route("/files/*rest", "/files//a/") == {"rest": ["", "a", ""]} and match_route("/a/:x", "/a/") is None
assert match_route("/", "/") == {} and match_route("/", "/a") is None and match_route("/a/", "/a/") == {} and match_route("/a/", "/a") is None
assert match_route("/:x?/#n", "/5") == {"x": None, "n": 5} and match_route("/:x?/#n", "/5/6") == {"x": "5", "n": 6}
assert match_route("/*a/:m?/*b", "/1/2") == {"a": [], "m": None, "b": ["1", "2"]}
assert match_route("/*a/:m/*b", "/1/2/3") == {"a": [], "m": "1", "b": ["2", "3"]}
assert match_route("/*a/#n/*b/#m", "/x/1/y/2/3") == {"a": ["x"], "n": 1, "b": ["y", "2"], "m": 3}
assert match_route("/*a/end", "/end/end") == {"a": ["end"]} and match_route("/:x?", "/") is None
assert match_route("/*a/:b?/:c", "//k") == {"a": [""], "b": None, "c": "k"}
assert _raises(ValueError, match_route, "/:a/:a", "/1/2") and _raises(ValueError, match_route, "/:", "/x") and _raises(ValueError, match_route, "/:?", "/x")
assert _raises(ValueError, match_route, "x/y", "/x/y") and _raises(ValueError, match_route, "/x", "x") and _raises(ValueError, match_route, "/*a-b", "/q")
assert _raises(ValueError, match_route, "/:id/lit/#id", "/nope")
_pat = "/" + "/x/".join("*s%d" % i for i in range(14)) + "/y"
_path = "/" + "/".join(["x"] * 120)
assert match_route(_pat, _path) is None
_got = match_route(_pat, _path + "/y")
assert _got["s0"] == [] and _got["s12"] == [] and _got["s13"] == ["x"] * 107 and len(_got) == 14
''',
    "wrong": _mut(_REF_C03, "            if ok[i + 1][j]:\n                out[name] = None\n            else:\n                out[name] = parts[j]\n                j += 1",
                  "            if j < M and parts[j] != \"\" and ok[i + 1][j + 1]:\n                out[name] = parts[j]\n                j += 1\n            else:\n                out[name] = None"),
})


_REF_C04 = r'''
def resolve_profiles(text):
    order = []
    parents = {}
    ops = {}
    cur = None
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            inner = line[1:-1]
            plist = []
            if "<" in inner:
                inner, _, rest = inner.partition("<")
                plist = [p.strip() for p in rest.split(",")]
            name = inner.strip()
            if not name or name in parents or any(not p for p in plist):
                raise ValueError("bad header")
            order.append(name)
            parents[name] = plist
            ops[name] = []
            cur = name
            continue
        if cur is None:
            raise ValueError("entry before header")
        if line.startswith("!"):
            key = line[1:].strip()
            if not key:
                raise ValueError("empty key")
            ops[cur].append(("del", key, None))
            continue
        eq = line.find("=")
        if eq < 0:
            raise ValueError("not an entry")
        op, kend = "set", eq
        if eq > 0 and line[eq - 1] in "+-":
            op = "add" if line[eq - 1] == "+" else "sub"
            kend = eq - 1
        key = line[:kend].strip()
        if not key:
            raise ValueError("empty key")
        val = line[eq + 1:].strip()
        if op != "set":
            val = [x.strip() for x in val.split(",") if x.strip()]
        ops[cur].append((op, key, val))

    raw_cache = {}
    active = set()

    def raw(name):
        if name in raw_cache:
            return raw_cache[name]
        if name not in parents or name in active:
            raise ValueError("unknown parent or cycle")
        active.add(name)
        cur_map = {}
        for p in parents[name]:
            for k, v in raw(p).items():
                cur_map[k] = list(v) if isinstance(v, list) else v
        for op, key, val in ops[name]:
            if op == "set":
                cur_map[key] = val
            elif op == "del":
                cur_map.pop(key, None)
            elif op == "add":
                old = cur_map.get(key, [])
                if isinstance(old, str):
                    old = [old]
                cur_map[key] = list(old) + val
            else:
                if key in cur_map:
                    if isinstance(cur_map[key], str):
                        raise ValueError("-= on a string")
                    cur_map[key] = [x for x in cur_map[key] if x not in val]
        active.discard(name)
        raw_cache[name] = cur_map
        return cur_map

    def finish(rawmap):
        done = {}
        busy = set()

        def expand(s):
            out = []
            i = 0
            while i < len(s):
                if s[i] != "$":
                    out.append(s[i])
                    i += 1
                elif s[i + 1:i + 2] == "$":
                    out.append("$")
                    i += 2
                elif s[i + 1:i + 2] == "{":
                    j = s.find("}", i + 2)
                    if j < 0:
                        raise ValueError("unterminated reference")
                    v = final(s[i + 2:j])
                    out.append(",".join(v) if isinstance(v, list) else v)
                    i = j + 1
                else:
                    raise ValueError("stray $")
            return "".join(out)

        def final(key):
            if key in done:
                return done[key]
            if key not in rawmap or key in busy:
                raise ValueError("missing key or reference cycle")
            busy.add(key)
            v = rawmap[key]
            res = [expand(x) for x in v] if isinstance(v, list) else expand(v)
            busy.discard(key)
            done[key] = res
            return res

        return {k: final(k) for k in rawmap}

    return {name: finish(raw(name)) for name in order}
'''

ITEMS.append({
    "id": "C04",
    "kind": "parsing",
    "difficulty": "very hard",
    "entry_point": "resolve_profiles",
    "prompt": r"""Write a Python function `resolve_profiles(text: str) -> dict` that reads a configuration with profile inheritance and returns `{profile_name: {key: value}}` for every profile, where each value is a `str` or a `list` of `str`.

Lines are separated by `"\n"`; strip each line; ignore empty lines and lines that start with `#`.

Header: a line that starts with `[` and ends with `]`. Inside is `name` or `name < parent1, parent2, ...` (split at the first `<`; parents split on commas; everything stripped). An empty name, an empty parent name, or a second header with an already used name raises `ValueError`. Any other line belongs to the most recent header; such a line before the first header raises `ValueError`.

Operation lines (kept in order per profile):
- `!key` (line starts with `!`; the key is the rest, stripped, and must be non-empty, else `ValueError`): delete the key; no error if absent.
- Otherwise find the FIRST `=` (none: `ValueError`). If the character just before it is `+` or `-`, the operator is `+=` or `-=` and the key is the text before that character; else the operator is `=`. The key is stripped and must be non-empty (else `ValueError`). The value is the stripped text after that `=`.
- `key = value`: set the key to that string (may be empty).
- `key += a, b`: split the value on commas, strip the pieces, drop empty pieces, and append them to the key's list. If the key currently holds a string, it first becomes a one-item list holding that string; if the key is absent it starts as an empty list.
- `key -= a, b`: remove every occurrence of each listed piece from the key's list. Absent key: nothing happens. Key holds a string: `ValueError`.

Inheritance. A profile's raw map is built by starting empty, overlaying the raw maps of its parents in the listed order (a later parent's value for a key replaces an earlier one's completely), then applying the profile's own operations in order. Parents may be defined anywhere in the text. An unknown parent or an inheritance cycle (including a profile naming itself) raises `ValueError`. Changing an inherited list must not change the parent's result.

Interpolation happens last, separately for each profile, on its finished raw map; all `+=`/`-=` work is done on the raw, un-interpolated text. In every string value and every list item, scanning left to right:
- `$$` becomes `$`;
- `${key}` becomes the interpolated value of `key` IN THE PROFILE BEING RESOLVED (not the profile where the line was written); a list value is inserted as its interpolated items joined with `,`. The key is used exactly as written. Inserted text is not scanned again.
- a `$` followed by anything else (or at the end), a `${` without a closing `}`, a reference to a key the profile does not have, or a chain of references that leads back to itself raises `ValueError`.

All profiles are resolved, so an error in any profile raises. The result lists every profile (key order inside the dicts does not matter).

Example:

    [base]
    host = localhost
    url = http://${host}/api
    tags += a, b
    [prod < base]
    host = example.org
    tags -= a
    tags += c

returns `{"base": {"host": "localhost", "url": "http://localhost/api", "tags": ["a", "b"]}, "prod": {"host": "example.org", "url": "http://example.org/api", "tags": ["b", "c"]}}`.""" + _TAIL,
    "reference": _REF_C04,
    "tests": _RAISES + r'''
_t1 = "# base profile\n[base]\nhost = localhost\nurl = http://${host}/api\ntags += a, b\n\n[prod < base]\nhost = example.org\ntags -= a\ntags += c\n"
assert resolve_profiles(_t1) == {"base": {"host": "localhost", "url": "http://localhost/api", "tags": ["a", "b"]}, "prod": {"host": "example.org", "url": "http://example.org/api", "tags": ["b", "c"]}}
assert resolve_profiles("") == {} and resolve_profiles("[only]\n") == {"only": {}}
assert resolve_profiles("[c < a, b]\nz = 1\n[a]\nx = A\ny = A\n[b]\ny = B\n") == {"c": {"x": "A", "y": "B", "z": "1"}, "a": {"x": "A", "y": "A"}, "b": {"y": "B"}}
assert resolve_profiles("[a]\nk = 1\nm = 2\n[b < a]\n!k\n! nope\n") == {"a": {"k": "1", "m": "2"}, "b": {"m": "2"}}
assert resolve_profiles("[a]\nk = one\nk += two, , three\nj +=\ni -= x\n") == {"a": {"k": ["one", "two", "three"], "j": []}}
assert resolve_profiles("[a]\nk += x\nk = y\ne =\nq = a=b\nw = a # b\n") == {"a": {"k": "y", "e": "", "q": "a=b", "w": "a # b"}}
assert resolve_profiles("[a]\nl += x, y\ns = <${l}>\nh = H\nm += ${h}1, b\n")["a"] == {"l": ["x", "y"], "s": "<x,y>", "h": "H", "m": ["H1", "b"]}
assert resolve_profiles("[a]\nc = p,q\nl += ${c}, z\n")["a"]["l"] == ["p,q", "z"]
assert resolve_profiles("[a]\np = cost $$5 ${q}{x}\nq = $$\nr = ${q}{p}\n")["a"] == {"p": "cost $5 ${x}", "q": "$", "r": "${p}"}
assert resolve_profiles("[a]\nl += x, y, x, ${h}\nh = x\nl -= x\n")["a"]["l"] == ["y", "x"]
_t2 = "[top]\nl += 1\n[left < top]\nl += 2\n[right < top]\nl += 3\nv = R\n[bot < left, right]\nl += 4\n"
assert resolve_profiles(_t2) == {"top": {"l": ["1"]}, "left": {"l": ["1", "2"]}, "right": {"l": ["1", "3"], "v": "R"}, "bot": {"l": ["1", "3", "4"], "v": "R"}}
assert resolve_profiles("[ p2 < p1 , p0 ]\n[p0]\na = ${b}\nb = 0\n[p1]\nb = 1\n")["p2"] == {"a": "0", "b": "0"}
assert resolve_profiles("[a]\nx = ${y}${y}\ny = ${z}!\nz = Z\n[b < a]\nz += 1, 2\n")["b"] == {"x": "Z,1,2!Z,1,2!", "y": "Z,1,2!", "z": ["Z", "1", "2"]}
assert resolve_profiles("[a]\nk -= 1\nk += 1, 2, 1\n[b < a]\nk -= 1, 2\n") == {"a": {"k": ["1", "2", "1"]}, "b": {"k": []}}
assert _raises(ValueError, resolve_profiles, "[a]\nu = ${h}\nh = 1\n[b < a]\n!h\n")
assert _raises(ValueError, resolve_profiles, "[a]\nx = ${y}\ny = ${x}\n") and _raises(ValueError, resolve_profiles, "[a]\nx = a${x}\n")
assert _raises(ValueError, resolve_profiles, "[a]\nx = $y\n") and _raises(ValueError, resolve_profiles, "[a]\nx = ${y\ny = 1\n") and _raises(ValueError, resolve_profiles, "[a]\nx = 5$\n")
assert _raises(ValueError, resolve_profiles, "[a < zz]\n") and _raises(ValueError, resolve_profiles, "[a < b]\n[b < c]\n[c < a]\n") and _raises(ValueError, resolve_profiles, "[a < a]\n")
assert _raises(ValueError, resolve_profiles, "[a]\n[b]\n[a]\n") and _raises(ValueError, resolve_profiles, "k = 1\n[a]\n") and _raises(ValueError, resolve_profiles, "[a]\njust words\n")
assert _raises(ValueError, resolve_profiles, "[a]\n= 3\n") and _raises(ValueError, resolve_profiles, "[ ]\n") and _raises(ValueError, resolve_profiles, "[a < b, ]\n[b]\n")
assert _raises(ValueError, resolve_profiles, "[a]\nk = s\n[b < a]\nk -= s\n") and _raises(ValueError, resolve_profiles, "[a]\n!\n") and _raises(ValueError, resolve_profiles, "[a]\n += 3\n")
''',
    "wrong": _mut(_REF_C04, "                cur_map[key] = [x for x in cur_map[key] if x not in val]",
                  "                lst = list(cur_map[key])\n                for x in val:\n                    if x in lst:\n                        lst.remove(x)\n                cur_map[key] = lst"),
})


_REF_C05 = r'''
import re

def run_script(source, max_steps):
    name_re = re.compile(r"[a-z]+")
    num_re = re.compile(r"-?[0-9]+")
    ops = ("+", "-", "*", "/", "%", "<", ">", "=")

    def parse_expr(toks):
        if len(toks) % 2 == 0:
            raise ValueError("bad expression")
        out = []
        for i, tk in enumerate(toks):
            if i % 2 == 1:
                if tk not in ops:
                    raise ValueError("bad operator")
                out.append(tk)
            elif num_re.fullmatch(tk):
                out.append(int(tk))
            elif name_re.fullmatch(tk):
                out.append(tk)
            else:
                raise ValueError("bad operand")
        return out

    program = []
    stack = [("top", None, program)]
    for raw in source.split("\n"):
        toks = raw.split()
        if not toks or toks[0].startswith("#"):
            continue
        kw = toks[0]
        block = stack[-1][2]
        if kw == "set":
            if len(toks) < 4 or not name_re.fullmatch(toks[1]) or toks[2] != "=":
                raise ValueError("bad set")
            block.append(["set", toks[1], parse_expr(toks[3:])])
        elif kw == "emit":
            block.append(["emit", parse_expr(toks[1:])])
        elif kw == "if":
            node = ["if", parse_expr(toks[1:]), [], []]
            block.append(node)
            stack.append(("if", node, node[2]))
        elif kw == "while":
            node = ["while", parse_expr(toks[1:]), []]
            block.append(node)
            stack.append(("while", node, node[2]))
        elif kw in ("else", "end", "break", "skip", "halt"):
            if len(toks) != 1:
                raise ValueError("extra tokens")
            if kw == "else":
                if stack[-1][0] != "if":
                    raise ValueError("else without if")
                node = stack.pop()[1]
                stack.append(("else", node, node[3]))
            elif kw == "end":
                if stack[-1][0] == "top":
                    raise ValueError("end without block")
                stack.pop()
            else:
                if kw != "halt" and not any(s[0] == "while" for s in stack):
                    raise ValueError(kw + " outside while")
                block.append([kw])
        else:
            raise ValueError("unknown statement")
    if len(stack) != 1:
        raise ValueError("unclosed block")

    class Stop(Exception):
        pass

    class Break(Exception):
        pass

    class Skip(Exception):
        pass

    env = {}
    out = []
    used = [0]

    def tick():
        if used[0] >= max_steps:
            raise Stop("limit")
        used[0] += 1

    def val(x):
        return x if isinstance(x, int) else env.get(x, 0)

    def ev(expr):
        acc = val(expr[0])
        for i in range(1, len(expr), 2):
            op, b = expr[i], val(expr[i + 1])
            if op == "+":
                acc += b
            elif op == "-":
                acc -= b
            elif op == "*":
                acc *= b
            elif op in "/%":
                if b == 0:
                    raise Stop("error")
                acc = acc // b if op == "/" else acc % b
            elif op == "<":
                acc = int(acc < b)
            elif op == ">":
                acc = int(acc > b)
            else:
                acc = int(acc == b)
        return acc

    def run(block):
        for st in block:
            tick()
            kind = st[0]
            if kind == "set":
                env[st[1]] = ev(st[2])
            elif kind == "emit":
                out.append(ev(st[1]))
            elif kind == "if":
                run(st[2] if ev(st[1]) != 0 else st[3])
            elif kind == "while":
                first = True
                while True:
                    if not first:
                        tick()
                    first = False
                    if ev(st[1]) == 0:
                        break
                    try:
                        run(st[2])
                    except Break:
                        break
                    except Skip:
                        continue
            elif kind == "break":
                raise Break()
            elif kind == "skip":
                raise Skip()
            else:
                raise Stop("halt")

    try:
        run(program)
    except Stop as stop:
        return out, stop.args[0]
    return out, "done"
'''

ITEMS.append({
    "id": "C05",
    "kind": "parsing",
    "difficulty": "very hard",
    "entry_point": "run_script",
    "prompt": r"""Write a Python function `run_script(source: str, max_steps: int) -> tuple[list[int], str]` that interprets a tiny language called "Ember" and returns `(emitted_values, status)`.

Lines are separated by `"\n"`. Each line is split into tokens on whitespace. Lines with no tokens and lines whose first token starts with `#` are ignored. The first token decides the statement:

- `set NAME = EXPR` - assign. NAME is one or more lowercase letters a-z; the third token must be `=`.
- `emit EXPR` - append the value to the output list.
- `if EXPR` ... `else` ... `end` - the `else` part is optional. The condition is true when non-zero.
- `while EXPR` ... `end` - loop while the condition is non-zero.
- `break` - leave the innermost enclosing `while`.
- `skip` - jump to the next condition check of the innermost enclosing `while`.
- `halt` - stop the program.
`else`, `end`, `break`, `skip`, `halt` must be the only token on their line.

EXPR is: operand, operator, operand, operator, ..., operand - at least one operand, every piece a separate token. An operand is an integer literal (optional `-` directly followed by digits, e.g. `-12`) or a variable NAME. Operators: `+ - * / % < > =`. There is NO precedence: an expression is evaluated strictly left to right (`2 + 3 * 4` is 20). `/` and `%` are floor division and modulo exactly like Python's `//` and `%`; `<`, `>`, `=` (equality) give 1 or 0. A variable that was never set has the value 0. Any word of lowercase letters is a valid variable name, even `end` or `set`.

Static checking. Before anything runs, the whole source is checked, and `ValueError` is raised for: an unknown first token; a malformed `set`; a malformed expression (empty, bad operand, bad operator, wrong alternation); extra tokens after `else`/`end`/`break`/`skip`/`halt`; `else` that does not belong directly to an open `if` without an `else` yet; `end` with no open block; a block still open at the end; `break` or `skip` that is not inside any `while` (being inside an `if` that is inside a `while` is fine). This applies even to lines that would never execute.

Steps. Each executed `set`, `emit`, `break`, `skip`, `halt`, and each evaluation of an `if` or `while` condition costs one step (`else` and `end` cost nothing). When something costing a step is about to execute and `max_steps` steps have already been used, the run stops with status `"limit"`. The limit is checked before anything else about that statement.

Status: `"done"` if the program ran off its end, `"halt"` after a `halt`, `"limit"` as above, `"error"` if a division or modulo by zero occurred (the run stops at once; the failing statement has no effect). The output list holds everything emitted before the stop.

Example:

    set n = 5
    set f = 1
    while n > 1
      set f = f * n
      set n = n - 1
    end
    emit f

uses exactly 16 steps: with `max_steps` 16 or more the result is `([120], "done")`, with 15 it is `([], "limit")`.""" + _TAIL,
    "reference": _REF_C05,
    "tests": _RAISES + r'''
_p1 = "set n = 5\nset f = 1\nwhile n > 1\n  set f = f * n\n  set n = n - 1\nend\nemit f\n"
assert run_script(_p1, 100) == ([120], "done") and run_script(_p1, 16) == ([120], "done") and run_script(_p1, 15) == ([], "limit")
assert run_script("emit 2 + 3 * 4\nemit 2 - 3 - -4\nemit 7 / 2 * 2\nemit -7 / 2\nemit -7 % 3\nemit 1 < 2 = 1\nemit q", 50) == ([20, 3, 6, -4, 2, 1, 0], "done")
_p3 = "set i = 0\nwhile 1\n  set i = i + 1\n  if i > 6\n    break\n  end\n  if i % 2\n    skip\n  end\n  emit i\nend\nemit 99"
assert run_script(_p3, 1000) == ([2, 4, 6, 99], "done")
_p4 = "set a = 0\nwhile a < 2\n set b = 0\n while 1\n  set b = b + 1\n  if b = 3\n   break\n  else\n   emit a * 10 + b\n  end\n end\n set a = a + 1\nend"
assert run_script(_p4, 1000) == ([1, 2, 11, 12], "done")
assert run_script("emit 1\nhalt\nemit 2", 10) == ([1], "halt")
assert run_script("emit 5\nset x = 3 / z\nemit 6", 10) == ([5], "error") and run_script("emit 4 % 0", 10) == ([], "error")
assert run_script("while 1\n emit 7\nend", 5) == ([7, 7], "limit") and run_script("while 1\n emit 7\nend", 6) == ([7, 7, 7], "limit")
assert run_script("", 0) == ([], "done") and run_script("halt", 0) == ([], "limit") and run_script("halt", 1) == ([], "halt")
assert run_script("emit 1 / 0", 0) == ([], "limit") and run_script("emit 1 / 0", 1) == ([], "error")
assert run_script("# c\n\n   \nif 0\nemit 1\nelse\nemit 2\nend\nif 0\nemit 3\nend\n  #x y z\nemit 4", 10) == ([2, 4], "done")
assert run_script("set i = 0\nwhile i < 3\nset i = i + 1\nskip\nemit 100\nend\nemit i", 100) == ([3], "done")
_p6 = "set i = 0\nwhile i < 3\nset i = i + 1\nskip\nend"
assert run_script(_p6, 11) == ([], "done") and run_script(_p6, 10) == ([], "limit")
assert run_script("while 1\nif 1\nbreak\nend\nend", 3) == ([], "done") and run_script("while 1\nif 1\nbreak\nend\nend", 2) == ([], "limit")
assert run_script("set end = 3\nset set = end + 1\nemit set * end", 9) == ([12], "done")
_p5 = "set i = 0\nwhile i < 3\n set i = i + 1\n set j = 0\n while j < 3\n  set j = j + 1\n  if j = 2\n   skip\n  end\n  if i = 2\n   break\n  end\n  emit i * 10 + j\n end\nend"
assert run_script(_p5, 1000) == ([11, 13, 31, 33], "done")
assert run_script("set x = 10\nwhile x\n set x = x - 3\n emit x\n if x < 0\n  halt\n end\nend\nemit 5", 1000) == ([7, 4, 1, -2], "halt")
assert run_script("set a = 1\nwhile a < 1000000\n set a = a * 2\nend\nemit a", 1000) == ([1048576], "done")
assert _raises(ValueError, run_script, "emit 1\nhalt\nend", 10) and _raises(ValueError, run_script, "break", 10) and _raises(ValueError, run_script, "if 1\nskip\nend", 10)
assert _raises(ValueError, run_script, "if 1\nelse\nelse\nend", 10) and _raises(ValueError, run_script, "while 1\nelse\nend", 0) and _raises(ValueError, run_script, "if 1", 10)
assert _raises(ValueError, run_script, "set x = 1 +", 10) and _raises(ValueError, run_script, "emit", 10) and _raises(ValueError, run_script, "x = 3", 10)
assert _raises(ValueError, run_script, "set X = 1", 10) and _raises(ValueError, run_script, "emit 1+2", 10) and _raises(ValueError, run_script, "halt now", 10)
assert _raises(ValueError, run_script, "set x 1", 10) and _raises(ValueError, run_script, "emit 1 ** 2", 10) and _raises(ValueError, run_script, "halt\nemit 1 +", 10)
assert _raises(ValueError, run_script, "emit 1 2", 10) and _raises(ValueError, run_script, "emit - 1", 10) and _raises(ValueError, run_script, "while 1\nif 1\nelse\nend\nend\nskip", 10)
''',
    "wrong": _mut(_REF_C05, "                    except Skip:\n                        continue", "                    except Skip:\n                        first = True\n                        continue"),
})


_REF_C06 = r'''
import re

def pluck(data, query):
    name_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    int_re = re.compile(r"-?[0-9]+")
    idx_re = re.compile(r"(-?[0-9]+)?(:)?(-?[0-9]+)?")
    n = len(query)

    def read_str(i):
        i += 1
        out = []
        while True:
            if i >= n:
                raise ValueError("unterminated string")
            ch = query[i]
            if ch == '"':
                return "".join(out), i + 1
            if ch == "\\":
                if query[i + 1:i + 2] not in ('"', "\\"):
                    raise ValueError("bad escape")
                out.append(query[i + 1])
                i += 2
            else:
                out.append(ch)
                i += 1

    def skip_sp(i):
        while i < n and query[i] == " ":
            i += 1
        return i

    steps = []
    i = 0
    while i < n:
        if query[i] == ".":
            kind = "key"
            i += 1
            if query[i:i + 1] == ".":
                kind = "deep"
                i += 1
            m = name_re.match(query, i)
            if not m:
                raise ValueError("name expected")
            steps.append((kind, m.group()))
            i = m.end()
        elif query[i] == "[":
            i += 1
            nxt = query[i:i + 1]
            if nxt == '"':
                key, i = read_str(i)
                steps.append(("key", key))
            elif nxt == "*":
                steps.append(("all",))
                i += 1
            elif nxt == "?":
                i = skip_sp(i + 1)
                m = name_re.match(query, i)
                if not m:
                    raise ValueError("name expected")
                i = skip_sp(m.end())
                if query[i:i + 2] in ("==", "!=", "<=", ">="):
                    op = query[i:i + 2]
                elif query[i:i + 1] in ("<", ">"):
                    op = query[i]
                else:
                    raise ValueError("operator expected")
                i = skip_sp(i + len(op))
                if query[i:i + 1] == '"':
                    lit, i = read_str(i)
                else:
                    m2 = int_re.match(query, i)
                    if not m2:
                        raise ValueError("literal expected")
                    lit = int(m2.group())
                    i = m2.end()
                i = skip_sp(i)
                steps.append(("filter", m.group(), op, lit))
            else:
                m = idx_re.match(query, i)
                a, colon, b = m.group(1), m.group(2), m.group(3)
                if colon is None:
                    if a is None or b is not None:
                        raise ValueError("bad index")
                    steps.append(("index", int(a)))
                else:
                    steps.append(("slice", None if a is None else int(a), None if b is None else int(b)))
                i = m.end()
            if query[i:i + 1] != "]":
                raise ValueError("] expected")
            i += 1
        else:
            raise ValueError("unexpected character")

    def deep(node, name, out):
        if isinstance(node, dict):
            if name in node:
                out.append(node[name])
            for v in node.values():
                deep(v, name, out)
        elif isinstance(node, list):
            for v in node:
                deep(v, name, out)

    def test(v, op, lit):
        if type(v) is not type(lit):
            return op == "!="
        return {"==": v == lit, "!=": v != lit, "<": v < lit, "<=": v <= lit,
                ">": v > lit, ">=": v >= lit}[op]

    nodes = [data]
    for st in steps:
        out = []
        for node in nodes:
            if st[0] == "key":
                if isinstance(node, dict) and st[1] in node:
                    out.append(node[st[1]])
            elif st[0] == "deep":
                deep(node, st[1], out)
            elif st[0] == "all":
                if isinstance(node, dict):
                    out.extend(node.values())
                elif isinstance(node, list):
                    out.extend(node)
            elif st[0] == "index":
                if isinstance(node, list) and -len(node) <= st[1] < len(node):
                    out.append(node[st[1]])
            elif st[0] == "slice":
                if isinstance(node, list):
                    out.extend(node[st[1]:st[2]])
            else:
                if isinstance(node, list):
                    for el in node:
                        if isinstance(el, dict) and st[1] in el and test(el[st[1]], st[2], st[3]):
                            out.append(el)
        nodes = out
    return nodes
'''

ITEMS.append({
    "id": "C06",
    "kind": "parsing",
    "difficulty": "very hard",
    "entry_point": "pluck",
    "prompt": r"""Write a Python function `pluck(data, query: str) -> list` that selects values from nested data with a small query language.

`data` is built only from `dict` (string keys), `list`, `int` and `str`. A query is a sequence of steps written one after another with nothing between them. Evaluation keeps a list of current nodes, initially `[data]`; each step is applied to every current node in order, and the results are concatenated in order to give the new list. The function returns the final list. The empty query returns `[data]`.

NAME means: a letter or `_` followed by letters, digits or `_`. INT means: an optional `-` followed by one or more digits.

Steps:
- `.NAME` - if the node is a dict that has this key: its value. Otherwise nothing.
- `["TEXT"]` - the same with an arbitrary key. Inside the quotes `\"` stands for `"` and `\\` for `\`; a backslash before anything else is an error.
- `[INT]` - if the node is a list and the index is in range (negative indices count from the end, as in Python): that element. Otherwise nothing.
- `[A:B]` - A and B are each an INT or omitted. If the node is a list: the elements of the Python slice `node[A:B]`. Otherwise nothing.
- `[*]` - all elements of a list, or all values of a dict in insertion order. A scalar gives nothing.
- `..NAME` - deep search. Visit the node itself and everything inside it in this order: visit a node; if it is a dict having the key NAME, output that key's value; then visit its children (dict values in insertion order, list elements in order) the same way. So a dict's own match comes before matches found deeper inside it, and a matched value is itself searched too.
- `[?NAME OP LITERAL]` - filter. If the node is a list: output those elements that are dicts having the key NAME whose value passes the test. Other nodes give nothing. OP is one of `==`, `!=`, `<`, `<=`, `>`, `>=`. LITERAL is an INT or a `"TEXT"` string as above. If the value and the literal are of different types (int vs str, or the value is a dict or list), the test is true for `!=` and false for every other operator. Space characters are allowed (optionally) after `?`, around OP and before `]` - and nowhere else in a query.

Any query that does not follow this syntax raises `ValueError`. The whole query is checked, so a syntax error raises even when earlier steps produce no nodes.

Example, with `d = {"shop": {"items": [{"t": "A", "p": 5}, {"t": "B", "p": 12}, {"t": "C"}], "p": 1}}`:
- `pluck(d, ".shop.items[?p < 10].t")` returns `["A"]`
- `pluck(d, "..p")` returns `[1, 5, 12]`
- `pluck(d, ".shop.items[-1].t")` returns `["C"]`, and `pluck(d, ".shop.items[*].p")` returns `[5, 12]`.""" + _TAIL,
    "reference": _REF_C06,
    "tests": _RAISES + r'''
_d = {"store": {"books": [{"t": "A", "p": 5, "tags": ["x", "y"]}, {"t": "B", "p": 12}, {"t": "C"}, "loose", {"t": "D", "p": "5"}], "p": 1, "a.b": {"p": 7}}, "n": [10, 20, 30, 40]}
assert pluck(_d, "") == [_d] and pluck(_d, ".n[0]") == [10] and pluck(_d, ".n[-1]") == [40] and pluck(_d, ".n[4]") == [] and pluck(_d, ".n[-5]") == []
assert pluck(_d, ".n[1:3]") == [20, 30] and pluck(_d, ".n[:2]") == [10, 20] and pluck(_d, ".n[-2:]") == [30, 40] and pluck(_d, ".n[:]") == [10, 20, 30, 40] and pluck(_d, ".n[3:1]") == []
assert pluck(_d, ".store.books[*].t") == ["A", "B", "C", "D"] and pluck(_d, ".n[*]") == [10, 20, 30, 40]
assert pluck(_d, ".store.books[?p < 10].t") == ["A"] and pluck(_d, ".store.books[?p>=5].t") == ["A", "B"]
assert pluck(_d, ".store.books[?p != 5].t") == ["B", "D"] and pluck(_d, '.store.books[?p == "5"].t') == ["D"]
assert pluck(_d, '.store.books[? t  >  "B" ].t') == ["C", "D"] and pluck(_d, ".store.books[?p > -1].t") == ["A", "B"]
assert pluck(_d, ".store.books[?tags != 0].t") == ["A"] and pluck(_d, ".store.books[?tags == 0].t") == []
assert pluck(_d, "..p") == [1, 5, 12, "5", 7]
assert pluck(_d, '.store["a.b"].p') == [7] and pluck(_d, '["n"][0]') == [10] and pluck(_d, "..tags[*]") == ["x", "y"] and pluck(_d, "..t") == ["A", "B", "C", "D"]
assert pluck(_d, ".store[*]") == [_d["store"]["books"], 1, {"p": 7}] and pluck(_d, ".store[*].p") == [7]
assert pluck(_d, ".n.x") == [] and pluck(_d, ".store[0]") == [] and pluck(_d, ".missing.deeper[2]") == [] and pluck(_d, ".n[?p == 1]") == [] and pluck(_d, ".store[?p == 7]") == []
_e = {"a": {"a": {"a": 1}}}
assert pluck(_e, "..a") == [{"a": {"a": 1}}, {"a": 1}, 1] and pluck(_e, "..a..a") == [{"a": 1}, 1, 1] and pluck(_e, "..a.a.a") == [1]
_f = {"l": [{"k": 'q"z'}, {"k": "\\"}, {"k": "]"}], 'we"ird': 3}
assert pluck(_f, '.l[?k == "q\\"z"]') == [{"k": 'q"z'}] and pluck(_f, '.l[?k == "\\\\"]') == [{"k": "\\"}] and pluck(_f, '["we\\"ird"]') == [3]
assert pluck(_f, '.l[?k == "]"]') == [{"k": "]"}] and pluck(_f, '.l[?k<"]"][*]') == ["\\"]
assert pluck([[1, 2], [3], "s", {"z": [4]}], "[*][*]") == [1, 2, 3, [4]] and pluck([[1, 2], [3]], "[*][0]") == [1, 3] and pluck([[1, 2], [3]], "[*][1:]") == [2]
assert pluck(5, "") == [5] and pluck(5, "..x") == [] and pluck({"_x1": {"y": 2}}, "._x1.y") == [2]
assert _raises(ValueError, pluck, _d, ".") and _raises(ValueError, pluck, _d, "n") and _raises(ValueError, pluck, _d, ".n[") and _raises(ValueError, pluck, _d, ".n[x]")
assert _raises(ValueError, pluck, _d, ".n[1:2:3]") and _raises(ValueError, pluck, _d, ".9a") and _raises(ValueError, pluck, _d, ".n[?p < ]") and _raises(ValueError, pluck, _d, ".n[?p = 5]")
assert _raises(ValueError, pluck, _d, ".n[ 1 ]") and _raises(ValueError, pluck, _d, '["abc]') and _raises(ValueError, pluck, _d, ".a b") and _raises(ValueError, pluck, _d, "..")
assert _raises(ValueError, pluck, {}, ".a.b[") and _raises(ValueError, pluck, _d, "..[0]") and _raises(ValueError, pluck, _d, '["a\\nb"]') and _raises(ValueError, pluck, _d, ".n[]")
assert _raises(ValueError, pluck, _d, ".n[1-2]") and _raises(ValueError, pluck, _d, ".n[*") and _raises(ValueError, pluck, _d, ".n[?p < 5") and _raises(ValueError, pluck, _d, ".n[1 :2]")
''',
    "wrong": _mut(_REF_C06, "            if name in node:\n                out.append(node[name])\n            for v in node.values():\n                deep(v, name, out)",
                  "            for v in node.values():\n                deep(v, name, out)\n            if name in node:\n                out.append(node[name])"),
})

# ---------------------------------------------------------------------------
# Kind 2: interval / calendar / scheduling (C07-C11)
# ---------------------------------------------------------------------------

# Deterministic pseudo-random stream used by tests that need large inputs.
_LCG = '''
def _lcg(seed):
    x = seed
    while True:
        x = (x * 6364136223846793005 + 1442695040888963407) % 18446744073709551616
        yield x >> 33
'''

_REF_C07 = r'''
import bisect

def grant_slots(requests, units):
    n = len(requests)
    res = [[] for _ in range(n)]
    events = []
    for i, (s, e, p) in enumerate(requests):
        events.append((s, 1, i))
        events.append((e, 0, i))
    events.sort()
    active = []          # sorted by rank: best first
    opened = [0] * n

    def close(i, t):
        s = opened[i]
        if s < t:
            if res[i] and res[i][-1][1] == s:
                res[i][-1] = (res[i][-1][0], t)
            else:
                res[i].append((s, t))

    for t, kind, i in events:
        s, e, p = requests[i]
        key = (-p, s, i)
        pos = bisect.bisect_left(active, key)
        if kind == 0:
            del active[pos]
            if pos < units:
                close(i, t)
                if len(active) >= units:
                    opened[active[units - 1][2]] = t
        else:
            active.insert(pos, key)
            if pos < units:
                opened[i] = t
                if len(active) > units:
                    close(active[units][2], t)
    return res
'''

ITEMS.append({
    "id": "C07",
    "kind": "interval",
    "difficulty": "very hard",
    "entry_point": "grant_slots",
    "prompt": r"""Write a Python function `grant_slots(requests: list[tuple[int, int, int]], units: int) -> list[list[tuple[int, int]]]`.

A depot owns `units` identical charging bays (`units >= 1`). Request number i (its index in the list) is `(start, end, priority)`: it wants one bay during the half-open time interval `[start, end)`, with integers `0 <= start < end <= 10**9`. A request is ACTIVE at time t when `start <= t < end`.

At every moment the bays go to the best-ranked active requests: if at most `units` requests are active they all hold a bay; otherwise exactly the `units` best-ranked ones do. Ranking: higher `priority` first; among equal priorities the earlier `start` first; among those the lower index first. So a request can lose its bay when better-ranked requests become active and get it back later, any number of times.

Return a list with one entry per request (same order): the sorted list of maximal intervals `(a, b)`, meaning `[a, b)`, during which that request holds a bay. "Maximal" means two intervals of the same request never touch or overlap - `(2, 5)` followed by `(5, 9)` must be reported as `(2, 9)` - and no interval is empty. A request that never holds a bay gets `[]`.

There can be up to 50,000 requests, many of them active at the same time, so comparing every request against every other one (or re-sorting the active set at every start/end time) is too slow; the whole call must finish within a couple of seconds.

Examples:
- `grant_slots([(0, 10, 1), (2, 5, 3), (4, 8, 2), (5, 6, 3)], 1)` returns `[[(0, 2), (8, 10)], [(2, 5)], [(6, 8)], [(5, 6)]]`.
- The same requests with `units = 2` give `[[(0, 4), (6, 10)], [(2, 5)], [(4, 8)], [(5, 6)]]`.
- `grant_slots([(0, 5, 1), (1, 3, 1), (1, 6, 1), (0, 2, 1)], 1)` returns `[[(0, 5)], [], [(5, 6)], []]` (equal priorities: the earlier start keeps the bay).""" + _TAIL,
    "reference": _REF_C07,
    "tests": _LCG + r'''
def _brute(requests, units):
    pts = sorted({x for s, e, p in requests for x in (s, e)})
    res = [[] for _ in requests]
    for a, b in zip(pts, pts[1:]):
        act = sorted((-p, s, i) for i, (s, e, p) in enumerate(requests) if s <= a < e)
        for _, _, i in act[:units]:
            if res[i] and res[i][-1][1] == a:
                res[i][-1] = (res[i][-1][0], b)
            else:
                res[i].append((a, b))
    return res

_R = [(0, 10, 1), (2, 5, 3), (4, 8, 2), (5, 6, 3)]
assert grant_slots([], 3) == []
assert grant_slots(_R, 1) == [[(0, 2), (8, 10)], [(2, 5)], [(6, 8)], [(5, 6)]]
assert grant_slots(_R, 2) == [[(0, 4), (6, 10)], [(2, 5)], [(4, 8)], [(5, 6)]]
assert grant_slots(_R, 3) == [[(0, 10)], [(2, 5)], [(4, 8)], [(5, 6)]]
assert grant_slots([(0, 5, 1), (1, 3, 1), (1, 6, 1), (0, 2, 1)], 1) == [[(0, 5)], [], [(5, 6)], []]
assert grant_slots([(0, 5, 1), (1, 3, 1), (1, 6, 1), (0, 2, 1)], 2) == [[(0, 5)], [(2, 3)], [(3, 6)], [(0, 2)]]
assert grant_slots([(0, 10, 1), (3, 5, 0), (5, 7, 0)], 1) == [[(0, 10)], [], []]
assert grant_slots([(0, 10, 1), (2, 4, 5), (4, 6, 5)], 1) == [[(0, 2), (6, 10)], [(2, 4)], [(4, 6)]]
assert grant_slots([(0, 10, 1), (2, 4, 5), (4, 6, 5), (0, 3, 2)], 2) == [[(0, 2), (3, 10)], [(2, 4)], [(4, 6)], [(0, 3)]]
assert grant_slots([(5, 9, 2), (5, 9, 2), (5, 9, 2)], 2) == [[(5, 9)], [(5, 9)], []]
assert grant_slots([(0, 4, 1), (0, 4, 9), (4, 8, 9), (2, 6, 1)], 1) == [[], [(0, 4)], [(4, 8)], []]
assert grant_slots([(0, 6, 1), (1, 2, 2), (3, 4, 2), (5, 6, 2)], 1) == [[(0, 1), (2, 3), (4, 5)], [(1, 2)], [(3, 4)], [(5, 6)]]
_g = _lcg(7)
for _case in range(40):
    _reqs = []
    for _ in range(1 + next(_g) % 9):
        _s = next(_g) % 12
        _reqs.append((_s, _s + 1 + next(_g) % 8, next(_g) % 3))
    _u = 1 + next(_g) % 3
    assert grant_slots(_reqs, _u) == _brute(_reqs, _u), (_reqs, _u)
_g = _lcg(2026)
_big = []
for _ in range(30000):
    _s = next(_g) % 100000
    _big.append((_s, _s + 1 + next(_g) % 60000, next(_g) % 50))
_out = grant_slots(_big, 7)
assert len(_out) == 30000
assert sum(len(x) for x in _out) == 167
assert sum((i + 1) * (b - a) for i, x in enumerate(_out) for a, b in x) == 16457972963
assert sum(b - a for x in _out for a, b in x) == 1112428
assert all(x[k][1] < x[k + 1][0] for x in _out for k in range(len(x) - 1))
_g = _lcg(31337)
_big = []
for _ in range(30000):
    _s = next(_g) % 3000000
    _big.append((_s, _s + 1 + next(_g) % 1500, next(_g) % 6))
_out = grant_slots(_big, 3)
assert sum(len(x) for x in _out) == 21350
assert sum((i + 1) * (b - a) for i, x in enumerate(_out) for a, b in x) == 133922887448
assert sum(1 for x in _out if not x) == 13130
''',
    "wrong": _mut(_REF_C07, "        key = (-p, s, i)", "        key = (-p, 0, i)"),
})


_REF_C08 = r'''
def tessel_shift(date, days):
    y, m, d = date

    def leap(year):
        return (year % 6 == 0 and year % 90 != 0) or year % 450 == 0

    def month_len(year, month):
        base = 37 if month % 2 == 1 else 36
        return base + (1 if month == 4 and leap(year) else 0)

    if not (1 <= m <= 9) or not (1 <= d <= month_len(y, m)):
        raise ValueError("invalid date")

    def leaps_upto(year):
        return year // 6 - year // 90 + year // 450

    # days from 1/1 of year 1 to 1/1 of year y
    n = 329 * (y - 1) + leaps_upto(y - 1) - leaps_upto(0)
    for mm in range(1, m):
        n += month_len(y, mm)
    n += d - 1
    n += days

    cycles, rest = divmod(n, 148121)        # 450 years = 148121 days
    year = 1 + 450 * cycles
    while True:
        ylen = 330 if leap(year) else 329
        if rest < ylen:
            break
        rest -= ylen
        year += 1
    month = 1
    while rest >= month_len(year, month):
        rest -= month_len(year, month)
        month += 1
    return (year, month, rest + 1, n % 6)
'''

ITEMS.append({
    "id": "C08",
    "kind": "interval",
    "difficulty": "very hard",
    "entry_point": "tessel_shift",
    "prompt": r"""Write a Python function `tessel_shift(date: tuple[int, int, int], days: int) -> tuple[int, int, int, int]` for the invented "Tessel" calendar.

Calendar rules:
- A year has 9 months. Months 1, 3, 5, 7, 9 have 37 days; months 2, 4, 6, 8 have 36 days. That is 329 days.
- In a leap year month 4 has 37 days instead of 36 (330 days in the year).
- Year `y` is a leap year if (`y` is divisible by 6 and not divisible by 90) or `y` is divisible by 450.
- Years are numbered with all integers: ..., -2, -1, 0, 1, 2, ... (year 0 exists and comes right before year 1). The leap rule applies to zero and negative years by ordinary divisibility, so year 0 and year -6 are leap years, year -90 is not, year -450 is.
- The week has 6 days, numbered 0..5. The date (1, 1, 1) - year 1, month 1, day 1 - is weekday 0, and weekdays cycle without interruption in both directions (the day before (1, 1, 1) is weekday 5).

`date` is `(year, month, day)`. If the month is not in 1..9 or the day does not exist in that month of that year, raise `ValueError`.

Return `(year, month, day, weekday)` of the date that lies `days` days after `date` (before it, if `days` is negative; `days = 0` returns the date itself with its weekday).

`days` can be as large as 10**18 in absolute value and years can be around 10**15 in absolute value, so walking day by day or year by year is impossible; the function must do direct arithmetic and return immediately.

Examples:
- `tessel_shift((1, 1, 1), 0)` returns `(1, 1, 1, 0)`.
- `tessel_shift((1, 1, 37), 1)` returns `(1, 2, 1, 1)`.
- `tessel_shift((1, 1, 1), 329)` returns `(2, 1, 1, 5)` (year 1 is not a leap year; 329 mod 6 is 5).
- `tessel_shift((1, 1, 1), -1)` returns `(0, 9, 37, 5)`.
- `tessel_shift((6, 4, 36), 1)` returns `(6, 4, 37, 3)` because year 6 is a leap year, while `tessel_shift((5, 4, 36), 1)` returns `(5, 5, 1, 4)`.
- `tessel_shift((5, 4, 37), 0)` raises `ValueError`.""" + _TAIL,
    "reference": _REF_C08,
    "tests": _RAISES + r'''
def _leap(y):
    return (y % 6 == 0 and y % 90 != 0) or y % 450 == 0

def _mlen(y, m):
    return (37 if m % 2 else 36) + (1 if m == 4 and _leap(y) else 0)

def _walk(date, days):
    """Independent day-by-day walk starting from (1, 1, 1) = weekday 0."""
    y, m, d, w = 1, 1, 1, 0
    # first walk from (1,1,1) to `date`, then `days` further
    def fwd(y, m, d, w):
        d += 1
        if d > _mlen(y, m):
            d = 1
            m += 1
            if m > 9:
                m = 1
                y += 1
        return y, m, d, (w + 1) % 6
    def back(y, m, d, w):
        d -= 1
        if d < 1:
            m -= 1
            if m < 1:
                m = 9
                y -= 1
            d = _mlen(y, m)
        return y, m, d, (w - 1) % 6
    target = tuple(date)
    step = fwd if target >= (1, 1, 1) else back
    while (y, m, d) != target:
        y, m, d, w = step(y, m, d, w)
    step = fwd if days >= 0 else back
    for _ in range(abs(days)):
        y, m, d, w = step(y, m, d, w)
    return (y, m, d, w)

assert tessel_shift((1, 1, 1), 0) == (1, 1, 1, 0) and tessel_shift((1, 1, 37), 1) == (1, 2, 1, 1)
assert tessel_shift((1, 1, 1), 329) == (2, 1, 1, 5) and tessel_shift((1, 1, 1), -1) == (0, 9, 37, 5)
assert tessel_shift((6, 4, 36), 1) == (6, 4, 37, 3) and tessel_shift((5, 4, 36), 1) == (5, 5, 1, 4)
assert tessel_shift((0, 4, 37), 0) == _walk((0, 4, 37), 0) and tessel_shift((0, 1, 1), 330) == (1, 1, 1, 0)
assert tessel_shift((1, 1, 1), -330) == (0, 1, 1, 0) and tessel_shift((1, 1, 1), -331) == (-1, 9, 37, 5)
assert tessel_shift((90, 4, 36), 1) == (90, 5, 1, _walk((90, 4, 36), 1)[3]) and tessel_shift((450, 4, 36), 1)[:3] == (450, 4, 37)
assert tessel_shift((-90, 4, 36), 1)[:3] == (-90, 5, 1) and tessel_shift((-450, 4, 36), 1)[:3] == (-450, 4, 37) and tessel_shift((-6, 4, 37), 1)[:3] == (-6, 5, 1)
assert all(tessel_shift((1, 1, 1), n) == _walk((1, 1, 1), n) for n in range(-700, 700, 7))
assert all(tessel_shift((y, 9, 37), n) == _walk((y, 9, 37), n) for y in (-7, -6, -1, 0, 5, 6, 89, 90) for n in (-400, -1, 0, 1, 2, 330, 700))
assert all(tessel_shift((y, 4, 30), n) == _walk((y, 4, 30), n) for y in (-91, -90, 449, 450, 451) for n in (-2000, -7, 6, 7, 2000))
assert tessel_shift((1, 1, 1), 148121) == (451, 1, 1, 148121 % 6) and tessel_shift((1, 1, 1), -148121) == (-449, 1, 1, (-148121) % 6)
assert tessel_shift((451, 1, 1), -148121) == (1, 1, 1, 0) and tessel_shift((450, 9, 37), 1) == (451, 1, 1, 5)
assert tessel_shift((1, 1, 1), 148121 * 10**12) == (1 + 450 * 10**12, 1, 1, (148121 * 10**12) % 6)
assert tessel_shift((1, 1, 1), 10**18) == (3038056723894654, 7, 11, 4)
assert tessel_shift((1, 1, 1), -10**18) == (-3038056723894653, 3, 29, 2)
assert tessel_shift((10**15, 9, 37), 12345678901234567) == (1037506872796941, 1, 12, 3)
assert tessel_shift((-10**15 + 7, 4, 36), -98765432109876543) == (-1300054985109764, 1, 26, 1)
assert tessel_shift(tessel_shift((777, 3, 3), 10**18 - 11)[:3], -(10**18 - 11)) == tessel_shift((777, 3, 3), 0)
assert tessel_shift(tessel_shift((-123456, 8, 36), -(10**17) - 5)[:3], 10**17 + 5)[:3] == (-123456, 8, 36)
assert _raises(ValueError, tessel_shift, (5, 4, 37), 0) and _raises(ValueError, tessel_shift, (1, 10, 1), 0) and _raises(ValueError, tessel_shift, (1, 0, 1), 5)
assert _raises(ValueError, tessel_shift, (1, 2, 37), 0) and _raises(ValueError, tessel_shift, (1, 1, 0), 0) and _raises(ValueError, tessel_shift, (90, 4, 37), 1) and _raises(ValueError, tessel_shift, (3, 9, 38), 1)
''',
    "wrong": _mut(_REF_C08, "        return year // 6 - year // 90 + year // 450", "        return int(year / 6) - int(year / 90) + int(year / 450)"),
})


_REF_C09 = r'''
import re

def count_fires(spec, blackouts, a, b):
    fields = spec.split()
    if len(fields) != 3:
        raise ValueError("need three fields")

    def parse(field, top):
        out = set()
        for term in field.split(","):
            pieces = term.split("/")
            if len(pieces) > 2:
                raise ValueError("bad term")
            step = None
            if len(pieces) == 2:
                if not re.fullmatch(r"[0-9]+", pieces[1]) or int(pieces[1]) < 1:
                    raise ValueError("bad step")
                step = int(pieces[1])
            base = pieces[0]
            if base == "*":
                lo, hi = 0, top
            elif re.fullmatch(r"[0-9]+", base):
                lo = int(base)
                hi = top if step is not None else lo
            elif re.fullmatch(r"[0-9]+-[0-9]+", base):
                lo, hi = (int(x) for x in base.split("-"))
            else:
                raise ValueError("bad term")
            if lo > hi or hi > top:
                raise ValueError("out of range")
            out.update(range(lo, hi + 1, step or 1))
        return out

    minutes = parse(fields[0], 59)
    hours = parse(fields[1], 23)
    wdays = parse(fields[2], 6)
    week = 10080
    pre = [0] * (week + 1)
    for t in range(week):
        hit = (t % 60 in minutes) and (t // 60 % 24 in hours) and (t // 1440 in wdays)
        pre[t + 1] = pre[t] + (1 if hit else 0)

    def upto(t):
        return (t // week) * pre[week] + pre[t % week]

    if b <= a:
        return 0
    total = upto(b) - upto(a)
    clipped = sorted((max(s, a), min(e, b)) for s, e in blackouts if max(s, a) < min(e, b))
    cur_s = cur_e = None
    for s, e in clipped:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total -= upto(cur_e) - upto(cur_s)
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total -= upto(cur_e) - upto(cur_s)
    return total
'''

ITEMS.append({
    "id": "C09",
    "kind": "interval",
    "difficulty": "very hard",
    "entry_point": "count_fires",
    "prompt": r"""Write a Python function `count_fires(spec: str, blackouts: list[tuple[int, int]], a: int, b: int) -> int` that counts how often a repeating alarm fires.

Time is an integer number of minutes. Minute 0 is 00:00 on weekday 0; a day has 1440 minutes and the week has 7 days (weekdays 0..6), repeating forever. So minute t has minute-of-hour `t % 60`, hour `t // 60 % 24` and weekday `t // 1440 % 7`.

`spec` consists of exactly three fields separated by whitespace (any amount, and it may also appear at both ends): MINUTE (values 0..59), HOUR (0..23), WEEKDAY (0..6). Each field is a comma-separated list of one or more terms, and its value set is the union of its terms. With MAX being the field's largest value, a term is one of:
- `*` - every value 0..MAX
- `N` - the single value N
- `N-M` - every value from N to M inclusive; requires N <= M
- any of these three followed by `/S`, a step S >= 1: `*/S` is 0, S, 2S, ... up to MAX; `N-M/S` is N, N+S, N+2S, ... not exceeding M; `N/S` is N, N+S, N+2S, ... not exceeding MAX.
Numbers are written with digits only. Anything else - a wrong number of fields, an empty term, a value above MAX, N > M, a step of 0, more than one `/`, signs, letters - raises `ValueError` (always, whatever the other arguments are).

The alarm FIRES at minute t when all three of its minute-of-hour, hour and weekday are in the corresponding sets, and t is not inside any blackout. A blackout `(s, e)` covers the minutes `s <= t < e` (integers, `0 <= s <= e <= 10**18`); blackouts may overlap each other, touch, be empty or lie outside the range asked for; there can be up to 2000 of them.

Return the number of minutes t with `a <= t < b` at which the alarm fires. `0 <= a` and `b <= 10**18`; if `b <= a` the answer is 0. The range can span about 10**14 weeks, so the function must not walk through the range minute by minute, day by day or week by week.

Examples:
- `count_fires("0 0 *", [], 0, 10080)` returns 7 (once per day at midnight).
- `count_fires("*/15 9-17 1-5", [], 0, 10080)` returns 180 (4 per hour, 9 hours, 5 days).
- `count_fires("* * *", [(10, 20), (15, 30), (100, 200)], 0, 150)` returns 80: 150 minutes minus the 20 minutes of the merged blackout 10..30 minus the 50 minutes 100..150.
- `count_fires("30 12 0", [], 0, 10080 * 10**12)` returns `10**12`.""" + _TAIL,
    "reference": _REF_C09,
    "tests": _RAISES + r'''
def _slow(spec, blackouts, a, b):
    def vals(field, top):
        out = set()
        for term in field.split(","):
            base, _, st = term.partition("/")
            st = int(st) if st else None
            if base == "*":
                lo, hi = 0, top
            elif "-" in base:
                lo, hi = map(int, base.split("-"))
            else:
                lo = int(base)
                hi = top if st else lo
            out |= set(range(lo, hi + 1, st or 1))
        return out
    f = spec.split()
    mi, ho, wd = vals(f[0], 59), vals(f[1], 23), vals(f[2], 6)
    n = 0
    for t in range(a, b):
        if t % 60 in mi and t // 60 % 24 in ho and t // 1440 % 7 in wd:
            if not any(s <= t < e for s, e in blackouts):
                n += 1
    return n

assert count_fires("0 0 *", [], 0, 10080) == 7 and count_fires("*/15 9-17 1-5", [], 0, 10080) == 180
assert count_fires("* * *", [(10, 20), (15, 30), (100, 200)], 0, 150) == 80
assert count_fires("30 12 0", [], 0, 10080 * 10**12) == 10**12
assert count_fires("0 0 *", [], 1, 1441) == 1 and count_fires("0 0 *", [], 0, 1) == 1 and count_fires("0 0 *", [], 1, 1440) == 0
assert count_fires("0 */6 0,6", [], 0, 10080) == 8 and count_fires("5/20 0 3", [], 0, 10080) == 3 and count_fires("10-50/20,7 23 2/2", [], 0, 10080) == 12
assert count_fires("  59   23\t6 ", [], 10079, 10080) == 1 and count_fires("59 23 6", [], 0, 10079) == 0
assert count_fires("* * *", [], 5, 5) == 0 and count_fires("* * *", [], 9, 3) == 0 and count_fires("* * *", [(0, 10**18)], 0, 10**18) == 0
assert count_fires("* * *", [(5, 5), (7, 9), (9, 12), (8, 10), (40, 50)], 0, 30) == 25
assert count_fires("* * *", [(0, 3), (10**18 - 4, 10**18)], 0, 10**18) == 10**18 - 7
assert count_fires("0 0 *", [(0, 1440 * 10**6)], 0, 1440 * 10**9) == 10**9 - 10**6
assert count_fires("0 0 *", [(1, 1440), (1441, 2880)], 0, 2881) == 3 and count_fires("0 0 *", [(0, 1), (1440, 1441)], 0, 2881) == 1
assert count_fires("0,30 */2 1-5/2", [], 0, 10080 * 7 * 10**13) == 2 * 12 * 3 * 7 * 10**13
assert count_fires("7 3 2", [], 123456789, 123456789 + 10080 * 5) == 5
_bl = [(3000, 4000), (3500, 9000), (20000, 20010), (12000, 12000), (15000, 15500)]
assert all(count_fires(sp, _bl, lo, hi) == _slow(sp, _bl, lo, hi) for sp in ("*/7 */5 *", "3-40/9,58 1,2,22 0-6/3", "13 * 1,5", "0/25 6/9 *") for lo, hi in ((0, 22000), (3999, 20005), (9001, 9002), (10079, 30241)))
assert count_fires("*/7 */5 *", [(10**17, 10**17 + 10**6), (10**17 + 500, 10**17 + 20000)], 12345, 10**18 - 54321) == 31249999999966668
assert count_fires("3-40/9,58 1,2,22 0-6/3", [(i * 10**14 + i, i * 10**14 + 5 * 10**13) for i in range(2000)], 777, 10**18) == 4821428571439148
assert _raises(ValueError, count_fires, "60 0 0", [], 0, 10) and _raises(ValueError, count_fires, "* *", [], 0, 10) and _raises(ValueError, count_fires, "* * * *", [], 0, 10)
assert _raises(ValueError, count_fires, "*/0 * *", [], 0, 10) and _raises(ValueError, count_fires, "5-3 * *", [], 0, 10) and _raises(ValueError, count_fires, "a * *", [], 0, 10)
assert _raises(ValueError, count_fires, "1,,2 * *", [], 0, 10) and _raises(ValueError, count_fires, "* 24 *", [], 0, 10) and _raises(ValueError, count_fires, "* * 7", [], 0, 10)
assert _raises(ValueError, count_fires, "1/2/3 * *", [], 0, 10) and _raises(ValueError, count_fires, "-1 * *", [], 0, 10) and _raises(ValueError, count_fires, "", [], 0, 10)
assert _raises(ValueError, count_fires, "1- * *", [], 9, 3) and _raises(ValueError, count_fires, "* * 0-7", [], 0, 10) and _raises(ValueError, count_fires, "*/ * *", [], 0, 10)
''',
    "wrong": _mut(_REF_C09, "        if cur_e is None or s > cur_e:", "        if True:"),
})


_REF_C10 = r'''
import heapq

def edf_outcomes(jobs, switch):
    n = len(jobs)
    result = [None] * n
    rem = [w for _, _, w in jobs]
    order = sorted(range(n), key=lambda i: (jobs[i][0], i))
    ptr = 0
    heap = []
    t = 0
    setup = None
    target = None
    progress = 0
    while True:
        while ptr < n and jobs[order[ptr]][0] <= t:
            i = order[ptr]
            heapq.heappush(heap, (jobs[i][1], jobs[i][0], i))
            ptr += 1
        while heap and t + rem[heap[0][2]] > heap[0][0]:
            heapq.heappop(heap)                      # hopeless: abandoned
        nxt = jobs[order[ptr]][0] if ptr < n else None
        if not heap:
            if nxt is None:
                break
            t = nxt
            continue
        deadline, _, i = heap[0]
        if target != i:
            target = i
            progress = 0
        if switch == 0:
            setup = i
        if setup == i:
            end = t + rem[i]
            if nxt is not None and nxt < end:
                end = nxt
            rem[i] -= end - t
            t = end
            if rem[i] == 0:
                result[i] = t
                heapq.heappop(heap)
        else:
            end = t + (switch - progress)
            hopeless_at = deadline - rem[i] + 1
            if hopeless_at < end:
                end = hopeless_at
            if nxt is not None and nxt < end:
                end = nxt
            progress += end - t
            t = end
            if progress == switch:
                setup = i
    return result
'''

ITEMS.append({
    "id": "C10",
    "kind": "interval",
    "difficulty": "very hard",
    "entry_point": "edf_outcomes",
    "prompt": r"""Write a Python function `edf_outcomes(jobs: list[tuple[int, int, int]], switch: int) -> list` that simulates one machine working through jobs with deadlines.

Job number i (its index in the list) is `(release, deadline, work)`: integers with `0 <= release < deadline` and `work >= 1`. `switch >= 0` is the changeover time of the machine.

The machine has a "set up for" marker: the job it is currently tooled for (initially none). Time advances in ticks; tick t covers the time from t to t + 1. In every tick t = 0, 1, 2, ... the following happens in this order:

1. Every job with `release == t` becomes available.
2. Every available job that can no longer finish in time, i.e. with `t + remaining_work > deadline`, is abandoned for good (its work so far is lost).
3. The TARGET of this tick is the available job with the earliest deadline; ties go to the earlier release, then to the lower index. If no job is available the machine idles in this tick.
4. If the machine is set up for the target, it does one unit of work on it. When the remaining work reaches 0 the job is finished; its completion time is t + 1, and it is no longer available.
5. Otherwise this is a changeover tick. A changeover needs `switch` consecutive ticks with the same target; when the `switch`-th of these ticks is over, the machine becomes set up for that target (and works on it from the next tick, if it is still the target). If the target changes before that, the progress made is lost and the count restarts for the new target. If `switch == 0` there are no changeover ticks: the machine becomes set up for the target at once and works in this very tick.

The "set up for" marker changes only when a changeover completes. So after an interrupted changeover the machine is still set up for the job it was set up for before, and needs no changeover to continue that job; and after finishing a job the machine stays set up for the finished job, so the next job needs a changeover.

Return a list with one entry per job: its completion time, or `None` if it was abandoned.

There can be 100,000 jobs and times up to 10**12, so ticks must not be simulated one by one.

Examples:
- `edf_outcomes([(0, 10, 5)], 2)` returns `[7]` (ticks 0-1 changeover, ticks 2-6 work).
- `edf_outcomes([(0, 10, 5)], 6)` returns `[None]`: the changeover ends after tick 5, but at tick 6 we have 6 + 5 > 10.
- `edf_outcomes([(0, 20, 4), (3, 9, 2)], 1)` returns `[9, 6]`: after the changeover in tick 0, job 0 works in ticks 1-2; at tick 3 job 1 becomes the target (changeover in tick 3, work in ticks 4-5); job 0 then needs a new changeover (tick 6) and works in ticks 7-8.""" + _TAIL,
    "reference": _REF_C10,
    "tests": _LCG + r'''
def _ticks(jobs, switch):
    n = len(jobs)
    res = [None] * n
    rem = [w for _, _, w in jobs]
    avail = set()
    pending = n
    setup = target = None
    progress = 0
    t = 0
    while pending:
        for i, (r, d, w) in enumerate(jobs):
            if r == t:
                avail.add(i)
        for i in sorted(avail):
            if t + rem[i] > jobs[i][1]:
                avail.discard(i)
                pending -= 1
        if avail:
            i = min(avail, key=lambda j: (jobs[j][1], jobs[j][0], j))
            if i != target:
                target, progress = i, 0
            if switch == 0:
                setup = i
            if setup == i:
                rem[i] -= 1
                if rem[i] == 0:
                    res[i] = t + 1
                    avail.discard(i)
                    pending -= 1
            else:
                progress += 1
                if progress == switch:
                    setup = i
        t += 1
    return res

assert edf_outcomes([], 3) == []
assert edf_outcomes([(0, 10, 5)], 2) == [7] and edf_outcomes([(0, 10, 5)], 6) == [None] and edf_outcomes([(0, 10, 5)], 5) == [10]
assert edf_outcomes([(0, 20, 4), (3, 9, 2)], 1) == [9, 6]
assert edf_outcomes([(0, 20, 4), (3, 9, 2)], 0) == [6, 5]
assert edf_outcomes([(0, 5, 5), (0, 5, 5)], 0) == [5, None] and edf_outcomes([(0, 5, 5), (0, 5, 5)], 1) == [None, None]
assert edf_outcomes([(0, 100, 10), (4, 9, 3)], 2) == [19, 9]
assert edf_outcomes([(0, 100, 10), (4, 8, 3)], 2) == [16, None]
assert edf_outcomes([(0, 100, 10), (2, 50, 1), (2, 50, 1), (1, 50, 1)], 1) == [18, 5, 7, 3]
assert edf_outcomes([(5, 9, 2), (0, 30, 3)], 3) == [None, 12]
assert edf_outcomes([(0, 30, 6), (4, 9, 2)], 3) == [17, 9]
assert edf_outcomes([(0, 30, 6), (4, 8, 2)], 3) == [15, None] and edf_outcomes([(0, 30, 6), (4, 7, 2)], 3) == [11, None]
assert edf_outcomes([(10**11, 10**12, 5 * 10**11), (0, 10**12, 3 * 10**11)], 7) == [8 * 10**11 + 14, 3 * 10**11 + 7]
_g = _lcg(99)
for _case in range(120):
    _jobs = []
    for _ in range(1 + next(_g) % 6):
        _r = next(_g) % 14
        _w = 1 + next(_g) % 5
        _jobs.append((_r, _r + 1 + next(_g) % 16, _w))
    _sw = next(_g) % 4
    assert edf_outcomes(_jobs, _sw) == _ticks(_jobs, _sw), (_jobs, _sw)
_g = _lcg(4242)
_big = []
for _ in range(60000):
    _r = next(_g) % 10**11
    _w = 1 + next(_g) % 3000000
    _big.append((_r, _r + _w + next(_g) % 40000000, _w))
_out = edf_outcomes(_big, 1000)
_done = [x for x in _out if x is not None]
assert len(_out) == 60000
assert len(_done) == 8197
assert sum(_done) == 8954296281537
assert sum(i for i, x in enumerate(_out) if x is None) == 1554221094
''',
    "wrong": _mut(_REF_C10, "        if target != i:\n            target = i\n            progress = 0", "        if target != i:\n            target = i\n            progress = 0\n            setup = None"),
})


_REF_C11 = r'''
from math import gcd

def lit_time(beacons, horizon):
    if horizon <= 0 or not beacons:
        return 0
    cycle = 1
    for p, _, _ in beacons:
        cycle = cycle * p // gcd(cycle, p)
    settle = max(o + l for _, o, l in beacons)
    span = min(horizon, settle + cycle)
    lit = bytearray(span)
    for p, o, l in beacons:
        if o >= span:
            continue
        if l >= p:
            lit[o:span] = b"\x01" * (span - o)
            continue
        start = o
        while start < span:
            end = min(span, start + l)
            lit[start:end] = b"\x01" * (end - start)
            start += p
    pre = [0] * (span + 1)
    for i in range(span):
        pre[i + 1] = pre[i] + lit[i]
    if horizon <= settle + cycle:
        return pre[horizon]
    per_cycle = pre[settle + cycle] - pre[settle]
    full, rest = divmod(horizon - settle, cycle)
    return pre[settle] + full * per_cycle + (pre[settle + rest] - pre[settle])
'''

ITEMS.append({
    "id": "C11",
    "kind": "interval",
    "difficulty": "hard",
    "entry_point": "lit_time",
    "prompt": r"""Write a Python function `lit_time(beacons: list[tuple[int, int, int]], horizon: int) -> int`.

Each beacon is `(period, first, length)` with integers `period >= 1`, `first >= 0`, `length >= 1`. The beacon switches on at the times `first`, `first + period`, `first + 2 * period`, ... (there is no flash before `first`), and each time it stays lit for `length` time units: the k-th flash (k = 0, 1, 2, ...) lights the half-open interval `[first + k * period, first + k * period + length)`. `length` may be larger than `period`, in which case flashes of the same beacon overlap.

Return the total length of time within `[0, horizon)` during which AT LEAST ONE beacon is lit. Because all numbers are integers this equals the number of integers t with `0 <= t < horizon` such that some beacon is lit throughout `[t, t + 1)`.

Limits: at most 8 beacons; every `first` and `length` is at most 10,000; the least common multiple of all periods is at most 10,000; but `horizon` can be as large as 10**18, so the answer must be computed without walking through the whole horizon. `horizon <= 0` or an empty list gives 0.

Examples:
- `lit_time([(10, 0, 3)], 25)` returns 9 (lit during 0-3, 10-13, 20-23).
- `lit_time([(6, 0, 2), (4, 1, 2)], 12)` returns 8: the union is 0-3, 5-8, 9-11.
- `lit_time([(4, 0, 1), (6, 100, 6)], 10**9)` returns `10**9 - 75`: before time 100 only the first beacon is on (25 units); from 100 on the second one is always lit.
- `lit_time([(5, 3, 4)], 10**18)` returns `8 * 10**17 - 2`.""" + _TAIL,
    "reference": _REF_C11,
    "tests": _LCG + r'''
def _direct(beacons, horizon):
    return sum(1 for t in range(horizon) if any(t >= o and (l >= p or (t - o) % p < l) for p, o, l in beacons))

assert lit_time([(10, 0, 3)], 25) == 9 and lit_time([(10, 0, 3)], 10**18) == 3 * 10**17
assert lit_time([(6, 0, 2), (4, 1, 2)], 12) == 8 and lit_time([(6, 0, 2), (4, 1, 2)], 12 * 10**15) == 8 * 10**15
assert lit_time([(4, 0, 1), (6, 100, 6)], 10**9) == 10**9 - 75
assert lit_time([(5, 3, 4)], 10**18) == 8 * 10**17 - 2
assert lit_time([], 100) == 0 and lit_time([(3, 0, 1)], 0) == 0 and lit_time([(3, 0, 1)], -5) == 0 and lit_time([(3, 5, 1)], 5) == 0
assert lit_time([(10, 5, 3)], 10**18) == 3 * 10**17 and lit_time([(10, 8, 3)], 10**18) == 3 * 10**17 - 1
assert lit_time([(7, 9000, 20)], 10**18) == 10**18 - 9000 and lit_time([(1, 0, 1)], 10**18) == 10**18
assert lit_time([(10, 0, 1), (10, 5, 1), (10, 0, 1)], 10**18) == 2 * 10**17
assert lit_time([(10, 0, 5), (15, 2, 5)], 30) == _direct([(10, 0, 5), (15, 2, 5)], 30) == 20
assert lit_time([(10, 9995, 6), (4, 1, 1)], 10**12) == 699999995504
assert lit_time([(9, 100, 4), (12, 3, 5), (8, 1000, 3), (72, 50, 30)], 10**18) == 916666666666666531
assert lit_time([(2500, 9000, 2499), (10000, 0, 1), (16, 7, 3), (625, 624, 100)], 10**18 - 1) == 999699999999993826
_g = _lcg(5)
for _case in range(60):
    _bs = []
    for _ in range(1 + next(_g) % 4):
        _bs.append(([1, 2, 3, 4, 6, 12][next(_g) % 6], next(_g) % 40, 1 + next(_g) % 9))
    for _h in (1, 17, 53, 54, 55, 200, 301):
        assert lit_time(_bs, _h) == _direct(_bs, _h), (_bs, _h)
    _h = 10**6 * 12 + next(_g) % 12
    assert lit_time(_bs, _h) == _direct(_bs, 120 + _h % 12) + (_h - 120 - _h % 12) // 12 * (_direct(_bs, 132) - _direct(_bs, 120)), _bs
''',
    "wrong": _mut(_REF_C11, "    settle = max(o + l for _, o, l in beacons)", "    settle = 0"),
})

# ---------------------------------------------------------------------------
# Kind 3: simulation with huge horizons (C12-C16)
# ---------------------------------------------------------------------------

_REF_C12 = r'''
def frog_visits(n, broken, target, jumps):
    bad = set(broken)
    pos, direction, k = 0, 1, 0
    count = 0
    seen = {}
    while k < jumps:
        state = (pos, direction, k % n)
        if state in seen:
            k0, c0 = seen[state]
            period = k - k0
            cycles = (jumps - k) // period
            k += cycles * period
            count += cycles * (count - c0)
            seen = {}
            if k >= jumps:
                break
        seen[state] = (k, count)
        k += 1
        pos = (pos + direction * k) % n
        if pos in bad:
            while pos in bad:
                pos = (pos + direction) % n
            direction = -direction
        if pos == target:
            count += 1
    return (pos, count)
'''

ITEMS.append({
    "id": "C12",
    "kind": "simulation",
    "difficulty": "hard",
    "entry_point": "frog_visits",
    "prompt": r"""Write a Python function `frog_visits(n: int, broken: list[int], target: int, jumps: int) -> tuple[int, int]`.

A pond has `n` lily pads arranged in a ring, numbered 0..n-1 clockwise (pad n-1 is next to pad 0). Some pads are broken (listed in `broken`); pad 0 and pad `target` are never broken.

A frog starts on pad 0, travelling clockwise. It makes jumps numbered 1, 2, 3, ...:
- Jump number k moves the frog exactly k pads along the ring in its current direction of travel (clockwise = increasing pad numbers, counter-clockwise = decreasing; k may be larger than n, the frog simply goes around).
- If the pad it lands on is broken, the frog keeps moving one pad at a time in the same direction until it reaches a pad that is not broken, and rests there. Having been thrown off like this, it reverses its direction of travel for all following jumps (until the next time this happens).
- If the landing pad is not broken, the frog rests there and keeps its direction.

Return `(final_pad, visits)` after `jumps` jumps: the pad the frog rests on at the end, and the number of jumps (among jumps 1..`jumps`) after which the frog rested on pad `target`. The start on pad 0 before the first jump does not count as a visit.

Limits: `2 <= n <= 300`, `0 <= jumps <= 10**18`. Simulating every jump is impossible for large `jumps`; note that the jump length keeps growing, so think carefully about what determines the frog's future.

Example: `frog_visits(5, [1], 3, 10)` returns `(3, 4)`. Jump 1 lands on pad 1 (broken): the frog slides on to pad 2 and now travels counter-clockwise. Jumps 2..10 then rest on pads 0, 2, 3, 3, 2, 0, 2, 3, 3. Pad 3 was reached after jumps 4, 5, 9 and 10. `frog_visits(5, [1], 3, 4)` returns `(3, 1)` and `frog_visits(5, [1], 3, 0)` returns `(0, 0)`.""" + _TAIL,
    "reference": _REF_C12,
    "tests": r'''
def _sim(n, broken, target, jumps):
    bad = set(broken)
    pos, d, cnt = 0, 1, 0
    for k in range(1, jumps + 1):
        pos = (pos + d * k) % n
        if pos in bad:
            while pos in bad:
                pos = (pos + d) % n
            d = -d
        cnt += pos == target
    return (pos, cnt)

assert frog_visits(5, [1], 3, 10) == (3, 4) and frog_visits(5, [1], 3, 4) == (3, 1) and frog_visits(5, [1], 3, 0) == (0, 0)
assert frog_visits(5, [], 3, 7) == (3, 2) and frog_visits(5, [2], 3, 7) == (3, 2)
assert frog_visits(2, [], 0, 10**18) == (0, 5 * 10**17) and frog_visits(2, [1], 0, 10**18) == (0, 10**18)
assert frog_visits(7, [], 0, 7 * 10**17) == (0, 2 * 10**17)
assert frog_visits(4, [], 2, 8) == (0, 2) and frog_visits(4, [], 2, 8 * 10**15 + 3) == (2, 2 * 10**15 + 1)
assert frog_visits(6, [1, 2, 3, 4, 5], 0, 12345) == (0, 12345)
assert all(frog_visits(9, [4, 5], 1, j) == _sim(9, [4, 5], 1, j) for j in range(0, 400))
assert all(frog_visits(n, b, t, j) == _sim(n, b, t, j) for n, b, t in ((10, [3], 9), (12, [1, 2, 7], 3), (13, [12, 6], 1), (16, [8], 0), (30, [29, 1, 15], 2)) for j in (1, 2, 50, 999, 5000, 20001))
assert frog_visits(300, [7, 150, 151, 299], 6, 60000) == _sim(300, [7, 150, 151, 299], 6, 60000)
assert frog_visits(300, [7, 150, 151, 299], 5, 60000) == _sim(300, [7, 150, 151, 299], 5, 60000)
assert frog_visits(9, [4, 5], 1, 10**18) == (1, 333333333333333334)
assert frog_visits(300, [7, 150, 151, 299], 6, 10**18) == (197, 13333333333333329)
assert frog_visits(299, [1], 13, 10**18 - 1) == (289, 13377926421404682)
assert frog_visits(256, [3, 10, 77, 200], 11, 987654321987654321) == (23, 38580246952642734)
assert frog_visits(30, [29, 1, 15], 2, 10**12 + 7) == (14, 116666666665)
assert frog_visits(97, [50], 0, 97 * 2 * 10**9 + 5) == (15, 4000000000)
assert frog_visits(300, [7, 150, 151, 299], 5, 10**18) == (197, 19)
''',
    "wrong": _mut(_REF_C12, "        state = (pos, direction, k % n)", "        state = (pos, direction)"),
})


_REF_C13 = r'''
def colony_census(egg_nights, larva_nights, adult_nights, eggs, bonus, nights):
    MOD = 1_000_000_007
    E, L, A = egg_nights, larva_nights, adult_nights
    size = E + L + A
    # mat[to][frm]
    mat = [[0] * size for _ in range(size)]
    for a in range(E):
        mat[a + 1 if a + 1 < E else E][a] += 1
    for a in range(L):
        mat[E + a + 1 if a + 1 < L else E + L][E + a] += 1
    for a in range(A):
        frm = E + L + a
        mat[0][frm] += eggs + (bonus if a == A - 1 else 0)
        if a + 1 < A:
            mat[frm + 1][frm] += 1
    mat = [[v % MOD for v in row] for row in mat]

    def mul(x, y):
        cols = list(zip(*y))
        return [[sum(a * b for a, b in zip(row, col)) % MOD for col in cols] for row in x]

    vec = [0] * size
    vec[0] = 1
    n = nights
    while n > 0:
        if n & 1:
            vec = [sum(a * b for a, b in zip(row, vec)) % MOD for row in mat]
        n >>= 1
        if n:
            mat = mul(mat, mat)
    return (sum(vec[:E]) % MOD, sum(vec[E:E + L]) % MOD, sum(vec[E + L:]) % MOD)
'''

ITEMS.append({
    "id": "C13",
    "kind": "simulation",
    "difficulty": "very hard",
    "entry_point": "colony_census",
    "prompt": r"""Write a Python function `colony_census(egg_nights: int, larva_nights: int, adult_nights: int, eggs: int, bonus: int, nights: int) -> tuple[int, int, int]` that predicts the size of a glow-beetle colony.

Every individual is an egg, a larva or an adult, and has an age: the number of nights it has already spent in its current stage. The colony starts with exactly one egg of age 0. Each night the following happens simultaneously to every individual that exists at the start of the night:

- An adult lays `eggs` new eggs. If this is the adult's last night (see below) it lays `eggs + bonus` eggs instead. Then its age increases by 1; when its age reaches `adult_nights` it dies. So every adult lays on exactly `adult_nights` nights, the last of which is the bonus night.
- A larva's age increases by 1; when it reaches `larva_nights` the larva becomes an adult of age 0. (It lays nothing during this night.)
- An egg's age increases by 1; when it reaches `egg_nights` the egg becomes a larva of age 0.

Eggs laid during a night exist from the end of that night, with age 0; they are not themselves processed during that night.

Return `(eggs_count, larvae_count, adults_count)` after `nights` nights, each number reduced modulo 1,000,000,007.

Limits: `egg_nights`, `larva_nights`, `adult_nights` are each between 1 and 6; `0 <= eggs, bonus <= 10**9`; `0 <= nights <= 10**18`. The population grows exponentially and `nights` is far too large to simulate night by night, so the function needs a method whose running time grows only with the logarithm of `nights`.

Example: `colony_census(1, 1, 2, 3, 0, n)` for n = 0, 1, ..., 6 gives `(1, 0, 0)`, `(0, 1, 0)`, `(0, 0, 1)`, `(3, 0, 1)`, `(3, 3, 0)`, `(0, 3, 3)`, `(9, 0, 6)`. In night 4, for instance, the single adult lays 3 eggs and then dies (age 2), while the 3 older eggs become larvae.
With a bonus, `colony_census(1, 1, 2, 3, 5, 4)` is `(8, 3, 0)`.""" + _TAIL,
    "reference": _REF_C13,
    "tests": r'''
def _sim(E, L, A, eggs, bonus, nights):
    eg, la, ad = [0] * E, [0] * L, [0] * A
    eg[0] = 1
    for _ in range(nights):
        laid = eggs * sum(ad) + bonus * ad[A - 1]
        new_ad = [la[L - 1]] + ad[:A - 1]
        new_la = [eg[E - 1]] + la[:L - 1]
        new_eg = [laid] + eg[:E - 1]
        eg, la, ad = new_eg, new_la, new_ad
    M = 1_000_000_007
    return (sum(eg) % M, sum(la) % M, sum(ad) % M)

assert [colony_census(1, 1, 2, 3, 0, n) for n in range(7)] == [(1, 0, 0), (0, 1, 0), (0, 0, 1), (3, 0, 1), (3, 3, 0), (0, 3, 3), (9, 0, 6)]
assert colony_census(1, 1, 2, 3, 5, 4) == (8, 3, 0) and colony_census(1, 1, 2, 3, 5, 3) == (3, 0, 1)
assert colony_census(2, 3, 4, 1, 0, 0) == (1, 0, 0) and colony_census(2, 3, 4, 1, 0, 1) == (1, 0, 0) and colony_census(2, 3, 4, 1, 0, 2) == (0, 1, 0)
assert colony_census(2, 3, 4, 1, 0, 5) == (0, 0, 1) and colony_census(2, 3, 4, 1, 0, 6) == (1, 0, 1) and colony_census(2, 3, 4, 1, 0, 9) == (2, 2, 0)
assert colony_census(3, 2, 1, 0, 0, 5) == (0, 0, 1) and colony_census(3, 2, 1, 0, 0, 6) == (0, 0, 0) and colony_census(3, 2, 1, 0, 0, 10**18) == (0, 0, 0)
assert colony_census(1, 1, 1, 1, 0, 10**18) == [(1, 0, 0), (0, 1, 0), (0, 0, 1)][10**18 % 3]
assert colony_census(1, 1, 1, 0, 2, 3 * 40 + 1) == (0, pow(2, 40, 1_000_000_007), 0)
assert colony_census(1, 1, 1, 10**9, 10**9, 3) == (2 * 10**9 % 1_000_000_007, 0, 0)
assert all(colony_census(E, L, A, f, b, n) == _sim(E, L, A, f, b, n) for E, L, A, f, b in ((1, 1, 1, 2, 0), (2, 1, 3, 1, 1), (3, 3, 2, 4, 0), (6, 6, 6, 3, 7), (1, 4, 2, 0, 5), (2, 2, 6, 10**9, 1)) for n in (1, 2, 7, 19, 40, 121))
assert colony_census(6, 5, 4, 2, 1, 300) == _sim(6, 5, 4, 2, 1, 300)
assert colony_census(1, 1, 2, 3, 0, 10**18) == (116710615, 178366875, 189366006)
assert colony_census(6, 6, 6, 3, 7, 10**18) == (401940295, 563962446, 88381179)
assert colony_census(2, 3, 4, 1, 0, 999999999999999989) == (832800933, 573173366, 945739702)
assert colony_census(4, 1, 6, 10**9, 10**9, 10**17 + 1) == (831790633, 835516176, 405043234)
assert colony_census(3, 5, 2, 12345, 0, 2**60) == (724230808, 516160675, 773635196)
''',
    "wrong": _mut(_REF_C13, "(bonus if a == A - 1 else 0)", "(bonus if a == 0 else 0)"),
})


_REF_C14 = r'''
def tank_level(capacity, low, high, fill, drain, level, pump_on, ticks):
    left = ticks
    seen = {}
    while left > 0:
        key = (level, pump_on)
        if key in seen:
            left %= seen[key] - left
            seen = {}
            if left == 0:
                break
        seen[key] = left
        if pump_on:
            net = fill - drain
            if net > 0:
                need = max(1, -((level - high) // net))
                if need > left:
                    level += left * net
                    left = 0
                else:
                    level = min(capacity, level + need * net)
                    left -= need
                    pump_on = False
            elif net == 0:
                if level >= high:
                    pump_on = False
                    left -= 1
                else:
                    left = 0
            else:
                level = max(0, level + net)
                left -= 1
                if low < level and level >= high:
                    pump_on = False
                else:
                    level = max(0, level + net * left)
                    left = 0
        else:
            if drain == 0:
                if level <= low:
                    pump_on = True
                    left -= 1
                else:
                    left = 0
            else:
                need = max(1, -((low - level) // drain))
                if need > left:
                    level -= left * drain
                    left = 0
                else:
                    level = max(0, level - need * drain)
                    left -= need
                    pump_on = True
    return (level, pump_on)
'''

ITEMS.append({
    "id": "C14",
    "kind": "simulation",
    "difficulty": "very hard",
    "entry_point": "tank_level",
    "prompt": r"""Write a Python function `tank_level(capacity: int, low: int, high: int, fill: int, drain: int, level: int, pump_on: bool, ticks: int) -> tuple[int, bool]` that simulates a water tank with an automatic pump and returns `(level, pump_on)` after `ticks` ticks.

In every tick, in this order:
1. The level changes by `(fill if pump_on else 0) - drain`. The result is clamped to the range `0..capacity` (never below 0, never above `capacity`).
2. The controller looks at the new level: if `level <= low` it switches the pump ON; otherwise if `level >= high` it switches the pump OFF; otherwise the pump stays as it is.

Note that the controller only acts at the end of a tick: if the tank starts with the pump on and the level already at or above `high`, the pump still runs during the first tick.

Limits: `0 <= low < high <= capacity <= 10**18`, `0 <= level <= capacity`, `0 <= fill <= 1000`, `0 <= drain <= 1000`, `0 <= ticks <= 10**18`.

So the tank can be astronomically large compared with the flow rates (one filling may take 10**15 ticks), or `low` and `high` can be close together (the pump toggles every few ticks, 10**17 times), or both effects can combine. The function must return quickly in all of these cases: neither tick-by-tick simulation nor simulating every single on/off phase is acceptable in general.

Examples (capacity 100, low 20, high 80, fill 15, drain 5, starting at level 50 with the pump on, so the level rises by 10 per tick while pumping):
- `tank_level(100, 20, 80, 15, 5, 50, True, 3)` returns `(80, False)`.
- `tank_level(100, 20, 80, 15, 5, 50, True, 15)` returns `(20, True)` (12 ticks of draining 5 per tick).
- From there the tank repeats a cycle of 18 ticks, so `tank_level(100, 20, 80, 15, 5, 50, True, 15 + 18 * 10**15 + 4)` returns `(60, True)`.
- `tank_level(100, 20, 80, 5, 5, 90, True, 10**18)` returns `(20, True)`: with the pump on the level stays at 90 for one tick (fill equals drain), the controller then switches the pump off, the tank drains to 20, the pump comes on again and from then on the level stays at 20 forever.""" + _TAIL,
    "reference": _REF_C14,
    "tests": _LCG + r'''
def _sim(capacity, low, high, fill, drain, level, on, ticks):
    for _ in range(ticks):
        level = max(0, min(capacity, level + (fill if on else 0) - drain))
        if level <= low:
            on = True
        elif level >= high:
            on = False
    return (level, on)

assert tank_level(100, 20, 80, 15, 5, 50, True, 3) == (80, False) and tank_level(100, 20, 80, 15, 5, 50, True, 15) == (20, True)
assert tank_level(100, 20, 80, 15, 5, 50, True, 15 + 18 * 10**15 + 4) == (60, True) and tank_level(100, 20, 80, 15, 5, 50, True, 0) == (50, True)
assert tank_level(100, 20, 80, 5, 5, 90, True, 10**18) == (20, True) and tank_level(100, 20, 80, 5, 5, 90, True, 1) == (90, False)
assert tank_level(100, 20, 80, 5, 5, 50, True, 10**18) == (50, True) and tank_level(100, 20, 80, 0, 0, 50, False, 10**18) == (50, False)
assert tank_level(100, 20, 80, 0, 0, 10, False, 10**18) == (10, True) and tank_level(100, 20, 80, 7, 0, 10, False, 10**18) == _sim(100, 20, 80, 7, 0, 10, False, 1000)
assert tank_level(100, 20, 80, 3, 5, 100, True, 4) == (83, False) and tank_level(100, 20, 80, 3, 5, 79, True, 4) == (71, True) and tank_level(100, 20, 80, 3, 5, 100, True, 10**18) == (0, True)
assert tank_level(100, 20, 80, 3, 5, 100, False, 10**18) == (0, True) and tank_level(100, 20, 80, 3, 5, 83, True, 2) == (76, False)
assert tank_level(100, 0, 100, 1000, 1, 0, False, 10**18) == _sim(100, 0, 100, 1000, 1, 0, False, 1 + (10**18 - 1) % 101 + 202)
assert tank_level(10**18, 10, 10**18 - 5, 1000, 1, 0, True, 10**15) == (999 * 10**15, True)
assert tank_level(10**18, 10, 10**18 - 5, 1000, 1, 0, True, 10**18) == (1001001001001000, False)
assert tank_level(10**18, 5 * 10**17, 5 * 10**17 + 1, 1000, 999, 7, False, 10**18) == (499999999999999999, True)
assert tank_level(10**18, 123456789, 123456789 + 5000, 997, 613, 10**17, True, 10**18 - 1) == (123460271, False)
assert tank_level(10**12, 10**6, 10**11, 7, 3, 10**12, False, 10**18) == (24709750000, False)
assert tank_level(1000, 300, 310, 13, 5, 0, False, 10**18) == (312, False)
assert tank_level(10**9, 0, 10**9, 1000, 999, 5 * 10**8, True, 10**18) == (503001002, True)
_g = _lcg(77)
for _case in range(300):
    _cap = 5 + next(_g) % 60
    _lo = next(_g) % _cap
    _hi = _lo + 1 + next(_g) % (_cap - _lo)
    _args = (_cap, _lo, _hi, next(_g) % 12, next(_g) % 9, next(_g) % (_cap + 1), bool(next(_g) % 2))
    for _t in (1, 2, 3, 9, 50, 333):
        assert tank_level(*_args, _t) == _sim(*_args, _t), (_args, _t)
for _case in range(40):
    _lo = next(_g) % 500
    _hi = _lo + 1 + next(_g) % 400
    _cap = _hi + next(_g) % 300
    _args = (_cap, _lo, _hi, next(_g) % 60, next(_g) % 40, next(_g) % (_cap + 1), bool(next(_g) % 2))
    assert tank_level(*_args, 5000) == _sim(*_args, 5000), _args
''',
    "wrong": _mut(_REF_C14, "                    level = min(capacity, level + need * net)", "                    level = min(high, level + need * net)"),
})


_REF_C15 = r'''
def queue_waits(pattern, period, repeats, busy_until):
    if repeats <= 0 or not pattern:
        return (0, 0)
    total = sum(s for _, s in pattern)
    pre = [0]
    alone = []                 # finish times within one repetition when the desk is free at its start
    f = 0
    for a, s in pattern:
        f = max(a, f) + s
        alone.append(f)
        pre.append(pre[-1] + s)
    end_alone = f
    drift = total - period
    floor_ = end_alone - period

    def backlog(r):
        # time (relative to the start of repetition r) at which the desk becomes free of earlier work
        if r == 0:
            return busy_until
        return max(busy_until + r * drift, floor_ + (r - 1) * max(drift, 0))

    waits = 0
    for j, (a, s) in enumerate(pattern):
        if j > 0 and alone[j - 1] > a:
            waits += repeats
            continue
        limit = a - pre[j]             # the job waits iff backlog > limit
        if drift >= 0:
            lo, hi = -1, repeats       # backlog never decreases: find the first repetition that waits
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if backlog(mid) > limit:
                    hi = mid
                else:
                    lo = mid
            waits += repeats - hi
        else:
            if busy_until > limit:
                waits += 1
            lo, hi = 0, repeats        # from repetition 1 on the backlog never increases
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if backlog(mid) > limit:
                    lo = mid
                else:
                    hi = mid
            waits += lo
    return ((repeats - 1) * period + max(backlog(repeats - 1) + total, end_alone), waits)
'''

ITEMS.append({
    "id": "C15",
    "kind": "simulation",
    "difficulty": "very hard",
    "entry_point": "queue_waits",
    "prompt": r'''Write a Python function `queue_waits(pattern: list[tuple[int, int]], period: int, repeats: int, busy_until: int) -> tuple[int, int]` about a single service desk with a repeating arrival pattern.

`pattern` is a list of `(offset, service)` pairs: integers with `0 <= offset < period`, offsets in non-decreasing order, and `service >= 1`. The pattern is repeated `repeats` times: in repetition r (r = 0, 1, ..., repeats - 1) job j arrives at time `r * period + offset_j` and needs `service_j` time units at the desk.

The desk is still occupied by older work until time `busy_until` (>= 0). After that it serves the jobs one at a time, in order of arrival (jobs of the same repetition with equal offsets in list order), without interruption and without idling when a job is present:

    start  = max(arrival, finish time of the previous job)     (for the very first job: max(arrival, busy_until))
    finish = start + service

A job WAITED if its start is strictly later than its arrival.

Return `(last_finish, waited)`: the finish time of the very last job, and the number of jobs (over all repetitions) that waited. If `repeats <= 0` or the pattern is empty, return `(0, 0)`.

Limits: up to 1000 jobs in the pattern; `period`, every `service` <= 10**9; `repeats <= 10**15`; `busy_until <= 10**18`. The total number of jobs is far too large to simulate one by one, or even repetition by repetition. Beware: a large initial backlog may melt away very slowly (by as little as one time unit per repetition), with different jobs of the pattern ceasing to wait at different repetitions; and when the pattern holds more work than fits into one period, the backlog grows forever.

Examples:
- `queue_waits([(0, 3), (2, 2), (9, 1)], 10, 1, 0)` returns `(10, 1)`: the jobs run 0-3, 3-5 (waited one unit) and 9-10. With `repeats = 1000` the result is `(10000, 1000)`: every repetition looks the same.
- `queue_waits([(0, 6), (5, 6)], 10, 3, 0)` returns `(36, 5)`. Repetition 0: 0-6 and 6-12 (second job waited). Repetition 1: arrivals 10 and 15, served 12-18 and 18-24 (both waited). Repetition 2: 24-30 and 30-36 (both waited). With `repeats = 10**15` the result is `(12 * 10**15, 2 * 10**15 - 1)`.
- `queue_waits([(0, 2), (5, 2)], 10, 4, 13)` returns `(37, 5)`: the jobs are served 13-15, 15-17, 17-19, 19-21, 21-23 (these five waited), then 25-27, 30-32, 35-37 (no waiting).''' + _TAIL,
    "reference": _REF_C15,
    "tests": _LCG + r'''
def _sim(pattern, period, repeats, busy):
    f = busy
    waited = 0
    for r in range(repeats):
        for off, s in pattern:
            a = r * period + off
            start = max(a, f)
            waited += start > a
            f = start + s
    return (f, waited)

assert queue_waits([(0, 3), (2, 2), (9, 1)], 10, 1, 0) == (10, 1) and queue_waits([(0, 3), (2, 2), (9, 1)], 10, 1000, 0) == (10000, 1000)
assert queue_waits([(0, 6), (5, 6)], 10, 3, 0) == (36, 5) and queue_waits([(0, 6), (5, 6)], 10, 10**15, 0) == (12 * 10**15, 2 * 10**15 - 1)
assert queue_waits([(0, 2), (5, 2)], 10, 4, 13) == (37, 5) and queue_waits([(0, 2), (5, 2)], 10, 1, 13) == (17, 2)
assert queue_waits([], 10, 5, 3) == (0, 0) and queue_waits([(0, 1)], 10, 0, 3) == (0, 0) and queue_waits([(3, 4)], 10, 1, 0) == (7, 0)
assert queue_waits([(3, 4)], 10, 10**15, 0) == ((10**15 - 1) * 10 + 7, 0) and queue_waits([(0, 10)], 10, 10**15, 0) == (10**16, 0)
assert queue_waits([(0, 11)], 10, 10**15, 0) == (11 * 10**15, 10**15 - 1) and queue_waits([(9, 2)], 10, 10**15, 0) == (10**16 + 1, 0)
assert queue_waits([(9, 2), (9, 1)], 10, 4, 0) == (42, 4) and queue_waits([(9, 2), (9, 1)], 10, 10**15, 0) == (10**16 + 2, 10**15)
assert queue_waits([(0, 5), (5, 5)], 10, 10**12, 0) == (10**13, 0) and queue_waits([(0, 5), (4, 6)], 10, 10**12, 0) == (11 * 10**12, 2 * 10**12 - 1)
assert queue_waits([(0, 1)], 10, 10**15, 10**9) == ((10**15 - 1) * 10 + 1, 111111112)
assert queue_waits([(0, 10)], 10, 10**15, 7) == (10**16 + 7, 10**15) and queue_waits([(0, 10)], 10, 10**15, 0) == (10**16, 0)
assert queue_waits([(5, 1)], 10, 3, 5) == (26, 0) and queue_waits([(5, 1)], 10, 3, 6) == (26, 1) and queue_waits([(5, 1)], 10, 3, 10**18) == (10**18 + 3, 3)
assert queue_waits([(0, 2), (500000000, 999999999)], 10**9, 10**15, 0) == (10**24 + 10**15 + 499999998, 2 * 10**15 - 2)
assert queue_waits([(0, 1), (7, 1), (900000, 99998)], 10**6, 10**15, 10**12) == (999999999999999999998, 3333335)
assert queue_waits([(1000, 1), (2000, 10**9 - 1001), (2000, 1), (999999999, 1000)], 10**9, 10**15 - 3, 5) == (1000000000999997000001996, 3999999999999986)
assert queue_waits([(i * 1000, 999 if i % 7 else 1000) for i in range(1000)], 10**6, 123456789012345, 10**18) == (124350986544161420335, 123456789012345000)
assert queue_waits([(i * 999983 % 10**9, 1 + i * 7919 % 2000000) for i in sorted(range(1000), key=lambda i: i * 999983 % 10**9)], 10**9, 10**15, 10**17) == (1000000000000000053288789, 943000545011234574)
assert queue_waits([(i * 999983 % 10**9, 1 + i * 7919 % 1900000) for i in sorted(range(1000), key=lambda i: i * 999983 % 10**9)], 10**9, 10**15, 10**17) == (1000000000000000017199015, 719000332707779471)
_g = _lcg(12)
for _case in range(300):
    _per = 5 + next(_g) % 30
    _pat = sorted((next(_g) % _per, 1 + next(_g) % 9) for _ in range(1 + next(_g) % 5))
    _busy = next(_g) % 4 * (next(_g) % 150)
    for _r in (1, 2, 3, 7, 40):
        assert queue_waits(_pat, _per, _r, _busy) == _sim(_pat, _per, _r, _busy), (_pat, _per, _r, _busy)
for _case in range(40):
    _per = 2000 + next(_g) % 1000
    _pat = sorted((next(_g) % _per, 1 + next(_g) % 90) for _ in range(40))
    _busy = next(_g) % 30000
    assert queue_waits(_pat, _per, 600, _busy) == _sim(_pat, _per, 600, _busy), (_pat, _per, _busy)
''',
    "wrong": _mut(_REF_C15, "        if j > 0 and alone[j - 1] > a:\n            waits += repeats\n            continue\n", ""),
})


_REF_C16 = r'''
from math import gcd

def spiral_position(n, first, grow, group, dirs):
    vec = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
    if not dirs or any(ch not in vec for ch in dirs):
        raise ValueError("bad directions")
    m = len(dirs)

    def length(j):                    # leg number j + 1
        return first + grow * (j // group)

    def total(k):                     # steps in the first k legs
        q, r = divmod(k, group)
        return k * first + grow * (group * q * (q - 1) // 2 + q * r)

    lo, hi = 0, 1
    while total(hi) <= n:
        hi *= 2
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if total(mid) <= n:
            lo = mid
        else:
            hi = mid
    legs = lo                         # complete legs
    block = m * group // gcd(m, group)
    blocks, rest = divmod(legs, block)
    # displacement of block b = base + b * (block // group) * grow * drift
    bx = by = dx = dy = 0
    for r in range(block):
        vx, vy = vec[dirs[r % m]]
        bx += vx * length(r)
        by += vy * length(r)
        dx += vx
        dy += vy
    tri = blocks * (blocks - 1) // 2
    scale = (block // group) * grow
    x = blocks * bx + tri * scale * dx
    y = blocks * by + tri * scale * dy
    for j in range(blocks * block, legs):
        vx, vy = vec[dirs[j % m]]
        x += vx * length(j)
        y += vy * length(j)
    vx, vy = vec[dirs[legs % m]]
    part = n - total(legs)
    return (x + vx * part, y + vy * part)
'''

_WRONG_C16 = r'''
def spiral_position(n, first, grow, group, dirs):
    vec = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
    if not dirs or any(ch not in vec for ch in dirs):
        raise ValueError("bad directions")
    x = y = 0
    k = 1
    while n > 0:
        length = first + grow * (k // group)      # grows one leg too early
        step = min(length, n)
        vx, vy = vec[dirs[(k - 1) % len(dirs)]]
        x += vx * step
        y += vy * step
        n -= step
        k += 1
    return (x, y)
'''

ITEMS.append({
    "id": "C16",
    "kind": "simulation",
    "difficulty": "hard",
    "entry_point": "spiral_position",
    "prompt": r"""Write a Python function `spiral_position(n: int, first: int, grow: int, group: int, dirs: str) -> tuple[int, int]` that tells where a surveying robot is after `n` steps.

The robot starts at `(0, 0)` on an infinite grid and walks in straight legs, numbered 1, 2, 3, ...:
- Leg number k is `first + grow * ((k - 1) // group)` steps long (integer division). So the first `group` legs have length `first`, the next `group` legs have length `first + grow`, and so on.
- Leg number k goes in the direction given by the character `dirs[(k - 1) % len(dirs)]`: the direction string is used cyclically. `"N"` is +y, `"S"` is -y, `"E"` is +x, `"W"` is -x. Each step moves one unit.

Return the robot's `(x, y)` after exactly `n` steps in total (the last leg may be unfinished).

`dirs` must be a non-empty string over the letters `N`, `E`, `S`, `W`; otherwise raise `ValueError`. Limits: `first >= 1`, `grow >= 0`, `1 <= group <= 50`, `len(dirs) <= 12`, and `0 <= n <= 10**50`. The number of legs can therefore be astronomically large (with `grow = 0` there are `n / first` of them), so the function must not walk leg by leg, and all arithmetic must be exact integer arithmetic - floating point is not precise enough at this size.

Examples:
- `first=1, grow=1, group=2, dirs="ENWS"` is the familiar square spiral with legs E1, N1, W2, S2, E3, N3, ...: `spiral_position(n, 1, 1, 2, "ENWS")` for n = 0, 1, 2, 4, 6, 9, 12 gives `(0, 0)`, `(1, 0)`, `(1, 1)`, `(-1, 1)`, `(-1, -1)`, `(2, -1)`, `(2, 2)`.
- `spiral_position(10, 1, 1, 1, "ENWS")` returns `(-2, -2)` (legs E1, N2, W3, S4).
- `spiral_position(7, 2, 0, 1, "EN")` returns `(4, 3)` (legs E2, N2, E2, then one step of the next N leg).
- `spiral_position(10**30, 1, 0, 1, "EEW")` returns `(333333333333333333333333333334, 0)`.""" + _TAIL,
    "reference": _REF_C16,
    "tests": _RAISES + _LCG + r'''
def _walk(n, first, grow, group, dirs):
    vec = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
    x = y = 0
    k = 1
    while n > 0:
        step = min(first + grow * ((k - 1) // group), n)
        vx, vy = vec[dirs[(k - 1) % len(dirs)]]
        x, y, n, k = x + vx * step, y + vy * step, n - step, k + 1
    return (x, y)

assert [spiral_position(n, 1, 1, 2, "ENWS") for n in (0, 1, 2, 4, 6, 9, 12)] == [(0, 0), (1, 0), (1, 1), (-1, 1), (-1, -1), (2, -1), (2, 2)]
assert spiral_position(10, 1, 1, 1, "ENWS") == (-2, -2) and spiral_position(7, 2, 0, 1, "EN") == (4, 3)
assert spiral_position(10**30, 1, 0, 1, "EEW") == (333333333333333333333333333334, 0)
assert spiral_position(10**30, 5, 0, 3, "N") == (0, 10**30) and spiral_position(0, 3, 4, 5, "S") == (0, 0)
assert spiral_position(10**30, 1, 0, 7, "ENWS") == (0, 0) and spiral_position(10**30 + 1, 1, 0, 7, "ENWS") == (1, 0)
assert spiral_position(2 * 10**24 * (2 * 10**24 + 1), 1, 1, 2, "ENWS") == (-(10**24), -(10**24))
assert spiral_position(2 * 10**24 * (2 * 10**24 + 1) + 5, 1, 1, 2, "ENWS") == (-(10**24) + 5, -(10**24))
assert spiral_position((2 * 10**14 + 1) ** 2, 1, 1, 2, "ENWS") == (10**14 + 1, -(10**14)) and spiral_position((2 * 10**14 + 1) ** 2 - 1, 1, 1, 2, "ENWS") == (10**14, -(10**14))
assert all(spiral_position(n, 1, 1, 2, "ENWS") == _walk(n, 1, 1, 2, "ENWS") for n in range(0, 300))
assert all(spiral_position(n, f, g, grp, d) == _walk(n, f, g, grp, d) for f, g, grp, d in ((3, 2, 5, "NNE"), (1, 0, 4, "ENWSE"), (2, 7, 1, "WS"), (4, 1, 50, "NESWNESWNESW"), (1, 3, 9, "SSSSEN")) for n in (0, 1, 5, 77, 1000, 4321, 99999))
_g = _lcg(8)
for _case in range(150):
    _d = "".join("NESW"[next(_g) % 4] for _ in range(1 + next(_g) % 12))
    _a = (1 + next(_g) % 5, next(_g) % 4, 1 + next(_g) % 50, _d)
    for _n in (next(_g) % 50, next(_g) % 5000, next(_g) % 200000):
        assert spiral_position(_n, *_a) == _walk(_n, *_a), (_n, _a)
assert spiral_position(10**30, 3, 2, 5, "NNE") == (333333333333333423846630002938, 666666666666666576153369997062)
assert spiral_position(10**30 - 1, 1, 3, 9, "SSSSEN") == (166666666666666653303708882769, -500000000000000040088873351692)
assert spiral_position(123456789012345678901234567890, 4, 1, 50, "NESWNESWNESW") == (-17349574721817, 35136418288203)
assert spiral_position(10**29 + 7, 1000, 0, 13, "ENWSE") == (20000000000000000000000000007, 0)
assert spiral_position(999999999999999999999999999999, 2, 7, 1, "WS") == (-500000000000000904835317284719, -499999999999999095164682715280)
assert _raises(ValueError, spiral_position, 5, 1, 1, 1, "") and _raises(ValueError, spiral_position, 5, 1, 1, 1, "NEX") and _raises(ValueError, spiral_position, 0, 1, 1, 1, "ne")
''',
    "wrong": _WRONG_C16,
})

# ---------------------------------------------------------------------------
# Kind 4: counting / combinatorial / number routines (C17-C21)
# ---------------------------------------------------------------------------

_REF_C17 = r'''
from functools import lru_cache

def kth_arrangement(letters, k):
    if k < 1:
        raise ValueError("k must be >= 1")
    kinds = sorted(set(letters))
    m = len(kinds)
    n = len(letters)
    start = tuple(letters.count(c) for c in kinds)

    @lru_cache(maxsize=None)
    def ways(cnt, last, first):
        if not any(cnt):
            return 1 if (last != first or n == 1) else 0
        total = 0
        for i in range(m):
            if cnt[i] and i != last:
                total += ways(cnt[:i] + (cnt[i] - 1,) + cnt[i + 1:], i, first)
        return total

    out = []
    cnt, last, first = start, -1, -1
    for pos in range(n):
        for i in range(m):
            if not cnt[i] or i == last:
                continue
            nxt = cnt[:i] + (cnt[i] - 1,) + cnt[i + 1:]
            w = ways(nxt, i, i if pos == 0 else first)
            if k <= w:
                out.append(kinds[i])
                cnt, last = nxt, i
                if pos == 0:
                    first = i
                break
            k -= w
        else:
            return None
    return "".join(out)
'''

ITEMS.append({
    "id": "C17",
    "kind": "counting",
    "difficulty": "very hard",
    "entry_point": "kth_arrangement",
    "prompt": r"""Write a Python function `kth_arrangement(letters: str, k: int)`.

`letters` is a non-empty string of lowercase letters, possibly with repeats, e.g. `"aabbc"`. An ARRANGEMENT is a string that uses exactly these letters (each as often as it occurs in `letters`), written around a bracelet: the last letter is also a neighbour of the first. An arrangement is VALID when no two neighbouring letters are equal - that is, no two adjacent letters of the string are equal AND, if the string has two or more letters, its first and last letters differ. (A one-letter string is valid.)

Two arrangements are the same if they are the same string; rotations of a bracelet count as different strings. Consider all distinct valid arrangements sorted in ordinary lexicographic order. Return the k-th one (k = 1 is the first). If there are fewer than k valid arrangements, return `None`. If `k < 1`, raise `ValueError`.

Limits: `letters` has at most 28 letters and at most 4 distinct letters. The number of valid arrangements can exceed 10**11, so they cannot be generated one by one: count with dynamic programming and build the answer letter by letter.

Examples:
- `kth_arrangement("aabb", 1)` returns `"abab"`, `kth_arrangement("aabb", 2)` returns `"baba"`, and `kth_arrangement("aabb", 3)` returns `None`.
- `kth_arrangement("aab", 1)` returns `None` (`aba` is not valid: first and last are both `a`).
- `kth_arrangement("cba", 4)` returns `"bca"` (all six orders of three different letters are valid).
- `kth_arrangement("aabbc", k)` for k = 1..10 gives `ababc`, `abacb`, `abcab`, `acbab`, `babac`, `babca`, `bacba`, `bcaba`, `cabab`, `cbaba` (for instance `bacab` is missing because it starts and ends with `b`).""" + _TAIL,
    "reference": _REF_C17,
    "tests": _RAISES + r'''
from itertools import permutations as _perms

def _all(letters):
    out = set()
    for p in _perms(letters):
        s = "".join(p)
        if all(s[i] != s[i + 1] for i in range(len(s) - 1)) and (len(s) == 1 or s[0] != s[-1]):
            out.add(s)
    return sorted(out)

assert kth_arrangement("aabb", 1) == "abab" and kth_arrangement("aabb", 2) == "baba" and kth_arrangement("aabb", 3) is None
assert kth_arrangement("aab", 1) is None and kth_arrangement("cba", 4) == "bca" and kth_arrangement("cba", 7) is None
assert [kth_arrangement("aabbc", k) for k in range(1, 12)] == ["ababc", "abacb", "abcab", "acbab", "babac", "babca", "bacba", "bcaba", "cabab", "cbaba", None]
assert kth_arrangement("a", 1) == "a" and kth_arrangement("a", 2) is None and kth_arrangement("aa", 1) is None and kth_arrangement("ba", 2) == "ba"
assert kth_arrangement("zzzz", 1) is None and kth_arrangement("aaab", 1) is None and kth_arrangement("ababab", 2) == "bababa"
assert _raises(ValueError, kth_arrangement, "abc", 0) and _raises(ValueError, kth_arrangement, "aa", -3)
for _letters in ("aabbc", "abcd", "aabbcc", "aaabbbc", "aabbccdd", "aaabcd", "abbbccd", "aaaabbcd", "xxyyzzz"):
    _exp = _all(_letters)
    assert [kth_arrangement(_letters, k) for k in range(1, len(_exp) + 2)] == _exp + [None], _letters
assert len(_all("aabbccdd")) == 744 and kth_arrangement("ddccbbaa", 744) == _all("aabbccdd")[-1] == "dcdcbaba"
_L = "a" * 7 + "b" * 7 + "c" * 7 + "d" * 7
assert kth_arrangement(_L, 1) == 'abababababababcdcdcdcdcdcdcd'
assert kth_arrangement(_L, 10**11) == 'adcbadbdcbacdacdbdababcdcacb'
assert kth_arrangement(_L, 135790246813) == 'badbcadcdacabacbdcbadbdcdbac'
assert kth_arrangement(_L, 428434032456) == 'dcdcdcdcdcdcdcbababababababa'
assert kth_arrangement(_L, 428434032457) is None and kth_arrangement(_L, 10**15) is None
assert kth_arrangement("a" * 14 + "b" * 14, 2) == "ba" * 14 and kth_arrangement("a" * 14 + "b" * 14, 3) is None
assert kth_arrangement("a" * 12 + "b" * 9 + "c" * 6, 1) == 'ababababababababcacacacacbc'
assert kth_arrangement("a" * 12 + "b" * 9 + "c" * 6, 40000) == 'ababacabacbabababacacbcabac'
assert kth_arrangement("a" * 13 + "b" * 9 + "c" * 4, 1) == 'abababababababababacacacac'
assert kth_arrangement("a" * 13 + "b" * 9 + "c" * 4, 716) == "ba" * 9 + "ca" * 4 and kth_arrangement("a" * 13 + "b" * 9 + "c" * 4, 1430) == "ca" * 4 + "ba" * 9
assert kth_arrangement("a" * 13 + "b" * 9 + "c" * 4, 1431) is None
_lo, _hi = 1, 10**16
while _hi - _lo > 1:
    _mid = (_lo + _hi) // 2
    if kth_arrangement("aaaabbbbbccccccddd", _mid) is None:
        _hi = _mid
    else:
        _lo = _mid
assert _lo == 4858758
assert kth_arrangement("aaaabbbbbccccccddd", _lo) == 'dcdcdcbcbcbacababa'
''',
    "wrong": _mut(_REF_C17, "            return 1 if (last != first or n == 1) else 0", "            return 1"),
})


_REF_C18 = r'''
from functools import lru_cache

def count_peaky(lo, hi, peaks, q, t):
    @lru_cache(maxsize=None)
    def free(rem, last, rising, p, v):
        if rem == 0:
            return 1 if (p == peaks and v == t) else 0
        total = 0
        for d in range(10):
            p2 = p + (1 if rising and d < last else 0)
            if p2 > peaks:
                continue
            total += free(rem - 1, d, d > last, p2, (v * 10 + d) % q)
        return total

    def upto(n):
        if n < 0:
            return 0
        digits = [int(c) for c in str(n)]
        total = 1 if (peaks == 0 and t == 0) else 0           # the number 0
        for length in range(1, len(digits)):
            for d in range(1, 10):
                total += free(length - 1, d, False, 0, d % q)
        # same length as n
        last, rising, p, v = None, False, 0, 0
        for i, cur in enumerate(digits):
            rem = len(digits) - i - 1
            for d in range(1 if i == 0 else 0, cur):
                if i == 0:
                    total += free(rem, d, False, 0, d % q)
                else:
                    p2 = p + (1 if rising and d < last else 0)
                    if p2 <= peaks:
                        total += free(rem, d, d > last, p2, (v * 10 + d) % q)
            if i > 0:
                p += 1 if rising and cur < last else 0
                rising = cur > last
            last = cur
            v = (v * 10 + cur) % q
        if n > 0 and p == peaks and v == t:
            total += 1
        return total

    if lo > hi:
        return 0
    return upto(hi) - upto(lo - 1)
'''

ITEMS.append({
    "id": "C18",
    "kind": "counting",
    "difficulty": "very hard",
    "entry_point": "count_peaky",
    "prompt": r"""Write a Python function `count_peaky(lo: int, hi: int, peaks: int, q: int, t: int) -> int` that counts integers with a given digit shape.

Write a non-negative integer n in decimal without leading zeros (the number 0 is the single digit `0`). A digit of n is a PEAK if it has a neighbour on both sides and is strictly greater than both of them. The first and the last digit are never peaks, so numbers with one or two digits have no peaks. For example 1320 has one peak (the 3), 13231 has two (both 3s), 1332 has none (the 3s are not strictly greater than each other), 90909 has one (the middle 9).

Return how many integers n with `lo <= n <= hi` satisfy both
1. n has exactly `peaks` peaks, and
2. `n % q == t`.

Limits: `0 <= lo`, `hi <= 10**15`, `0 <= peaks <= 7`, `1 <= q <= 12`, `0 <= t < q`. If `lo > hi` return 0. The range can contain 10**15 numbers, so they cannot be examined one by one; a digit-by-digit dynamic programme is needed, and the whole call should take well under a second.

Examples:
- `count_peaky(0, 99, 0, 1, 0)` returns 100 and `count_peaky(0, 99, 1, 1, 0)` returns 0.
- `count_peaky(100, 199, 1, 1, 0)` returns 44: the numbers 1bc with b > 1 and b > c; for b = 2..9 there are b choices of c, and 2 + 3 + ... + 9 = 44.
- `count_peaky(120, 131, 1, 2, 0)` returns 2: the numbers with one peak in that range are 120, 121, 130 and 131, and only 120 and 130 are even.""" + _TAIL,
    "reference": _REF_C18,
    "tests": r'''
def _peaks(n):
    s = str(n)
    return sum(1 for i in range(1, len(s) - 1) if s[i] > s[i - 1] and s[i] > s[i + 1])

def _slow(lo, hi, peaks, q, t):
    return sum(1 for n in range(lo, hi + 1) if n % q == t and _peaks(n) == peaks)

assert count_peaky(0, 99, 0, 1, 0) == 100 and count_peaky(0, 99, 1, 1, 0) == 0
assert count_peaky(100, 199, 1, 1, 0) == 44 and count_peaky(120, 131, 1, 2, 0) == 2
assert count_peaky(0, 0, 0, 1, 0) == 1 and count_peaky(0, 0, 0, 7, 0) == 1 and count_peaky(0, 0, 0, 7, 3) == 0 and count_peaky(0, 0, 1, 1, 0) == 0
assert count_peaky(5, 4, 0, 1, 0) == 0 and count_peaky(13231, 13231, 2, 1, 0) == 1 and count_peaky(1332, 1332, 0, 3, 0) == 1 and count_peaky(90909, 90909, 1, 1, 0) == 1
assert count_peaky(0, 999, 1, 1, 0) == _slow(0, 999, 1, 1, 0) == 240
assert all(count_peaky(0, 99999, p, 1, 0) == _slow(0, 99999, p, 1, 0) for p in (0, 1, 2, 3))
assert all(count_peaky(lo, hi, p, q, t) == _slow(lo, hi, p, q, t) for lo, hi in ((1, 54321), (999, 100001), (70707, 70999), (9, 10), (12345, 67890)) for p, q, t in ((0, 7, 3), (1, 12, 11), (2, 5, 0), (1, 2, 1)))
assert all(count_peaky(n, n, _peaks(n), 9, n % 9) == 1 and count_peaky(n, n, _peaks(n) + 1, 9, n % 9) == 0 for n in (0, 7, 10, 101, 1210, 98789, 123454321, 10**15, 919191919191919))
assert sum(count_peaky(0, 10**15, p, 1, 0) for p in range(8)) == 10**15 + 1
assert sum(count_peaky(0, 10**12, 3, 3, t) for t in range(3)) == count_peaky(0, 10**12, 3, 1, 0)
assert count_peaky(0, 10**15, 0, 1, 0) == 1944918481339
assert count_peaky(0, 987654321012345, 4, 7, 5) == 50302866395214
assert count_peaky(1, 10**15 - 1, 7, 5, 1) == 136419137858
assert count_peaky(1, 999999999999, 2, 4, 3) == 69707381794
assert count_peaky(55555, 444444444444444, 6, 1, 0) == 14932034538934
''',
    "wrong": _mut(_REF_C18, "            p2 = p + (1 if rising and d < last else 0)\n            if p2 > peaks:", "            p2 = p + (1 if rising and d <= last else 0)\n            if p2 > peaks:"),
})


_REF_C19 = r'''
from math import gcd

def kth_chime(k, ring, mute):
    if k < 1:
        raise ValueError("k must be >= 1")
    ring = sorted(set(ring))
    mute = sorted(set(mute))
    if all(any(r % m == 0 for m in mute) for r in ring):
        return None

    def subsets(values):
        out = [(1, 1)]                       # (lcm, sign)
        for v in values:
            out += [(l * v // gcd(l, v), -s) for l, s in out]
        return out

    terms = {}
    for lm, sm in subsets(mute):
        for lr, sr in subsets(ring)[1:]:
            l = lm * lr // gcd(lm, lr)
            terms[l] = terms.get(l, 0) - sm * sr
    terms = [(l, c) for l, c in terms.items() if c]

    def count(n):
        return sum(c * (n // l) for l, c in terms)

    hi = 1
    while count(hi) < k:
        hi *= 2
    lo = 0
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if count(mid) >= k:
            hi = mid
        else:
            lo = mid
    return hi
'''

ITEMS.append({
    "id": "C19",
    "kind": "counting",
    "difficulty": "very hard",
    "entry_point": "kth_chime",
    "prompt": r"""Write a Python function `kth_chime(k: int, ring: list[int], mute: list[int])`.

A clock tower counts the hours 1, 2, 3, ... forever. In hour number x the bell CHIMES when
- x is divisible by at least one number in `ring`, and
- x is not divisible by any number in `mute`.

Return the k-th hour in which the bell chimes (k = 1 gives the first such hour). If the bell never chimes at all, return `None`. If `k < 1`, raise `ValueError`.

Limits: `ring` has 1 to 6 numbers, `mute` has 0 to 6 numbers, every number is between 2 and 60 (lists may contain duplicates, which change nothing); `k` can be as large as 10**15. The answer can therefore be around 10**17, and the pattern of chimes repeats only after the least common multiple of all the numbers, which can exceed 10**10 - so neither stepping through the hours nor tabulating one full period is feasible. The call must finish in well under a second.

Examples:
- `kth_chime(1, [4, 6], [8])` returns 4 and `kth_chime(5, [4, 6], [8])` returns 20: the chiming hours are 4, 6, 12, 18, 20, 28, 30, ... (8, 16, 24 are muted).
- `kth_chime(10**15, [6], [4])` returns `12 * 10**15 - 6` (the hours 6, 18, 30, ...).
- `kth_chime(1, [6, 10], [2])` returns `None`: every multiple of 6 or 10 is even.
- `kth_chime(3, [6, 9], [3, 4])` returns `None` as well, but `kth_chime(3, [6, 9], [4])` returns 18 (hours 6, 9, 18, ...).""" + _TAIL,
    "reference": _REF_C19,
    "tests": _RAISES + r'''
def _slow(k, ring, mute, limit=200000):
    for x in range(1, limit):
        if any(x % r == 0 for r in ring) and not any(x % m == 0 for m in mute):
            k -= 1
            if k == 0:
                return x
    return None

assert kth_chime(1, [4, 6], [8]) == 4 and kth_chime(5, [4, 6], [8]) == 20 and kth_chime(7, [4, 6], [8]) == 30
assert kth_chime(10**15, [6], [4]) == 12 * 10**15 - 6 and kth_chime(1, [6], [4]) == 6
assert kth_chime(1, [6, 10], [2]) is None and kth_chime(3, [6, 9], [3, 4]) is None and kth_chime(3, [6, 9], [4]) == 18
assert kth_chime(10**15, [7], []) == 7 * 10**15 and kth_chime(10**15, [2, 2, 2], []) == 2 * 10**15
assert kth_chime(10**15, [2, 3], []) == 3 * 10**15 // 2 and kth_chime(4, [2, 3], []) == 6 and kth_chime(5, [2, 3], []) == 8
assert kth_chime(10**15, [60], [60]) is None and kth_chime(1, [60, 59], [60]) == 59 and kth_chime(60, [60, 59], [60]) == 59 * 61
assert kth_chime(2, [5], [10, 15]) == 25 and kth_chime(10**15, [5], [10, 15]) == 15 * 10**15 - 5
assert kth_chime(1, [12], [8, 9]) == 12 and kth_chime(3, [12], [8, 9]) == 84 and kth_chime(1, [36], [8, 9]) is None
assert all(kth_chime(k, r, m) == _slow(k, r, m) for r, m in (([4, 6, 9], [5, 8]), ([7, 11, 13], [2]), ([2], [3, 5, 7]), ([10, 15, 21, 35], [4, 9, 25, 49]), ([6, 10, 14, 15], [12, 20, 28, 30, 9, 49]), ([30, 42, 2, 9, 5, 60], [8, 27])) for k in (1, 2, 3, 10, 57, 400, 2999))
assert kth_chime(10**15, [4, 6, 9], [5, 8]) == 4736842105263156
assert kth_chime(10**15, [53, 59, 47, 43, 41, 37], [31, 29, 23, 19, 17, 13]) == 10895329640197872
assert kth_chime(999999999999989, [32, 27, 25, 49, 11, 13], [64, 81, 17, 19, 23, 58]) == 5057590357664271
assert kth_chime(123456789012345, [6, 10, 14, 15], [12, 20, 28, 30, 9, 49]) == 1080246903858010
assert kth_chime(10**15, [60, 59, 58, 57, 56, 55], [54, 53, 52, 51, 50, 49]) == 13042419904786443
assert kth_chime(10**15 - 1, [2], [3, 5, 7, 11, 13, 17]) == 5539388020833328
assert _raises(ValueError, kth_chime, 0, [4], []) and _raises(ValueError, kth_chime, -1, [6], [2])
''',
    "wrong": _mut(_REF_C19, "    if all(any(r % m == 0 for m in mute) for r in ring):", "    if any(any(r % m == 0 for m in mute) for r in ring):"),
})


_REF_C20 = r'''
import heapq
from math import gcd

def count_packable(sizes, lo, hi):
    g = 0
    for s in sizes:
        g = gcd(g, s)
    units = sorted(set(s // g for s in sizes))
    base = units[0]
    dist = [None] * base
    dist[0] = 0
    heap = [(0, 0)]
    while heap:
        d, r = heapq.heappop(heap)
        if dist[r] != d:
            continue
        for u in units[1:]:
            nd = d + u
            nr = nd % base
            if dist[nr] is None or nd < dist[nr]:
                dist[nr] = nd
                heapq.heappush(heap, (nd, nr))

    def upto(n):
        if n < 0:
            return 0
        m = n // g
        return sum((m - d) // base + 1 for d in dist if d is not None and d <= m)

    if lo > hi:
        return 0
    return upto(hi) - upto(lo - 1)
'''

ITEMS.append({
    "id": "C20",
    "kind": "counting",
    "difficulty": "very hard",
    "entry_point": "count_packable",
    "prompt": r"""Write a Python function `count_packable(sizes: list[int], lo: int, hi: int) -> int`.

A warehouse ships goods in crates. `sizes` lists the available crate sizes (positive integers; duplicates may occur and change nothing); there is an unlimited supply of every size. A quantity n is PACKABLE if it can be shipped exactly, i.e. n is a sum of crate sizes with repetition allowed: `n = c1 * sizes[0] + c2 * sizes[1] + ...` with integer counts `c >= 0`. The quantity 0 is packable (no crates).

Return how many integers n with `lo <= n <= hi` are packable (`lo >= 0`; if `lo > hi` return 0).

Limits: 1 to 5 sizes; the SMALLEST size is at most 5,000 but the other sizes can be as large as 10**9; `hi` can be as large as 10**18. So you can neither test the quantities one by one nor build a table up to `hi`, and even a table up to (smallest size) x (largest size) is far too big. The call must finish in about a second.

Examples:
- `count_packable([3, 5], 0, 10)` returns 7 (packable: 0, 3, 5, 6, 8, 9, 10).
- `count_packable([3, 5], 8, 10**18)` returns `10**18 - 7` (every n >= 8 is packable).
- `count_packable([4, 6], 1, 20)` returns 9 (the even numbers from 4 to 20).
- `count_packable([6, 10, 15], 0, 30)` returns 16 (0, 6, 10, 12, 15, 16, 18, 20, 21, 22, 24, 25, 26, 27, 28, 30; note that 29 is not packable).""" + _TAIL,
    "reference": _REF_C20,
    "tests": _LCG + r'''
def _table(sizes, limit):
    ok = [False] * (limit + 1)
    ok[0] = True
    for n in range(1, limit + 1):
        ok[n] = any(n >= s and ok[n - s] for s in sizes)
    return ok

def _slow(sizes, lo, hi):
    return sum(_table(sizes, hi)[lo:hi + 1])

assert count_packable([3, 5], 0, 10) == 7 and count_packable([3, 5], 8, 10**18) == 10**18 - 7 and count_packable([3, 5], 0, 10**18) == 10**18 - 3
assert count_packable([4, 6], 1, 20) == 9 and count_packable([6, 10, 15], 0, 30) == 16 and count_packable([6, 10, 15], 29, 29) == 0
assert count_packable([7], 0, 10**18) == 10**18 // 7 + 1 and count_packable([7, 7, 14], 1, 70) == 10 and count_packable([1, 10**9], 5, 10**18) == 10**18 - 4
assert count_packable([5, 3], 7, 7) == 0 and count_packable([5, 3], 9, 4) == 0 and count_packable([2, 10**9], 0, 0) == 1 and count_packable([2, 10**9], 1, 1) == 0
assert count_packable([2, 10**9 - 1], 0, 2 * 10**9 + 2) == 10**9 + 2 + 5 * 10**8 + 2
assert count_packable([1000, 1001], 0, 10**18) == 10**18 + 1 - 999 * 1000 // 2
assert count_packable([4999, 5000], 0, 4999 * 5000) == 4999 * 5000 + 1 - (4998 * 4999) // 2
assert count_packable([10, 15, 25], 0, 10**18) == 10**18 // 5 and count_packable([10, 15, 25], 0, 24) == 4
assert all(count_packable(sz, lo, hi) == _slow(sz, lo, hi) for sz in ([3, 5], [4, 6, 9], [6, 9, 20], [5, 8, 13, 21], [12, 18, 30, 45], [7, 11, 13, 17, 19], [2, 3], [9, 9, 9]) for lo, hi in ((0, 0), (0, 1), (1, 50), (17, 300), (43, 44), (0, 999)))
_g = _lcg(321)
for _case in range(40):
    _sz = [2 + next(_g) % 60 for _ in range(1 + next(_g) % 5)]
    _lo = next(_g) % 400
    _hi = _lo + next(_g) % 3000
    assert count_packable(_sz, _lo, _hi) == _slow(_sz, _lo, _hi), (_sz, _lo, _hi)
_tab = _table([97, 1009, 2003], 300000)
assert count_packable([97, 1009, 2003], 0, 300000) == sum(_tab) and count_packable([2003, 97, 1009], 12345, 23456) == sum(_tab[12345:23457])
assert count_packable([4999, 10**9 - 1, 10**9 - 7, 999999937], 0, 10**18) == 999999954403284240
assert count_packable([4999, 10**9 - 1, 10**9 - 7, 999999937], 10**11, 2 * 10**11) == 100000000001
assert count_packable([5000, 750000000, 999999990, 123456780], 1, 10**18) == 99999999283541025
assert count_packable([4096, 6561, 15625, 16807, 14641], 0, 10**7) == 9779443
assert count_packable([3989, 3989 * 4001, 4001 * 4003, 4003 * 3989 + 1], 10**6, 10**17 + 12345) == 99999998933111500
''',
    "wrong": _mut(_REF_C20, "if d is not None and d <= m)", "if d is not None and d < m)"),
})


_REF_C21 = r'''
from math import gcd

def next_alignment(gears, t0):
    classes = [(0, 1)]                       # (residue, modulus)
    for period, start, width in gears:
        merged = set()
        for r1, m1 in classes:
            g = gcd(m1, period)
            lcm = m1 // g * period
            step = period // g
            inv = pow(m1 // g, -1, step) if step > 1 else 0
            for j in range(width):
                r2 = (start + j) % period
                diff = r2 - r1
                if diff % g:
                    continue
                k = (diff // g * inv) % step
                merged.add(((r1 + m1 * k) % lcm, lcm))
        classes = list(merged)
        if not classes:
            return None
    return min(t0 + (r - t0) % m for r, m in classes)
'''

ITEMS.append({
    "id": "C21",
    "kind": "counting",
    "difficulty": "very hard",
    "entry_point": "next_alignment",
    "prompt": r"""Write a Python function `next_alignment(gears: list[tuple[int, int, int]], t0: int)`.

A lock has several gears. Gear i is `(period, start, width)` with integers `period >= 1`, `0 <= start < period`, `1 <= width <= period`. At integer time t (t can be any integer >= 0) the gear is OPEN when

    (t - start) % period < width

i.e. it opens at times start, start + period, start + 2*period, ... and each time stays open for `width` consecutive time units (the open window may wrap past a multiple of the period). The lock can be turned at time t when ALL gears are open at t.

Return the smallest integer `t >= t0` at which the lock can be turned, or `None` if there is no such time. (`t0 >= 0`; with an empty list of gears the answer is `t0`.)

Limits: at most 6 gears; periods up to 10**9 and NOT necessarily coprime to each other; `t0` up to 10**18; the product of all the widths is at most 20,000. The answer can be astronomically large (the combined pattern repeats only after the least common multiple of the periods, up to about 10**54), so stepping through time is impossible - the function has to work with congruences, and must correctly detect when no solution exists. It must finish in about a second.

Examples:
- `next_alignment([(4, 1, 1), (6, 3, 1)], 0)` returns 9, and with `t0 = 10` it returns 21 (t must be 1 mod 4 and 3 mod 6; the pattern repeats every 12).
- `next_alignment([(4, 0, 1), (6, 3, 1)], 0)` returns `None` (t would have to be even and odd).
- `next_alignment([(4, 0, 1), (6, 3, 2)], 0)` returns 4 (gear 2 is open when t % 6 is 3 or 4).
- `next_alignment([(10, 8, 4)], 12)` returns 18 and `next_alignment([(10, 8, 4)], 20)` returns 20 (open when t % 10 is 8, 9, 0 or 1).""" + _TAIL,
    "reference": _REF_C21,
    "tests": _LCG + r'''
def _scan(gears, t0, limit):
    for t in range(t0, t0 + limit):
        if all((t - s) % p < w for p, s, w in gears):
            return t
    return None

assert next_alignment([(4, 1, 1), (6, 3, 1)], 0) == 9 and next_alignment([(4, 1, 1), (6, 3, 1)], 10) == 21 and next_alignment([(4, 1, 1), (6, 3, 1)], 9) == 9
assert next_alignment([(4, 0, 1), (6, 3, 1)], 0) is None and next_alignment([(4, 0, 1), (6, 3, 2)], 0) == 4
assert next_alignment([(10, 8, 4)], 12) == 18 and next_alignment([(10, 8, 4)], 20) == 20 and next_alignment([(10, 8, 4)], 22) == 28
assert next_alignment([], 77) == 77 and next_alignment([(1, 0, 1)], 10**18) == 10**18 and next_alignment([(5, 0, 5), (7, 6, 7)], 123) == 123
assert next_alignment([(7, 3, 1)], 10**18) == 10**18 + (3 - 10**18) % 7 and next_alignment([(10**9, 5, 1)], 6) == 10**9 + 5
assert next_alignment([(3, 2, 1), (5, 3, 1), (7, 2, 1)], 0) == 23 and next_alignment([(3, 2, 1), (5, 3, 1), (7, 2, 1)], 24) == 128
assert next_alignment([(6, 1, 1), (10, 3, 1), (15, 13, 1)], 0) == 13 and next_alignment([(6, 1, 1), (10, 3, 1), (15, 12, 1)], 0) is None
assert next_alignment([(12, 0, 1), (18, 6, 1)], 1) == 24 and next_alignment([(12, 0, 1), (18, 5, 1)], 1) is None and next_alignment([(12, 0, 2), (18, 5, 8)], 1) == 12
assert next_alignment([(10**9, 0, 1), (10**9 - 1, 0, 1)], 1) == 10**9 * (10**9 - 1)
assert next_alignment([(10**9, 7, 1), (10**9, 7, 1), (5 * 10**8, 7, 3)], 10**18) == 10**18 + 7 and next_alignment([(10**9, 7, 1), (5 * 10**8, 8, 3)], 0) is None
_g = _lcg(2718)
for _case in range(150):
    _gs = []
    for _ in range(1 + next(_g) % 4):
        _p = 1 + next(_g) % 12
        _gs.append((_p, next(_g) % _p, 1 + next(_g) % min(_p, 3)))
    _t0 = next(_g) % 100
    assert next_alignment(_gs, _t0) == _scan(_gs, _t0, 30000), (_gs, _t0)
assert next_alignment([(999999937, 12345, 3), (999999893, 999999892, 2), (10**9, 500, 10), (999999999, 0, 5)], 10**18) == 1545184324303292674151018000000507
assert next_alignment([(2**29, 1, 4), (3**18, 7, 4), (5**12, 100, 5), (7**10, 6, 5), (11**8, 0, 5), (13**8, 2, 10)], 10**18) == 68183349194288254154834447438192263851562500100
assert next_alignment([(6 * 10**8, 599999999, 20), (9 * 10**8, 3, 10), (4 * 10**8, 399999990, 100)], 123456789012345678) == 123456790800000003
assert next_alignment([(720720, 5, 2), (360360 * 3, 720725, 2), (10**9, 999999995, 3), (999999000, 500, 60)], 0) == None
assert next_alignment([(10**9, 0, 100), (10**9 - 2, 0, 100), (10**9 - 4, 10**9 - 5, 2)], 5 * 10**17) == 999999971000000099
''',
    "wrong": _mut(_REF_C21, "    return min(t0 + (r - t0) % m for r, m in classes)", "    return min(r if r >= t0 else r + ((t0 - r) // m + 1) * m for r, m in classes)"),
})

# ---------------------------------------------------------------------------
# Kind 5: graph / grid search with state (C22-C26)
# ---------------------------------------------------------------------------

_REF_C22 = r'''
def ferry_plan(routes, src, dst, t0):
    if src == dst:
        return (t0, 0)
    ports = {src, dst}
    for a, b, _, _, _ in routes:
        ports.add(a)
        ports.add(b)
    best = {src: t0}                 # earliest arrival using at most k ferries
    history = []
    for _ in range(len(ports) - 1):
        new = dict(best)
        for a, b, first, every, duration in routes:
            if a not in best:
                continue
            t = best[a]
            if t <= first:
                dep = first
            else:
                dep = first + -(-(t - first) // every) * every
            arr = dep + duration
            if b not in new or arr < new[b]:
                new[b] = arr
        best = new
        history.append(best.get(dst))
    final = history[-1]
    if final is None:
        return None
    return (final, history.index(final) + 1)
'''

ITEMS.append({
    "id": "C22",
    "kind": "graph",
    "difficulty": "very hard",
    "entry_point": "ferry_plan",
    "prompt": r"""Write a Python function `ferry_plan(routes: list[tuple[str, str, int, int, int]], src: str, dst: str, t0: int)` that plans a trip through an archipelago.

Each route is `(a, b, first, every, duration)`: a ferry sails one way from port `a` to port `b`, departing at the times `first`, `first + every`, `first + 2 * every`, ... (integers, `first >= 0`, `every >= 1`), and each sailing arrives `duration >= 1` time units after it departs. Several routes may connect the same pair of ports. A route with `a == b` may occur and is useless.

A traveller is at port `src` at time `t0`. They may wait at a port for any length of time, and may board a sailing that departs at the very moment they arrive (changing ferries takes no time).

Return `(arrival, ferries)` where
- `arrival` is the earliest possible time of arrival at `dst`, and
- `ferries` is the smallest number of sailings used by any itinerary that arrives at `dst` at exactly that earliest time.
If `src == dst` return `(t0, 0)`. If `dst` cannot be reached return `None`.

Be careful with the second number: the itinerary with the fewest sailings is not necessarily one that reaches every intermediate port as early as possible. Arriving somewhere later, but with fewer sailings, can still catch the same final ferry.

Limits: up to 60 ports and 400 routes; times up to 10**12.

Examples:
- `ferry_plan([("A", "B", 0, 10, 5), ("B", "C", 6, 10, 5), ("A", "C", 0, 100, 30)], "A", "C", 0)` returns `(11, 2)`; starting at `t0 = 1` it returns `(21, 2)` (leave A at 10, reach B at 15, leave B at 16).
- With routes `[("A", "P", 0, 1, 1), ("P", "Q", 1, 1, 1), ("Q", "X", 2, 1, 1), ("A", "X", 0, 100, 7), ("X", "D", 10, 100, 5)]`, `ferry_plan(routes, "A", "D", 0)` returns `(15, 2)`: X can be reached at time 3 with three sailings or at time 7 with one, and both catch the sailing that leaves X at 10.
- `ferry_plan([("A", "B", 0, 10, 5)], "B", "A", 0)` returns `None`.""" + _TAIL,
    "reference": _REF_C22,
    "tests": _LCG + r'''
def _paths(routes, src, dst, t0):
    """Exhaustive search over itineraries that never visit a port twice."""
    best = [None]
    def go(port, t, legs, seen):
        if port == dst:
            cand = (t, legs)
            if best[0] is None or cand < best[0]:
                best[0] = cand
            return
        for a, b, first, every, dur in routes:
            if a == port and b not in seen:
                dep = first if t <= first else t + (first - t) % every
                go(b, dep + dur, legs + 1, seen | {b})
    go(src, t0, 0, {src})
    return best[0]

_r1 = [("A", "B", 0, 10, 5), ("B", "C", 6, 10, 5), ("A", "C", 0, 100, 30)]
assert ferry_plan(_r1, "A", "C", 0) == (11, 2) and ferry_plan(_r1, "A", "C", 1) == (21, 2) and ferry_plan(_r1, "A", "C", 7) == (21, 2)
assert ferry_plan(_r1, "A", "C", 91) == (111, 2) and ferry_plan(_r1, "A", "C", 100) == (111, 2) and ferry_plan(_r1, "B", "C", 16) == (21, 1)
_r2 = [("A", "P", 0, 1, 1), ("P", "Q", 1, 1, 1), ("Q", "X", 2, 1, 1), ("A", "X", 0, 100, 7), ("X", "D", 10, 100, 5)]
assert ferry_plan(_r2, "A", "D", 0) == (15, 2) and ferry_plan(_r2, "A", "X", 0) == (3, 3) and ferry_plan(_r2, "A", "D", 1) == (15, 4)
assert ferry_plan(_r2, "A", "D", 8) == (115, 2) and ferry_plan(_r2, "A", "D", 101) == (115, 4) and ferry_plan(_r2, "A", "D", 100) == (115, 2)
assert ferry_plan([("A", "B", 0, 10, 5)], "B", "A", 0) is None and ferry_plan([], "A", "A", 9) == (9, 0) and ferry_plan([], "A", "B", 9) is None
assert ferry_plan([("A", "B", 0, 10, 5)], "A", "Z", 0) is None and ferry_plan([("A", "A", 0, 1, 1), ("A", "B", 3, 5, 2)], "A", "B", 4) == (10, 1)
assert ferry_plan([("A", "B", 5, 7, 3), ("A", "B", 6, 100, 1)], "A", "B", 0) == (7, 1) and ferry_plan([("A", "B", 5, 7, 3), ("A", "B", 6, 100, 1)], "A", "B", 7) == (15, 1)
assert ferry_plan([("A", "B", 10**12 - 1, 1, 1), ("B", "C", 0, 10**12, 1)], "A", "C", 5) == (10**12 + 1, 2)
assert ferry_plan([("A", "B", 0, 3, 10**11), ("B", "C", 0, 7, 10**11), ("C", "D", 0, 11, 10**11)], "A", "D", 10**12) == _paths([("A", "B", 0, 3, 10**11), ("B", "C", 0, 7, 10**11), ("C", "D", 0, 11, 10**11)], "A", "D", 10**12)
_r3 = [("S", "a", 0, 1, 1), ("a", "b", 0, 1, 1), ("b", "c", 0, 1, 1), ("c", "M", 0, 1, 1), ("S", "M", 0, 50, 9), ("M", "d", 10, 50, 1), ("d", "e", 0, 1, 1), ("e", "N", 0, 1, 1), ("M", "N", 10, 50, 8), ("N", "T", 20, 50, 1)]
assert ferry_plan(_r3, "S", "T", 0) == (21, 3) and ferry_plan(_r3, "S", "N", 0) == (13, 4) and ferry_plan(_r3, "S", "M", 0) == (4, 4)
_r4 = [("A", "B", 0, 5, 2), ("B", "A", 1, 5, 2), ("B", "C", 4, 9, 3), ("C", "A", 0, 4, 1), ("A", "C", 2, 20, 9)]
assert all(ferry_plan(_r4, s, d, t) == _paths(_r4, s, d, t) for s in "ABC" for d in "ABC" if s != d for t in range(0, 40, 3))
_g = _lcg(1618)
for _case in range(150):
    _n = 3 + next(_g) % 4
    _routes = []
    for _ in range(3 + next(_g) % 9):
        _routes.append(("p%d" % (next(_g) % _n), "p%d" % (next(_g) % _n), next(_g) % 12, 1 + next(_g) % 15, 1 + next(_g) % 9))
    _t = next(_g) % 20
    assert ferry_plan(_routes, "p0", "p%d" % (_n - 1), _t) == _paths(_routes, "p0", "p%d" % (_n - 1), _t), (_routes, _t)
_big = [("n%d" % i, "n%d" % (i + 1), (i * 37) % 101, 3 + i % 17, 1 + (i * 7) % 13) for i in range(59)]
_big += [("n%d" % i, "n%d" % (i + 5), 50 + (i * 53) % 400, 97 + i, 40 + i % 9) for i in range(54)]
_big += [("n%d" % (i + 3), "n%d" % i, 0, 2, 1) for i in range(56)]
assert ferry_plan(_big, "n0", "n59", 0) == (679, 31)
assert ferry_plan(_big, "n0", "n59", 10**12) == (1000000000599, 31)
assert ferry_plan(_big, "n7", "n44", 12345) == (12715, 21)
assert ferry_plan(_big, "n59", "n0", 0) is None
assert ferry_plan(_big, "n57", "n0", 3) == (41, 19)
assert ferry_plan(_big, "n30", "n31", 10**6) == (1000007, 1)
''',
    "wrong": r'''
import heapq

def ferry_plan(routes, src, dst, t0):
    # Dijkstra on (arrival, ferries) labels: keeps only the best label per port
    if src == dst:
        return (t0, 0)
    out = {}
    for r in routes:
        out.setdefault(r[0], []).append(r)
    best = {src: (t0, 0)}
    heap = [(t0, 0, src)]
    while heap:
        t, legs, port = heapq.heappop(heap)
        if best.get(port) != (t, legs):
            continue
        if port == dst:
            return (t, legs)
        for a, b, first, every, duration in out.get(port, []):
            dep = first if t <= first else first + -(-(t - first) // every) * every
            cand = (dep + duration, legs + 1)
            if b not in best or cand < best[b]:
                best[b] = cand
                heapq.heappush(heap, (cand[0], cand[1], b))
    return None
''',
})


_REF_C23 = r'''
def courier_cost(n, roads, depot, jobs, capacity):
    INF = float("inf")
    dist = [[INF] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0
    for a, b, w in roads:
        if w < dist[a][b]:
            dist[a][b] = dist[b][a] = w
    for k in range(n):
        dk = dist[k]
        for i in range(n):
            dik = dist[i][k]
            if dik == INF:
                continue
            di = dist[i]
            for j in range(n):
                v = dik + dk[j]
                if v < di[j]:
                    di[j] = v
    k = len(jobs)
    if any(size > capacity for _, _, size in jobs):
        return None
    layer = {((0,) * k, depot): 0}
    for _ in range(2 * k):
        nxt = {}
        for (status, node), cost in layer.items():
            load = sum(jobs[i][2] for i in range(k) if status[i] == 1)
            for i in range(k):
                if status[i] == 0:
                    if load + jobs[i][2] > capacity:
                        continue
                    target = jobs[i][0]
                elif status[i] == 1:
                    target = jobs[i][1]
                else:
                    continue
                d = dist[node][target]
                if d == INF:
                    continue
                key = (status[:i] + (status[i] + 1,) + status[i + 1:], target)
                c = cost + d
                if c < nxt.get(key, INF):
                    nxt[key] = c
        layer = nxt
    best = INF
    for (status, node), cost in layer.items():
        best = min(best, cost + dist[node][depot])
    return None if best == INF else best
'''

ITEMS.append({
    "id": "C23",
    "kind": "graph",
    "difficulty": "very hard",
    "entry_point": "courier_cost",
    "prompt": r"""Write a Python function `courier_cost(n: int, roads: list[tuple[int, int, int]], depot: int, jobs: list[tuple[int, int, int]], capacity: int)` that plans a courier's day.

The town has junctions `0..n-1`. Each road `(a, b, length)` connects two junctions in both directions with an integer `length >= 1`; there may be several roads between the same pair (use any) and the network need not be connected.

Each job is `(pickup, dropoff, size)`: one parcel of the given size (`size >= 1`) waits at junction `pickup` and must be brought to junction `dropoff`. The van starts at `depot` with no parcels, must deliver every parcel, and must end at `depot`. Rules:
- A parcel can only be loaded at its pickup junction and only be unloaded at its dropoff junction (no leaving parcels anywhere else), and of course it must be loaded before it is unloaded.
- The total size of the parcels in the van may never exceed `capacity`.
- The van may drive through any junction any number of times, with or without loading or unloading there; loading and unloading take no time and can happen in any order when the van is at a junction. Several jobs may share junctions, and a job's pickup may equal its dropoff or the depot.

Return the minimum total distance driven, or `None` if the jobs cannot all be done (some junction that is needed cannot be reached, or a parcel is larger than `capacity`). With no jobs the answer is 0.

Limits: `n <= 60`, at most 6 jobs. Trying every order of pickups and deliveries by brute force (12 events) is too slow in Python; plan over states instead.

Examples, on the ring `roads = [(0, 1, 5), (1, 2, 5), (2, 3, 5), (0, 3, 5)]` with `n = 4`, `depot = 0`:
- `courier_cost(4, roads, 0, [(1, 2, 1)], 1)` returns 20 (0 -> 1 -> 2 -> back to 0).
- `courier_cost(4, roads, 0, [(1, 2, 1), (1, 3, 1)], 2)` returns 20 (load both at 1, drive on around the ring).
- `courier_cost(4, roads, 0, [(1, 2, 1), (1, 3, 1)], 1)` returns 30: the van can carry only one parcel, so it must come back to junction 1 (0 -> 1 -> 2 -> 1 -> 0 -> 3 -> 0, for example).
- `courier_cost(4, roads, 0, [(1, 2, 3)], 2)` returns `None`.""" + _TAIL,
    "reference": _REF_C23,
    "tests": _LCG + r'''
from itertools import permutations as _perms

def _brute(n, roads, depot, jobs, capacity):
    INF = float("inf")
    d = [[INF] * n for _ in range(n)]
    for i in range(n):
        d[i][i] = 0
    for a, b, w in roads:
        d[a][b] = min(d[a][b], w)
        d[b][a] = min(d[b][a], w)
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if d[i][k] + d[k][j] < d[i][j]:
                    d[i][j] = d[i][k] + d[k][j]
    best = INF
    events = [(i, e) for i in range(len(jobs)) for e in (0, 1)]
    for order in _perms(events):
        held, load, at, cost, ok = set(), 0, depot, 0, True
        for i, e in order:
            if e == 0:
                load += jobs[i][2]
                held.add(i)
                if load > capacity:
                    ok = False
                    break
            else:
                if i not in held:
                    ok = False
                    break
                load -= jobs[i][2]
            cost += d[at][jobs[i][e]]
            at = jobs[i][e]
        if ok:
            best = min(best, cost + d[at][depot])
    return None if best == INF else best

_ring = [(0, 1, 5), (1, 2, 5), (2, 3, 5), (0, 3, 5)]
assert courier_cost(4, _ring, 0, [(1, 2, 1)], 1) == 20 and courier_cost(4, _ring, 0, [(1, 2, 1), (1, 3, 1)], 2) == 20
assert courier_cost(4, _ring, 0, [(1, 2, 1), (1, 3, 1)], 1) == 30 and courier_cost(4, _ring, 0, [(1, 2, 3)], 2) is None
assert courier_cost(4, _ring, 0, [], 1) == 0 and courier_cost(1, [], 0, [(0, 0, 1)], 1) == 0 and courier_cost(4, _ring, 2, [(2, 2, 5), (2, 2, 5)], 5) == 0
assert courier_cost(4, _ring, 0, [(1, 3, 1), (3, 1, 1)], 1) == 30 and courier_cost(4, _ring, 0, [(0, 2, 1), (2, 0, 1)], 1) == 20
assert courier_cost(5, _ring, 0, [(1, 4, 1)], 1) is None and courier_cost(5, _ring, 4, [(1, 2, 1)], 1) is None and courier_cost(5, _ring, 0, [(1, 2, 1)], 1) == 20
assert courier_cost(3, [(0, 1, 9), (0, 1, 4), (1, 2, 1), (0, 2, 7), (2, 2, 3)], 0, [(2, 1, 2)], 2) == 10
_line = [(i, i + 1, 1) for i in range(9)]
assert courier_cost(10, _line, 0, [(9, 0, 1)], 1) == 18 and courier_cost(10, _line, 5, [(0, 9, 1), (9, 0, 1)], 1) == 26
assert courier_cost(10, _line, 0, [(2, 8, 2), (3, 7, 2), (4, 6, 2)], 6) == 16 and courier_cost(10, _line, 0, [(2, 8, 2), (3, 7, 2), (4, 6, 2)], 2) == 28
assert courier_cost(10, _line, 0, [(8, 2, 2), (7, 3, 2), (6, 4, 2)], 2) == _brute(10, _line, 0, [(8, 2, 2), (7, 3, 2), (6, 4, 2)], 2)
assert courier_cost(10, _line, 4, [(1, 3, 3), (3, 1, 2), (6, 2, 2)], 4) == _brute(10, _line, 4, [(1, 3, 3), (3, 1, 2), (6, 2, 2)], 4)
assert courier_cost(10, _line, 4, [(1, 3, 3), (3, 1, 2), (6, 2, 2), (2, 7, 1)], 4) == 16
_g = _lcg(555)
for _case in range(40):
    _n = 3 + next(_g) % 6
    _roads = [(next(_g) % _n, next(_g) % _n, 1 + next(_g) % 20) for _ in range(_n + next(_g) % (2 * _n))]
    _jobs = [(next(_g) % _n, next(_g) % _n, 1 + next(_g) % 3) for _ in range(1 + next(_g) % 3)]
    _cap = 2 + next(_g) % 4
    assert courier_cost(_n, _roads, 0, _jobs, _cap) == _brute(_n, _roads, 0, _jobs, _cap), (_n, _roads, _jobs, _cap)
_g = _lcg(909)
_broads = [(i, (i + 1) % 60, 3 + next(_g) % 40) for i in range(60)] + [(next(_g) % 60, next(_g) % 60, 20 + next(_g) % 200) for _ in range(90)]
_bjobs = [(next(_g) % 60, next(_g) % 60, 1 + next(_g) % 4) for _ in range(6)]
assert courier_cost(60, _broads, 17, _bjobs, 4) == 1143
assert courier_cost(60, _broads, 17, _bjobs, 5) == 952
assert courier_cost(60, _broads, 17, _bjobs, 100) == 854
assert courier_cost(60, _broads, 0, _bjobs[:5] + [(_bjobs[0][1], _bjobs[0][0], 4)], 4) == 1001
assert courier_cost(60, _broads, 17, _bjobs, 3) is None
assert courier_cost(60, _broads[:59], 59, _bjobs, 100) == 2382
''',
    "wrong": _mut(_REF_C23, "            load = sum(jobs[i][2] for i in range(k) if status[i] == 1)", "            load = sum(1 for i in range(k) if status[i] == 1)"),
})


_REF_C24 = r'''
def last_link_times(n, cables, pairs):
    res = [0] * len(pairs)
    parent = list(range(n))
    waiting = [set() for _ in range(n)]
    for qi, (u, v) in enumerate(pairs):
        if u == v:
            res[qi] = None
        else:
            waiting[u].add(qi)
            waiting[v].add(qi)

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    for a, b, t in sorted(cables, key=lambda c: -c[2]):
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        if len(waiting[ra]) < len(waiting[rb]):
            ra, rb = rb, ra
        big, small = waiting[ra], waiting[rb]
        for q in small:
            if q in big:
                res[q] = t
                big.discard(q)
            else:
                big.add(q)
        waiting[rb] = set()
        parent[rb] = ra
    return res
'''

ITEMS.append({
    "id": "C24",
    "kind": "graph",
    "difficulty": "very hard",
    "entry_point": "last_link_times",
    "prompt": r"""Write a Python function `last_link_times(n: int, cables: list[tuple[int, int, int]], pairs: list[tuple[int, int]]) -> list` about an ageing computer network.

There are `n` machines numbered `0..n-1`. Each cable `(a, b, fail)` connects machines `a` and `b` (in both directions) and works at every time strictly before its failure time `fail` (an integer >= 1); from time `fail` on it is dead for good. Several cables may join the same two machines, and a cable may join a machine to itself.

Two machines can talk at time t if they are connected through a chain of cables that all still work at time t.

For every pair `(u, v)` in `pairs` return the last moment of contact, defined as the largest `fail` value F such that u and v are connected using only cables whose failure time is at least F. (Equivalently: the two machines can talk at every time before F and never from F on.) Special cases: if u and v are not connected even when all cables are used, the answer is 0; if `u == v` the answer is `None` (a machine can always talk to itself).

Return the list of answers in the order of `pairs`.

Limits: `n`, the number of cables and the number of pairs can each be up to 100,000, and the network can be long and thin (for example one chain through all machines). Answering each pair with its own graph search, or by walking a tree path machine by machine for each pair, is far too slow: the whole call must finish in a few seconds, which requires an approach that is close to linear overall (for example processing cables from the latest failure to the earliest while merging groups, or a tree with fast ancestor jumps).

Examples:
- `last_link_times(4, [(0, 1, 5), (1, 2, 3), (0, 2, 9), (2, 3, 4)], [(0, 1), (1, 2), (0, 3), (3, 3)])` returns `[5, 5, 4, None]`: machines 1 and 2 stay connected through machine 0 until time 5, when cable 0-1 fails.
- `last_link_times(3, [(0, 1, 7)], [(0, 2), (1, 0)])` returns `[0, 7]`.""" + _TAIL,
    "reference": _REF_C24,
    "tests": _LCG + r'''
def _slow(n, cables, pairs):
    w = [[0] * n for _ in range(n)]
    for a, b, f in cables:
        if a != b and f > w[a][b]:
            w[a][b] = w[b][a] = f
    for k in range(n):
        for i in range(n):
            for j in range(n):
                v = min(w[i][k], w[k][j])
                if v > w[i][j]:
                    w[i][j] = v
    return [None if u == v else w[u][v] for u, v in pairs]

assert last_link_times(4, [(0, 1, 5), (1, 2, 3), (0, 2, 9), (2, 3, 4)], [(0, 1), (1, 2), (0, 3), (3, 3)]) == [5, 5, 4, None]
assert last_link_times(3, [(0, 1, 7)], [(0, 2), (1, 0)]) == [0, 7] and last_link_times(3, [], [(0, 1), (2, 2)]) == [0, None] and last_link_times(2, [(0, 1, 1)], []) == []
assert last_link_times(2, [(0, 1, 3), (1, 0, 8), (0, 1, 5), (1, 1, 99)], [(0, 1), (1, 0), (0, 1), (1, 1)]) == [8, 8, 8, None]
assert last_link_times(5, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 4, 4)], [(0, 4), (1, 3), (4, 0)]) == [4, 4, 4]
assert last_link_times(6, [(0, 1, 10), (1, 2, 2), (2, 3, 10), (3, 0, 1), (4, 5, 6)], [(0, 2), (1, 3), (0, 3), (4, 5), (0, 4), (5, 1)]) == [2, 2, 2, 6, 0, 0]
assert last_link_times(4, [(0, 1, 10**9), (1, 2, 10**9), (2, 3, 1)], [(0, 2), (0, 3), (3, 1)]) == [10**9, 1, 1]
_g = _lcg(42)
for _case in range(80):
    _n = 2 + next(_g) % 8
    _cab = [(next(_g) % _n, next(_g) % _n, 1 + next(_g) % 9) for _ in range(next(_g) % 14)]
    _prs = [(next(_g) % _n, next(_g) % _n) for _ in range(12)]
    assert last_link_times(_n, _cab, _prs) == _slow(_n, _cab, _prs), (_n, _cab, _prs)
_g = _lcg(1234)
_n = 150
_cab = [(next(_g) % _n, next(_g) % _n, 1 + next(_g) % 1000) for _ in range(260)]
_prs = [(next(_g) % _n, next(_g) % _n) for _ in range(600)]
assert last_link_times(_n, _cab, _prs) == _slow(_n, _cab, _prs)
_g = _lcg(77)
_N = 30000
_chain = [(i, i + 1, 1 + next(_g) % 10**9) for i in range(_N - 1)]
_pairs = [(next(_g) % _N, next(_g) % _N) for _ in range(30000)]
_out = last_link_times(_N, _chain, _pairs)
assert len(_out) == 30000
assert all((o is None) == (u == v) for o, (u, v) in zip(_out, _pairs))
assert all(o == min(f for _, _, f in _chain[min(u, v):max(u, v)]) for o, (u, v) in list(zip(_out, _pairs))[:300] if u != v)
assert sum(o for o in _out if o) == 15373632419
_extra = _chain + [(next(_g) % _N, next(_g) % _N, 1 + next(_g) % 10**9) for _ in range(25000)]
_out2 = last_link_times(_N, _extra, _pairs)
assert all(b is None or b >= a for a, b in zip(_out, _out2))
assert sum(o for o in _out2 if o) == 13766984948430
_split = [c for c in _extra if c[0] % 1000 and c[1] % 1000]
_out3 = last_link_times(_N, _split, _pairs)
assert sum(1 for o in _out3 if o == 0) == 62
assert sum(o for o in _out3 if o) == 13721985852886
''',
    "wrong": _mut(_REF_C24, "            if q in big:\n                res[q] = t\n                big.discard(q)", "            if q in big:\n                res[q] = t - 1\n                big.discard(q)"),
})


_REF_C25 = r'''
from collections import deque

def sync_moves(grid):
    rows, cols = len(grid), len(grid[0])
    where = {}
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] in "ABab":
                where[grid[r][c]] = (r, c)
    vec = {"D": (1, 0), "L": (0, -1), "R": (0, 1), "U": (-1, 0)}

    def move(p, d):
        r, c = p[0] + d[0], p[1] + d[1]
        if 0 <= r < rows and 0 <= c < cols and grid[r][c] != "#":
            return (r, c)
        return p

    start = (where["A"], where["B"], True)
    goal_a, goal_b = where["a"], where["b"]
    parent = {start: None}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        pa, pb, mirrored = state
        if pa == goal_a and pb == goal_b:
            out = []
            while parent[state] is not None:
                state, cmd = parent[state]
                out.append(cmd)
            return "".join(reversed(out))
        for cmd in "DLRUX":
            if cmd == "X":
                nxt = (pa, pb, not mirrored)
            else:
                dr, dc = vec[cmd]
                na = move(pa, (dr, dc))
                nb = move(pb, (dr, -dc if mirrored else dc))
                if grid[na[0]][na[1]] == "x" or grid[nb[0]][nb[1]] == "x":
                    continue
                if na == nb or (na == pb and nb == pa):
                    continue
                nxt = (na, nb, mirrored)
            if nxt not in parent:
                parent[nxt] = (state, cmd)
                queue.append(nxt)
    return None
'''

ITEMS.append({
    "id": "C25",
    "kind": "graph",
    "difficulty": "hard",
    "entry_point": "sync_moves",
    "prompt": r"""Write a Python function `sync_moves(grid: list[str])` that solves a two-robot puzzle and returns the best command string, or `None` if the puzzle has no solution.

`grid` is a list of equal-length strings; row 0 is the top. Cells: `.` free, `#` wall, `x` pit, `A` and `B` the starting cells of the two robots, `a` and `b` their target cells (each of these four letters occurs exactly once; all four are otherwise free cells, and any robot may walk over any of them).

Both robots obey the same stream of commands, one character each:
- `U`, `D`, `L`, `R` - robot A tries to move one cell up, down, left or right. Robot B tries to move one cell too: vertically the same way as A, horizontally the same way as A when the link is in "parallel" mode but the OPPOSITE way (L and R exchanged) in "mirror" mode. The link starts in mirror mode.
- `X` - toggles the link between mirror and parallel mode; nobody moves.

Executing a move command: for each robot separately, look at the cell it tries to enter; if that cell is outside the grid or a wall, the robot stays where it is, otherwise it enters the cell. Both robots move at the same time, each judged against the grid only. The command is FORBIDDEN (it may not be issued at all) if afterwards
- either robot stands on a pit, or
- both robots stand on the same cell, or
- the two robots have exchanged cells (each ends on the cell where the other one was).

The puzzle is solved as soon as robot A stands on `a` and robot B stands on `b` at the same time (the link mode does not matter).

Return the shortest command string that solves the puzzle. If several shortest strings exist, return the one that is smallest in ordinary string order (so `D` < `L` < `R` < `U` < `X`). Grids are at most 12 x 12.

Examples:
- `sync_moves(["A.a", "B.b"])` returns `"XRR"`: in mirror mode B would run the wrong way, so the link is switched first.
- `sync_moves(["A.a", "b.B"])` returns `"RR"`.
- `sync_moves(["Aa", "bB"])` returns `"R"`.
- `sync_moves(["A#a", "B#b"])` returns `None`, and so does `sync_moves(["A.B", "...", "b.a"])`: without walls both robots always share a row, so they can never pass each other.""" + _TAIL,
    "reference": _REF_C25,
    "tests": r'''
from itertools import product as _product

def _brute(grid, maxlen):
    """Try every command string in order of length, then alphabetically."""
    rows, cols = len(grid), len(grid[0])
    pos = {grid[r][c]: (r, c) for r in range(rows) for c in range(cols) if grid[r][c] in "ABab"}
    vec = {"D": (1, 0), "L": (0, -1), "R": (0, 1), "U": (-1, 0)}
    def step(p, dr, dc):
        r, c = p[0] + dr, p[1] + dc
        return (r, c) if 0 <= r < rows and 0 <= c < cols and grid[r][c] != "#" else p
    def run(cmds):
        pa, pb, mirror = pos["A"], pos["B"], True
        for ch in cmds:
            if ch == "X":
                mirror = not mirror
                continue
            dr, dc = vec[ch]
            na, nb = step(pa, dr, dc), step(pb, dr, -dc if mirror else dc)
            if grid[na[0]][na[1]] == "x" or grid[nb[0]][nb[1]] == "x" or na == nb or (na == pb and nb == pa):
                return False
            pa, pb = na, nb
        return pa == pos["a"] and pb == pos["b"]
    for n in range(maxlen + 1):
        for cmds in _product("DLRUX", repeat=n):
            if run(cmds):
                return "".join(cmds)
    return None

assert sync_moves(["A.a", "B.b"]) == "XRR" and sync_moves(["A.a", "b.B"]) == "RR" and sync_moves(["Aa", "bB"]) == "R"
assert sync_moves(["A#a", "B#b"]) is None and sync_moves(["A.B", "...", "b.a"]) is None and sync_moves(["A.b.B.a"]) is None
assert sync_moves(["Ab", "xx", "aB"]) is None and sync_moves(["Ax.a", "....", "B..b"]) is None and sync_moves(["A.a", "Bxb"]) is None
assert sync_moves(["A.", "a.", "B.", "b."]) == "D" and sync_moves(["a.", "A.", "b.", "B."]) == "U" and sync_moves(["AaxbB"]) == "R"
assert sync_moves(["A..", "x.a", "B.b"]) == "XRDR" and sync_moves(["A.a.B.b"]) == "XRR"
assert sync_moves(["A.Ba", "..#.", "b..."]) == "DRRURDDR" and sync_moves(["a.B", "#.#", "b.A"]) == "LUUXLDDL"
assert sync_moves(["......", "..xB..", "..b#xA", ".....a"]) == "URRDDXR" and sync_moves(["#.#b.", "B.A.#", "....a"]) == "DXRRRUU"
assert sync_moves([".b.#.x", "a..A##", "#..B.#"]) == "RUULLXL" and sync_moves(["B#.", ".aA", ".x#", "..b"]) == "DDDLLXR"
assert sync_moves(["aB#.", ".bA#"]) == "LLDLUXL" and sync_moves([".xbA..", ".a.B##"]) == "LUXRDLL"
assert sync_moves(["xab", "..#", "#AB"]) == "URURXLDDRUXLUU"
assert sync_moves([".x##a.", "......", "A.b#B.", "x..x.."]) == "URXLUDRRRDXRUL"
assert sync_moves([".a....", "b.A.B#"]) == "ULDRRRURDLXLLL"
assert sync_moves(["a.....", "B..#Ab", "...#x."]) == "ULDLLUXRRDLLXL"
assert sync_moves([".x...a", "x....#", "#..#xx", "....Bb", "..#.#A"]) == "RURLDLLUUUXRRR"
assert sync_moves(["x..A", "b..#", ".ax.", "....", ".B.."]) == "UUULLUXRDLDLXR"
assert all(sync_moves(g) == _brute(g, 4) for g in (["A.a", "B.b"], ["A.a", "b.B"], ["A..", "x.a", "B.b"], ["A.a.B.b"], ["Aa", "bB"], ["a.", "A.", "b.", "B."]))
assert all(_brute(g, 5) is None for g in (["A.B", "...", "b.a"], ["A.Ba", "..#.", "b..."], ["aB#.", ".bA#"]))
_g1 = ["A....#....", ".###.#.##.", ".#a..#..#.", ".#.####.#.", ".#......#.", ".####.###.", "......#b..", ".####.#.#.", ".#....#.#.", "B#.####..."]
assert sync_moves(_g1) == "UUULLLLLUULLUURUUXRRRDDDDDDLL"
_g2 = ["A..........a", "............", "..x......x..", "............", "b..........B"]
assert sync_moves(_g2) == "RRRRRRRRRRR"
_g3 = ["#####a#####", "A.........B", "#####b#####"]
assert sync_moves(_g3) is None
_g4 = ["A.#.....#..b", "..#.###.#.#.", "....#x#...#.", "###.#.#####.", "....#.......", ".####.#####.", "......#a..#.", "B.###...#..."]
assert sync_moves(_g4) == "DDRRRDDLULLDDLXRUURRRRDRRUUUU"
''',
    "wrong": _mut(_REF_C25, "                if na == nb or (na == pb and nb == pa):\n                    continue", "                if na == nb:\n                    continue"),
})


_REF_C26 = r'''
import heapq

def craft_cost(prices, recipes, target):
    users = {}                    # ingredient -> list of (recipe index, quantity)
    missing = []
    acc = []
    heap = []
    for idx, (product, fee, needs) in enumerate(recipes):
        missing.append(len(needs))
        acc.append(fee)
        for item, qty in needs.items():
            users.setdefault(item, []).append((idx, qty))
        if not needs:
            heap.append((fee, product))
    for item, price in prices.items():
        heap.append((price, item))
    heapq.heapify(heap)
    cost = {}
    while heap:
        c, item = heapq.heappop(heap)
        if item in cost:
            continue
        cost[item] = c
        if item == target:
            return c
        for idx, qty in users.get(item, ()):
            acc[idx] += qty * c
            missing[idx] -= 1
            if missing[idx] == 0 and recipes[idx][0] not in cost:
                heapq.heappush(heap, (acc[idx], recipes[idx][0]))
    return None
'''

ITEMS.append({
    "id": "C26",
    "kind": "graph",
    "difficulty": "very hard",
    "entry_point": "craft_cost",
    "prompt": r"""Write a Python function `craft_cost(prices: dict[str, int], recipes: list[tuple[str, int, dict[str, int]]], target: str)` that finds the cheapest way to obtain one unit of an item in a crafting game.

- `prices` maps an item name to the price of BUYING one unit (integer >= 1). Items not in `prices` cannot be bought.
- Each recipe is `(product, fee, ingredients)`: paying `fee` (integer >= 0) and using up `ingredients[x]` units (integer >= 1) of every listed item x produces ONE unit of `product`. The ingredients dict may be empty (the recipe then costs just its fee). An item can have any number of recipes, and may also be buyable.

Every unit that is used up has to be obtained separately, each by buying or by any of its recipes, whichever is cheapest. So the cost of one unit of an item is the minimum of
- its price (if it has one), and
- for each of its recipes: `fee + sum(quantity * cost(ingredient))`, provided every ingredient is obtainable.
An item with no price and no usable recipe is unobtainable. Recipes may refer to each other in cycles (A is made from B, and B can be made from A); a cycle never gives anything for free, it just means those recipes may or may not be useful.

Return the minimum cost of one unit of `target` (costs can be huge integers - use exact arithmetic), or `None` if it is unobtainable (including when the name is unknown).

Limits: up to 30,000 items and 30,000 recipes, at most 5 ingredients per recipe. Dependency chains can be 20,000 recipes deep and the recipes come in arbitrary order, so plain recursion will overflow the stack and repeatedly sweeping over all recipes until nothing changes is quadratic and too slow. The call must finish in about a second.

Examples:
- `craft_cost({"ore": 3, "coal": 2}, [("bar", 1, {"ore": 2, "coal": 1})], "bar")` returns 9.
- `craft_cost({"ore": 3, "coal": 2, "bar": 8}, [("bar", 1, {"ore": 2, "coal": 1})], "bar")` returns 8.
- `craft_cost({"a": 5, "x": 100, "j": 50}, [("t", 0, {"a": 1, "x": 1}), ("a", 0, {"x": 1, "j": 1}), ("x", 1, {"a": 1})], "t")` returns 11: a costs 5 (bought), x costs 6 (made from a), t costs 5 + 6.
- `craft_cost({}, [("p", 1, {"q": 1}), ("q", 1, {"p": 1})], "p")` returns `None`.""" + _TAIL,
    "reference": _REF_C26,
    "tests": _LCG + r'''
def _fix(prices, recipes, target):
    cost = dict(prices)
    changed = True
    while changed:
        changed = False
        for product, fee, needs in recipes:
            if all(x in cost for x in needs):
                c = fee + sum(q * cost[x] for x, q in needs.items())
                if product not in cost or c < cost[product]:
                    cost[product] = c
                    changed = True
    return cost.get(target)

assert craft_cost({"ore": 3, "coal": 2}, [("bar", 1, {"ore": 2, "coal": 1})], "bar") == 9
assert craft_cost({"ore": 3, "coal": 2, "bar": 8}, [("bar", 1, {"ore": 2, "coal": 1})], "bar") == 8
_r1 = [("t", 0, {"a": 1, "x": 1}), ("a", 0, {"x": 1, "j": 1}), ("x", 1, {"a": 1})]
assert craft_cost({"a": 5, "x": 100, "j": 50}, _r1, "t") == 11 and craft_cost({"a": 5, "x": 100, "j": 50}, _r1, "x") == 6
assert craft_cost({"a": 500, "x": 100, "j": 50}, _r1, "t") == 250 and craft_cost({"x": 100, "j": 50}, _r1, "t") == 250 and craft_cost({"a": 5, "j": 50}, _r1, "t") == 11
assert craft_cost({}, [("p", 1, {"q": 1}), ("q", 1, {"p": 1})], "p") is None and craft_cost({"ore": 3}, [], "gold") is None and craft_cost({"ore": 3}, [], "ore") == 3
assert craft_cost({}, [("air", 0, {}), ("sky", 2, {"air": 7})], "sky") == 2 and craft_cost({}, [("air", 4, {}), ("air", 3, {}), ("sky", 2, {"air": 7})], "sky") == 23
assert craft_cost({"a": 1}, [("b", 0, {"a": 2, "zzz": 1}), ("b", 10, {"a": 3})], "b") == 13 and craft_cost({"a": 1}, [("b", 0, {"a": 2, "zzz": 1})], "b") is None
assert craft_cost({"w": 2}, [("p", 5, {"w": 1, "q": 1}), ("q", 5, {"w": 1, "p": 1}), ("q", 40, {"w": 3})], "p") == 53
assert craft_cost({"s": 1}, [("m", 0, {"s": 3}), ("l", 0, {"m": 3}), ("xl", 0, {"l": 3}), ("l", 20, {})], "xl") == 27
assert craft_cost({"s": 4}, [("m", 0, {"s": 3}), ("l", 0, {"m": 3}), ("xl", 0, {"l": 3}), ("l", 20, {})], "xl") == 60
_dbl = [("d%d" % (i + 1), 0, {"d%d" % i: 2}) for i in range(200)]
assert craft_cost({"d0": 1}, _dbl, "d200") == 2**200 and craft_cost({"d0": 1, "d150": 7}, _dbl, "d200") == 7 * 2**50
_g = _lcg(31)
for _case in range(150):
    _names = ["i%d" % k for k in range(3 + next(_g) % 7)]
    _prices = {nm: 1 + next(_g) % 60 for nm in _names if next(_g) % 3 == 0}
    _recipes = []
    for _ in range(next(_g) % 12):
        _needs = {_names[next(_g) % len(_names)]: 1 + next(_g) % 3 for _ in range(next(_g) % 4)}
        _recipes.append((_names[next(_g) % len(_names)], next(_g) % 9, _needs))
    for _nm in _names:
        assert craft_cost(_prices, _recipes, _nm) == _fix(_prices, _recipes, _nm), (_prices, _recipes, _nm)
_N = 20000
_chain = [("c%d" % i, 1 + i % 3, {"c%d" % (i - 1): 1, "base": 1 + i % 2}) for i in range(_N, 0, -1)]
assert craft_cost({"c0": 10, "base": 2}, _chain, "c%d" % _N) == 10 + sum(1 + i % 3 + 2 * (1 + i % 2) for i in range(1, _N + 1))
assert craft_cost({"c0": 10, "base": 2, "c12345": 1}, _chain, "c%d" % _N) == 1 + sum(1 + i % 3 + 2 * (1 + i % 2) for i in range(12346, _N + 1))
assert craft_cost({"base": 2}, _chain, "c%d" % _N) is None
_loop = _chain + [("c0", 0, {"c%d" % _N: 1})] + [("c%d" % (5 * i), 3, {"c%d" % (5 * i + 7): 1}) for i in range(3000)]
assert craft_cost({"c9000": 50, "base": 1}, _loop, "c%d" % _N) == 38551
assert craft_cost({"c9000": 50, "base": 1}, _loop, "c3") == 18061
assert craft_cost({"c19999": 5, "base": 1}, _loop, "c8") == 38
''',
    "wrong": r'''
def craft_cost(prices, recipes, target):
    # memoised recursion with an "in progress" guard: remembers values computed while an ancestor was blocked
    import sys
    sys.setrecursionlimit(1000000)
    by_product = {}
    for product, fee, needs in recipes:
        by_product.setdefault(product, []).append((fee, needs))
    memo = {}
    active = set()

    def cost(item):
        if item in memo:
            return memo[item]
        if item in active:
            return None
        active.add(item)
        best = prices.get(item)
        for fee, needs in by_product.get(item, []):
            total = fee
            for x, q in needs.items():
                c = cost(x)
                if c is None:
                    total = None
                    break
                total += q * c
            if total is not None and (best is None or total < best):
                best = total
        active.discard(item)
        memo[item] = best
        return best

    return cost(target)
''',
})

# ---------------------------------------------------------------------------
# Kind 6: stateful classes (C27-C30)
# ---------------------------------------------------------------------------

_REF_C27 = r'''
class VaultKV:
    _MISSING = object()

    def __init__(self):
        self._data = {}
        self._index = {}
        self._locks = set()
        self._log = []
        self._marks = []            # (name, length of the log at begin)

    def _store(self, key, value):
        old = self._data.get(key, self._MISSING)
        if old is not self._MISSING:
            bucket = self._index[old]
            bucket.discard(key)
            if not bucket:
                del self._index[old]
        if value is self._MISSING:
            self._data.pop(key, None)
        else:
            self._data[key] = value
            self._index.setdefault(value, set()).add(key)
        return old

    def _change(self, key, value):
        old = self._store(key, value)
        if self._marks:
            self._log.append((0, key, old))

    def put(self, key, value):
        if key in self._locks:
            raise PermissionError(key)
        self._change(key, value)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def drop(self, key):
        if key in self._locks:
            raise PermissionError(key)
        if key not in self._data:
            return False
        self._change(key, self._MISSING)
        return True

    def incr(self, key, by=1):
        if key in self._locks:
            raise PermissionError(key)
        old = self._data.get(key, 0)
        if not isinstance(old, int):
            raise TypeError("not an integer")
        self._change(key, old + by)
        return old + by

    def lock(self, key):
        if key not in self._locks:
            self._locks.add(key)
            if self._marks:
                self._log.append((1, key, False))

    def unlock(self, key):
        if key in self._locks:
            self._locks.discard(key)
            if self._marks:
                self._log.append((1, key, True))

    def locked(self, key):
        return key in self._locks

    def begin(self, name=None):
        self._marks.append((name, len(self._log)))

    def commit(self):
        if not self._marks:
            raise RuntimeError("no transaction")
        self._marks.pop()
        if not self._marks:
            self._log.clear()
        return len(self._marks)

    def rollback(self, name=None):
        if not self._marks:
            raise RuntimeError("no transaction")
        if name is None:
            idx = len(self._marks) - 1
        else:
            idx = len(self._marks) - 1
            while idx >= 0 and self._marks[idx][0] != name:
                idx -= 1
            if idx < 0:
                raise KeyError(name)
        start = self._marks[idx][1]
        del self._marks[idx:]
        while len(self._log) > start:
            kind, key, old = self._log.pop()
            if kind == 0:
                self._store(key, old)
            elif old:
                self._locks.add(key)
            else:
                self._locks.discard(key)
        return len(self._marks)

    def depth(self):
        return len(self._marks)

    def holders(self, value):
        return sorted(self._index.get(value, ()))

    def size(self):
        return len(self._data)
'''

ITEMS.append({
    "id": "C27",
    "kind": "class",
    "difficulty": "very hard",
    "entry_point": "VaultKV",
    "prompt": r"""Write a Python class `VaultKV`: an in-memory key-value store with key locks, nested transactions and a reverse lookup. Keys are strings; values are integers or strings.

Data methods:
- `put(key, value)` - store the value.
- `get(key, default=None)` - the value, or `default` if the key is absent.
- `drop(key) -> bool` - remove the key; `True` if it existed, `False` otherwise.
- `incr(key, by=1) -> int` - add `by` to the key's integer value (an absent key counts as 0) and return the new value. If the key holds a string, raise `TypeError`.
- `holders(value) -> list` - the sorted list of all keys that currently hold exactly this value.
- `size() -> int` - number of keys.

Locks:
- `lock(key)`, `unlock(key)`, `locked(key) -> bool`. Any key can be locked, whether it exists or not; locking a locked key or unlocking an unlocked one does nothing.
- While a key is locked, `put`, `drop` and `incr` on it raise `PermissionError` (this check comes first: before the existence check of `drop` and before the `TypeError` check of `incr`).

Transactions:
- `begin(name=None)` - open a new transaction inside the current one (transactions nest to any depth). A name is optional and need not be unique.
- `commit() -> int` - close the innermost open transaction and keep its changes: they become part of the enclosing transaction (which can still roll them back), or permanent if there is none.
- `rollback(name=None) -> int` - without a name: close the innermost open transaction and undo everything done since its `begin`. With a name: find the innermost open transaction that has this name, and roll back it and all transactions opened inside it.
- "Everything" includes lock changes: a rollback restores both the data and which keys are locked, exactly as they were at the corresponding `begin`.
- `depth() -> int` - number of open transactions. `commit` and `rollback` return the depth after the call.
- Errors: `commit` or `rollback` (with or without a name) when no transaction is open raises `RuntimeError`. `rollback(name)` when transactions are open but none has that name raises `KeyError` and changes nothing.

A method that raises must leave the store unchanged.

Performance: tests use about 50,000 keys, tens of thousands of nested open transactions and tens of thousands of `holders` calls. `begin` must therefore not copy the store, a rollback must cost time proportional to the changes it undoes, and `holders` must not scan all keys.

Example:

    v = VaultKV()
    v.put("a", 1); v.put("b", 1)
    v.begin(); v.put("a", 2); v.lock("b")
    v.holders(1)      # ["b"]
    v.begin("x"); v.drop("a"); v.unlock("b"); v.incr("b")     # b is now 2
    v.rollback()      # returns 1; a is 2 again, b is 1 and locked again
    v.rollback()      # returns 0; a is 1, b is 1 and unlocked""" + _TAIL,
    "reference": _REF_C27,
    "tests": _RAISES + r'''
v = VaultKV()
v.put("a", 1); v.put("b", 1)
v.begin(); v.put("a", 2); v.lock("b")
assert v.holders(1) == ["b"] and v.depth() == 1
v.begin("x"); v.drop("a"); v.unlock("b")
assert v.incr("b") == 2 and v.get("a") is None and v.holders(2) == ["b"]
assert v.rollback() == 1 and v.get("a") == 2 and v.get("b") == 1 and v.locked("b") and _raises(PermissionError, v.put, "b", 5)
assert v.rollback() == 0 and v.get("a") == 1 and v.get("b") == 1 and not v.locked("b") and v.holders(1) == ["a", "b"]
assert _raises(RuntimeError, v.rollback) and _raises(RuntimeError, v.commit) and _raises(RuntimeError, v.rollback, "x")
v.put("c", 2)
assert v.holders(3) == [] and v.get("z") is None and v.get("z", 5) == 5 and v.size() == 3 and v.drop("zz") is False
v.begin(); v.put("a", 2); assert v.drop("b") is True and v.holders(1) == [] and v.holders(2) == ["a", "c"]
v.begin("s"); v.put("d", 1)
assert v.incr("c") == 3 and v.incr("n", 5) == 5 and v.incr("n", -7) == -2 and v.size() == 4
assert v.rollback() == 1 and v.size() == 2 and v.holders(2) == ["a", "c"] and v.get("n") is None
assert v.commit() == 0 and v.get("a") == 2 and v.get("b") is None and v.depth() == 0
v.lock("a"); v.lock("ghost"); v.put("s", "text")
assert _raises(PermissionError, v.put, "a", 9) and _raises(PermissionError, v.drop, "a") and _raises(PermissionError, v.incr, "a") and v.get("a") == 2
assert _raises(PermissionError, v.put, "ghost", 1) and _raises(PermissionError, v.drop, "ghost") and v.get("ghost") is None and v.locked("ghost")
assert _raises(TypeError, v.incr, "s") and v.get("s") == "text" and v.holders("text") == ["s"]
v.lock("s"); assert _raises(PermissionError, v.incr, "s"); v.unlock("s"); v.unlock("s")
v.begin(); v.unlock("a"); v.put("a", 10); v.lock("q"); v.lock("q")
assert v.rollback() == 0 and v.get("a") == 2 and v.locked("a") and not v.locked("q")
v.begin(); v.lock("x1"); assert v.commit() == 0 and v.locked("x1")
v.begin("o"); v.begin("i"); v.put("k", 1); v.lock("k")
assert v.commit() == 1 and v.get("k") == 1 and v.locked("k") and v.rollback() == 0 and v.get("k") is None and not v.locked("k")
v.begin("a1"); v.put("p", 1); v.begin("b1"); v.put("p", 2); v.begin("a1"); v.put("p", 3); v.begin(); v.put("p", 4)
assert v.depth() == 4 and v.rollback("a1") == 2 and v.get("p") == 2
assert _raises(KeyError, v.rollback, "zzz") and v.depth() == 2 and v.get("p") == 2 and v.holders(2) == ["a", "c", "p"]
assert v.rollback("a1") == 0 and v.get("p") is None and v.holders(2) == ["a", "c"]
v.begin("t"); v.begin(); v.incr("cnt"); v.begin(); v.incr("cnt"); v.drop("c")
assert v.commit() == 2 and v.commit() == 1 and v.get("cnt") == 2 and v.rollback("t") == 0 and v.get("cnt") is None and v.get("c") == 2
big = VaultKV()
for _i in range(50000):
    big.put("k%d" % _i, _i % 25000)
big.begin("deep")
for _i in range(30000):
    big.begin()
    big.put("k%d" % _i, -1 - _i)
assert big.depth() == 30001 and big.holders(7) == [] and big.holders(5007) == ["k30007"] and big.holders(-8) == ["k7"]
assert sum(len(big.holders(_v)) for _v in range(20000)) == 15000
for _i in range(10000):
    big.rollback()
assert big.depth() == 20001 and big.holders(24999) == ["k24999", "k49999"] and big.holders(19999) == ["k44999"]
for _i in range(10000):
    big.commit()
assert big.depth() == 10001 and big.get("k15000") == -15001
assert big.rollback("deep") == 0 and big.holders(7) == ["k25007", "k7"] and sum(len(big.holders(_v)) for _v in range(25000)) == 50000
''',
    "wrong": _mut(_REF_C27, "            if kind == 0:\n                self._store(key, old)\n            elif old:\n                self._locks.add(key)\n            else:\n                self._locks.discard(key)",
                  "            if kind == 0:\n                self._store(key, old)"),
})


_REF_C28 = r'''
class PinCache:
    def __init__(self, max_items, max_weight):
        self._max_items = max_items
        self._max_weight = max_weight
        self._entries = {}          # key -> [value, weight, pinned, warm, stamp]
        self._clock = 0

    def _tick(self):
        self._clock += 1
        return self._clock

    def _plan(self, count, weight, max_items, max_weight, protect):
        """Keys to evict so that the limits hold, or None if impossible."""
        victims = []
        if count <= max_items and weight <= max_weight:
            return victims
        cands = [(e[3], e[4], k) for k, e in self._entries.items() if not e[2] and k != protect]
        cands.sort()
        for _, _, k in cands:
            victims.append(k)
            count -= 1
            weight -= self._entries[k][1]
            if count <= max_items and weight <= max_weight:
                return victims
        return None

    def _totals(self):
        return len(self._entries), sum(e[1] for e in self._entries.values())

    def put(self, key, value, weight=1):
        if weight < 1 or weight > self._max_weight:
            raise ValueError("bad weight")
        count, total = self._totals()
        old = self._entries.get(key)
        if old is None:
            count += 1
            total += weight
        else:
            total += weight - old[1]
        victims = self._plan(count, total, self._max_items, self._max_weight, key)
        if victims is None:
            raise OverflowError("pinned entries leave no room")
        pinned = old[2] if old is not None else False
        self._entries[key] = [value, weight, pinned, False, self._tick()]
        for k in victims:
            del self._entries[k]
        return victims

    def get(self, key, default=None):
        e = self._entries.get(key)
        if e is None:
            return default
        e[3] = True
        e[4] = self._tick()
        return e[0]

    def peek(self, key, default=None):
        e = self._entries.get(key)
        return default if e is None else e[0]

    def pin(self, key):
        if key not in self._entries:
            return False
        self._entries[key][2] = True
        return True

    def unpin(self, key):
        if key not in self._entries:
            return False
        self._entries[key][2] = False
        return True

    def drop(self, key):
        return self._entries.pop(key, None) is not None

    def resize(self, max_items, max_weight):
        count, total = self._totals()
        victims = self._plan(count, total, max_items, max_weight, None)
        if victims is None:
            raise OverflowError("pinned entries do not fit")
        self._max_items = max_items
        self._max_weight = max_weight
        for k in victims:
            del self._entries[k]
        return victims

    def keys(self):
        return [k for k, e in sorted(self._entries.items(), key=lambda kv: kv[1][4])]

    def stats(self):
        return self._totals()
'''

ITEMS.append({
    "id": "C28",
    "kind": "class",
    "difficulty": "very hard",
    "entry_point": "PinCache",
    "prompt": r"""Write a Python class `PinCache`: a cache limited both in the number of entries and in their total weight, with pinning and a two-level eviction order.

`PinCache(max_items: int, max_weight: int)` - both limits are positive integers.

Every entry has a value, a weight, a pinned flag (initially off), a temperature (COLD or WARM) and a position in the recency order. A USE makes an entry the most recently used one. Uses are: `put` (for a new key and for an existing key) and a successful `get`. Nothing else changes the recency order.

Methods:
- `put(key, value, weight=1) -> list`
  1. If `weight < 1` or `weight > max_weight`, raise `ValueError`.
  2. Store the entry. A new key starts unpinned. For an existing key the value and weight are replaced and the pinned flag is kept. In both cases the entry becomes COLD and most recently used.
  3. While the cache holds more than `max_items` entries or its total weight exceeds `max_weight`, evict one entry. Candidates are the entries that are not pinned and are not `key` itself. All COLD candidates are evicted before any WARM one; within the same temperature the least recently used goes first.
  4. If the limits are still violated when no candidate is left, raise `OverflowError` - and then the whole call must have no effect at all (nothing evicted; for an existing key the old value, weight, temperature and recency position remain).
  5. Return the list of evicted keys in eviction order (possibly empty).
- `get(key, default=None)` - if present: return the value; the entry becomes WARM and most recently used. Otherwise return `default`.
- `peek(key, default=None)` - like `get` but with no side effects at all.
- `pin(key) -> bool`, `unpin(key) -> bool` - set or clear the pinned flag; return `True` if the key is present (whether or not the flag changed), `False` if absent. Pinned entries are never evicted.
- `drop(key) -> bool` - remove the entry (pinned or not); `True` if it was present.
- `resize(max_items, max_weight) -> list` - change both limits, then evict as in step 3 (every unpinned entry is a candidate). If the new limits cannot be met because of pinned entries, raise `OverflowError` and change nothing (the old limits stay in force). Returns the evicted keys in order.
- `keys() -> list` - all keys from least to most recently used (temperature plays no role here).
- `stats() -> tuple[int, int]` - `(number of entries, total weight)`.

Example:

    c = PinCache(3, 10)
    c.put("a", "A", 3); c.put("b", "B", 3); c.put("c", "C", 3)     # each returns []
    c.put("d", "D", 1)     # ["a"]  (four entries: the least recently used cold one goes)
    c.get("b")             # "B"; b is now warm and most recent: keys() == ["c", "d", "b"]
    c.put("e", "E", 5)     # ["c"]
    c.put("f", "F", 6)     # ["d", "e"]: cold entries go first, the warm "b" survives; keys() == ["b", "f"]
    c.pin("f")
    c.put("g", "G", 5)     # OverflowError: evicting "b" would still leave weight 11; nothing changes""" + _TAIL,
    "reference": _REF_C28,
    "tests": _RAISES + r'''
c = PinCache(3, 10)
assert c.put("a", "A", 3) == [] and c.put("b", "B", 3) == [] and c.put("c", "C", 3) == [] and c.keys() == ["a", "b", "c"] and c.stats() == (3, 9)
assert c.put("d", "D", 1) == ["a"] and c.get("b") == "B" and c.keys() == ["c", "d", "b"] and c.get("a") is None and c.get("a", 0) == 0
assert c.put("e", "E", 5) == ["c"] and c.keys() == ["d", "b", "e"] and c.stats() == (3, 9)
assert c.put("f", "F", 6) == ["d", "e"] and c.keys() == ["b", "f"] and c.stats() == (2, 9)
assert c.pin("f") is True and c.pin("zz") is False and c.unpin("zz") is False
assert _raises(OverflowError, c.put, "g", "G", 5) and c.keys() == ["b", "f"] and c.stats() == (2, 9) and c.peek("g") is None and c.peek("b") == "B"
assert c.put("f", "F2", 8) == ["b"] and c.peek("f") == "F2" and c.stats() == (1, 8)
assert c.put("h", "H", 2) == [] and c.stats() == (2, 10) and c.put("i", "I", 1) == ["h"] and c.keys() == ["f", "i"]
assert c.unpin("f") is True and c.put("j", "J", 9) == ["f"] and c.keys() == ["i", "j"] and c.stats() == (2, 10)
assert _raises(ValueError, c.put, "k", "K", 11) and _raises(ValueError, c.put, "k", "K", 0) and _raises(ValueError, c.put, "i", "K", 11) and c.peek("i") == "I" and c.keys() == ["i", "j"]
c2 = PinCache(2, 10)
c2.put("p", 1, 5); c2.put("q", 2, 5); c2.pin("q")
assert c2.get("p") == 1 and c2.keys() == ["q", "p"] and c2.pin("p") and c2.pin("p")
assert _raises(OverflowError, c2.put, "p", 99, 6) and c2.peek("p") == 1 and c2.stats() == (2, 10) and c2.keys() == ["q", "p"]
assert _raises(OverflowError, c2.put, "r", 3, 1) and c2.keys() == ["q", "p"] and c2.unpin("q") and c2.unpin("p")
assert c2.put("q", 22, 4) == [] and c2.keys() == ["p", "q"] and c2.put("r", 3, 1) == ["q"] and c2.keys() == ["p", "r"]
c3 = PinCache(5, 100)
for _k in "abcd":
    c3.put(_k, _k.upper(), 10)
assert c3.get("a") == "A" and c3.pin("b") and c3.peek("c") == "C" and c3.keys() == ["b", "c", "d", "a"]
assert c3.resize(2, 100) == ["c", "d"] and c3.keys() == ["b", "a"] and c3.resize(1, 100) == ["a"] and c3.stats() == (1, 10)
assert _raises(OverflowError, c3.resize, 0, 100) and _raises(OverflowError, c3.resize, 5, 9) and _raises(OverflowError, c3.put, "z", "Z", 1) and c3.keys() == ["b"]
assert c3.unpin("b") and c3.put("z", "Z", 1) == ["b"] and c3.resize(4, 50) == [] and _raises(ValueError, c3.put, "y", "Y", 51) and c3.put("y", "Y", 50) == ["z"]
c4 = PinCache(4, 100)
for _k in "wxyz":
    c4.put(_k, 0, 20)
assert c4.get("w") == 0 and c4.get("x") == 0 and c4.put("y", 1, 20) == [] and c4.keys() == ["z", "w", "x", "y"]
assert c4.put("n", 5, 30) == ["z"] and c4.keys() == ["w", "x", "y", "n"] and c4.stats() == (4, 90)
assert c4.put("w", 7, 60) == ["y", "n"] and c4.keys() == ["x", "w"] and c4.stats() == (2, 80) and c4.drop("w") is True and c4.drop("w") is False and c4.stats() == (1, 20)
c5 = PinCache(3, 9)
c5.put("a", 1, 3); c5.put("b", 2, 3); c5.put("c", 3, 3)
assert c5.get("a") == 1 and c5.get("c") == 3 and c5.get("b") == 2 and c5.get("a") == 1 and c5.keys() == ["c", "b", "a"]
assert c5.put("d", 4, 6) == ["c", "b"] and c5.put("b", 2, 1) == ["d"] and c5.get("d") is None and c5.get("b") == 2 and c5.put("e", 5, 2) == []
assert c5.put("f", 6, 4) == ["e"] and c5.keys() == ["a", "b", "f"] and c5.stats() == (3, 8)
''',
    "wrong": _mut(_REF_C28, "        cands = [(e[3], e[4], k) for k, e in self._entries.items() if not e[2] and k != protect]", "        cands = [(e[4], e[3], k) for k, e in self._entries.items() if not e[2] and k != protect]"),
})


_REF_C29 = r'''
class Timeline:
    def __init__(self):
        self._text = {0: ""}
        self._parent = {0: None}
        self._kids = {0: []}
        self._pref = {}
        self._cur = 0
        self._next = 1

    def _mark(self):
        node = self._cur
        while self._parent[node] is not None:
            self._pref[self._parent[node]] = node
            node = self._parent[node]

    def _new(self, text):
        rev = self._next
        self._next += 1
        self._text[rev] = text
        self._parent[rev] = self._cur
        self._kids[rev] = []
        self._kids[self._cur].append(rev)
        self._cur = rev
        self._mark()
        return rev

    def write(self, s):
        return self._new(self._text[self._cur] + s)

    def erase(self, n):
        text = self._text[self._cur]
        if n < 0 or n > len(text):
            raise ValueError("cannot erase that many")
        return self._new(text[:len(text) - n])

    def undo(self):
        if self._parent[self._cur] is None:
            return False
        self._cur = self._parent[self._cur]
        self._mark()
        return True

    def redo(self):
        nxt = self._pref.get(self._cur)
        if nxt is None:
            return False
        self._cur = nxt
        self._mark()
        return True

    def checkout(self, rev):
        if rev not in self._text:
            raise KeyError(rev)
        self._cur = rev
        self._mark()

    def text(self):
        return self._text[self._cur]

    def current(self):
        return self._cur

    def parent(self, rev):
        return self._parent[rev]

    def children(self, rev):
        return sorted(self._kids[rev])

    def _path(self, rev):
        if rev not in self._text:
            raise KeyError(rev)
        out = []
        while rev is not None:
            out.append(rev)
            rev = self._parent[rev]
        return out[::-1]

    def log(self):
        return self._path(self._cur)

    def distance(self, a, b):
        pa, pb = self._path(a), self._path(b)
        common = 0
        while common < len(pa) and common < len(pb) and pa[common] == pb[common]:
            common += 1
        return (len(pa) - common, len(pb) - common)

    def prune(self, rev):
        if rev not in self._text:
            raise KeyError(rev)
        if rev == 0 or rev in self._path(self._cur):
            raise ValueError("cannot prune this revision")
        par = self._parent[rev]
        stack = [rev]
        removed = 0
        while stack:
            node = stack.pop()
            stack.extend(self._kids[node])
            del self._text[node], self._parent[node], self._kids[node]
            self._pref.pop(node, None)
            removed += 1
        self._kids[par].remove(rev)
        if self._pref.get(par) == rev:
            if self._kids[par]:
                self._pref[par] = max(self._kids[par])
            else:
                del self._pref[par]
        return removed
'''

ITEMS.append({
    "id": "C29",
    "kind": "class",
    "difficulty": "very hard",
    "entry_point": "Timeline",
    "prompt": r"""Write a Python class `Timeline`: a text buffer whose history is a TREE of revisions, with branching undo/redo.

Every revision has an integer id and a text. A new `Timeline` has only the root revision, id 0, with the empty text, and the root is the current revision. New revisions get the ids 1, 2, 3, ... in order of creation; ids are never reused.

Methods:
- `write(s: str) -> int` - create a new revision as a child of the current one, whose text is the current text followed by `s`; it becomes current. Returns its id.
- `erase(n: int) -> int` - the same, but the new text is the current text without its last `n` characters. `n = 0` is allowed. If `n < 0` or `n` exceeds the length of the current text, raise `ValueError` (no revision is created and no id is used up).
- `undo() -> bool` - move to the parent of the current revision. At the root: return `False` and do nothing.
- `redo() -> bool` - move to the PREFERRED child of the current revision (see below). If it has no children: return `False`.
- `checkout(rev: int)` - make any existing revision current. Unknown or pruned id: `KeyError`.
- `text() -> str`, `current() -> int` - of the current revision.
- `parent(rev) -> int | None` (`None` for the root), `children(rev) -> list[int]` (ascending ids).
- `log() -> list[int]` - the ids on the path from the root to the current revision, both included.
- `distance(a: int, b: int) -> tuple[int, int]` - `(ups, downs)`: how many parent steps lead from `a` up to the deepest revision that is an ancestor-or-self of both `a` and `b`, and how many child steps lead from there down to `b`.
- `prune(rev: int) -> int` - delete `rev` together with all its descendants and return how many revisions were deleted. Not allowed (raise `ValueError`, nothing changes) if `rev` is 0 or if the current revision is `rev` or one of its descendants.
`parent`, `children`, `distance` and `prune` raise `KeyError` for an unknown or pruned id (checked before the `ValueError` conditions).

Preferred child. Each revision that has children has exactly one preferred child, maintained by this rule: after every successful `write`, `erase`, `undo`, `redo` and `checkout`, for every revision r on the path from the root to the (new) current revision, r becomes the preferred child of its parent. So a freshly created revision is preferred; after `undo` the branch you just left stays preferred; and a `checkout` re-marks its whole path. When `prune` deletes the preferred child of a revision, the preferred child of that revision becomes its remaining child with the largest id (if any are left).

Example:

    t = Timeline()
    t.write("ab")      # 1
    t.write("cd")      # 2, text "abcd"
    t.undo()           # True, current is 1
    t.write("X")       # 3, text "abX"; revision 1 now has children [2, 3]
    t.undo(); t.redo() # back on 3 (the branch most recently used)
    t.checkout(2); t.undo(); t.redo()     # on 2 again: checkout(2) made 2 the preferred child of 1
    t.distance(2, 3)   # (1, 1)
    t.log()            # [0, 1, 2]""" + _TAIL,
    "reference": _REF_C29,
    "tests": _RAISES + r'''
t = Timeline()
assert t.current() == 0 and t.text() == "" and t.log() == [0] and t.undo() is False and t.redo() is False and t.parent(0) is None and t.children(0) == []
assert t.write("ab") == 1 and t.write("cd") == 2 and t.text() == "abcd" and t.undo() is True and t.text() == "ab" and t.current() == 1
assert t.write("X") == 3 and t.text() == "abX" and t.children(1) == [2, 3] and t.undo() and t.redo() and t.current() == 3
t.checkout(2)
assert t.undo() and t.redo() and t.current() == 2 and t.distance(2, 3) == (1, 1) and t.log() == [0, 1, 2]
assert t.erase(3) == 4 and t.text() == "a" and _raises(ValueError, t.erase, 2) and _raises(ValueError, t.erase, -1) and t.current() == 4
assert t.erase(0) == 5 and t.text() == "a" and t.children(4) == [5] and t.parent(3) == 1 and t.log() == [0, 1, 2, 4, 5]
assert t.distance(5, 3) == (3, 1) and t.distance(3, 3) == (0, 0) and t.distance(0, 5) == (0, 4) and t.distance(5, 0) == (4, 0) and t.distance(4, 5) == (0, 1)
assert _raises(ValueError, t.prune, 0) and _raises(ValueError, t.prune, 2) and _raises(ValueError, t.prune, 5) and _raises(KeyError, t.prune, 99) and t.children(1) == [2, 3]
assert t.prune(3) == 1 and t.children(1) == [2] and _raises(KeyError, t.checkout, 3) and _raises(KeyError, t.children, 3) and _raises(KeyError, t.parent, 3)
assert _raises(KeyError, t.distance, 3, 1) and _raises(KeyError, t.distance, 1, 42) and _raises(KeyError, t.prune, 3) and t.current() == 5
t.checkout(1)
assert t.write("p") == 6 and t.write("q") == 7 and t.text() == "abpq" and t.children(1) == [2, 6]
t.checkout(1)
assert t.redo() and t.current() == 6 and t.undo() and t.prune(6) == 2 and t.children(1) == [2] and _raises(KeyError, t.checkout, 7)
assert t.redo() and t.current() == 2 and t.redo() and t.current() == 4 and t.redo() and t.current() == 5 and t.redo() is False
t.checkout(2)
assert t.write("z") == 8 and t.text() == "abcdz" and t.children(2) == [4, 8]
t.checkout(0)
assert t.redo() and t.redo() and t.redo() and t.current() == 8 and t.redo() is False
t.checkout(5); t.checkout(0)
assert [t.redo(), t.current(), t.redo(), t.current(), t.redo(), t.current(), t.redo(), t.current(), t.redo()] == [True, 1, True, 2, True, 4, True, 5, False]
t.checkout(8)
assert t.write("!") == 9 and t.undo() and t.undo() and t.current() == 2 and t.redo() and t.current() == 8 and t.redo() and t.text() == "abcdz!"
t.checkout(4)
assert t.prune(8) == 2 and t.children(2) == [4] and t.undo() and t.redo() and t.current() == 4 and t.write("m") == 10 and t.children(4) == [5, 10]
t.checkout(5)
assert t.prune(10) == 1 and t.undo() and t.redo() and t.current() == 5 and t.log() == [0, 1, 2, 4, 5] and t.write("n") == 11 and t.parent(11) == 5
u = Timeline()
u.write("a"); u.undo(); u.write("b"); u.undo(); u.write("c"); u.undo()
assert u.children(0) == [1, 2, 3] and u.redo() and u.current() == 3 and u.undo() and u.prune(3) == 1 and u.redo() and u.current() == 2
u.checkout(1); u.checkout(0)
assert u.prune(1) == 1 and u.redo() and u.current() == 2 and u.undo() and _raises(ValueError, u.erase, 1) and u.write("") == 4 and u.text() == "" and u.distance(4, 2) == (1, 1)
''',
    "wrong": _mut(_REF_C29, "    def checkout(self, rev):\n        if rev not in self._text:\n            raise KeyError(rev)\n        self._cur = rev\n        self._mark()", "    def checkout(self, rev):\n        if rev not in self._text:\n            raise KeyError(rev)\n        self._cur = rev"),
})


_REF_C30 = r'''
class FairQueue:
    def __init__(self, aging, cap):
        self._aging = aging
        self._cap = cap
        self._waiting = {}          # job -> [base, waited, since or None (paused), seq]
        self._running = {}          # job -> [base, waited]
        self._seq = 0

    def _enqueue(self, job, base, waited, t):
        self._seq += 1
        self._waiting[job] = [base, waited, t, self._seq]

    def _waited(self, rec, t):
        return rec[1] + (t - rec[2] if rec[2] is not None else 0)

    def _ranked(self, t):
        rows = []
        for job, rec in self._waiting.items():
            if rec[2] is None:
                continue
            w = self._waited(rec, t)
            eff = rec[0] + min(self._cap, w // self._aging)
            rows.append((-eff, -w, rec[3], job, eff))
        rows.sort()
        return rows

    def submit(self, job, priority, t):
        if job in self._waiting or job in self._running:
            raise ValueError("duplicate job")
        self._enqueue(job, priority, 0, t)

    def start(self, t):
        rows = self._ranked(t)
        if not rows:
            return None
        job = rows[0][3]
        rec = self._waiting.pop(job)
        self._running[job] = [rec[0], self._waited(rec, t)]
        return job

    def finish(self, job, t):
        if job not in self._running:
            raise KeyError(job)
        del self._running[job]

    def requeue(self, job, t):
        if job not in self._running:
            raise KeyError(job)
        base, waited = self._running.pop(job)
        self._enqueue(job, base - 1, waited, t)

    def pause(self, job, t):
        if job not in self._waiting:
            raise KeyError(job)
        rec = self._waiting[job]
        if rec[2] is None:
            return False
        rec[1] = self._waited(rec, t)
        rec[2] = None
        return True

    def resume(self, job, t):
        if job not in self._waiting:
            raise KeyError(job)
        rec = self._waiting[job]
        if rec[2] is not None:
            return False
        rec[2] = t
        return True

    def cancel(self, job):
        if job in self._waiting:
            del self._waiting[job]
            return True
        if job in self._running:
            del self._running[job]
            return True
        return False

    def queue(self, t):
        return [(row[3], row[4]) for row in self._ranked(t)]
'''

ITEMS.append({
    "id": "C30",
    "kind": "class",
    "difficulty": "hard",
    "entry_point": "FairQueue",
    "prompt": r"""Write a Python class `FairQueue`: a job queue with priorities that grow while a job waits ("aging"), plus pausing, re-queueing and cancellation.

`FairQueue(aging: int, cap: int)` - `aging >= 1`, `cap >= 0`. Most methods take the current time `t` (an integer); across all calls `t` never decreases. Job names are strings.

A job is in one of the states WAITING, PAUSED or RUNNING (any number of jobs may be running), or it is gone. Each job has a base priority (integer, may become negative) and an accumulated waiting time: the total time it has spent in the WAITING state so far. Time spent PAUSED or RUNNING does not count.

At time t a WAITING job's effective priority is `base + min(cap, waited // aging)` where `waited` is its accumulated waiting time up to t.

Methods:
- `submit(job, priority, t)` - add a new WAITING job with zero waiting time. If a job with this name is currently WAITING, PAUSED or RUNNING, raise `ValueError`. (A name may be reused once the earlier job is gone.)
- `start(t)` - pick the WAITING job that ranks first and make it RUNNING; return its name, or `None` if no job is WAITING. Ranking: higher effective priority at time t first; among equals the larger accumulated waiting time first; among those the job that was enqueued earlier (a job is enqueued when it is submitted and again each time it is re-queued).
- `finish(job, t)` - a RUNNING job is done and gone. Not RUNNING: `KeyError`.
- `requeue(job, t)` - a RUNNING job goes back to WAITING: its base priority drops by 1, it keeps its accumulated waiting time (which continues to grow from t), and it counts as enqueued now. Not RUNNING: `KeyError`.
- `pause(job, t) -> bool` - a WAITING job becomes PAUSED (returns `True`); if it is already PAUSED return `False`. `resume(job, t) -> bool` - a PAUSED job becomes WAITING again (`True`), keeping its base priority, waiting time and enqueue order; if it is WAITING already return `False`. Both raise `KeyError` if the job is neither WAITING nor PAUSED.
- `cancel(job) -> bool` - remove the job whatever its state; `False` if there is no such job.
- `queue(t) -> list[tuple[str, int]]` - the WAITING jobs (not the paused ones) as `(name, effective priority at t)`, in the order in which repeated `start(t)` calls would take them.

Example with `q = FairQueue(aging=10, cap=3)`:

    q.submit("a", 5, 0); q.submit("b", 5, 0); q.submit("c", 7, 4)
    q.queue(4)       # [("c", 7), ("a", 5), ("b", 5)]
    q.queue(40)      # [("c", 10), ("a", 8), ("b", 8)]   (the bonus is capped at 3)
    q.submit("d", 6, 10)
    q.queue(20)      # [("c", 8), ("a", 7), ("b", 7), ("d", 7)]   (a and b have waited longer than d)
    q.start(20)      # "c"
    q.start(20)      # "a"
    q.requeue("a", 25)                # a: base 4, waited 20, waiting again from 25
    q.queue(30)      # [("b", 8), ("d", 8), ("a", 6)]""" + _TAIL,
    "reference": _REF_C30,
    "tests": _RAISES + r'''
q = FairQueue(aging=10, cap=3)
q.submit("a", 5, 0); q.submit("b", 5, 0); q.submit("c", 7, 4)
assert q.queue(4) == [("c", 7), ("a", 5), ("b", 5)] and q.queue(40) == [("c", 10), ("a", 8), ("b", 8)] and q.queue(9) == [("c", 7), ("a", 5), ("b", 5)]
q.submit("d", 6, 10)
assert q.queue(10) == [("c", 7), ("a", 6), ("b", 6), ("d", 6)] and q.queue(20) == [("c", 8), ("a", 7), ("b", 7), ("d", 7)]
assert q.start(20) == "c" and q.start(20) == "a" and q.queue(20) == [("b", 7), ("d", 7)]
q.requeue("a", 25)
assert q.queue(30) == [("b", 8), ("d", 8), ("a", 6)]
assert q.pause("b", 30) is True and q.pause("b", 31) is False and q.queue(35) == [("d", 8), ("a", 7)]
assert q.resume("b", 50) is True and q.resume("b", 50) is False and q.queue(50) == [("d", 9), ("b", 8), ("a", 7)]
q.finish("c", 50)
assert _raises(KeyError, q.finish, "c", 51) and _raises(KeyError, q.finish, "b", 51) and _raises(KeyError, q.requeue, "b", 51) and _raises(KeyError, q.requeue, "zz", 51)
assert _raises(ValueError, q.submit, "a", 1, 52) and q.queue(52) == [("d", 9), ("b", 8), ("a", 7)]
q.submit("c", 1, 52)
assert q.cancel("d") is True and q.cancel("d") is False and q.start(52) == "b" and _raises(ValueError, q.submit, "b", 9, 52)
assert _raises(KeyError, q.pause, "b", 53) and _raises(KeyError, q.pause, "nope", 53) and _raises(KeyError, q.resume, "b", 53) and q.resume("a", 53) is False
assert q.cancel("b") is True and _raises(KeyError, q.finish, "b", 60) and q.queue(60) == [("a", 7), ("c", 1)] and q.queue(62) == [("a", 7), ("c", 2)]
assert q.start(62) == "a" and q.start(62) == "c" and q.start(62) is None and q.queue(99) == []
q.requeue("c", 70); q.requeue("a", 70)
assert q.queue(70) == [("a", 6), ("c", 1)] and q.queue(100) == [("a", 6), ("c", 3)] and q.pause("a", 100) and q.start(100) == "c" and q.start(100) is None
q2 = FairQueue(1000, 0)
q2.submit("p", 1, 0); q2.submit("q", 1, 0)
assert q2.start(0) == "p" and q2.queue(5) == [("q", 1)]
q2.requeue("p", 0); q2.submit("r", 0, 0)
assert q2.queue(0) == [("q", 1), ("p", 0), ("r", 0)] and q2.queue(10**9) == [("q", 1), ("p", 0), ("r", 0)]
q3 = FairQueue(5, 100)
q3.submit("x", 0, 0); q3.submit("y", 0, 0); q3.submit("z", 3, 14)
assert q3.pause("x", 10) and q3.queue(14) == [("z", 3), ("y", 2)] and q3.queue(15) == [("y", 3), ("z", 3)] and q3.resume("x", 20)
assert q3.queue(20) == [("y", 4), ("z", 4), ("x", 2)] and q3.queue(29) == [("z", 6), ("y", 5), ("x", 3)]
assert q3.start(30) == "y" and q3.start(30) == "z" and q3.queue(30) == [("x", 4)]
q3.requeue("y", 40); q3.requeue("z", 40)
assert q3.queue(40) == [("x", 6), ("y", 5), ("z", 5)] and q3.pause("y", 45) and q3.cancel("y") and q3.queue(50) == [("x", 8), ("z", 7)]
q4 = FairQueue(3, 2)
q4.submit("m", -5, 7); q4.submit("n", -4, 7)
assert q4.queue(7) == [("n", -4), ("m", -5)] and q4.pause("n", 8) and q4.queue(13) == [("m", -3)] and q4.resume("n", 13) and q4.queue(13) == [("m", -3), ("n", -4)]
assert q4.queue(15) == [("m", -3), ("n", -3)] and q4.start(15) == "m" and q4.queue(17) == [("n", -3)] and q4.queue(18) == [("n", -2)] and q4.queue(10**6) == [("n", -2)]
''',
    "wrong": _mut(_REF_C30, "        if rec[2] is None:\n            return False\n        rec[1] = self._waited(rec, t)\n        rec[2] = None\n        return True", "        if rec[2] is None:\n            return False\n        rec[2] = None\n        return True"),
})

# ---------------------------------------------------------------------------
# Calibration tasks (CP1-CP6): one per kind, same style and difficulty
# ---------------------------------------------------------------------------

_REF_CP1 = r'''
import re

def unpack_fields(layout, data):
    toks = []
    i, n = 0, len(layout)
    word = re.compile(r"[A-Za-z0-9_]+")
    while i < n:
        ch = layout[i]
        if ch.isspace():
            i += 1
        elif ch in "[]{};":
            toks.append(ch)
            i += 1
        else:
            m = word.match(layout, i)
            if not m:
                raise ValueError("bad character")
            toks.append(m.group())
            i = m.end()
    pos = [0]
    int_type = re.compile(r"([ui])(8|16|24|32)(le)?")
    name_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take(expected=None):
        tok = peek()
        if tok is None or (expected is not None and tok != expected):
            raise ValueError("unexpected token")
        pos[0] += 1
        return tok

    def name():
        tok = take()
        if not name_re.fullmatch(tok):
            raise ValueError("bad name")
        return tok

    def count():
        take("[")
        tok = take()
        if tok.isdigit():
            val = int(tok)
        elif name_re.fullmatch(tok):
            val = tok
        else:
            raise ValueError("bad count")
        take("]")
        return val

    def block(closing):
        stmts = []
        names = set()
        while True:
            tok = peek()
            if tok == ";":
                take()
                continue
            if tok == closing:
                return stmts
            st = statement()
            if st[1] is not None:
                if st[1] in names:
                    raise ValueError("duplicate field")
                names.add(st[1])
            stmts.append(st)
            if peek() != closing:
                take(";")

    def statement():
        kind = take()
        if kind == "pad":
            return ("pad", None, count())
        if kind == "group":
            nm = name()
            cnt = count()
            take("{")
            body = block("}")
            take("}")
            return ("group", nm, cnt, body)
        if kind in ("bytes", "text"):
            nm = name()
            return (kind, nm, count())
        m = int_type.fullmatch(kind)
        if not m:
            raise ValueError("unknown type")
        nm = name()
        cnt = count() if peek() == "[" else None
        return ("int", nm, cnt, m.group(1) == "i", int(m.group(2)) // 8, "little" if m.group(3) else "big")

    program = block(None)
    at = [0]

    def grab(k):
        if at[0] + k > len(data):
            raise ValueError("out of data")
        chunk = data[at[0]:at[0] + k]
        at[0] += k
        return chunk

    def resolve(cnt, scopes):
        if isinstance(cnt, int):
            return cnt
        for scope in reversed(scopes):
            if cnt in scope:
                v = scope[cnt]
                if type(v) is not int or v < 0:
                    raise ValueError("bad count value")
                return v
        raise ValueError("unknown count name")

    def run(stmts, scopes):
        out = {}
        scopes = scopes + [out]
        for st in stmts:
            kind = st[0]
            if kind == "pad":
                grab(resolve(st[2], scopes))
            elif kind == "group":
                k = resolve(st[2], scopes)
                out[st[1]] = [run(st[3], scopes) for _ in range(k)]
            elif kind == "bytes":
                out[st[1]] = bytes(grab(resolve(st[2], scopes)))
            elif kind == "text":
                chunk = bytes(grab(resolve(st[2], scopes)))
                if any(b >= 0x80 for b in chunk):
                    raise ValueError("not ASCII")
                out[st[1]] = chunk.rstrip(b"\x00").decode("ascii")
            else:
                _, nm, cnt, signed, size, order = st
                if cnt is None:
                    out[nm] = int.from_bytes(grab(size), order, signed=signed)
                else:
                    k = resolve(cnt, scopes)
                    out[nm] = [int.from_bytes(grab(size), order, signed=signed) for _ in range(k)]
        return out

    result = run(program, [])
    if at[0] != len(data):
        raise ValueError("trailing data")
    return result
'''

ITEMS.append({
    "id": "CP1",
    "kind": "parsing",
    "difficulty": "very hard",
    "entry_point": "unpack_fields",
    "prompt": r"""Write a Python function `unpack_fields(layout: str, data: bytes) -> dict` that decodes binary data according to a layout written in a small description language, and returns a dict of field name -> value (in layout order).

Layout syntax. Tokens are words (letters, digits, `_`) and the single characters `[ ] { } ;`; whitespace may appear between any two tokens and is required only between two adjacent words. A layout is a list of statements separated by `;`. Empty statements are allowed (so `;;` and a trailing `;` are fine). Statements:

- `TYPE NAME` - one integer. TYPE is `u8`, `u16`, `u24`, `u32` (unsigned) or `i8`, `i16`, `i24`, `i32` (signed two's complement), 1 to 4 bytes, big-endian by default; the suffix `le` (as in `u16le`, `i32le`) means little-endian.
- `TYPE NAME[COUNT]` - a list of COUNT such integers.
- `bytes NAME[COUNT]` - COUNT raw bytes, as a `bytes` object.
- `text NAME[COUNT]` - COUNT bytes decoded as ASCII into a `str`, after removing all trailing zero bytes (0x00). A byte >= 0x80 is an error.
- `pad[COUNT]` - skip COUNT bytes; produces no field.
- `group NAME[COUNT] { statements }` - a list of COUNT dicts; each is decoded by running the inner statements (same syntax, `;`-separated) once.

NAME is a letter or `_` followed by letters, digits or `_`. COUNT is either a decimal number (digits only) or the NAME of an integer field that has ALREADY been decoded: it is looked up first among the fields decoded so far in the dict currently being filled, then in the enclosing group's dict (for the element being decoded), and so on outwards to the top level. The value found must be a plain integer >= 0 (not a list, bytes, text or group).

Errors - always `ValueError`:
- Syntax errors anywhere in the layout: unknown type, bad name, missing `]` or `}`, a missing `;` between statements, stray tokens or characters. The entire layout is checked before any decoding, so this applies even to a group body that would be decoded zero times.
- Two fields with the same name directly in the same statement list (top level, or the body of one group). The same name in different lists is fine. This is also checked up front.
- A COUNT name that cannot be found at the time it is needed, or whose value is not a plain non-negative integer.
- Running out of data, or data left over after the last statement.

Examples:
- `unpack_fields("u8 n; u16le vals[n]; text tag[4]", bytes([2, 1, 0, 0, 1, 111, 107, 0, 0]))` returns `{"n": 2, "vals": [1, 256], "tag": "ok"}`.
- `unpack_fields("u8 n; group pts[n] { i8 x; i8 y; }; bytes rest[2]", bytes([2, 1, 255, 3, 4, 9, 8]))` returns `{"n": 2, "pts": [{"x": 1, "y": -1}, {"x": 3, "y": 4}], "rest": b"\t\x08"}`.
- `unpack_fields("", b"")` returns `{}`.""" + _TAIL,
    "reference": _REF_CP1,
    "tests": _RAISES + r'''
assert unpack_fields("u8 n; u16le vals[n]; text tag[4]", bytes([2, 1, 0, 0, 1, 111, 107, 0, 0])) == {"n": 2, "vals": [1, 256], "tag": "ok"}
assert unpack_fields("u8 n; group pts[n] { i8 x; i8 y; }; bytes rest[2]", bytes([2, 1, 255, 3, 4, 9, 8])) == {"n": 2, "pts": [{"x": 1, "y": -1}, {"x": 3, "y": 4}], "rest": b"\t\x08"}
assert unpack_fields("", b"") == {} and unpack_fields(" ; ;\n ", b"") == {} and list(unpack_fields("u8 z; u8 a; u8 m", b"\x01\x02\x03")) == ["z", "a", "m"]
_b = bytes.fromhex("0102 0102 fffe feff 010203 fdffff 00000100 ffffffff")
assert unpack_fields("u16 a; u16le b; i16 c; i16le d; u24 e; i24le f; u32 g; i32 h", _b) == {"a": 258, "b": 513, "c": -2, "d": -2, "e": 66051, "f": -3, "g": 256, "h": -1}
assert unpack_fields("i8 a;u8 b;u8le c;i32le d;u32le e", bytes([128, 128, 7, 0, 0, 0, 128, 1, 0, 0, 128])) == {"a": -128, "b": 128, "c": 7, "d": -2**31, "e": 2**31 + 1}
assert unpack_fields("bytes raw[3]; pad[2]; u8 last;", b"abcXY\x07") == {"raw": b"abc", "last": 7}
assert unpack_fields("u8 w; u8 h; group rows[h] { u8 tag; group cells[w] { u8 v } }", bytes([2, 2, 9, 1, 2, 8, 3, 4])) == {"w": 2, "h": 2, "rows": [{"tag": 9, "cells": [{"v": 1}, {"v": 2}]}, {"tag": 8, "cells": [{"v": 3}, {"v": 4}]}]}
assert unpack_fields("u8 n; group g[n] { u8 n; u8 d[n] }", bytes([2, 1, 7, 2, 8, 9])) == {"n": 2, "g": [{"n": 1, "d": [7]}, {"n": 2, "d": [8, 9]}]}
assert unpack_fields("u8 n; group g[1] { u8 d[n]; u8 n }", bytes([2, 5, 6, 9])) == {"n": 2, "g": [{"d": [5, 6], "n": 9}]}
assert unpack_fields("u8 n; u8 xs[n]; text t[0]; group g[n] { u8 q }; bytes b[n]", b"\x00") == {"n": 0, "xs": [], "t": "", "g": [], "b": b""}
assert unpack_fields("text t [ 4 ] ;text u[3]", b"a\x00b\x00\x00\x00\x00") == {"t": "a\x00b", "u": ""}
assert unpack_fields("u8 k; pad[k]; group g[2]{pad[1];u8 v;};u16 end", bytes([3, 0, 0, 0, 9, 1, 9, 2, 1, 0])) == {"k": 3, "g": [{"v": 1}, {"v": 2}], "end": 256}
assert _raises(ValueError, unpack_fields, "u16 a", b"\x01") and _raises(ValueError, unpack_fields, "u8 a", b"\x01\x02") and _raises(ValueError, unpack_fields, "u7 a", b"\x01")
assert _raises(ValueError, unpack_fields, "u8 xs[n]", b"\x01") and _raises(ValueError, unpack_fields, "u8 xs[n]; u8 n", b"\x01\x01") and _raises(ValueError, unpack_fields, "u8 a[1]; u8 b[a]", b"\x01\x01")
assert _raises(ValueError, unpack_fields, "i8 n; u8 xs[n]", b"\xff") and _raises(ValueError, unpack_fields, "u8 a; u8 a", b"\x01\x02") and _raises(ValueError, unpack_fields, "text t[1]", b"\x80")
assert _raises(ValueError, unpack_fields, "u8", b"\x01") and _raises(ValueError, unpack_fields, "u8 a b", b"\x01") and _raises(ValueError, unpack_fields, "u8 a[", b"\x01")
assert _raises(ValueError, unpack_fields, "group g[1] { u8 x", b"\x01") and _raises(ValueError, unpack_fields, "u8 a; }", b"\x01") and _raises(ValueError, unpack_fields, "u8 9a", b"\x01")
assert _raises(ValueError, unpack_fields, "u8 a,", b"\x01") and _raises(ValueError, unpack_fields, "u8 a u8 b", b"\x01\x02") and _raises(ValueError, unpack_fields, "u8 a[-1]", b"\x01")
assert _raises(ValueError, unpack_fields, "u8 n; group g[n] { u9 x }", b"\x00") and _raises(ValueError, unpack_fields, "u8 n; group g[n] { u8 x; u8 x }", b"\x00")
assert _raises(ValueError, unpack_fields, "u8 g; group g[1] { u8 x }", b"\x01\x02") and _raises(ValueError, unpack_fields, "bytes b[2]; u8 c[b]", b"\x00\x01\x02")
assert _raises(ValueError, unpack_fields, "group g[2] { u8 x }", b"\x01") and _raises(ValueError, unpack_fields, "u8 n; group g[n] { u8 x } u8 y", b"\x00\x01") and _raises(ValueError, unpack_fields, "pad[2]", b"\x01")
''',
    "wrong": _mut(_REF_CP1, "        for scope in reversed(scopes):", "        for scope in scopes:"),
})


_REF_CP2 = r'''
def understaffed(shifts, breaks, demand, horizon):
    def merged(intervals):
        out = []
        for s, e in sorted(intervals):
            if s >= e:
                continue
            if out and s <= out[-1][1]:
                if e > out[-1][1]:
                    out[-1][1] = e
            else:
                out.append([s, e])
        return out

    by_worker = {}
    for w, s, e in shifts:
        by_worker.setdefault(w, ([], []))[0].append((s, e))
    for w, s, e in breaks:
        if w in by_worker:
            by_worker[w][1].append((s, e))

    delta = {}
    for w, (sh, br) in by_worker.items():
        sh = merged(sh)
        br = merged(br)
        j = 0
        for s, e in sh:
            cur = s
            while j < len(br) and br[j][1] <= cur:
                j += 1
            k = j
            while k < len(br) and br[k][0] < e:
                if br[k][0] > cur:
                    delta[cur] = delta.get(cur, 0) + 1
                    delta[br[k][0]] = delta.get(br[k][0], 0) - 1
                cur = max(cur, br[k][1])
                k += 1
            if cur < e:
                delta[cur] = delta.get(cur, 0) + 1
                delta[e] = delta.get(e, 0) - 1
            j = max(j, k - 1)

    need_at = {}
    for t, r in demand:
        need_at[t] = r
    points = sorted(set(delta) | set(need_at) | {0, horizon})
    present = 0
    need = 0
    out = []
    for idx, p in enumerate(points):
        present += delta.get(p, 0)
        if p in need_at:
            need = need_at[p]
        if p >= horizon:
            break
        nxt = min(points[idx + 1], horizon)
        a = max(p, 0)
        if a >= nxt:
            continue
        lack = need - present
        if lack > 0:
            if out and out[-1][1] == a and out[-1][2] == lack:
                out[-1] = (out[-1][0], nxt, lack)
            else:
                out.append((a, nxt, lack))
    return out
'''

ITEMS.append({
    "id": "CP2",
    "kind": "interval",
    "difficulty": "very hard",
    "entry_point": "understaffed",
    "prompt": r"""Write a Python function `understaffed(shifts, breaks, demand, horizon) -> list[tuple[int, int, int]]` that reports when a shop has fewer people on the floor than required.

All times are integers; every interval `(start, end)` is half-open, covering `start <= t < end`.

- `shifts` is a list of `(worker, start, end)`. A worker may have several shifts; they may overlap or touch each other (the worker still counts only once at any moment).
- `breaks` is a list of `(worker, start, end)`. During a break the worker is NOT on the floor, even if a shift covers that time. Breaks may overlap each other, lie partly or wholly outside the worker's shifts, or belong to a worker with no shifts at all (then they have no effect).
- So a worker is PRESENT at time t when t lies in at least one of their shifts and in none of their breaks.
- `demand` is a list of `(time, required)` change points, in any order: from `time` on, `required` people are needed, until the next later change point. Before the earliest change point the requirement is 0. If two entries have the same time, the one that comes later in the list wins.
- `horizon` (> 0): only the window `0 <= t < horizon` is examined. Shifts, breaks and change points may lie partly or entirely outside it; a change point at a negative time still sets the requirement in force at time 0.

At a moment t the DEFICIT is `required(t) - present(t)`. Return the list of maximal segments `(a, b, deficit)` such that the deficit is the same positive number throughout `a <= t < b`, sorted by `a`. "Maximal" means that two adjacent segments that touch never have the same deficit (merge them), even if a shift change or a demand change point falls at the boundary. Moments with deficit <= 0 are not reported.

Limits: up to 100,000 shifts, 100,000 breaks and 100,000 change points, times up to about 10**9, so the solution must be a sort-and-sweep, not a scan over time units or over all workers at every event.

Example:

    understaffed([("ann", 0, 8), ("bob", 4, 12)], [("ann", 3, 5)], [(0, 1), (6, 2), (10, 0)], 12)

returns `[(3, 4, 1), (8, 10, 1)]`: ann is away 3-5 and bob only arrives at 4, so nobody is present during 3-4 while one person is required; during 8-10 two are required and only bob is there.
With `demand = [(0, 2)]` instead, the result is `[(0, 3, 1), (3, 4, 2), (4, 5, 1), (8, 12, 1)]`.""" + _TAIL,
    "reference": _REF_CP2,
    "tests": _LCG + r'''
def _slow(shifts, breaks, demand, horizon):
    out = []
    order = sorted(range(len(demand)), key=lambda i: (demand[i][0], i))
    for t in range(horizon):
        workers = {w for w, s, e in shifts if s <= t < e} - {w for w, s, e in breaks if s <= t < e}
        need = 0
        for i in order:
            if demand[i][0] <= t:
                need = demand[i][1]
        lack = need - len(workers)
        if lack > 0:
            if out and out[-1][1] == t and out[-1][2] == lack:
                out[-1] = (out[-1][0], t + 1, lack)
            else:
                out.append((t, t + 1, lack))
    return out

_s = [("ann", 0, 8), ("bob", 4, 12)]
assert understaffed(_s, [("ann", 3, 5)], [(0, 1), (6, 2), (10, 0)], 12) == [(3, 4, 1), (8, 10, 1)]
assert understaffed(_s, [("ann", 3, 5)], [(0, 2)], 12) == [(0, 3, 1), (3, 4, 2), (4, 5, 1), (8, 12, 1)]
assert understaffed([], [], [], 10) == [] and understaffed([], [], [(0, 3)], 10) == [(0, 10, 3)] and understaffed([], [("x", 0, 5)], [(4, 1)], 10) == [(4, 10, 1)]
assert understaffed([], [], [(-5, 2), (20, 9)], 10) == [(0, 10, 2)] and understaffed([], [], [(3, 1), (3, 4), (7, 0)], 10) == [(3, 7, 4)]
assert understaffed([("a", 0, 5), ("a", 3, 9), ("a", 9, 10)], [], [(0, 1)], 12) == [(10, 12, 1)]
assert understaffed([("a", 0, 10)], [("a", 2, 4), ("a", 3, 6), ("a", 6, 7), ("a", 20, 30)], [(0, 1)], 10) == [(2, 7, 1)]
assert understaffed([("a", 0, 5), ("b", 5, 10)], [], [(0, 2)], 10) == [(0, 10, 1)]
assert understaffed([("a", 0, 5), ("b", 5, 10)], [], [(0, 2), (5, 2), (7, 2)], 10) == [(0, 10, 1)]
assert understaffed([("a", 0, 5), ("b", 3, 10)], [], [(0, 1), (5, 2)], 10) == [(5, 10, 1)]
assert understaffed([("a", -10, 3), ("b", 8, 50)], [("b", 9, 100)], [(-1, 1)], 10) == [(3, 8, 1), (9, 10, 1)]
assert understaffed([("a", 2, 6)], [("a", 0, 3), ("a", 5, 9)], [(0, 1)], 8) == [(0, 3, 1), (5, 8, 1)]
assert understaffed([("a", 0, 4), ("b", 0, 4), ("c", 2, 4)], [("b", 1, 2)], [(0, 3), (3, 1)], 5) == [(0, 1, 1), (1, 2, 2), (4, 5, 1)]
_g = _lcg(808)
for _case in range(120):
    _names = "abcd"[:1 + next(_g) % 4]
    _sh = [(_names[next(_g) % len(_names)], next(_g) % 30 - 3, 0) for _ in range(next(_g) % 7)]
    _sh = [(w, s, s + 1 + next(_g) % 12) for w, s, _ in _sh]
    _br = [(_names[next(_g) % len(_names)], next(_g) % 30 - 3, 0) for _ in range(next(_g) % 6)]
    _br = [(w, s, s + 1 + next(_g) % 6) for w, s, _ in _br]
    _dm = [(next(_g) % 34 - 4, next(_g) % 4) for _ in range(next(_g) % 6)]
    _hz = 1 + next(_g) % 32
    assert understaffed(_sh, _br, _dm, _hz) == _slow(_sh, _br, _dm, _hz), (_sh, _br, _dm, _hz)
_g = _lcg(2468)
_bs = []
for _i in range(60000):
    _st = next(_g) % 10**9
    _bs.append(("w%d" % (next(_g) % 4000), _st, _st + 1 + next(_g) % 40000000))
_bb = []
for _i in range(60000):
    _st = next(_g) % 10**9
    _bb.append(("w%d" % (next(_g) % 4200), _st, _st + 1 + next(_g) % 3000000))
_bd = [(next(_g) % 10**9, 1000 + next(_g) % 1200) for _i in range(50000)]
_res = understaffed(_bs, _bb, _bd, 10**9)
assert len(_res) == 157091
assert sum((b - a) * d for a, b, d in _res) == 610624041910
assert sum(b - a for a, b, d in _res) == 963063788
assert all(x[1] <= y[0] and (x[1] < y[0] or x[2] != y[2]) for x, y in zip(_res, _res[1:])) and all(a < b and d > 0 for a, b, d in _res)
''',
    "wrong": _mut(_REF_CP2, "            if out and out[-1][1] == a and out[-1][2] == lack:", "            if False:"),
})


_REF_CP3 = r'''
def shuffle_rounds(n, program, rounds, positions):
    moves = []
    for text in program:
        parts = text.split()
        if not parts:
            raise ValueError("empty move")
        name, raw = parts[0], parts[1:]
        try:
            args = [int(x) for x in raw]
        except ValueError:
            raise ValueError("bad argument")
        want = {"rot": 1, "rev": 2, "lift": 2, "swap": 2, "weave": 0}
        if name not in want or len(args) != want[name]:
            raise ValueError("bad move")
        if name in ("rev", "lift") and not (0 <= args[0] <= args[1] < n):
            raise ValueError("bad range")
        if name == "swap" and not (0 <= args[0] < n and 0 <= args[1] < n):
            raise ValueError("bad position")
        moves.append((name, args))

    row = list(range(n))
    for name, args in moves:
        if name == "rot":
            k = args[0] % n
            if k:
                row = row[-k:] + row[:-k]
        elif name == "rev":
            i, j = args
            row[i:j + 1] = row[i:j + 1][::-1]
        elif name == "lift":
            i, j = args
            row = row[i:j + 1] + row[:i] + row[j + 1:]
        elif name == "swap":
            i, j = args
            row[i], row[j] = row[j], row[i]
        else:
            half = (n + 1) // 2
            front, back = row[:half], row[half:]
            row = [None] * n
            row[0::2] = front
            row[1::2] = back
    # after one round position i holds the tile that started at row[i]
    result = [None] * n
    seen = [False] * n
    for start in range(n):
        if seen[start]:
            continue
        cycle = []
        x = start
        while not seen[x]:
            seen[x] = True
            cycle.append(x)
            x = row[x]
        size = len(cycle)
        shift = rounds % size
        for idx, pos in enumerate(cycle):
            result[pos] = cycle[(idx + shift) % size]
    return [result[p] for p in positions]
'''

ITEMS.append({
    "id": "CP3",
    "kind": "simulation",
    "difficulty": "hard",
    "entry_point": "shuffle_rounds",
    "prompt": r"""Write a Python function `shuffle_rounds(n: int, program: list[str], rounds: int, positions: list[int]) -> list[int]`.

A row has `n` positions numbered `0..n-1` from the left. Initially tile number t lies at position t. A machine rearranges the row by executing the moves of `program` in order; one complete pass through the program is a ROUND, and the machine performs `rounds` rounds (`0 <= rounds <= 10**18`). Return, for each position in `positions`, the number of the tile lying there at the end.

Each move is a string of whitespace-separated words:
- `rot K` - rotate the whole row to the right by K: the tile at position i moves to position `(i + K) mod n`. K may be any integer (negative means to the left; |K| may exceed n).
- `rev I J` - reverse the order of the tiles at positions I..J inclusive.
- `lift I J` - take out the tiles at positions I..J inclusive, close the gap, and put them at the very left of the row in their original order.
- `swap I J` - exchange the tiles at positions I and J (I = J is allowed and does nothing).
- `weave` - split the row into a front part (the first `ceil(n / 2)` tiles) and a back part (the rest), then interleave them starting with the front part: front[0], back[0], front[1], back[1], ... (when n is odd, the last tile of the front part ends up last).

Validation: before anything is executed (even when `rounds` is 0) every move is checked, and `ValueError` is raised for an unknown move name, a wrong number of arguments, an argument that is not an integer written in the usual way (optional `-`, digits), a position outside `0..n-1` in `rev`, `lift` or `swap`, or `I > J` in `rev` or `lift`.

Limits: `1 <= n <= 20,000`, up to 200 moves. `rounds` is far too large to run round by round; the call must finish in about a second.

Examples with `n = 5` (rows written left to right):
- one round of `["rot 1"]` gives `4 0 1 2 3`, so `shuffle_rounds(5, ["rot 1"], 1, [0, 1])` returns `[4, 0]`, and with `rounds = 7` it returns `[3, 4]`.
- one round of `["weave"]` gives `0 3 1 4 2`; of `["lift 2 3"]` gives `2 3 0 1 4`; of `["rev 1 3"]` gives `0 3 2 1 4`.
- one round of `["rot 1", "rev 0 2", "weave"]` gives `1 2 0 3 4` (after the rot: `4 0 1 2 3`; after the rev: `1 0 4 2 3`), and two rounds give `2 0 1 3 4`. So `shuffle_rounds(5, ["rot 1", "rev 0 2", "weave"], 2, [0, 1, 2, 3, 4])` returns `[2, 0, 1, 3, 4]`.""" + _TAIL,
    "reference": _REF_CP3,
    "tests": _RAISES + _LCG + r'''
def _slow(n, program, rounds, positions):
    row = list(range(n))
    for _ in range(rounds):
        for text in program:
            p = text.split()
            a = [int(x) for x in p[1:]]
            if p[0] == "rot":
                new = [None] * n
                for i in range(n):
                    new[(i + a[0]) % n] = row[i]
                row = new
            elif p[0] == "rev":
                seg = row[a[0]:a[1] + 1]
                seg.reverse()
                row = row[:a[0]] + seg + row[a[1] + 1:]
            elif p[0] == "lift":
                row = row[a[0]:a[1] + 1] + row[:a[0]] + row[a[1] + 1:]
            elif p[0] == "swap":
                row[a[0]], row[a[1]] = row[a[1]], row[a[0]]
            else:
                half = (n + 1) // 2
                front, back = row[:half], row[half:]
                row = []
                for i in range(half):
                    row.append(front[i])
                    if i < len(back):
                        row.append(back[i])
    return [row[p] for p in positions]

_all5 = [0, 1, 2, 3, 4]
assert shuffle_rounds(5, ["rot 1"], 1, [0, 1]) == [4, 0] and shuffle_rounds(5, ["rot 1"], 7, [0, 1]) == [3, 4] and shuffle_rounds(5, ["rot -6"], 1, _all5) == [1, 2, 3, 4, 0]
assert shuffle_rounds(5, ["weave"], 1, _all5) == [0, 3, 1, 4, 2] and shuffle_rounds(5, ["lift 2 3"], 1, _all5) == [2, 3, 0, 1, 4] and shuffle_rounds(5, ["rev 1 3"], 1, _all5) == [0, 3, 2, 1, 4]
assert shuffle_rounds(5, ["rot 1", "rev 0 2", "weave"], 1, _all5) == [1, 2, 0, 3, 4] and shuffle_rounds(5, ["rot 1", "rev 0 2", "weave"], 2, _all5) == [2, 0, 1, 3, 4]
assert shuffle_rounds(5, ["swap 0 4", "swap 2 2"], 1, [4, 0, 2]) == [0, 4, 2] and shuffle_rounds(5, ["swap 0 4"], 10**18, _all5) == _all5 and shuffle_rounds(5, ["swap 0 4"], 10**18 + 1, [0]) == [4]
assert shuffle_rounds(4, ["weave"], 1, [0, 1, 2, 3]) == [0, 2, 1, 3] and shuffle_rounds(1, ["weave", "rot 5", "rev 0 0", "lift 0 0"], 99, [0, 0]) == [0, 0]
assert shuffle_rounds(6, [], 10**18, [5, 0]) == [5, 0] and shuffle_rounds(6, ["rot 2", "lift 1 4"], 0, [3]) == [3] and shuffle_rounds(7, ["  rot   3  "], 2, []) == []
assert shuffle_rounds(7, ["rot 1"], 10**18, [0, 6]) == [(0 - 10**18) % 7, (6 - 10**18) % 7] and shuffle_rounds(8, ["rot 3", "rot -3"], 12345, [5]) == [5]
assert all(shuffle_rounds(n, prog, r, list(range(n))) == _slow(n, prog, r, list(range(n))) for n, prog in ((7, ["weave"]), (8, ["weave", "rot 3"]), (9, ["lift 3 5", "rev 2 8", "swap 0 6"]), (10, ["rot -3", "weave", "lift 9 9", "rev 0 9"]), (11, ["weave", "weave", "swap 1 10", "rot 25"])) for r in (0, 1, 2, 3, 10, 61))
_g = _lcg(1357)
for _case in range(60):
    _n = 2 + next(_g) % 14
    _prog = []
    for _ in range(1 + next(_g) % 6):
        _k = next(_g) % 5
        _i = next(_g) % _n
        _j = _i + next(_g) % (_n - _i)
        _prog.append(["rot %d" % (next(_g) % 41 - 20), "rev %d %d" % (_i, _j), "lift %d %d" % (_i, _j), "swap %d %d" % (_j, _i), "weave"][_k])
    _r = next(_g) % 40
    assert shuffle_rounds(_n, _prog, _r, list(range(_n))) == _slow(_n, _prog, _r, list(range(_n))), (_n, _prog, _r)
_P = ["weave", "rot 7", "lift 100 4999", "rev 3 19000", "swap 0 19999", "weave", "rot -1234", "lift 0 0", "rev 9999 10000"]
_pos = [0, 1, 2, 9999, 10000, 19998, 19999]
assert shuffle_rounds(20000, _P, 1, _pos) == _slow(20000, _P, 1, _pos) and shuffle_rounds(20000, _P, 3, _pos) == _slow(20000, _P, 3, _pos)
assert shuffle_rounds(20000, _P, 10**18, _pos) == [18037, 11536, 1254, 5660, 1214, 11053, 17153]
assert shuffle_rounds(20000, _P, 987654321987654321, _pos) == [13819, 12124, 19890, 19254, 10048, 12556, 287]
assert sum(i * t for i, t in enumerate(shuffle_rounds(20000, _P, 10**17 + 3, list(range(20000))))) == 2001023903676
assert shuffle_rounds(19997, ["weave", "rot 1", "weave"], 2**61 - 1, [0, 7, 19996]) == [4497, 1730, 7749]
assert sorted(shuffle_rounds(20000, _P, 10**18, list(range(20000)))) == list(range(20000))
assert _raises(ValueError, shuffle_rounds, 5, ["spin 1"], 1, [0]) and _raises(ValueError, shuffle_rounds, 5, ["rot"], 1, [0]) and _raises(ValueError, shuffle_rounds, 5, ["rot 1 2"], 1, [0])
assert _raises(ValueError, shuffle_rounds, 5, ["rev 3 1"], 1, [0]) and _raises(ValueError, shuffle_rounds, 5, ["rev 0 5"], 1, [0]) and _raises(ValueError, shuffle_rounds, 5, ["swap -1 2"], 1, [0])
assert _raises(ValueError, shuffle_rounds, 5, ["rot x"], 1, [0]) and _raises(ValueError, shuffle_rounds, 5, ["weave 2"], 1, [0]) and _raises(ValueError, shuffle_rounds, 5, ["rot 1", "lift 2 1"], 0, [0]) and _raises(ValueError, shuffle_rounds, 5, ["rot 1.5"], 0, [0])
''',
    "wrong": _mut(_REF_CP3, "            result[pos] = cycle[(idx + shift) % size]", "            result[pos] = cycle[(idx - shift) % size]"),
})


_REF_CP4 = r'''
from functools import lru_cache

def kth_route(width, height, blocked, max_turns, k):
    if k < 1:
        raise ValueError("k must be >= 1")
    bad = set((x, y) for x, y in blocked)
    goal = (width - 1, height - 1)
    if (0, 0) in bad or goal in bad:
        return None

    @lru_cache(maxsize=None)
    def ways(x, y, last, turns):
        if (x, y) == goal:
            return 1
        total = 0
        for move, nx, ny in ((0, x + 1, y), (1, x, y + 1)):
            if nx >= width or ny >= height or (nx, ny) in bad:
                continue
            t2 = turns + (1 if last != 2 and last != move else 0)
            if t2 <= max_turns:
                total += ways(nx, ny, move, t2)
        return total

    out = []
    x = y = turns = 0
    last = 2
    while (x, y) != goal:
        for move, nx, ny in ((0, x + 1, y), (1, x, y + 1)):
            if nx >= width or ny >= height or (nx, ny) in bad:
                continue
            t2 = turns + (1 if last != 2 and last != move else 0)
            if t2 > max_turns:
                continue
            w = ways(nx, ny, move, t2)
            if k <= w:
                out.append("RU"[move])
                x, y, last, turns = nx, ny, move, t2
                break
            k -= w
        else:
            return None
    return "".join(out) if k == 1 else None
'''

ITEMS.append({
    "id": "CP4",
    "kind": "counting",
    "difficulty": "very hard",
    "entry_point": "kth_route",
    "prompt": r"""Write a Python function `kth_route(width: int, height: int, blocked: list[tuple[int, int]], max_turns: int, k: int)`.

A delivery robot drives on a grid of cells `(x, y)` with `0 <= x < width` and `0 <= y < height`. It starts on `(0, 0)` and must reach `(width - 1, height - 1)`. Each step is either `R` (x increases by 1) or `U` (y increases by 1), so a route is a string of `width - 1` letters `R` and `height - 1` letters `U` in some order.

A route is VALID when
- it never stands on a blocked cell (`blocked` lists cells `(x, y)`; if the start or the goal itself is blocked there is no valid route), and
- it has at most `max_turns` turns, where a turn is a place in the string where two consecutive letters differ (`RRUUR` has 2 turns). `max_turns >= 0`.

Take all valid routes as strings and sort them in ordinary lexicographic order (`R` before `U`). Return the k-th one (k = 1 is the first), or `None` if there are fewer than k valid routes. If `k < 1` raise `ValueError`. On a 1 x 1 grid the only route is the empty string.

Limits: `width, height <= 30`; the number of valid routes can exceed 10**16, so routes cannot be listed one by one - count with dynamic programming (the count of completions depends on the cell, the previous letter and the turns used so far) and build the answer letter by letter. `k` can be as large as 10**18.

Examples:
- `kth_route(3, 2, [], 5, k)` for k = 1, 2, 3, 4 gives `"RRU"`, `"RUR"`, `"URR"`, `None`.
- `kth_route(3, 2, [], 1, 2)` returns `"URR"` (with at most one turn only `RRU` and `URR` remain).
- `kth_route(3, 2, [(1, 0)], 5, 1)` returns `"URR"` and `kth_route(3, 2, [(1, 0)], 5, 2)` returns `None`.
- `kth_route(3, 3, [(1, 1)], 2, k)` for k = 1, 2, 3 gives `"RRUU"`, `"UURR"`, `None`.""" + _TAIL,
    "reference": _REF_CP4,
    "tests": _RAISES + _LCG + r'''
from itertools import combinations as _comb

def _all(width, height, blocked, max_turns):
    bad = set(blocked)
    out = []
    n = width + height - 2
    for ups in _comb(range(n), height - 1):
        s = "".join("U" if i in ups else "R" for i in range(n))
        x = y = 0
        ok = (0, 0) not in bad
        for ch in s:
            if ch == "R":
                x += 1
            else:
                y += 1
            if (x, y) in bad:
                ok = False
        if ok and sum(1 for i in range(n - 1) if s[i] != s[i + 1]) <= max_turns:
            out.append(s)
    return sorted(out)

assert [kth_route(3, 2, [], 5, k) for k in (1, 2, 3, 4)] == ["RRU", "RUR", "URR", None]
assert kth_route(3, 2, [], 1, 2) == "URR" and kth_route(3, 2, [], 1, 3) is None and kth_route(3, 2, [], 0, 1) is None
assert kth_route(3, 2, [(1, 0)], 5, 1) == "URR" and kth_route(3, 2, [(1, 0)], 5, 2) is None
assert [kth_route(3, 3, [(1, 1)], 2, k) for k in (1, 2, 3)] == ["RRUU", "UURR", None]
assert kth_route(1, 1, [], 0, 1) == "" and kth_route(1, 1, [], 0, 2) is None and kth_route(1, 1, [(0, 0)], 3, 1) is None
assert kth_route(5, 1, [], 0, 1) == "RRRR" and kth_route(1, 4, [], 0, 1) == "UUU" and kth_route(5, 1, [(2, 0)], 9, 1) is None
assert kth_route(4, 4, [(0, 0)], 9, 1) is None and kth_route(4, 4, [(3, 3)], 9, 1) is None and kth_route(2, 2, [(1, 0), (0, 1)], 9, 1) is None
assert _raises(ValueError, kth_route, 3, 3, [], 4, 0) and _raises(ValueError, kth_route, 1, 1, [], 0, -1)
for _w, _h, _bl in ((4, 4, []), (5, 3, [(2, 1)]), (3, 6, [(1, 2), (2, 4)]), (6, 5, [(1, 1), (3, 2), (4, 4), (0, 3)]), (7, 4, [(5, 0), (5, 1), (2, 3)]), (2, 9, [])):
    for _mt in (0, 1, 2, 3, 5, 20):
        _exp = _all(_w, _h, _bl, _mt)
        assert [kth_route(_w, _h, _bl, _mt, k) for k in range(1, len(_exp) + 2)] == _exp + [None], (_w, _h, _bl, _mt)
_g = _lcg(246)
for _case in range(40):
    _w, _h = 1 + next(_g) % 6, 1 + next(_g) % 6
    _bl = [(next(_g) % _w, next(_g) % _h) for _ in range(next(_g) % 4)]
    _mt = next(_g) % 7
    _exp = _all(_w, _h, _bl, _mt)
    _k = 1 + next(_g) % (len(_exp) + 2)
    assert kth_route(_w, _h, _bl, _mt, _k) == (_exp[_k - 1] if _k <= len(_exp) else None), (_w, _h, _bl, _mt, _k)
assert kth_route(30, 30, [], 100, 1) == "R" * 29 + "U" * 29 and kth_route(30, 30, [], 1, 2) == "U" * 29 + "R" * 29 and kth_route(30, 30, [], 1, 3) is None
assert kth_route(30, 30, [], 100, 30067266499541040) == "U" * 29 + "R" * 29 and kth_route(30, 30, [], 100, 30067266499541041) is None
_B = [(3, 3), (10, 12), (12, 10), (20, 20), (25, 7), (7, 25), (15, 15), (28, 29), (1, 0)]
assert kth_route(30, 30, _B, 100, 10**15) == 'UURRRRRRRRRURUURUUUURRRURRURURRRRRUURUUUUURRUUUUURUUURURRU'
assert kth_route(30, 30, _B, 9, 4 * 10**7) == 'UUUUUUUUUUUUUUUUUURRRRRRUUURRRRRUUURRURRRRRRRRRRRRRRRRUUUU'
assert kth_route(30, 30, _B, 9, 40809430) == 'UUUUUUUUUUUUUUUUUUUUUUUUUUUURRRRRRRRRRRRRRRRRRRRRRRRRRRRRU'
assert kth_route(30, 30, _B, 9, 40809431) is None
assert kth_route(30, 30, _B, 12, 12345678901) == 'UUUUURRRRRRRRUURUUUUUUUURRRUURRRRRRRRRUUUUURRRRUUUUURRRRUU'
assert kth_route(30, 30, _B, 3, 20) == 'UUUUUUUUUUUUUUUUUUUUUUUUUUURRRRRRRRRRRRRRRRRRRRRRRRRRRRRUU'
assert kth_route(30, 30, _B, 3, 22) is None
assert kth_route(30, 30, _B, 58, 10**18) is None
_lo, _hi = 0, 10**18
while _hi - _lo > 1:
    _mid = (_lo + _hi) // 2
    if kth_route(30, 30, _B, 7, _mid) is None:
        _hi = _mid
    else:
        _lo = _mid
assert _lo == 791233
assert kth_route(30, 30, _B, 7, _lo) == 'UUUUUUUUUUUUUUUUUUUUUUUUUUUURRRRRRRRRRRRRRRRRRRRRRRRRRRRRU'
''',
    "wrong": _mut(_REF_CP4, "            t2 = turns + (1 if last != 2 and last != move else 0)\n            if t2 > max_turns:", "            t2 = turns + (1 if last != move else 0)\n            if t2 > max_turns:"),
})


_REF_CP5 = r'''
from collections import deque

def sled_ticks(grid):
    rows, cols = len(grid), len(grid[0])
    beacons = {}
    start = goal = None
    for r in range(rows):
        for c in range(cols):
            ch = grid[r][c]
            if ch == "S":
                start = (r, c)
            elif ch == "G":
                goal = (r, c)
            elif ch == "*":
                beacons[(r, c)] = 1 << len(beacons)
    full = (1 << len(beacons)) - 1
    first = (start[0], start[1], 0, 0, 0)
    dist = {first: 0}
    queue = deque([first])
    while queue:
        state = queue.popleft()
        r, c, vx, vy, mask = state
        d = dist[state]
        if grid[r][c] == "~":
            options = [(vx, vy)]
        else:
            options = [(vx + ax, vy + ay) for ax in (-1, 0, 1) for ay in (-1, 0, 1)
                       if abs(vx + ax) <= 3 and abs(vy + ay) <= 3]
        for nvx, nvy in options:
            rr, cc, mm = r, c, mask
            ok = True
            for dr, dc, steps in ((0, 1 if nvx > 0 else -1, abs(nvx)), (1 if nvy > 0 else -1, 0, abs(nvy))):
                for _ in range(steps):
                    rr += dr
                    cc += dc
                    if not (0 <= rr < rows and 0 <= cc < cols) or grid[rr][cc] == "#":
                        ok = False
                        break
                    mm |= beacons.get((rr, cc), 0)
                if not ok:
                    break
            if not ok:
                continue
            nxt = (rr, cc, nvx, nvy, mm)
            if nxt in dist:
                continue
            dist[nxt] = d + 1
            if (rr, cc) == goal and nvx == 0 and nvy == 0 and mm == full:
                return d + 1
            queue.append(nxt)
    return None
'''

ITEMS.append({
    "id": "CP5",
    "kind": "graph",
    "difficulty": "very hard",
    "entry_point": "sled_ticks",
    "prompt": r"""Write a Python function `sled_ticks(grid: list[str])` that returns the minimum number of ticks a rocket sled needs to finish a course, or `None` if it cannot.

`grid` is a list of equal-length strings; row 0 is the top, column 0 the left. Cells: `.` free, `#` wall, `S` start (exactly one), `G` goal (exactly one), `~` ice, `*` beacon (at most 2). `S`, `G`, `~` and `*` cells can be driven on like free cells.

The sled has a position and a velocity `(vx, vy)`: `vx` is in columns per tick (positive = right), `vy` in rows per tick (positive = down). It starts on `S` with velocity `(0, 0)`. Each tick consists of:

1. Steering. If the sled is NOT on an ice cell, the driver adds -1, 0 or +1 to `vx` and, independently, -1, 0 or +1 to `vy`. Each component must stay within -3..3 (choices that would leave this range are not available). If the sled IS on an ice cell, the velocity cannot be changed in this tick.
2. Moving. The sled first makes `|vx|` single-cell steps horizontally (in the direction of the sign of `vx`), then `|vy|` single-cell steps vertically. Every cell it steps on - the intermediate ones and the final one - must be inside the grid and must not be a wall. A velocity whose move would break this rule cannot be chosen; if the sled is on ice and its forced move breaks the rule, it has crashed and that line of play is dead.
3. Every beacon cell stepped on during the move (including the final cell) is collected.

The course is finished at the end of a tick in which the sled is on `G` with velocity `(0, 0)` and has collected all beacons. (So it has to arrive on `G` and then spend one more tick braking to a standstill there; merely passing over `G` does not count. A sled with velocity `(0, 0)` does not move during the tick, but the tick still counts.)

Grids are at most 12 x 12.

Examples:
- `sled_ticks(["SG"])` returns 2 (tick 1: velocity (1, 0), arrive on G; tick 2: brake to (0, 0)).
- `sled_ticks(["S..G"])` returns 4: velocities 1, 1, 1, 0. (Going 1, 2 reaches G after two ticks but at speed 2; the sled can only slow to 1 and would leave the grid.)
- `sled_ticks(["S#", ".G"])` returns 3: (0, 1), then (1, 0), then (0, 0). The diagonal move (1, 1) is impossible because its horizontal step hits the wall.
- `sled_ticks(["*SG"])` returns 5, `sled_ticks(["S~~G"])` returns 4, and `sled_ticks(["S#G"])` returns `None`.""" + _TAIL,
    "reference": _REF_CP5,
    "tests": r'''
assert sled_ticks(["SG"]) == 2 and sled_ticks(["S..G"]) == 4 and sled_ticks(["S#", ".G"]) == 3
assert sled_ticks(["*SG"]) == 5 and sled_ticks(["S~~G"]) == 4 and sled_ticks(["S#G"]) is None
assert sled_ticks(["S.G"]) == 3 and sled_ticks(["S....G"]) == 5 and sled_ticks(["G....S"]) == 5 and sled_ticks(["S", ".", ".", "G"]) == 4
assert sled_ticks(["S~G"]) == 3 and sled_ticks(["S*G"]) == 3 and sled_ticks(["S~G*"]) == 6 and sled_ticks(["S~#G"]) is None
assert sled_ticks(["S..........G"]) == 7
assert sled_ticks(["S.........G."]) == 7
assert sled_ticks(["S~~~~~~~~~~G"]) == 12
assert sled_ticks(["S.~~~~~~~~.G"]) == 12
assert sled_ticks(["*....S....*G"]) == 12
assert sled_ticks(["S.#", "..#", "G.."]) == 3
assert sled_ticks(["S..", ".#.", "..G"]) == 4
assert sled_ticks(["S.*", "###", "G.."]) is None
assert sled_ticks(["S~.", "#..", "*.G"]) == 7
assert sled_ticks(["S~.", "#..", "G.."]) == 4
assert sled_ticks(["S...#...", "....#.*.", "....#...", "........", "....#...", "*...#..G"]) == 14
assert sled_ticks(["S.....~.....", "......~.....", "......~.....", "~~~~~~~~~~~~", "......~.....", "......~....G"]) == 7
_m1 = ["S....#......", ".###.#.####.", ".#...#....#.", ".#.#####..#.", ".#.....#..#.", ".#####.#.##.", ".....#.#..#.", ".###.#.##.#.", ".#...#....#.", ".#.#####..#.", ".#........#G", "............"]
assert sled_ticks(_m1) == 13
_m2 = ["S...........", "..........*.", "............", "....####....", "....#G.#....", "....#..#....", "....#.......", "............", ".*..........", "............"]
assert sled_ticks(_m2) == 18
_m3 = ["S~~~~~~~~~~.", "###########.", "G~~~~~~~~~~.", "############"]
assert sled_ticks(_m3) == 25
_m4 = ["S.~.....~..*", "..~.....~...", "..~..#..~...", "..~..#..~...", "*.~..#..~..G"]
assert sled_ticks(_m4) == 13
assert sled_ticks(["S.......", "~~~~~~~~", "........", ".......G"]) == 6
assert sled_ticks(["S~~.", "...~", "~..~", "G~~."]) == 4
''',
    "wrong": _mut(_REF_CP5, "            for dr, dc, steps in ((0, 1 if nvx > 0 else -1, abs(nvx)), (1 if nvy > 0 else -1, 0, abs(nvy))):", "            for dr, dc, steps in ((1 if nvy > 0 else -1, 0, abs(nvy)), (0, 1 if nvx > 0 else -1, abs(nvx))):"),
})


_REF_CP6 = r'''
class SwapDesk:
    def __init__(self):
        self._orders = {}           # id -> [owner, side, price, qty, stamp]
        self._next_id = 1
        self._stamp = 0

    def _tick(self):
        self._stamp += 1
        return self._stamp

    def _side(self, side):
        rows = [(oid, o) for oid, o in self._orders.items() if o[1] == side]
        if side == "buy":
            rows.sort(key=lambda r: (-r[1][2], r[1][4]))
        else:
            rows.sort(key=lambda r: (r[1][2], r[1][4]))
        return rows

    def limit(self, owner, side, price, qty, tif="gtc"):
        if side not in ("buy", "sell") or tif not in ("gtc", "ioc", "fok") or price < 1 or qty < 1:
            raise ValueError("bad order")
        oid = self._next_id
        self._next_id += 1
        if side == "buy":
            cands = [(i, o) for i, o in self._side("sell") if o[2] <= price]
        else:
            cands = [(i, o) for i, o in self._side("buy") if o[2] >= price]
        if tif == "fok" and sum(o[3] for _, o in cands if o[0] != owner) < qty:
            return (oid, [])
        trades = []
        left = qty
        for i, o in cands:
            if left == 0:
                break
            if o[0] == owner:
                del self._orders[i]
                continue
            take = min(left, o[3])
            trades.append((i, o[2], take))
            o[3] -= take
            left -= take
            if o[3] == 0:
                del self._orders[i]
        if left and tif == "gtc":
            self._orders[oid] = [owner, side, price, left, self._tick()]
        return (oid, trades)

    def cancel(self, order_id):
        return self._orders.pop(order_id, None) is not None

    def amend(self, order_id, qty):
        if qty < 1:
            raise ValueError("bad quantity")
        o = self._orders.get(order_id)
        if o is None:
            return False
        if qty > o[3]:
            o[4] = self._tick()
        o[3] = qty
        return True

    def depth(self, side, levels):
        out = []
        for _, o in self._side(side):
            if out and out[-1][0] == o[2]:
                out[-1] = (o[2], out[-1][1] + o[3])
            else:
                if len(out) == levels:
                    break
                out.append((o[2], o[3]))
        return out

    def best(self, side):
        top = self.depth(side, 1)
        return top[0] if top else None

    def open_orders(self, owner):
        return [(i, o[1], o[2], o[3]) for i, o in sorted(self._orders.items()) if o[0] == owner]
'''

ITEMS.append({
    "id": "CP6",
    "kind": "class",
    "difficulty": "very hard",
    "entry_point": "SwapDesk",
    "prompt": r"""Write a Python class `SwapDesk`: a small exchange that matches buy and sell orders for one product.

`limit(owner: str, side: str, price: int, qty: int, tif: str = "gtc") -> tuple[int, list[tuple[int, int, int]]]`
- `side` is `"buy"` or `"sell"`, `tif` is `"gtc"`, `"ioc"` or `"fok"`, `price >= 1`, `qty >= 1`; anything else raises `ValueError` (and uses up no order id).
- Every accepted call gets the next order id: 1, 2, 3, ... (whether or not the order ends up resting in the book).
- Matching. An incoming BUY at price P can match resting SELL orders whose price is <= P, cheapest first; an incoming SELL at price P can match resting BUY orders whose price is >= P, highest first. Among resting orders with the same price, the one with the older time priority comes first. The incoming order walks through these orders in that sequence while it still has quantity left:
  - if the resting order belongs to the SAME owner as the incoming order, the resting order is cancelled (removed from the book, no trade) and the walk continues;
  - otherwise they trade `min(remaining incoming qty, resting qty)` units at the RESTING order's price; a resting order whose quantity reaches 0 leaves the book.
- Afterwards, if the incoming order still has quantity left: with `"gtc"` it rests in the book with that remaining quantity (time priority: now); with `"ioc"` the rest is dropped.
- `"fok"` (fill or kill): first check whether the walk described above would fill the order completely (same-owner orders contribute nothing). If not, nothing happens at all - no trades, no cancellations. If yes, execute it normally.
- Returns `(order_id, trades)`, each trade being `(resting_order_id, price, quantity)` in execution order.

Other methods:
- `cancel(order_id) -> bool` - remove a resting order; `False` if that id is not resting (unknown, filled, cancelled, or never rested).
- `amend(order_id, qty) -> bool` - `qty < 1` raises `ValueError` (checked first). If the order is not resting return `False`. Otherwise set its remaining quantity to `qty` and return `True`; a decrease (or no change) keeps its time priority, an increase moves it to the back of its price level (time priority: now). Amending never triggers matching.
- `best(side)` - `(price, total resting quantity at that price)` for the best level of that side (highest buy / lowest sell), or `None` if the side is empty.
- `depth(side, levels) -> list[tuple[int, int]]` - the same for up to `levels` price levels, best first.
- `open_orders(owner) -> list[tuple[int, str, int, int]]` - that owner's resting orders as `(order_id, side, price, remaining_qty)`, by ascending id.

Example:

    d = SwapDesk()
    d.limit("ann", "sell", 105, 10)     # (1, [])
    d.limit("bob", "sell", 103, 5)      # (2, [])
    d.limit("cat", "sell", 103, 7)      # (3, [])
    d.limit("dan", "buy", 104, 8)       # (4, [(2, 103, 5), (3, 103, 3)])
    d.best("sell")                      # (103, 4)
    d.limit("eve", "buy", 110, 20, "fok")   # (5, [])  - only 14 available, nothing happens
    d.limit("eve", "buy", 110, 14, "fok")   # (6, [(3, 103, 4), (1, 105, 10)])""" + _TAIL,
    "reference": _REF_CP6,
    "tests": _RAISES + r'''
d = SwapDesk()
assert d.limit("ann", "sell", 105, 10) == (1, []) and d.limit("bob", "sell", 103, 5) == (2, []) and d.limit("cat", "sell", 103, 7) == (3, [])
assert d.best("sell") == (103, 12) and d.best("buy") is None and d.depth("sell", 5) == [(103, 12), (105, 10)] and d.depth("sell", 1) == [(103, 12)] and d.depth("buy", 3) == []
assert d.limit("dan", "buy", 104, 8) == (4, [(2, 103, 5), (3, 103, 3)]) and d.best("sell") == (103, 4) and d.open_orders("dan") == [] and d.open_orders("cat") == [(3, "sell", 103, 4)]
assert d.limit("dan", "buy", 102, 6) == (5, []) and d.best("buy") == (102, 6) and d.open_orders("dan") == [(5, "buy", 102, 6)]
assert d.limit("eve", "sell", 101, 10, "ioc") == (6, [(5, 102, 6)]) and d.best("buy") is None and d.best("sell") == (103, 4) and d.open_orders("eve") == []
assert d.limit("eve", "buy", 110, 20, "fok") == (7, []) and d.depth("sell", 9) == [(103, 4), (105, 10)]
assert d.limit("eve", "buy", 110, 14, "fok") == (8, [(3, 103, 4), (1, 105, 10)]) and d.best("sell") is None and d.cancel(1) is False and d.cancel(7) is False
assert d.limit("ann", "sell", 50, 5) == (9, []) and d.limit("bob", "sell", 50, 5) == (10, []) and d.limit("ann", "buy", 60, 3) == (11, [(10, 50, 3)])
assert d.open_orders("ann") == [] and d.best("sell") == (50, 2) and d.limit("bob", "buy", 40, 5) == (12, []) and d.open_orders("bob") == [(10, "sell", 50, 2), (12, "buy", 40, 5)]
assert d.limit("bob", "buy", 55, 2, "fok") == (13, []) and d.best("sell") == (50, 2) and d.limit("bob", "buy", 55, 2, "ioc") == (14, []) and d.best("sell") is None
assert d.cancel(12) is True and d.cancel(12) is False and d.best("buy") is None
assert d.limit("x", "buy", 30, 5) == (15, []) and d.limit("y", "buy", 30, 5) == (16, []) and d.amend(15, 3) is True and d.best("buy") == (30, 8)
assert d.limit("z", "sell", 30, 4) == (17, [(15, 30, 3), (16, 30, 1)]) and d.amend(16, 10) is True and d.limit("x", "buy", 30, 1) == (18, [])
assert d.amend(16, 12) is True and d.amend(16, 12) is True and d.limit("z", "sell", 30, 2) == (19, [(18, 30, 1), (16, 30, 1)]) and d.open_orders("y") == [(16, "buy", 30, 11)]
assert d.amend(999, 5) is False and d.amend(18, 5) is False and _raises(ValueError, d.amend, 16, 0) and _raises(ValueError, d.amend, 999, 0) and d.cancel(16) is True and d.cancel(18) is False
assert _raises(ValueError, d.limit, "a", "hold", 1, 1) and _raises(ValueError, d.limit, "a", "buy", 0, 1) and _raises(ValueError, d.limit, "a", "buy", 1, 0) and _raises(ValueError, d.limit, "a", "buy", 1, 1, "day")
assert d.limit("a", "buy", 1, 1) == (20, []) and d.depth("buy", 2) == [(1, 1)]
e = SwapDesk()
assert e.limit("s", "sell", 10, 5) == (1, []) and e.limit("b", "buy", 10, 8) == (2, [(1, 10, 5)]) and e.best("buy") == (10, 3) and e.open_orders("b") == [(2, "buy", 10, 3)]
assert e.limit("p", "buy", 9, 4) == (3, []) and e.limit("q", "buy", 11, 2) == (4, []) and e.limit("r", "buy", 10, 1) == (5, []) and e.depth("buy", 2) == [(11, 2), (10, 4)]
assert e.limit("s", "sell", 9, 20) == (6, [(4, 11, 2), (2, 10, 3), (5, 10, 1), (3, 9, 4)]) and e.best("sell") == (9, 10) and e.best("buy") is None
assert e.limit("s", "buy", 12, 3) == (7, []) and e.best("sell") is None and e.open_orders("s") == [(7, "buy", 12, 3)]
assert e.limit("t", "sell", 12, 2, "fok") == (8, [(7, 12, 2)]) and e.limit("t", "sell", 13, 1, "fok") == (9, []) and e.limit("t", "sell", 13, 1, "ioc") == (10, []) and e.best("sell") is None
assert e.limit("u", "sell", 20, 1) == (11, []) and e.limit("s", "sell", 15, 4) == (12, []) and e.limit("u", "sell", 15, 1) == (13, []) and e.limit("s", "buy", 20, 3, "fok") == (14, [])
assert e.depth("sell", 3) == [(15, 5), (20, 1)] and e.limit("s", "buy", 20, 2, "fok") == (15, [(13, 15, 1), (11, 20, 1)]) and e.open_orders("s") == [(7, "buy", 12, 1)] and e.depth("sell", 3) == []
''',
    "wrong": _mut(_REF_CP6, "            trades.append((i, o[2], take))", "            trades.append((i, price, take))"),
})


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------

_KINDS = ("parsing", "interval", "simulation", "counting", "graph", "class")


def _self_check(verbose=False):
    import time
    ok = 0
    problems = []
    seen_ids = set()
    expected_ids = ["C%02d" % i for i in range(1, 31)] + ["CP%d" % i for i in range(1, 7)]
    if [it["id"] for it in ITEMS] != expected_ids:
        problems.append(("ALL", ["ids are not C01..C30, CP1..CP6 in order"]))
    for item in ITEMS:
        iid = item["id"]
        errs = []
        if iid in seen_ids:
            errs.append("duplicate id")
        seen_ids.add(iid)
        for key in ("id", "kind", "difficulty", "entry_point", "prompt", "reference", "tests", "wrong"):
            if key not in item:
                errs.append("missing key " + key)
        if item.get("kind") not in _KINDS:
            errs.append("unknown kind")
        if not item["prompt"].rstrip("\n").endswith(
                "Reply with one Python code block containing the complete solution. Standard library only."):
            errs.append("prompt tail missing")
        if item["entry_point"] not in item["prompt"]:
            errs.append("entry point not named in prompt")
        n_words = len(item["prompt"].split())
        if n_words > 620:
            errs.append("prompt too long: %d words" % n_words)
        n_asserts = sum(1 for line in item["tests"].splitlines() if line.startswith("assert "))
        if not 12 <= n_asserts <= 25:
            errs.append("assert count %d outside 12..25" % n_asserts)
        if item["wrong"] == item["reference"]:
            errs.append("wrong == reference")
        t0 = time.time()
        try:
            ns = {"__name__": "solution"}
            exec(item["reference"], ns)
            if item["entry_point"] not in ns:
                errs.append("reference does not define entry point")
            exec(item["tests"], ns)
        except BaseException as exc:  # noqa: BLE001
            errs.append("reference FAILS tests: %r" % (exc,))
        dt = time.time() - t0
        for _retry in range(2):         # a busy machine can inflate one run: keep the best of three
            if dt <= 2.0 or errs:
                break
            t0 = time.time()
            ns = {"__name__": "solution"}
            exec(item["reference"], ns)
            exec(item["tests"], ns)
            dt = min(dt, time.time() - t0)
        if dt > 2.0:
            errs.append("too slow: %.2fs" % dt)
        try:
            ns = {"__name__": "solution"}
            exec(item["wrong"], ns)
            exec(item["tests"], ns)
            errs.append("wrong solution PASSES tests")
        except Exception:  # noqa: BLE001
            pass
        if verbose:
            print("%s %-10s %-9s words=%3d asserts=%2d %.3fs %s" % (
                iid, item["kind"], item["difficulty"], n_words, n_asserts, dt, "; ".join(errs) or "ok"))
        if errs:
            problems.append((iid, errs))
        else:
            ok += 1
    return ok, problems


if __name__ == "__main__":
    import sys
    _ok, _problems = _self_check(verbose="-v" in sys.argv)
    for _iid, _errs in _problems:
        print("FAIL %s: %s" % (_iid, "; ".join(_errs)))
    print("%s %d/%d" % ("OK" if not _problems else "NOT OK", _ok, len(ITEMS)))
    sys.exit(0 if not _problems else 1)
