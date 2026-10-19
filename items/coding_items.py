"""Bonsai-2 coding items: 40 test tasks (C01..C40) + 3 pilot tasks (CP1..CP3).

Fresh, never-published tasks written for a pre-registered local-LLM comparison.
Each item: id, kind, difficulty, entry_point, prompt, reference, tests, wrong.
  - prompt     : full task statement shown to the model
  - reference  : complete solution (verified to pass `tests`)
  - tests      : plain asserts, exec'd in the namespace the solution defined
  - wrong      : plausible-but-wrong solution that `tests` must reject
Run `python coding_items.py` to self-check (prints "OK 43/43").
Stdlib only. The module imports on Python 3.9+; references/tests target 3.12.
"""

_TAIL = "\n\nReply with one Python code block containing the complete solution. Standard library only.\n"

# Helper prepended to test sources that check for ValueError.
_RAISES = '''
def _raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ValueError:
        return True
    return False
'''


def _mut(src, old, new):
    """Build a 'wrong' solution by editing one fragment of a reference."""
    if old not in src:
        raise AssertionError("mutation target not found: %r" % (old,))
    return src.replace(old, new)


ITEMS = []

# ---------------------------------------------------------------------------
# Kind 1: parsing / formatting of invented mini-formats (C01-C05)
# ---------------------------------------------------------------------------

_REF_C01 = r'''
import re

def _scalar(s):
    if re.fullmatch(r"-?[0-9]+", s):
        return int(s)
    if s == "yes":
        return True
    if s == "no":
        return False
    return s

def _convert(val):
    if len(val) >= 2 and val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    if "|" in val:
        return [_scalar(piece.strip()) for piece in val.split("|")]
    return _scalar(val)

def _strip_comment(raw):
    out = []
    quoted = False
    for ch in raw:
        if ch == '"':
            quoted = not quoted
        elif ch == "#" and not quoted:
            break
        out.append(ch)
    return "".join(out)

def parse_stanza(text):
    result = {}
    current = ""
    for raw in text.split("\n"):
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if not name:
                raise ValueError("empty section name")
            current = name
            result.setdefault(name, {})
            continue
        if "=" not in line:
            raise ValueError("not an entry: " + line)
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            raise ValueError("empty key")
        result.setdefault(current, {})[key] = _convert(val.strip())
    return result
'''

ITEMS.append({
    "id": "C01",
    "kind": "parsing",
    "difficulty": "hard",
    "entry_point": "parse_stanza",
    "prompt": r"""Write a Python function `parse_stanza(text: str) -> dict` that parses a small configuration format called "Stanza" and returns a dict mapping section name (str) to a dict of that section's entries (key str -> converted value).

Processing, line by line (lines are separated by "\n"):

1. Comments. Scan the line left to right. A `"` character toggles "quoted mode" on/off (there are no escape sequences; quoted mode always ends at the end of the line). A `#` seen while NOT in quoted mode starts a comment: it and everything after it on the line are removed.
2. Strip leading and trailing whitespace from what is left. If nothing is left, ignore the line.
3. Section header. If the line starts with `[` and ends with `]`, it is a section header. The section name is the text between those two brackets with surrounding whitespace stripped. An empty name raises `ValueError`. Following entries belong to this section. A header for a name seen before continues that earlier section (the entries are merged). A section named by a header appears in the result even if it has no entries.
4. Entry. Any other line must contain `=`, otherwise raise `ValueError`. The key is the text before the FIRST `=`, stripped; an empty key raises `ValueError`. The raw value is everything after the first `=`, stripped (it may be empty and may itself contain `=`).
5. Entries that appear before any section header belong to the section named `""` (empty string). The `""` section is present in the result only if it has at least one entry.
6. If a key is repeated inside the same section, the later value replaces the earlier one.

Value conversion, applied to the raw value in this order:

a. If it has length >= 2 and both starts and ends with `"`, the value is the string between that first and last character, unchanged (no further conversion, even if it looks like a number or contains `|`).
b. Otherwise, if it contains `|`, the value is a list: split on `|`, strip each piece, and convert each piece with the scalar rule (c). An empty piece becomes the empty string.
c. Scalar rule: an optional `-` followed by one or more digits 0-9 and nothing else -> `int`; exactly `yes` -> `True`; exactly `no` -> `False` (both case-sensitive); anything else -> the string itself.

Example: the text

    name = "Ada # Lovelace"   # a comment
    [limits]
    max = 10
    modes = fast | 3 | yes

returns `{"": {"name": "Ada # Lovelace"}, "limits": {"max": 10, "modes": ["fast", 3, True]}}`.

`parse_stanza("")` returns `{}`.""" + _TAIL,
    "reference": _REF_C01,
    "tests": _RAISES + r'''
assert parse_stanza("") == {}
assert parse_stanza("# only a comment\n\n   \n") == {}
assert parse_stanza('name = "Ada # Lovelace"   # a comment\n[limits]\nmax = 10\nmodes = fast | 3 | yes\n') == {"": {"name": "Ada # Lovelace"}, "limits": {"max": 10, "modes": ["fast", 3, True]}}
assert parse_stanza("[a]\n[b]\nx=1\n[a]\ny = no\n") == {"a": {"y": False}, "b": {"x": 1}}
assert parse_stanza("k = 1\nk = two\n") == {"": {"k": "two"}}
assert parse_stanza("v = -42\nw = - 42\nx = 007\ny = Yes\nz =\n") == {"": {"v": -42, "w": "- 42", "x": 7, "y": "Yes", "z": ""}}
assert parse_stanza('p = "a|b"\nq = a|b\nr = "12"\n') == {"": {"p": "a|b", "q": ["a", "b"], "r": "12"}}
assert parse_stanza("l = 1 | | no |x y\n") == {"": {"l": [1, "", False, "x y"]}}
assert parse_stanza("eq = a=b\n") == {"": {"eq": "a=b"}}
assert parse_stanza('h = "x#y" # z\n[ sec ]\n') == {"": {"h": "x#y"}, "sec": {}}
assert parse_stanza("  [s]  # c\n  k  =  yes  # c\n") == {"s": {"k": True}}
assert _raises(parse_stanza, "just words")
assert _raises(parse_stanza, "[ ]")
assert _raises(parse_stanza, "= 5")
''',
    "wrong": _mut(_REF_C01, "elif ch == \"#\" and not quoted:", "elif ch == \"#\":"),
})


_REF_C02 = r'''
def render_ledger(rows, width):
    def fmt(cents):
        a = abs(cents)
        s = "{:,}.{:02d}".format(a // 100, a % 100)
        return "(" + s + ")" if cents < 0 else s + " "

    total = sum(c for _, c in rows)
    all_rows = list(rows) + [("TOTAL", total)]
    texts = [fmt(c) for _, c in all_rows]
    amount_w = max(len(t) for t in texts)
    label_w = width - amount_w - 1
    if label_w < 5:
        raise ValueError("width too small")
    lines = []
    for (label, _), text in zip(all_rows, texts):
        if len(label) > label_w:
            label = label[:label_w - 1] + "~"
        lines.append(label.ljust(label_w) + " " + text.rjust(amount_w))
    lines.insert(len(rows), "-" * width)
    return lines
'''

ITEMS.append({
    "id": "C02",
    "kind": "parsing",
    "difficulty": "hard",
    "entry_point": "render_ledger",
    "prompt": r"""Write a Python function `render_ledger(rows: list[tuple[str, int]], width: int) -> list[str]` that renders a fixed-width ledger. Each row is `(label, amount_cents)`; amounts are integers in cents and may be negative or zero.

Output lines, in order:
- one line per row, in input order;
- a rule line consisting of exactly `width` `-` characters;
- a total line whose label is `TOTAL` and whose amount is the sum of all row amounts (0 if there are no rows).

Amount text (used for rows and for the total):
- Take the absolute value; write the whole units with `,` as thousands separator, then `.`, then exactly two digits of cents. Examples: 123456 -> `1,234.56`, 5 -> `0.05`, 0 -> `0.00`.
- A negative amount is wrapped in parentheses: `(1,234.56)`.
- A non-negative amount gets ONE trailing space instead: `1,234.56 ` (so that digits line up with the parenthesised ones).

Layout:
- Let A be the length of the longest amount text among all rows AND the total line. Every amount text is right-aligned (padded with spaces on the left) to width A.
- Let L = width - A - 1. If L < 5, raise `ValueError`.
- A label longer than L is replaced by its first L-1 characters followed by `~`. A shorter label is padded with spaces on the right to L.
- A row line or total line is: label column (L chars) + one space + amount column (A chars). Every returned line is therefore exactly `width` characters long.

Example: `render_ledger([("Rent", -120000), ("Salary", 250000)], 20)` returns exactly these four strings:

    "Rent      (1,200.00)"
    "Salary     2,500.00 "
    "--------------------"
    "TOTAL      1,300.00 "

Example: `render_ledger([], 12)` returns `["------------", "TOTAL  0.00 "]`.""" + _TAIL,
    "reference": _REF_C02,
    "tests": _RAISES + r'''
assert render_ledger([("Rent", -120000), ("Salary", 250000)], 20) == ["Rent      (1,200.00)", "Salary     2,500.00 ", "--------------------", "TOTAL      1,300.00 "]
assert render_ledger([], 12) == ["------------", "TOTAL  0.00 "]
assert render_ledger([], 11) == ["-----------", "TOTAL 0.00 "]
assert _raises(render_ledger, [], 10)
assert render_ledger([("Groceries and sundries", -5)], 14) == ["Grocer~ (0.05)", "--------------", "TOTAL   (0.05)"]
assert render_ledger([("a", 99999), ("b", 1)], 15) == ["a       999.99 ", "b         0.01 ", "---------------", "TOTAL 1,000.00 "]
assert _raises(render_ledger, [("a", 99999), ("b", 1)], 14)
assert render_ledger([("x", -100), ("y", 100)], 12) == ["x     (1.00)", "y      1.00 ", "------------", "TOTAL  0.00 "]
assert render_ledger([("abcde", 0), ("abcdef", 0)], 11) == ["abcde 0.00 ", "abcd~ 0.00 ", "-----------", "TOTAL 0.00 "]
assert render_ledger([("big", 123456789)], 22) == ["big      1,234,567.89 ", "----------------------", "TOTAL    1,234,567.89 "]
assert render_ledger([("neg", -123456789), ("pos", 100000)], 24) == ["neg       (1,234,567.89)", "pos            1,000.00 ", "------------------------", "TOTAL     (1,233,567.89)"]
assert all(len(line) == 30 for line in render_ledger([("one", 1), ("two", -22222222), ("a very long label that will not fit", 3)], 30))
''',
    "wrong": _mut(_REF_C02, "amount_w = max(len(t) for t in texts)", "amount_w = max(len(t) for t in texts[:-1] or texts)"),
})


_REF_C03 = r'''
import re

_TOKEN = re.compile(r"(!?)([A-Z])([1-9][0-9]?)(?:-([A-Z])([1-9][0-9]?))?")

def expand_slots(spec):
    if not spec.strip():
        return []
    result = []
    for token in spec.split(","):
        token = token.strip()
        m = _TOKEN.fullmatch(token)
        if not m:
            raise ValueError("bad token: %r" % token)
        remove, letter, lo, letter2, hi = m.groups()
        lo = int(lo)
        if letter2 is None:
            numbers = [lo]
        else:
            if letter2 != letter:
                raise ValueError("range across letters")
            hi = int(hi)
            step = 1 if hi >= lo else -1
            numbers = list(range(lo, hi + step, step))
        for n in numbers:
            slot = letter + str(n)
            if remove:
                if slot in result:
                    result.remove(slot)
            elif slot not in result:
                result.append(slot)
    return result
'''

ITEMS.append({
    "id": "C03",
    "kind": "parsing",
    "difficulty": "medium",
    "entry_point": "expand_slots",
    "prompt": r"""Write a Python function `expand_slots(spec: str) -> list[str]` that expands a warehouse "slot spec" into an ordered list of slot names.

A slot name is one uppercase letter A-Z followed by a number from 1 to 99 written without leading zeros, e.g. `B7`, `K42`. (`A0`, `A07`, `A100`, `a1` are not valid slot names.)

The spec is a comma-separated list of tokens. Whitespace around a token (before/after the commas) is ignored; no whitespace is allowed inside a token. If the whole spec is empty or only whitespace, return `[]`. Otherwise an empty token (e.g. from `"A1,,B2"` or a trailing comma) raises `ValueError`.

A token is one of:
- `SLOT` - a single slot;
- `SLOT-SLOT` - a range. Both ends must have the same letter (otherwise `ValueError`). It stands for every slot from the first number to the second number inclusive, IN THAT DIRECTION: `C7-C5` means C7, C6, C5 in that order. `A5-A5` is just A5.
- either of the above prefixed with `!`, which makes it a removal token.

Process the tokens left to right, maintaining a result list (initially empty):
- A normal token appends each of its slots, in order, skipping any slot that is already in the list.
- A removal token removes each of its slots from the list if present (slots not present are ignored).
- A slot that was removed can be added again by a later token; it is then appended at the end.

Any token that does not match the forms above raises `ValueError`.

Examples:
- `expand_slots("A1-A3, B2, !A2")` returns `["A1", "A3", "B2"]`.
- `expand_slots("C7-C5,C6,!C7,C7")` returns `["C6", "C5", "C7"]`.""" + _TAIL,
    "reference": _REF_C03,
    "tests": _RAISES + r'''
assert expand_slots("") == []
assert expand_slots("   ") == []
assert expand_slots("A1-A3, B2, !A2") == ["A1", "A3", "B2"]
assert expand_slots("C7-C5,C6,!C7,C7") == ["C6", "C5", "C7"]
assert expand_slots("B2,B2,B1-B3") == ["B2", "B1", "B3"]
assert expand_slots("!A1") == []
assert expand_slots("A99-A97,A5-A5") == ["A99", "A98", "A97", "A5"]
assert expand_slots("D1-D4,!D2-D3,D3") == ["D1", "D4", "D3"]
assert expand_slots(" D1-D4 , !D4-D2 ") == ["D1"]
assert _raises(expand_slots, "A1,,B2") and _raises(expand_slots, "A1,")
assert _raises(expand_slots, "A1-B3")
assert _raises(expand_slots, "A0") and _raises(expand_slots, "A100") and _raises(expand_slots, "A01")
assert _raises(expand_slots, "a1") and _raises(expand_slots, "A1 - A3")
''',
    "wrong": _mut(_REF_C03, "step = 1 if hi >= lo else -1\n            numbers = list(range(lo, hi + step, step))",
                  "numbers = list(range(min(lo, hi), max(lo, hi) + 1))"),
})


_REF_C04 = r'''
def number_outline(entries):
    def letters(n):
        s = ""
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(97 + r) + s
        return s

    def roman(n):
        table = ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                 (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"))
        out = ""
        for value, sym in table:
            while n >= value:
                out += sym
                n -= value
        return out

    styles = (str, letters, roman)
    counters = []
    lines = []
    prev = 0
    for depth, title in entries:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        d = min(depth, prev + 1)
        while len(counters) < d:
            counters.append(0)
        counters[d - 1] += 1
        del counters[d:]
        label = ".".join(styles[i % 3](counters[i]) for i in range(d))
        lines.append("  " * (d - 1) + label + ") " + title)
        prev = d
    return lines
'''

ITEMS.append({
    "id": "C04",
    "kind": "parsing",
    "difficulty": "hard",
    "entry_point": "number_outline",
    "prompt": r"""Write a Python function `number_outline(entries: list[tuple[int, str]]) -> list[str]` that numbers the entries of an outline. Each entry is `(requested_depth, title)`. Return one output line per entry, in order.

Rules:

1. Any requested depth below 1 raises `ValueError`.
2. Effective depth. The first entry always has effective depth 1 (whatever was requested). For every later entry, effective depth = min(requested depth, effective depth of the previous entry + 1). So an outline can only go one level deeper at a time, but can come back up any number of levels.
3. Counters. There is one counter per level, all starting at 0. When an entry with effective depth d is processed, the counter of level d is increased by 1 and the counters of all levels deeper than d are reset to 0.
4. Label. Take the counters of levels 1..d, render each in the style of its level, and join them with `.`. The style depends on the level number:
   - levels 1, 4, 7, ...: decimal number (`1`, `2`, ... `10`, ...);
   - levels 2, 5, 8, ...: lowercase letters like spreadsheet columns: 1 -> `a`, 2 -> `b`, ..., 26 -> `z`, 27 -> `aa`, 28 -> `ab`, ..., 52 -> `az`, 53 -> `ba`, ..., 702 -> `zz`, 703 -> `aaa`;
   - levels 3, 6, 9, ...: lowercase Roman numerals in the standard subtractive form: 1 -> `i`, 4 -> `iv`, 9 -> `ix`, 14 -> `xiv`, 40 -> `xl`, 49 -> `xlix`, 90 -> `xc`, 400 -> `cd`, 900 -> `cm` (counters never exceed 3999).
5. Line. `2 * (d - 1)` spaces, then the label, then `)`, then one space, then the title.

Example: `number_outline([(1, "Intro"), (2, "Scope"), (2, "Terms"), (4, "Odd"), (1, "Body"), (2, "Core")])` returns

    ["1) Intro", "  1.a) Scope", "  1.b) Terms", "    1.b.i) Odd", "2) Body", "  2.a) Core"]

(the entry "Odd" requested depth 4 but the previous effective depth was 2, so it gets depth 3). An empty input returns `[]`.""" + _TAIL,
    "reference": _REF_C04,
    "tests": _RAISES + r'''
assert number_outline([]) == []
assert number_outline([(1, "Intro"), (2, "Scope"), (2, "Terms"), (4, "Odd"), (1, "Body"), (2, "Core")]) == ["1) Intro", "  1.a) Scope", "  1.b) Terms", "    1.b.i) Odd", "2) Body", "  2.a) Core"]
assert number_outline([(3, "X"), (3, "Y"), (3, "Z")]) == ["1) X", "  1.a) Y", "    1.a.i) Z"]
assert number_outline([(1, "a"), (2, "b"), (3, "c"), (4, "d"), (4, "e"), (9, "f")]) == ["1) a", "  1.a) b", "    1.a.i) c", "      1.a.i.1) d", "      1.a.i.2) e", "        1.a.i.2.a) f"]
assert number_outline([(1, "a"), (2, "b"), (3, "c"), (2, "d"), (3, "e")])[-1] == "    1.b.i) e"
assert number_outline([(1, "a"), (2, "b"), (3, "c"), (1, "d"), (2, "e"), (3, "f")])[-2:] == ["  2.a) e", "    2.a.i) f"]
assert _raises(number_outline, [(1, "a"), (0, "b")])
assert _raises(number_outline, [(0, "a")])
_r = number_outline([(1, "t")] + [(2, "x")] * 703)
assert _r[26] == "  1.z) x" and _r[27] == "  1.aa) x" and _r[28] == "  1.ab) x"
assert _r[52] == "  1.az) x" and _r[53] == "  1.ba) x"
assert _r[702] == "  1.zz) x" and _r[703] == "  1.aaa) x"
_q = number_outline([(1, "t"), (2, "u")] + [(3, "y")] * 90)
assert _q[5] == "    1.a.iv) y" and _q[10] == "    1.a.ix) y" and _q[15] == "    1.a.xiv) y"
assert _q[41] == "    1.a.xl) y" and _q[50] == "    1.a.xlix) y" and _q[91] == "    1.a.xc) y"
assert number_outline([(1, "a")] * 12)[-1] == "12) a"
''',
    "wrong": _mut(_REF_C04, "        del counters[d:]\n", ""),
})


_REF_C05 = r'''
def decode_frames(hex_text):
    digits = "".join(hex_text.split())
    if len(digits) % 2 or any(ch not in "0123456789abcdefABCDEF" for ch in digits):
        raise ValueError("bad hex")
    data = bytes(int(digits[i:i + 2], 16) for i in range(0, len(digits), 2))
    frames = []
    i = 0
    while i < len(data):
        if data[i] != 0x7E or i + 1 >= len(data):
            raise ValueError("bad frame start")
        n = data[i + 1]
        if i + 3 + n > len(data):
            raise ValueError("truncated frame")
        payload = data[i + 2:i + 2 + n]
        if (sum(payload) % 256) ^ 0x5A != data[i + 2 + n]:
            raise ValueError("bad checksum")
        record = {}
        j = 0
        while j < n:
            if j + 2 > n:
                raise ValueError("truncated record header")
            tag, length = payload[j], payload[j + 1]
            value = payload[j + 2:j + 2 + length]
            if len(value) < length:
                raise ValueError("record overruns payload")
            j += 2 + length
            if tag == 0x01:
                record["count"] = record.get("count", 0) + int.from_bytes(value, "big")
            elif tag == 0x02:
                record["delta"] = record.get("delta", 0) + int.from_bytes(value, "big", signed=True)
            elif tag == 0x03:
                if any(b >= 0x80 for b in value):
                    raise ValueError("non-ASCII label")
                record["label"] = value.decode("ascii")
        frames.append(record)
        i += 3 + n
    return frames
'''

ITEMS.append({
    "id": "C05",
    "kind": "parsing",
    "difficulty": "very hard",
    "entry_point": "decode_frames",
    "prompt": r"""Write a Python function `decode_frames(hex_text: str) -> list[dict]` that decodes a byte stream written as hexadecimal text.

Input text: hex digits (upper or lower case). Whitespace may appear anywhere, even between the two digits of one byte; remove ALL whitespace first. After that, an odd number of digits or any non-hex character raises `ValueError`. Empty input (no bytes) returns `[]`.

The bytes are zero or more frames, back to back. A frame is:
- 1 byte: the marker 0x7E;
- 1 byte: N, the payload length (0..255);
- N payload bytes;
- 1 checksum byte, which must equal `(sum of the payload bytes mod 256) XOR 0x5A`.

A wrong marker, a frame that is cut short (missing length byte, payload bytes or checksum byte), or a wrong checksum raises `ValueError`.

The payload of a frame is a sequence of records that must fill it exactly. A record is: 1 tag byte, 1 length byte L, then L value bytes. If a record's header or value would run past the end of the payload, raise `ValueError`.

Each frame decodes to one dict, built from its records in order:
- tag 0x01: the value is an unsigned big-endian integer (L = 0 means 0). Key `"count"`. If the frame has several such records, their values are ADDED.
- tag 0x02: the value is a signed two's-complement big-endian integer of L bytes (L = 0 means 0; e.g. the single byte FF is -1, the two bytes FF 38 are -200). Key `"delta"`. Several such records in a frame are ADDED.
- tag 0x03: the value is ASCII text. Key `"label"` (a `str`, possibly empty). Any value byte >= 0x80 raises `ValueError`. If the frame has several such records, the LAST one wins.
- any other tag: the record is skipped (its value bytes are not interpreted).

A key is present in a frame's dict only if a record with that tag occurred in the frame. Return the list of dicts, one per frame, in order.

Examples:
- `decode_frames("7E 03 01 01 05 5D")` returns `[{"count": 5}]` (payload 01 01 05, sum 7, 7 XOR 0x5A = 0x5D).
- `decode_frames("7e005a7E030201FF58")` returns `[{}, {"delta": -1}]`.""" + _TAIL,
    "reference": _REF_C05,
    "tests": _RAISES + r'''
def _f(*p):
    return "7e%02x" % len(p) + "".join("%02x" % b for b in p) + "%02x" % ((sum(p) % 256) ^ 0x5A)
assert decode_frames("") == [] and decode_frames("  \n ") == []
assert decode_frames("7E 03 01 01 05 5D") == [{"count": 5}]
assert decode_frames("7e005a7E030201FF58") == [{}, {"delta": -1}]
assert decode_frames("7 E 0 0 5 A") == [{}]
assert decode_frames(_f(1, 2, 1, 0, 2, 2, 0xFF, 0x38, 3, 2, 0x68, 0x69)) == [{"count": 256, "delta": -200, "label": "hi"}]
assert decode_frames(_f(1, 1, 3, 1, 1, 4, 2, 1, 0x80, 2, 1, 5, 3, 1, 0x61, 3, 1, 0x62)) == [{"count": 7, "delta": -123, "label": "b"}]
assert decode_frames(_f(9, 3, 1, 2, 0x99, 1, 1, 2)) == [{"count": 2}]
assert decode_frames(_f(1, 1, 1) + "  " + _f(3, 0) + _f(2, 0, 1, 0)) == [{"count": 1}, {"label": ""}, {"delta": 0, "count": 0}]
assert decode_frames(_f(2, 2, 0x7F, 0xFF, 2, 3, 0xFF, 0xFF, 0xFE, 1, 3, 1, 0, 0)) == [{"delta": 32765, "count": 65536}]
assert _raises(decode_frames, "7E 03 01 01 05 5E")
assert _raises(decode_frames, "7F005A") and _raises(decode_frames, "7E005A00")
assert _raises(decode_frames, "7E0301") and _raises(decode_frames, "7E") and _raises(decode_frames, "7E00")
assert _raises(decode_frames, "7E0") and _raises(decode_frames, "7E00ZZ")
assert _raises(decode_frames, _f(1, 3, 1)) and _raises(decode_frames, _f(1, 1, 1, 2))
assert _raises(decode_frames, _f(3, 1, 0x80))
''',
    "wrong": _mut(_REF_C05, 'int.from_bytes(value, "big", signed=True)', 'int.from_bytes(value, "big")'),
})


# ---------------------------------------------------------------------------
# Kind 2: interval / schedule / calendar logic (C06-C10)
# ---------------------------------------------------------------------------

_REF_C06 = r'''
def merge_shift_windows(windows, min_gap):
    by_crew = {}
    for start, end, crew in windows:
        if start > end:
            raise ValueError("start after end")
        if start == end:
            continue
        by_crew.setdefault(crew, []).append((start, end))
    out = []
    for crew, spans in by_crew.items():
        spans.sort()
        cur_start, cur_end = spans[0]
        for start, end in spans[1:]:
            if start - cur_end <= min_gap:
                cur_end = max(cur_end, end)
            else:
                out.append((cur_start, cur_end, crew))
                cur_start, cur_end = start, end
        out.append((cur_start, cur_end, crew))
    out.sort(key=lambda w: (w[0], w[2]))
    return out
'''

ITEMS.append({
    "id": "C06",
    "kind": "interval",
    "difficulty": "medium",
    "entry_point": "merge_shift_windows",
    "prompt": r"""Write a Python function `merge_shift_windows(windows: list[tuple[int, int, str]], min_gap: int) -> list[tuple[int, int, str]]`.

Each window is `(start, end, crew)`: integer minutes `start` and `end` and a crew name. The input list is in no particular order. `min_gap` is an integer >= 0.

Rules:
1. If any window has `start > end`, raise `ValueError`.
2. Windows with `start == end` (zero length) are discarded before anything else; they never help to join other windows.
3. Two windows of the SAME crew belong together when they overlap, touch, or the gap between them (start of the later one minus end of the earlier one) is at most `min_gap`. This is transitive: chains of such windows merge into one window running from the smallest start to the largest end of the chain. Note that a window may lie completely inside an earlier, longer one.
4. Windows of different crews never merge, even if they overlap.
5. Return the merged windows as a list of `(start, end, crew)` tuples sorted by start ascending, then by crew name ascending.

Examples:
- `merge_shift_windows([(0, 60, "red"), (70, 90, "red"), (50, 80, "blue")], 10)` returns `[(0, 90, "red"), (50, 80, "blue")]`.
- `merge_shift_windows([(0, 60, "red"), (71, 90, "red")], 10)` returns `[(0, 60, "red"), (71, 90, "red")]`.""" + _TAIL,
    "reference": _REF_C06,
    "tests": _RAISES + r'''
assert merge_shift_windows([], 5) == []
assert merge_shift_windows([(0, 60, "red"), (70, 90, "red"), (50, 80, "blue")], 10) == [(0, 90, "red"), (50, 80, "blue")]
assert merge_shift_windows([(0, 60, "red"), (71, 90, "red")], 10) == [(0, 60, "red"), (71, 90, "red")]
assert merge_shift_windows([(0, 10, "a"), (15, 15, "a"), (20, 30, "a")], 5) == [(0, 10, "a"), (20, 30, "a")]
assert merge_shift_windows([(0, 100, "a"), (10, 20, "a"), (105, 110, "a")], 5) == [(0, 110, "a")]
assert merge_shift_windows([(40, 50, "a"), (0, 5, "a"), (20, 30, "a"), (5, 8, "a")], 0) == [(0, 8, "a"), (20, 30, "a"), (40, 50, "a")]
assert merge_shift_windows([(40, 50, "a"), (0, 5, "a"), (20, 30, "a"), (5, 8, "a")], 12) == [(0, 50, "a")]
assert merge_shift_windows([(5, 9, "zed"), (5, 7, "amy")], 0) == [(5, 7, "amy"), (5, 9, "zed")]
assert merge_shift_windows([(3, 3, "a")], 100) == []
assert merge_shift_windows([(0, 4, "a"), (4, 6, "b"), (6, 9, "a")], 1) == [(0, 4, "a"), (4, 6, "b"), (6, 9, "a")]
assert merge_shift_windows([(0, 4, "a"), (4, 6, "b"), (6, 9, "a")], 2) == [(0, 9, "a"), (4, 6, "b")]
assert _raises(merge_shift_windows, [(0, 4, "a"), (5, 3, "a")], 1)
''',
    "wrong": _mut(_REF_C06, "cur_end = max(cur_end, end)", "cur_end = end"),
})


_REF_C07 = r'''
import datetime

def shift_working_days(start, n, holidays, rest_days):
    rest = set(rest_days)
    if len(rest & set(range(7))) == 7:
        raise ValueError("no working weekday")
    closed = set(holidays)
    day = datetime.date.fromisoformat(start)
    one = datetime.timedelta(days=1)

    def working(d):
        return d.weekday() not in rest and d.isoformat() not in closed

    if n == 0:
        while not working(day):
            day += one
        return day.isoformat()
    step = one if n > 0 else -one
    left = abs(n)
    while left:
        day += step
        if working(day):
            left -= 1
    return day.isoformat()
'''

ITEMS.append({
    "id": "C07",
    "kind": "interval",
    "difficulty": "medium",
    "entry_point": "shift_working_days",
    "prompt": r"""Write a Python function `shift_working_days(start: str, n: int, holidays: list[str], rest_days: list[int]) -> str`.

- Dates are strings in the form `"YYYY-MM-DD"` (proleptic Gregorian calendar); the result is a date in the same form.
- `rest_days` lists weekday numbers that are never working days, with Monday = 0, Tuesday = 1, ..., Sunday = 6.
- `holidays` lists dates that are not working days.
- A working day is a date whose weekday is not in `rest_days` and which is not in `holidays`.

Result:
- `n > 0`: the n-th working day STRICTLY AFTER `start`.
- `n < 0`: the |n|-th working day STRICTLY BEFORE `start`.
- `n == 0`: `start` itself if it is a working day, otherwise the first working day after `start`.

`start` does not have to be a working day. If `rest_days` contains all seven weekdays, raise `ValueError`. You may assume `holidays` is a short finite list, so a result always exists otherwise.

Examples (2031-03-07 is a Friday):
- `shift_working_days("2031-03-07", 1, [], [5, 6])` returns `"2031-03-10"`.
- `shift_working_days("2031-03-07", 5, ["2031-03-12"], [5, 6])` returns `"2031-03-17"`.""" + _TAIL,
    "reference": _REF_C07,
    "tests": _RAISES + r'''
assert shift_working_days("2031-03-07", 1, [], [5, 6]) == "2031-03-10"
assert shift_working_days("2031-03-07", 5, ["2031-03-12"], [5, 6]) == "2031-03-17"
assert shift_working_days("2031-03-07", 0, [], [5, 6]) == "2031-03-07"
assert shift_working_days("2031-03-08", 0, [], [5, 6]) == "2031-03-10"
assert shift_working_days("2031-03-08", 0, ["2031-03-10"], [5, 6]) == "2031-03-11"
assert shift_working_days("2031-03-08", 1, [], [5, 6]) == "2031-03-10"
assert shift_working_days("2031-03-08", -1, [], [5, 6]) == "2031-03-07"
assert shift_working_days("2031-03-10", -1, ["2031-03-07"], [5, 6]) == "2031-03-06"
assert shift_working_days("2031-03-03", -3, [], [5, 6]) == "2031-02-26"
assert shift_working_days("2031-12-31", 3, ["2032-01-01"], [5, 6]) == "2032-01-06"
assert shift_working_days("2031-03-06", 2, [], [4]) == "2031-03-09"
assert shift_working_days("2031-02-28", 1, [], []) == "2031-03-01"
assert shift_working_days("2031-03-07", 1, ["2031-03-08", "2031-03-10"], [5, 6]) == "2031-03-11"
assert _raises(shift_working_days, "2031-03-07", 1, [], [0, 1, 2, 3, 4, 5, 6])
''',
    "wrong": _mut(_REF_C07, "        while not working(day):\n            day += one\n", ""),
})


_REF_C08 = r'''
def open_slots(busy, day_start, day_end, duration, step, cooldown):
    out = []
    t = day_start
    while t + duration <= day_end:
        if all(t + duration <= s or t >= e + cooldown for s, e in busy):
            out.append(t)
        t += step
    return out
'''

ITEMS.append({
    "id": "C08",
    "kind": "interval",
    "difficulty": "medium",
    "entry_point": "open_slots",
    "prompt": r"""Write a Python function `open_slots(busy: list[tuple[int, int]], day_start: int, day_end: int, duration: int, step: int, cooldown: int) -> list[int]` that lists the possible start times for a meeting. All times are integer minutes.

- `busy` is a list of busy intervals `(s, e)` with `s < e`. They are in no particular order, may overlap each other, and may lie partly or completely outside the day.
- Candidate start times are `day_start`, `day_start + step`, `day_start + 2*step`, ... - only those `t` with `t + duration <= day_end`.
- A candidate `t` is acceptable if, for EVERY busy interval `(s, e)`, at least one of these holds:
  - the meeting is over when the busy interval begins: `t + duration <= s`; or
  - the meeting starts at least `cooldown` minutes after the busy interval ended: `t >= e + cooldown`.
  (So the cooldown applies only after a busy interval, not before one.)
- `duration >= 1`, `step >= 1`, `cooldown >= 0`.

Return the acceptable start times in ascending order. If no candidate exists (for example `day_start >= day_end`, or `duration` longer than the day), return `[]`.

Example: `open_slots([(540, 600)], 480, 720, 60, 30, 15)` returns `[480, 630, 660]` (480 ends exactly when the busy interval starts; 600 is rejected because it is less than 15 minutes after 600).""" + _TAIL,
    "reference": _REF_C08,
    "tests": r'''
assert open_slots([(540, 600)], 480, 720, 60, 30, 15) == [480, 630, 660]
assert open_slots([(540, 600)], 480, 720, 60, 30, 0) == [480, 600, 630, 660]
assert open_slots([], 0, 100, 30, 25, 5) == [0, 25, 50]
assert open_slots([], 0, 100, 101, 1, 0) == []
assert open_slots([], 50, 50, 1, 1, 0) == [] and open_slots([], 60, 50, 1, 1, 0) == []
assert open_slots([(400, 480)], 480, 600, 30, 30, 10) == [510, 540, 570]
assert open_slots([(590, 700)], 480, 600, 30, 30, 10) == [480, 510, 540]
assert open_slots([(30, 40), (10, 35), (38, 50)], 0, 80, 10, 5, 0) == [0, 50, 55, 60, 65, 70]
assert open_slots([(30, 40), (10, 35), (38, 50)], 0, 80, 10, 5, 12) == [0, 65, 70]
assert open_slots([(0, 1000)], 0, 500, 10, 10, 0) == []
assert open_slots([(20, 30)], 7, 60, 13, 6, 1) == [7, 31, 37, 43]
assert open_slots([(10, 20)], 0, 30, 10, 10, 0) == [0, 20]
''',
    "wrong": _mut(_REF_C08, "t + duration <= s or", "t + duration + cooldown <= s or"),
})


_REF_C09 = r'''
def band_minutes(start, end):
    if start > end:
        raise ValueError("start after end")

    def band(m):
        w = m % 10080
        if w // 1440 >= 5:
            return 2
        tod = w % 1440
        return 1 if (tod < 360 or tod >= 1320) else 0

    def upto(x):
        weeks, rem = divmod(x, 10080)
        counts = [4800 * weeks, 2400 * weeks, 2880 * weeks]
        for m in range(rem):
            counts[band(m)] += 1
        return counts

    lo, hi = upto(start), upto(end)
    raw = [hi[i] - lo[i] for i in range(3)]
    if end - start < 5:
        raw = [0, 0, 0]
    billed = [-(-x // 15) * 15 for x in raw]
    return {"day": billed[0], "night": billed[1], "weekend": billed[2]}
'''

ITEMS.append({
    "id": "C09",
    "kind": "interval",
    "difficulty": "hard",
    "entry_point": "band_minutes",
    "prompt": r"""Write a Python function `band_minutes(start: int, end: int) -> dict` that computes billable minutes per tariff band for a parking stay.

Time is counted in whole minutes from minute 0 = Monday 00:00 of some week. Minutes keep counting past the end of the week (a week has 10080 minutes) and the weekly pattern repeats forever. The stay covers the minutes `start, start+1, ..., end-1` (so its length is `end - start`). `0 <= start`; if `start > end` raise `ValueError`.

Band of a single minute `m`:
- let `w = m mod 10080`, `day = w // 1440` (0 = Monday ... 6 = Sunday), `tod = w mod 1440` (minute of the day);
- if `day` is 5 or 6 (Saturday, Sunday): band `"weekend"` (all 24 hours);
- otherwise, if `tod < 360` or `tod >= 1320` (before 06:00 or from 22:00): band `"night"`;
- otherwise: band `"day"`.

Billing:
1. Count the stay's minutes in each band (raw counts).
2. Grace period: if the whole stay is shorter than 5 minutes (`end - start < 5`), all three results are 0.
3. Otherwise each band's raw count is rounded UP to a multiple of 15, separately per band (0 stays 0; an exact multiple stays unchanged).

Return `{"day": d, "night": n, "weekend": w}` (always all three keys, integer values).

`start` and `end` can be huge (10**15 and beyond), so the function must not loop over every minute of the stay.

Examples:
- `band_minutes(1310, 1330)` (Monday 21:50 to 22:10: 10 day minutes, 10 night minutes) returns `{"day": 15, "night": 15, "weekend": 0}`.
- `band_minutes(100, 103)` returns `{"day": 0, "night": 0, "weekend": 0}`.""" + _TAIL,
    "reference": _REF_C09,
    "tests": _RAISES + r'''
def _b(d, n, w):
    return {"day": d, "night": n, "weekend": w}
assert band_minutes(1310, 1330) == _b(15, 15, 0)
assert band_minutes(100, 103) == _b(0, 0, 0) and band_minutes(0, 0) == _b(0, 0, 0)
assert band_minutes(100, 104) == _b(0, 0, 0) and band_minutes(100, 105) == _b(0, 15, 0)
assert band_minutes(7190, 7210) == _b(0, 15, 15)
assert band_minutes(10020, 10500) == _b(60, 360, 60)
assert band_minutes(360, 375) == _b(15, 0, 0) and band_minutes(360, 376) == _b(30, 0, 0)
assert band_minutes(358, 363) == _b(15, 15, 0)
assert band_minutes(0, 10080) == _b(4800, 2400, 2880)
assert band_minutes(5 * 1440 - 1, 7 * 1440 + 1) == _b(0, 15, 2880)
assert band_minutes(0, 10080 * 10 ** 8) == _b(4800 * 10 ** 8, 2400 * 10 ** 8, 2880 * 10 ** 8)
assert band_minutes(10080 * 10 ** 7 + 1310, 10080 * 10 ** 7 + 1330) == _b(15, 15, 0)
assert band_minutes(5, 10080 * 10 ** 6 + 400) == _b(4800000045, 2400000360, 2880000000)
assert band_minutes(10 ** 15 - 3, 10 ** 15 + 3) == band_minutes((10 ** 15 - 3) % 10080, (10 ** 15 - 3) % 10080 + 6)
assert _raises(band_minutes, 10, 5)
''',
    "wrong": _mut(_REF_C09, "if end - start < 5:", "if end - start <= 5:"),
})


_REF_C10 = r'''
import calendar
import datetime

def meeting_dates(year, weekday, n, closed):
    if n == 0 or abs(n) > 5 or not 0 <= weekday <= 6:
        raise ValueError("bad arguments")
    closed = set(closed)
    out = []
    for month in range(1, 13):
        ndays = calendar.monthrange(year, month)[1]
        days = [d for d in range(1, ndays + 1)
                if datetime.date(year, month, d).weekday() == weekday]
        if abs(n) > len(days):
            continue
        day = days[n - 1] if n > 0 else days[n]
        cur = datetime.date(year, month, day)
        while cur.isoformat() in closed:
            cur += datetime.timedelta(days=1)
        if cur.month != month:
            continue
        out.append(cur.isoformat())
    return out
'''

ITEMS.append({
    "id": "C10",
    "kind": "interval",
    "difficulty": "hard",
    "entry_point": "meeting_dates",
    "prompt": r"""Write a Python function `meeting_dates(year: int, weekday: int, n: int, closed: list[str]) -> list[str]` that lists the dates of a monthly club meeting in the given year (Gregorian calendar). Dates are strings `"YYYY-MM-DD"`.

- `weekday` is 0 for Monday, 1 for Tuesday, ..., 6 for Sunday. Any other value raises `ValueError`.
- `n` selects which occurrence of that weekday in each month is the nominal meeting day:
  - `n` = 1..5 counts from the start of the month (1 = first, 2 = second, ...);
  - `n` = -1..-5 counts from the end of the month (-1 = last, -2 = second to last, ...);
  - `n` = 0 or |n| > 5 raises `ValueError`.
- If a month does not have that occurrence (e.g. no fifth Friday), the month has no meeting.
- `closed` is a list of dates on which the club house is closed. If the nominal day is in `closed`, the meeting moves to the next calendar day, repeatedly, until a day that is not in `closed` is found (any weekday is fine). If this moves the meeting out of its month, that month has no meeting at all.

Return the meeting dates for January..December of `year` in chronological order (months without a meeting are simply missing).

Examples (in 2031, January 1st is a Wednesday):
- `meeting_dates(2031, 6, 5, [])` (fifth Sundays) returns `["2031-03-30", "2031-06-29", "2031-08-31", "2031-11-30"]`.
- `meeting_dates(2031, 0, 1, ["2031-01-06"])[:2]` returns `["2031-01-07", "2031-02-03"]`.""" + _TAIL,
    "reference": _REF_C10,
    "tests": _RAISES + r'''
def _d(*md):
    return ["2031-%02d-%02d" % (md[i], md[i + 1]) for i in range(0, len(md), 2)]
assert meeting_dates(2031, 0, 1, []) == _d(1, 6, 2, 3, 3, 3, 4, 7, 5, 5, 6, 2, 7, 7, 8, 4, 9, 1, 10, 6, 11, 3, 12, 1)
assert meeting_dates(2031, 4, -1, []) == _d(1, 31, 2, 28, 3, 28, 4, 25, 5, 30, 6, 27, 7, 25, 8, 29, 9, 26, 10, 31, 11, 28, 12, 26)
assert meeting_dates(2031, 6, 5, []) == ["2031-03-30", "2031-06-29", "2031-08-31", "2031-11-30"]
assert meeting_dates(2031, 6, -5, []) == ["2031-03-02", "2031-06-01", "2031-08-03", "2031-11-02"]
assert meeting_dates(2031, 2, 2, []) == _d(1, 8, 2, 12, 3, 12, 4, 9, 5, 14, 6, 11, 7, 9, 8, 13, 9, 10, 10, 8, 11, 12, 12, 10)
assert meeting_dates(2031, 3, -2, []) == _d(1, 23, 2, 20, 3, 20, 4, 17, 5, 22, 6, 19, 7, 24, 8, 21, 9, 18, 10, 23, 11, 20, 12, 18)
assert meeting_dates(2031, 0, 1, ["2031-01-06"])[:2] == ["2031-01-07", "2031-02-03"]
assert meeting_dates(2031, 4, -1, ["2031-01-31", "2031-03-28", "2031-03-29"])[:3] == ["2031-02-28", "2031-03-30", "2031-04-25"]
assert len(meeting_dates(2031, 4, -1, ["2031-01-31", "2031-02-28", "2031-03-01", "2031-12-26", "2031-12-27"])) == 10
assert meeting_dates(2031, 4, -1, ["2031-12-26", "2031-12-27"])[-1] == "2031-12-28"
assert meeting_dates(2032, 6, 5, [])[0] == "2032-02-29"
assert meeting_dates(2031, 6, 5, ["2031-03-30", "2031-03-31", "2031-08-31"]) == ["2031-06-29", "2031-11-30"]
assert _raises(meeting_dates, 2031, 0, 0, []) and _raises(meeting_dates, 2031, 0, 6, []) and _raises(meeting_dates, 2031, 0, -6, [])
assert _raises(meeting_dates, 2031, 7, 1, []) and _raises(meeting_dates, 2031, -1, 1, [])
''',
    "wrong": _mut(_REF_C10, "if cur.month != month:", "if False:"),
})

# ---------------------------------------------------------------------------
# Kind 3: simulation of invented machines / games / rule systems (C11-C15)
# ---------------------------------------------------------------------------

_REF_C11 = r'''
import re

def run_tally(program, max_steps):
    toks = program.split()
    n = len(toks)
    stack, out = [], []
    pc = 0
    steps = 0
    while True:
        if pc == n:
            return ("done", out)
        if steps == max_steps:
            return ("limit", out)
        steps += 1
        t = toks[pc]
        if re.fullmatch(r"-?[0-9]+", t):
            stack.append(int(t))
        elif t == "dup":
            if not stack:
                return ("fault", out)
            stack.append(stack[-1])
        elif t == "drop":
            if not stack:
                return ("fault", out)
            stack.pop()
        elif t == "out":
            if not stack:
                return ("fault", out)
            out.append(stack.pop())
        elif t in ("swap", "add", "sub", "mul"):
            if len(stack) < 2:
                return ("fault", out)
            b = stack.pop()
            a = stack.pop()
            if t == "swap":
                stack.extend([b, a])
            elif t == "add":
                stack.append(a + b)
            elif t == "sub":
                stack.append(a - b)
            else:
                stack.append(a * b)
        else:
            m = re.fullmatch(r"(jmp|jz):(-?[0-9]+)", t)
            if not m:
                return ("fault", out)
            if m.group(1) == "jz":
                if not stack:
                    return ("fault", out)
                if stack.pop() != 0:
                    pc += 1
                    continue
            target = pc + int(m.group(2))
            if target < 0 or target > n:
                return ("fault", out)
            pc = target
            continue
        pc += 1
'''

ITEMS.append({
    "id": "C11",
    "kind": "simulation",
    "difficulty": "hard",
    "entry_point": "run_tally",
    "prompt": r"""Write a Python function `run_tally(program: str, max_steps: int) -> tuple[str, list[int]]` that simulates a small stack machine called the Tally machine and returns `(status, output)`.

The program is a string of tokens separated by whitespace; tokens are numbered from 0 and `n` is the number of tokens. The machine has a stack of integers (initially empty), an output list (initially empty), a program counter `pc` (initially 0) and a count of executed instructions (initially 0).

Main loop, repeated:
1. If `pc == n`, stop with status `"done"`.
2. Otherwise, if the number of instructions executed so far equals `max_steps`, stop with status `"limit"`.
3. Otherwise execute the token at `pc` (this counts as one executed instruction, whatever the token is).

Instructions:
- an integer literal (optional `-` then digits, e.g. `7`, `-12`): push it; `pc += 1`.
- `dup`: push a copy of the top value; `pc += 1`.
- `drop`: pop and discard the top value; `pc += 1`.
- `swap`: exchange the top two values; `pc += 1`.
- `add`, `sub`, `mul`: pop `b`, then pop `a`, push `a + b`, `a - b` or `a * b` (so `5 3 sub` leaves 2); `pc += 1`.
- `out`: pop the top value and append it to the output list; `pc += 1`.
- `jmp:K` (K is an integer written as optional `-` then digits): set `pc = pc + K`, relative to the position of the `jmp` token itself.
- `jz:K`: pop the top value; if it is 0 set `pc = pc + K`, otherwise `pc += 1`.

Faults - the machine stops immediately with status `"fault"` when:
- an instruction needs more values than the stack holds;
- the token is not one of the forms above (a malformed token is only a problem when the machine actually tries to execute it);
- a jump that is taken has a target below 0 or above `n` (a target of exactly `n` is allowed and ends the program with `"done"`). A `jz` whose popped value is non-zero does not jump, so its K is not checked.

The returned output is everything appended by `out` before the machine stopped.

Example: `run_tally("3 dup out 1 sub dup jz:2 jmp:-6 drop", 100)` returns `("done", [3, 2, 1])` and executes exactly 22 instructions; with `max_steps = 22` the result is the same, with `max_steps = 21` it is `("limit", [3, 2, 1])`, and with `max_steps = 10` it is `("limit", [3, 2])`.""" + _TAIL,
    "reference": _REF_C11,
    "tests": r'''
_P = "3 dup out 1 sub dup jz:2 jmp:-6 drop"
assert run_tally("", 10) == ("done", []) and run_tally("  ", 0) == ("done", [])
assert run_tally(_P, 100) == ("done", [3, 2, 1])
assert run_tally(_P, 22) == ("done", [3, 2, 1])
assert run_tally(_P, 21) == ("limit", [3, 2, 1])
assert run_tally(_P, 10) == ("limit", [3, 2])
assert run_tally("1 2 sub out", 99) == ("done", [-1])
assert run_tally("2 3 swap sub out -4 5 mul out 6 7 add out", 99) == ("done", [1, -20, 13])
assert run_tally("5 out add 7 out", 99) == ("fault", [5])
assert run_tally("1 out bogus", 99) == ("fault", [1]) and run_tally("1 out jmp:2 bogus", 99) == ("done", [1])
assert run_tally("jmp:0", 50) == ("limit", []) and run_tally("jmp:-1", 50) == ("fault", [])
assert run_tally("1 jz:9 7 out", 99) == ("done", [7]) and run_tally("0 jz:9 7 out", 99) == ("fault", [])
assert run_tally("0 jz:3 7 out 8 out", 99) == ("done", [8])
assert run_tally("7 out", 1) == ("limit", []) and run_tally("7 out", 2) == ("done", [7])
assert run_tally("jz:1", 5) == ("fault", []) and run_tally("4 dup drop drop drop", 9) == ("fault", [])
assert run_tally("9 out jmp:3 1 out 2 out jmp:-2", 6) == ("limit", [9, 2]) and run_tally("9 out jmp:3 1 out 2 out jmp:-2", 8) == ("limit", [9, 2, 2])
''',
    "wrong": _mut(_REF_C11,
                  '        if pc == n:\n            return ("done", out)\n        if steps == max_steps:\n            return ("limit", out)\n',
                  '        if steps == max_steps:\n            return ("limit", out)\n        if pc == n:\n            return ("done", out)\n'),
})


_REF_C12 = r'''
def sow_pits(pits, start):
    n = len(pits)
    if not 0 <= start < n or pits[start] == 0:
        raise ValueError("bad start pit")
    pits = list(pits)
    hand = pits[start]
    pits[start] = 0
    pos = start
    while hand:
        pos = (pos + 1) % n
        if pos == start:
            continue
        pits[pos] += 1
        hand -= 1
    captured = 0
    while pos != start and pits[pos] in (2, 3):
        captured += pits[pos]
        pits[pos] = 0
        pos = (pos - 1) % n
    return (pits, captured)
'''

ITEMS.append({
    "id": "C12",
    "kind": "simulation",
    "difficulty": "medium",
    "entry_point": "sow_pits",
    "prompt": r"""Write a Python function `sow_pits(pits: list[int], start: int) -> tuple[list[int], int]` that plays one move of a pebble game on a ring of pits and returns `(new_pits, captured)`.

`pits[i]` is the number of pebbles in pit `i`; the pits form a ring, so pit `len(pits) - 1` is followed by pit 0. There are at least 2 pits. The input list must not be modified.

1. Validation: if `start` is not a valid index (`0 <= start < len(pits)`; negative indices are NOT allowed) or pit `start` is empty, raise `ValueError`.
2. Sowing: take all pebbles out of pit `start` (it becomes 0). Then drop them one at a time into the following pits in increasing index order, wrapping around the ring. The start pit is always skipped, even when there are enough pebbles to go around the ring several times - it stays empty.
3. Capturing: look at the pit where the LAST pebble was dropped. While the pit you are looking at contains exactly 2 or exactly 3 pebbles: capture them (add them to the captured total, set the pit to 0) and move to the previous pit (index minus 1, wrapping around). Stop as soon as the pit you are looking at has any other count, or is the start pit.

Return the new list of pit counts and the total number of pebbles captured.

Examples:
- `sow_pits([4, 1, 2, 0, 1], 0)` returns `([0, 2, 3, 1, 0], 2)`: after sowing the pits are [0, 2, 3, 1, 2]; the last pebble landed in pit 4 (now 2, captured); pit 3 holds 1, so capturing stops.
- `sow_pits([1, 1, 2, 3], 3)` returns `([0, 0, 0, 0], 7)`: after sowing [2, 2, 3, 0]; pits 2, 1 and 0 are captured in turn, then the start pit is reached.""" + _TAIL,
    "reference": _REF_C12,
    "tests": _RAISES + r'''
assert sow_pits([4, 1, 2, 0, 1], 0) == ([0, 2, 3, 1, 0], 2)
assert sow_pits([1, 1, 2, 3], 3) == ([0, 0, 0, 0], 7)
assert sow_pits([0, 0, 7], 2) == ([4, 3, 0], 0)
assert sow_pits([1, 0, 5], 2) == ([4, 2, 0], 0)
assert sow_pits([0, 0, 4], 2) == ([0, 0, 0], 4)
assert sow_pits([3, 0, 0, 0, 0, 0], 0) == ([0, 1, 1, 1, 0, 0], 0)
assert sow_pits([2, 1, 1], 0) == ([0, 0, 0], 4)
assert sow_pits([5, 2, 9], 1) == ([6, 0, 10], 0)
assert sow_pits([1, 1, 5, 2, 1], 2) == ([2, 2, 0, 4, 2], 0) and sow_pits([1, 1, 4, 0, 1], 2) == ([0, 0, 0, 1, 0], 6)
assert sow_pits([0, 6, 1, 1], 1) == ([0, 0, 0, 0], 8)
_p = [4, 1, 2, 0, 1]
_r = sow_pits(_p, 0)
assert _p == [4, 1, 2, 0, 1] and _r[0] is not _p
assert _raises(sow_pits, [1, 2, 3], -1) and _raises(sow_pits, [1, 2, 3], 3)
assert _raises(sow_pits, [1, 0, 3], 1)
''',
    "wrong": _mut(_REF_C12, "        if pos == start:\n            continue\n", ""),
})


_REF_C13 = r'''
import re

def run_rover(grid, commands):
    if not re.fullmatch(r"(?:[FBLR][0-9]*)*", commands):
        raise ValueError("bad commands")
    items = []
    for letter, digits in re.findall(r"([FBLR])([0-9]*)", commands):
        count = int(digits) if digits else 1
        if count == 0:
            raise ValueError("zero count")
        items.append((letter, count))
    h, w = len(grid), len(grid[0])
    portals = {}
    r = c = 0
    for y in range(h):
        for x in range(w):
            ch = grid[y][x]
            if ch == "S":
                r, c = y, x
            elif "a" <= ch <= "z":
                portals.setdefault(ch, []).append((y, x))
    dirs = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    facing = 0

    def free(y, x):
        return 0 <= y < h and 0 <= x < w and grid[y][x] != "#"

    for letter, count in items:
        for _ in range(count):
            if letter == "L":
                facing = (facing - 1) % 4
                continue
            if letter == "R":
                facing = (facing + 1) % 4
                continue
            dr, dc = dirs[facing] if letter == "F" else dirs[(facing + 2) % 4]
            if not free(r + dr, c + dc):
                continue
            r, c = r + dr, c + dc
            while grid[r][c] == "~" and free(r + dr, c + dc):
                r, c = r + dr, c + dc
            ch = grid[r][c]
            if "a" <= ch <= "z":
                first, second = portals[ch]
                r, c = second if (r, c) == first else first
    return (r, c, "NESW"[facing])
'''

ITEMS.append({
    "id": "C13",
    "kind": "simulation",
    "difficulty": "very hard",
    "entry_point": "run_rover",
    "prompt": r"""Write a Python function `run_rover(grid: list[str], commands: str) -> tuple[int, int, str]` that drives a rover over a grid and returns its final `(row, col, facing)`.

Grid: a list of equal-length strings; row 0 is the top (north) row, column 0 the left (west) column. Cells:
- `.` floor
- `#` wall
- `~` ice
- `S` the start cell (exactly one; it behaves like floor)
- a lowercase letter `a`-`z`: a portal. Each letter that is used appears on exactly two cells.

The rover starts on `S` facing north. Facing is one of `"N"`, `"E"`, `"S"`, `"W"` (north = row - 1, east = col + 1).

Commands: a string made of items, each a letter `F`, `B`, `L` or `R` optionally followed by a decimal repeat count (`F3` = `FFF`; no count means 1; counts are written without leading zeros and must be at least 1). If `commands` contains anything else (other characters, lowercase letters, spaces, a count with no letter before it, a count of 0), raise `ValueError`. The empty string is valid.

- `L` / `R`: turn 90 degrees left (N -> W -> S -> E -> N) / right (N -> E -> S -> W -> N) without moving.
- `F`: take one step in the facing direction.
- `B`: take one step in the direction opposite to the facing, without changing the facing.

One step in a direction d:
1. Look at the adjacent cell in direction d. If it is outside the grid or a wall, the step does nothing at all.
2. Otherwise the rover moves onto it. Then sliding: while the rover is standing on an ice cell AND the next cell in direction d is inside the grid and not a wall, it moves one more cell in direction d. (So a slide ends on the first non-ice cell reached, or on an ice cell when the way ahead is blocked.)
3. If the cell where the rover has come to rest after step 2 is a portal, the rover is moved to the other cell with the same letter. Arriving through a portal triggers nothing further. Portals only act on a rover that came to rest on them by a step (a slide always stops on a portal cell, because a portal is not ice).

Turning, sliding and portals never change the facing.

Examples:
- `run_rover(["..#", ".S.", "..."], "F2RF")` returns `(0, 1, "E")` (the second F is blocked by the edge, the last F by the wall).
- `run_rover(["S~~.#"], "RF")` returns `(0, 3, "E")` (slides across both ice cells and stops on the floor cell).""" + _TAIL,
    "reference": _REF_C13,
    "tests": _RAISES + r'''
_g = ["a.~~#", ".S..a", "....."]
assert run_rover(["..#", ".S.", "..."], "F2RF") == (0, 1, "E")
assert run_rover(["S~~.#"], "RF") == (0, 3, "E")
assert run_rover(_g, "") == (1, 1, "N") and run_rover(_g, "F") == (0, 1, "N")
assert run_rover(_g, "FRF") == (0, 3, "E")
assert run_rover(_g, "FLF") == (1, 4, "W") and run_rover(_g, "FLF2") == (1, 3, "W")
assert run_rover(_g, "FLF2B") == (0, 0, "W")
assert run_rover(_g, "R3F") == (1, 0, "W") and run_rover(_g, "L4") == (1, 1, "N") and run_rover(_g, "L") == (1, 1, "W")
assert run_rover(_g, "RF3") == (0, 0, "E") and run_rover(_g, "RF4") == (0, 1, "E")
assert run_rover(_g, "B") == (2, 1, "N") and run_rover(_g, "B2") == (2, 1, "N")
assert run_rover(["S~~."], "LB") == (0, 3, "W")
assert run_rover(["S~~"], "RF") == (0, 2, "E") and run_rover(["S~~"], "RF2B") == (0, 0, "E")
assert run_rover(["S~b", "b.."], "RF") == (1, 0, "E")
assert run_rover(["#..", "~..", "~.S", "..."], "LF2RF") == (1, 0, "N") and run_rover(["#..", "~..", "~.S", "..."], "LF2RFB") == (3, 0, "N")
assert run_rover(["S.", "~~", "~#", ".."], "R2F12L2F") == (0, 0, "N")
assert _raises(run_rover, _g, "X") and _raises(run_rover, _g, "3F") and _raises(run_rover, _g, "F0") and _raises(run_rover, _g, "f") and _raises(run_rover, _g, "F R")
''',
    "wrong": _mut(_REF_C13, 'while grid[r][c] == "~" and free(r + dr, c + dc):', 'if grid[r][c] == "~" and free(r + dr, c + dc):'),
})


_REF_C14 = r'''
def checkout_finish_times(lanes, customers):
    if lanes < 1:
        raise ValueError("need at least one lane")
    finishes = [[] for _ in range(lanes)]
    out = []
    for arrival, items in customers:
        best = min(range(lanes),
                   key=lambda i: (sum(1 for f in finishes[i] if f > arrival), i))
        start = arrival
        if finishes[best]:
            start = max(arrival, finishes[best][-1])
        end = start + 10 + 3 * items
        finishes[best].append(end)
        out.append(end)
    return out
'''

ITEMS.append({
    "id": "C14",
    "kind": "simulation",
    "difficulty": "hard",
    "entry_point": "checkout_finish_times",
    "prompt": r"""Write a Python function `checkout_finish_times(lanes: int, customers: list[tuple[int, int]]) -> list[int]` that simulates a supermarket with `lanes` checkout lanes numbered 0..lanes-1.

`customers` is a list of `(arrival_time, items)` in order of arrival (arrival times are non-decreasing integers; `items >= 0`). Customers who arrive at the same time are handled in list order, and each one already sees the previous ones standing in their lanes.

When a customer arrives at time `t`:
1. They look at how many people are in each lane. A person counts as being in a lane if they joined it earlier and their finish time is strictly greater than `t` (someone finishing exactly at `t` has already left). This includes the person currently being served.
2. They join the lane with the FEWEST people; ties go to the lowest lane number. (They do not consider how long the people ahead will take.)
3. Each lane serves its customers in joining order. The customer's service starts at `max(t, finish time of the previous customer who joined that lane)` (or at `t` if nobody joined that lane before) and takes `10 + 3 * items` time units.

Return the list of finish times, in the same order as the input list. `lanes < 1` raises `ValueError`. An empty customer list returns `[]`.

Example: `checkout_finish_times(2, [(0, 10), (0, 1), (5, 1), (13, 2)])` returns `[40, 13, 53, 29]`: the first customer takes lane 0 (finishes at 40), the second lane 1 (13). At time 5 both lanes hold one person, so the third joins lane 0 and is served 40..53. At time 13 lane 1 is empty again (its customer finished exactly at 13), so the fourth is served there 13..29.""" + _TAIL,
    "reference": _REF_C14,
    "tests": _RAISES + r'''
assert checkout_finish_times(2, []) == []
assert checkout_finish_times(2, [(0, 10), (0, 1), (5, 1), (13, 2)]) == [40, 13, 53, 29]
assert checkout_finish_times(1, [(0, 0), (0, 0), (100, 1)]) == [10, 20, 113]
assert checkout_finish_times(3, [(0, 5), (0, 5), (0, 5), (0, 5)]) == [25, 25, 25, 50]
assert checkout_finish_times(2, [(0, 30), (1, 0), (2, 0), (3, 0)]) == [100, 11, 110, 21]
assert checkout_finish_times(2, [(0, 10), (0, 1), (13, 0)]) == [40, 13, 23]
assert checkout_finish_times(2, [(0, 10), (0, 1), (12, 0)]) == [40, 13, 50]
assert checkout_finish_times(2, [(0, 0), (0, 0), (10, 0)]) == [10, 10, 20]
assert checkout_finish_times(2, [(0, 0), (0, 0), (9, 0), (9, 0), (9, 0)]) == [10, 10, 20, 20, 30]
assert checkout_finish_times(3, [(0, 20), (0, 0), (0, 0), (10, 2), (10, 0), (11, 0)]) == [70, 10, 10, 26, 20, 80]
assert checkout_finish_times(5, [(7, 1)]) == [20]
assert _raises(checkout_finish_times, 0, [(0, 1)])
''',
    "wrong": _mut(_REF_C14, "if f > arrival", "if f >= arrival"),
})


_REF_C15 = r'''
def grow_moss(cells, steps):
    if any(ch not in ".oO" for ch in cells):
        raise ValueError("bad cell")

    def step(s):
        n = len(s)
        out = []
        for i, ch in enumerate(s):
            live = int(i > 0 and s[i - 1] != ".") + int(i + 1 < n and s[i + 1] != ".")
            if ch == ".":
                out.append("o" if live == 1 else ".")
            elif ch == "o":
                out.append("O" if live == 2 else ("." if live == 0 else "o"))
            else:
                out.append("." if live == 2 else ("o" if live == 0 else "O"))
        return "".join(out)

    seen = {cells: 0}
    history = [cells]
    cur = cells
    t = 0
    while t < steps:
        cur = step(cur)
        t += 1
        if cur in seen:
            first = seen[cur]
            period = t - first
            return history[first + (steps - first) % period]
        seen[cur] = t
        history.append(cur)
    return cur
'''

ITEMS.append({
    "id": "C15",
    "kind": "simulation",
    "difficulty": "very hard",
    "entry_point": "grow_moss",
    "prompt": r"""Write a Python function `grow_moss(cells: str, steps: int) -> str` that simulates moss growing on a row of stones.

`cells` is a string in which each character is one stone: `.` bare, `o` sprout, `O` mature. Any other character raises `ValueError`. The row does NOT wrap around: positions beyond either end count as bare. The empty string is valid and stays empty.

In one step every stone changes simultaneously, based only on the row as it was before the step. For a stone, let `live` be how many of its two neighbours (left and right) are `o` or `O` - so `live` is 0, 1 or 2.

- `.` becomes `o` if `live == 1`; otherwise it stays `.`.
- `o` becomes `O` if `live == 2`; becomes `.` if `live == 0`; stays `o` if `live == 1`.
- `O` becomes `.` if `live == 2`; becomes `o` if `live == 0`; stays `O` if `live == 1`.

Return the row after exactly `steps` steps (`steps >= 0`). `steps` can be huge (10**15 and beyond) while `cells` has at most 12 stones, so simulating every single step is not feasible - the function must still return quickly.

Example: starting from `"..o.."` the row is `".o.o."` after 1 step, `"o...o"` after 2 steps, `".o.o."` after 3 steps, and keeps alternating; so `grow_moss("..o..", 1)` returns `".o.o."` and `grow_moss("..o..", 10**15)` returns `"o...o"`.""" + _TAIL,
    "reference": _REF_C15,
    "tests": _RAISES + r'''
assert grow_moss("", 5) == "" and grow_moss("..o..", 0) == "..o.."
assert grow_moss("..o..", 1) == ".o.o." and grow_moss("..o..", 2) == "o...o" and grow_moss("..o..", 3) == ".o.o."
assert grow_moss("..o..", 10 ** 15) == "o...o" and grow_moss("..o..", 10 ** 15 + 1) == ".o.o."
assert grow_moss("o....", 1) == ".o..." and grow_moss("....o", 1) == "...o."
assert grow_moss("ooo", 1) == "oOo" and grow_moss("ooo", 2) == "o.o" and grow_moss("ooo", 3) == "..."
assert grow_moss("O", 1) == "o" and grow_moss("O", 2) == "." and grow_moss("O", 10 ** 12) == "."
assert grow_moss("OOO", 1) == "O.O" and grow_moss("OOO", 2) == "o.o"
assert grow_moss("oO", 1) == "oO" and grow_moss("oO", 10 ** 15) == "oO"
assert grow_moss(".oO.", 1) == "ooOo" and grow_moss(".oO.", 2) == "oO.o"
assert grow_moss("o.O.o.O", 4) == ".o...o."
assert grow_moss("oO.o.O..oO", 7) == ".ooOoo.ooo"
assert grow_moss("oO.o.O..oO", 10 ** 15) == "o.o..ooO.o"
assert grow_moss("..o...O...o.", 10 ** 15 + 7) == "ooO..OO..Ooo"
assert _raises(grow_moss, "o.x", 1) and _raises(grow_moss, "o.0", 0)
''',
    "wrong": _mut(_REF_C15, 'int(i > 0 and s[i - 1] != ".") + int(i + 1 < n and s[i + 1] != ".")',
                  'int(s[i - 1] != ".") + int(s[(i + 1) % n] != ".")'),
})


# ---------------------------------------------------------------------------
# Kind 4: string transformation with layered rules (C16-C20)
# ---------------------------------------------------------------------------

_REF_C16 = r'''
def dock_title(name):
    small = {"a", "an", "and", "of", "the", "in", "on", "to"}
    words = name.split()
    out = []
    for wi, word in enumerate(words):
        parts = word.split("-")
        done = []
        for pi, part in enumerate(parts):
            edge = (wi == 0 and pi == 0) or (wi == len(words) - 1 and pi == len(parts) - 1)
            if any(ch in "0123456789" for ch in part):
                done.append(part.upper())
            elif len(part) in (2, 3) and all("A" <= ch <= "Z" for ch in part):
                done.append(part)
            elif part.lower() in small and not edge:
                done.append(part.lower())
            else:
                done.append(part[:1].upper() + part[1:].lower())
        out.append("-".join(done))
    return " ".join(out)
'''

ITEMS.append({
    "id": "C16",
    "kind": "string",
    "difficulty": "hard",
    "entry_point": "dock_title",
    "prompt": r"""Write a Python function `dock_title(name: str) -> str` that puts a ship name into the harbour register's house style. Names consist of ASCII letters, digits, hyphens and whitespace.

1. Split the name into words on runs of whitespace (leading/trailing whitespace is ignored). The result is the transformed words joined by single spaces; a name with no words gives `""`.
2. Split every word into parts on `-`. Each part is transformed on its own and the parts are joined with `-` again (an empty part, as in `a--b`, stays empty).
3. Each part is transformed by the FIRST rule below that applies:
   a. Code: the part contains at least one digit -> the whole part in upper case (`mk2` -> `MK2`).
   b. Acronym: the part is 2 or 3 characters long and consists only of uppercase letters A-Z in the input -> unchanged (`USS` stays `USS`, and so does `OF`).
   c. Small word: the part, compared case-insensitively, is one of `a`, `an`, `and`, `of`, `the`, `in`, `on`, `to`, AND it is neither the first part of the first word nor the last part of the last word -> all lower case.
   d. Otherwise: first character upper case, all remaining characters lower case (`qUEEN` -> `Queen`, `ODIN` -> `Odin`).

Note that a small word in the very first position (first part of first word) or the very last position (last part of last word) falls through to rule d and is capitalised, unless rule a or b caught it earlier.

Examples:
- `dock_title("the  queen of the-sea")` returns `"The Queen of the-Sea"`.
- `dock_title("USS mk2-alpha TO")` returns `"USS MK2-Alpha TO"`.""" + _TAIL,
    "reference": _REF_C16,
    "tests": r'''
assert dock_title("") == "" and dock_title("   ") == ""
assert dock_title("the  queen of the-sea") == "The Queen of the-Sea"
assert dock_title("USS mk2-alpha TO") == "USS MK2-Alpha TO"
assert dock_title("a tale of a") == "A Tale of A"
assert dock_title("in-and-out") == "In-and-Out"
assert dock_title("queen AND country") == "Queen AND Country"
assert dock_title("the") == "The" and dock_title("THE") == "THE" and dock_title("tHe") == "The"
assert dock_title("ODIN rises") == "Odin Rises"
assert dock_title("x9 on the b2b") == "X9 on the B2B"
assert dock_title("to-the end-on") == "To-the End-On"
assert dock_title("north--star") == "North--Star"
assert dock_title("ab CD eFg hIJK") == "Ab CD Efg Hijk"
assert dock_title("\tisle  OF  man\n") == "Isle OF Man" and dock_title("isle Of man") == "Isle of Man"
assert dock_title("pride of-the To an-isle") == "Pride of-the to an-Isle"
assert dock_title("on a-7 AN") == "On a-7 AN"
''',
    "wrong": _mut(_REF_C16, "edge = (wi == 0 and pi == 0) or (wi == len(words) - 1 and pi == len(parts) - 1)",
                  "edge = wi == 0 or wi == len(words) - 1"),
})


_REF_C17 = r'''
import re

def mask_account_numbers(text):
    def fix(m):
        run = m.group(0)
        total = sum(1 for ch in run if ch in "0123456789")
        if total < 8:
            return run
        keep_from = total - 4
        out = []
        seen = 0
        for ch in run:
            if ch in "0123456789":
                seen += 1
                out.append("*" if seen <= keep_from else ch)
            else:
                out.append(ch)
        return "".join(out)

    return re.sub(r"[0-9](?:[ -]?[0-9])*", fix, text)
'''

ITEMS.append({
    "id": "C17",
    "kind": "string",
    "difficulty": "hard",
    "entry_point": "mask_account_numbers",
    "prompt": r"""Write a Python function `mask_account_numbers(text: str) -> str` that hides long numbers in a text.

Definitions (digits are the ASCII characters 0-9; a separator is a single space `" "` or a single hyphen `-`):
- Two digits are "linked" if they are directly adjacent, or if exactly ONE separator character stands between them.
- A digit run is a maximal substring that starts with a digit, ends with a digit, and in which each digit is linked to the next digit. So `1234 5678` is one run of 8 digits, `12-34 56` is one run of 6 digits, but `1234  5678` (two spaces), `1234 -5678` and `1234- 5678` are each two separate runs of 4 digits. A newline or any other character also ends a run.

Rule: in every digit run that contains 8 or more digits, replace every digit except the LAST FOUR digits of the run with `*`. Separators inside the run are kept as they are. Runs with fewer than 8 digits, and all other text, are left unchanged.

Examples:
- `mask_account_numbers("Card 4111 1111-1111 1111 exp 12/27")` returns `"Card **** ****-**** 1111 exp 12/27"`.
- `mask_account_numbers("tel 555-0199, id 1234  5678")` returns the text unchanged.""" + _TAIL,
    "reference": _REF_C17,
    "tests": r'''
assert mask_account_numbers("") == ""
assert mask_account_numbers("Card 4111 1111-1111 1111 exp 12/27") == "Card **** ****-**** 1111 exp 12/27"
assert mask_account_numbers("tel 555-0199, id 1234  5678") == "tel 555-0199, id 1234  5678"
assert mask_account_numbers("12345678") == "****5678" and mask_account_numbers("1234567") == "1234567"
assert mask_account_numbers("1-2-3-4-5-6-7-8-9") == "*-*-*-*-*-6-7-8-9"
assert mask_account_numbers("a12345678b87654321") == "a****5678b****4321"
assert mask_account_numbers("1234 5678 ") == "**** 5678 " and mask_account_numbers(" -1234 5678- ") == " -**** 5678- "
assert mask_account_numbers("1234 -5678") == "1234 -5678" and mask_account_numbers("1234- 5678") == "1234- 5678"
assert mask_account_numbers("0000000000001") == "*********0001"
assert mask_account_numbers("x 12 34 56 78 9 y") == "x ** ** *6 78 9 y"
assert mask_account_numbers("99-1234567") == "**-***4567"
assert mask_account_numbers("12345678\n12345678") == "****5678\n****5678" and mask_account_numbers("1234\n5678") == "1234\n5678"
assert mask_account_numbers("1234--5678 and 1234.5678") == "1234--5678 and 1234.5678"
assert mask_account_numbers("ref 12345678, 1234 567, 123456789012") == "ref ****5678, 1234 567, ********9012"
''',
    "wrong": _mut(_REF_C17, r"[0-9](?:[ -]?[0-9])*", r"[0-9](?:[ -]*[0-9])*"),
})


_REF_C18 = r'''
def wrap_note(text, width):
    if width < 2:
        raise ValueError("width must be at least 2")
    lines = []
    for paragraph in text.split("\n"):
        words = [w for w in paragraph.split(" ") if w]
        if not words:
            lines.append("")
            continue
        line = ""
        for word in words:
            if len(word) <= width:
                if not line:
                    line = word
                elif len(line) + 1 + len(word) <= width:
                    line += " " + word
                else:
                    lines.append(line)
                    line = word
            else:
                if line:
                    lines.append(line)
                piece = word
                while len(piece) > width:
                    lines.append(piece[:width - 1] + "-")
                    piece = piece[width - 1:]
                line = piece
        if line:
            lines.append(line)
    return lines
'''

ITEMS.append({
    "id": "C18",
    "kind": "string",
    "difficulty": "hard",
    "entry_point": "wrap_note",
    "prompt": r"""Write a Python function `wrap_note(text: str, width: int) -> list[str]` that word-wraps a note for a narrow display and returns the list of output lines. No output line may be longer than `width`.

- If `width < 2`, raise `ValueError`.
- Split `text` on `"\n"` into paragraphs. Each paragraph is wrapped independently and the resulting lines are concatenated in order.
- The words of a paragraph are its maximal runs of non-space characters (the only separator is the space character `" "`; any number of spaces between, before or after words is ignored). A paragraph with no words (empty or only spaces) produces exactly one empty line `""`.

Wrapping a paragraph: keep a current line, initially empty. For each word in order:
- If the word fits within `width` (`len(word) <= width`):
  - if the current line is empty, the word becomes the current line;
  - otherwise, if `len(current) + 1 + len(word) <= width`, append a space and the word to the current line;
  - otherwise output the current line, and the word becomes the new current line.
- If the word is longer than `width`:
  - first output the current line if it is not empty (a too-long word always starts on a fresh line);
  - then, while the remaining piece of the word is longer than `width`: output its first `width - 1` characters followed by `-`, and remove those `width - 1` characters from the piece;
  - the piece that is left (its length is at most `width`) becomes the current line, and following words may be appended to it by the normal rule.

At the end of the paragraph, output the current line if it is not empty.

Examples:
- `wrap_note("the quick brown fox", 9)` returns `["the quick", "brown fox"]`.
- `wrap_note("an extraordinarily big", 6)` returns `["an", "extra-", "ordin-", "arily", "big"]`.""" + _TAIL,
    "reference": _REF_C18,
    "tests": _RAISES + r'''
assert wrap_note("", 5) == [""] and wrap_note("   ", 5) == [""]
assert wrap_note("a\n\nb", 5) == ["a", "", "b"] and wrap_note("x\n", 4) == ["x", ""]
assert wrap_note("the quick brown fox", 9) == ["the quick", "brown fox"]
assert wrap_note("an extraordinarily big", 6) == ["an", "extra-", "ordin-", "arily", "big"]
assert wrap_note("ab cd", 5) == ["ab cd"] and wrap_note("ab cde", 5) == ["ab", "cde"]
assert wrap_note("abcde f", 5) == ["abcde", "f"]
assert wrap_note("abcdefg hi", 5) == ["abcd-", "efg", "hi"]
assert wrap_note("abcdefg hi", 6) == ["abcde-", "fg hi"]
assert wrap_note("abc", 2) == ["a-", "bc"] and wrap_note("abcd", 2) == ["a-", "b-", "cd"]
assert wrap_note("abcdefghi", 5) == ["abcd-", "efghi"]
assert wrap_note("  a   b  ", 3) == ["a b"]
assert wrap_note("hi abcdefg\nabcdefg hi there", 4) == ["hi", "abc-", "defg", "abc-", "defg", "hi", "the-", "re"]
assert wrap_note("one two three four five", 100) == ["one two three four five"]
assert _raises(wrap_note, "abc", 1) and _raises(wrap_note, "", 0)
''',
    "wrong": _mut(_REF_C18, "                line = piece\n", "                lines.append(piece)\n                line = \"\"\n"),
})


_REF_C19 = r'''
import re

def make_handle(raw, taken):
    s = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    if not s:
        s = "anon"
    if s[0] in "0123456789":
        s = "u_" + s
    if len(s) > 12:
        s = s[:12].rstrip("_")
    if s not in taken:
        return s
    k = 2
    while True:
        suffix = str(k)
        candidate = s[:12 - len(suffix)].rstrip("_") + suffix
        if candidate not in taken:
            return candidate
        k += 1
'''

ITEMS.append({
    "id": "C19",
    "kind": "string",
    "difficulty": "medium",
    "entry_point": "make_handle",
    "prompt": r"""Write a Python function `make_handle(raw: str, taken: list[str]) -> str` that turns a display name into a user handle. `raw` contains only ASCII characters. Apply these steps in exactly this order:

1. Convert to lower case.
2. Replace every maximal run of characters that are not `a`-`z` or `0`-`9` with a single underscore `_`.
3. Remove leading and trailing underscores.
4. If the result is empty, use `anon`.
5. If it starts with a digit, put `u_` in front.
6. If it is longer than 12 characters, keep only the first 12 and then remove trailing underscores again.
7. Call the result `base`. If `base` is not in `taken` (exact, case-sensitive comparison), return it.
8. Otherwise try k = 2, 3, 4, ... in turn. For each k let `suffix = str(k)`; the candidate is the first `12 - len(suffix)` characters of `base` (the whole of `base` if it is shorter), with trailing underscores removed, followed by `suffix`. Return the first candidate that is not in `taken`.

Examples:
- `make_handle("  Mary-Ann  O'Neil ", [])` returns `"mary_ann_o_n"`.
- `make_handle("7 Seas!", ["u_7_seas"])` returns `"u_7_seas2"`.""" + _TAIL,
    "reference": _REF_C19,
    "tests": r'''
assert make_handle("  Mary-Ann  O'Neil ", []) == "mary_ann_o_n"
assert make_handle("7 Seas!", ["u_7_seas"]) == "u_7_seas2"
assert make_handle("", []) == "anon" and make_handle("!!!", ["anon"]) == "anon2"
assert make_handle("?", ["anon", "anon2"]) == "anon3"
assert make_handle("Hello World", []) == "hello_world" and make_handle("__A__b__", []) == "a_b"
assert make_handle("abcdefghijk lmn", []) == "abcdefghijk"
assert make_handle("1234567890123", []) == "u_1234567890"
assert make_handle("abcdefghijkl", ["abcdefghijkl"]) == "abcdefghijk2"
assert make_handle("abcdefghijkl", ["abcdefghijkl"] + ["abcdefghijk%d" % k for k in range(2, 10)]) == "abcdefghij10"
assert make_handle("abcdefghij k", ["abcdefghij_k"]) == "abcdefghij2"
assert make_handle("Bob", ["Bob"]) == "bob" and make_handle("Bob", ["bob"]) == "bob2"
assert make_handle("bob", ["bob", "bob2", "bob4"]) == "bob3"
assert make_handle("9", []) == "u_9" and make_handle("a.b.c", ["a_b_c"]) == "a_b_c2"
assert make_handle("abcdefghi  9z", ["abcdefghi_9z"]) == "abcdefghi_92"
''',
    "wrong": _mut(_REF_C19, 's = s[:12].rstrip("_")', "s = s[:12]"),
})


_REF_C20 = r'''
def fill_template(template, values):
    out = []
    i = 0
    n = len(template)
    while i < n:
        ch = template[i]
        if ch == "{":
            if i + 1 < n and template[i + 1] == "{":
                out.append("{")
                i += 2
                continue
            j = template.find("}", i + 1)
            if j < 0:
                raise ValueError("unclosed field")
            body = template[i + 1:j]
            if "{" in body:
                raise ValueError("brace inside field")
            pieces = body.split("|")
            name = pieces[0]
            if name == "":
                raise ValueError("empty name")
            ops = []
            for f in pieces[1:]:
                if f in ("upper", "lower", "rev"):
                    ops.append((f, 0))
                    continue
                head, sep, num = f.partition(":")
                if head not in ("pad", "cut") or not sep or not num or any(c not in "0123456789" for c in num):
                    raise ValueError("bad filter: " + f)
                ops.append((head, int(num)))
            if name in values:
                s = str(values[name])
                for op, k in ops:
                    if op == "upper":
                        s = s.upper()
                    elif op == "lower":
                        s = s.lower()
                    elif op == "rev":
                        s = s[::-1]
                    elif op == "pad":
                        s = s + "." * (k - len(s))
                    else:
                        s = s[:k]
            else:
                s = "<" + name + "?>"
            out.append(s)
            i = j + 1
        elif ch == "}":
            if i + 1 < n and template[i + 1] == "}":
                out.append("}")
                i += 2
            else:
                raise ValueError("stray closing brace")
        else:
            out.append(ch)
            i += 1
    return "".join(out)
'''

ITEMS.append({
    "id": "C20",
    "kind": "string",
    "difficulty": "very hard",
    "entry_point": "fill_template",
    "prompt": r"""Write a Python function `fill_template(template: str, values: dict) -> str` that expands a small template language. Scan the template from left to right:

- `{{` (two opening braces in a row) produces a literal `{`.
- Otherwise a `{` starts a field. The field's content runs up to (not including) the NEXT `}` character, and that `}` ends the field. If there is no `}` after it, raise `ValueError`. If the content contains a `{`, raise `ValueError`.
- Outside a field, `}}` produces a literal `}`; a `}` that is not followed by another `}` raises `ValueError`.
- Every other character is copied unchanged.

Because scanning is strictly left to right, `"{{{a}}}"` is a literal `{`, then the field `{a}`, then a literal `}`; and `"{a}}}"` is the field `{a}` followed by a literal `}`.

Field content: split it on `|`. The first piece is the NAME, used exactly as written (no whitespace stripping); an empty name raises `ValueError`. Every further piece is a filter:
- `upper` - convert to upper case
- `lower` - convert to lower case
- `rev` - reverse the string
- `pad:N` - if the string is shorter than N characters, append `.` characters until its length is N
- `cut:N` - keep only the first N characters
N is written with digits only (a non-negative integer). Anything else in a filter position (unknown name, missing or malformed N, an empty piece, an argument on a filter that takes none) raises `ValueError`.

Value of a field:
- If NAME is a key of `values`: start with `str(values[NAME])` and apply the filters from left to right.
- If NAME is not a key of `values`: the field becomes `<NAME?>` (with the actual name), and the filters are NOT applied - but they are still checked, so an invalid filter raises `ValueError` here too.

Examples:
- `fill_template("Hi {name|upper}, {{ok}} {n|pad:4}!", {"name": "ada", "n": 7})` returns `"Hi ADA, {ok} 7...!"`.
- `fill_template("{who|rev} / {x|cut:2}", {"x": "abcdef"})` returns `"<who?> / ab"`.""" + _TAIL,
    "reference": _REF_C20,
    "tests": _RAISES + r'''
assert fill_template("", {}) == "" and fill_template("plain text", {"plain": 1}) == "plain text"
assert fill_template("Hi {name|upper}, {{ok}} {n|pad:4}!", {"name": "ada", "n": 7}) == "Hi ADA, {ok} 7...!"
assert fill_template("{who|rev} / {x|cut:2}", {"x": "abcdef"}) == "<who?> / ab"
assert fill_template("{{{a}}}", {"a": 1}) == "{1}" and fill_template("{a}}}", {"a": "z"}) == "z}"
assert fill_template("}}{{", {}) == "}{"
assert fill_template("{a|pad:3|rev|upper}", {"a": "xy"}) == ".YX"
assert fill_template("[{a|cut:0}][{a|pad:0}][{a|cut:9|lower}]", {"a": "Q"}) == "[][Q][q]"
assert fill_template("{a|upper}-{b}", {"a": None, "b": 3.5}) == "NONE-3.5"
assert fill_template("{ a }{a}", {" a ": 1}) == "1<a?>"
assert fill_template("{a|rev|pad:5|rev}", {"a": "abc"}) == "..abc"
assert _raises(fill_template, "{a", {"a": 1}) and _raises(fill_template, "a}", {"a": 1}) and _raises(fill_template, "{a}}", {"a": 1})
assert _raises(fill_template, "{a|shout}", {"a": 1}) and _raises(fill_template, "{b|nope}", {}) and _raises(fill_template, "{a|}", {"a": 1})
assert _raises(fill_template, "{|upper}", {"": 1}) and _raises(fill_template, "{}", {})
assert _raises(fill_template, "{a|pad:x}", {"a": 1}) and _raises(fill_template, "{a|pad}", {"a": 1}) and _raises(fill_template, "{a|cut:-1}", {"a": 1}) and _raises(fill_template, "{a|upper:3}", {"a": 1})
assert _raises(fill_template, "{a{b}}", {"a": 1, "b": 2}) and _raises(fill_template, "{b|pad:}", {})
''',
    "wrong": _mut(_REF_C20, "            ops = []\n            for f in pieces[1:]:", "            ops = []\n            for f in (pieces[1:] if name in values else []):"),
})

# ---------------------------------------------------------------------------
# Kind 5: aggregation / grouping / ranking with specified tie-breaks (C21-C25)
# ---------------------------------------------------------------------------

_REF_C21 = r'''
def league_table(matches):
    stats = {}
    for home, hg, away, ag in matches:
        if home == away:
            raise ValueError("team plays itself")
        for team in (home, away):
            stats.setdefault(team, [0, 0, 0])
        stats[home][1] += hg - ag
        stats[home][2] += hg
        stats[away][1] += ag - hg
        stats[away][2] += ag
        if hg > ag:
            stats[home][0] += 3
        elif hg < ag:
            stats[away][0] += 3
        else:
            stats[home][0] += 1
            stats[away][0] += 1
    order = sorted(stats, key=lambda t: (-stats[t][0], -stats[t][1], -stats[t][2], t))
    table = []
    for team in order:
        key = tuple(stats[team])
        rank = 1 + sum(1 for other in order if tuple(stats[other]) > key)
        table.append((rank, team, key[0], key[1], key[2]))
    return table
'''

ITEMS.append({
    "id": "C21",
    "kind": "aggregation",
    "difficulty": "medium",
    "entry_point": "league_table",
    "prompt": r"""Write a Python function `league_table(matches: list[tuple[str, int, str, int]]) -> list[tuple[int, str, int, int, int]]` that builds a league table.

Each match is `(home_team, home_goals, away_team, away_goals)`. A win gives 3 points, a draw 1 point each, a loss 0. If a match has the same team on both sides, raise `ValueError`.

For every team that appears in at least one match compute:
- `points`;
- `goal_diff` = goals scored minus goals conceded;
- `goals_for` = goals scored.

Order the teams by points (higher first), then goal_diff (higher first), then goals_for (higher first), then team name (ascending).

Rank: teams that are equal on all three of points, goal_diff and goals_for share the same rank. A team's rank is 1 + the number of teams that are strictly ahead of it on those three criteria (so ranks can go 1, 2, 2, 4).

Return a list of tuples `(rank, team, points, goal_diff, goals_for)` in table order. No matches -> `[]`.

Example: `league_table([("ash", 2, "birch", 0), ("cedar", 1, "dale", 1), ("ash", 0, "cedar", 0), ("birch", 3, "dale", 1)])` returns
`[(1, "ash", 4, 2, 2), (2, "birch", 3, 0, 3), (3, "cedar", 2, 0, 1), (4, "dale", 1, -2, 2)]`.""" + _TAIL,
    "reference": _REF_C21,
    "tests": _RAISES + r'''
assert league_table([]) == []
assert league_table([("ash", 2, "birch", 0), ("cedar", 1, "dale", 1), ("ash", 0, "cedar", 0), ("birch", 3, "dale", 1)]) == [(1, "ash", 4, 2, 2), (2, "birch", 3, 0, 3), (3, "cedar", 2, 0, 1), (4, "dale", 1, -2, 2)]
assert league_table([("x", 1, "y", 1), ("z", 1, "w", 1)]) == [(1, "w", 1, 0, 1), (1, "x", 1, 0, 1), (1, "y", 1, 0, 1), (1, "z", 1, 0, 1)]
assert league_table([("a", 1, "z", 0), ("c", 2, "d", 2)]) == [(1, "a", 3, 1, 1), (2, "c", 1, 0, 2), (2, "d", 1, 0, 2), (4, "z", 0, -1, 0)]
assert league_table([("p", 3, "q", 0), ("r", 1, "s", 0)]) == [(1, "p", 3, 3, 3), (2, "r", 3, 1, 1), (3, "s", 0, -1, 0), (4, "q", 0, -3, 0)]
assert league_table([("m", 2, "n", 2), ("o", 0, "k", 0)]) == [(1, "m", 1, 0, 2), (1, "n", 1, 0, 2), (3, "k", 1, 0, 0), (3, "o", 1, 0, 0)]
assert league_table([("u", 0, "v", 5)]) == [(1, "v", 3, 5, 5), (2, "u", 0, -5, 0)]
assert league_table([("u", 1, "v", 0), ("v", 1, "u", 0)]) == [(1, "u", 3, 0, 1), (1, "v", 3, 0, 1)]
assert league_table([("a", 1, "b", 0), ("b", 1, "c", 0), ("c", 1, "a", 0), ("d", 0, "e", 0)]) == [(1, "a", 3, 0, 1), (1, "b", 3, 0, 1), (1, "c", 3, 0, 1), (4, "d", 1, 0, 0), (4, "e", 1, 0, 0)]
assert league_table([("a", 4, "b", 4), ("a", 0, "c", 1), ("b", 2, "c", 2)]) == [(1, "c", 4, 1, 3), (2, "b", 2, 0, 6), (3, "a", 1, -1, 4)]
assert _raises(league_table, [("a", 1, "b", 0), ("c", 1, "c", 1)])
''',
    "wrong": _mut(_REF_C21, "rank = 1 + sum(1 for other in order if tuple(stats[other]) > key)",
                  "rank = 1 + len({tuple(stats[other]) for other in order if tuple(stats[other]) > key})"),
})


_REF_C22 = r'''
def top_spenders(events, k):
    order = sorted(range(len(events)), key=lambda i: (events[i]["ts"], i))
    orders = {}
    first_buy = {}
    for i in order:
        e = events[i]
        oid = e["order"]
        if e["type"] == "buy":
            if oid in orders:
                continue
            orders[oid] = [e["customer"], e["cents"], False]
            first_buy.setdefault(e["customer"], e["ts"])
        elif oid in orders and not orders[oid][2]:
            if e["type"] == "refund":
                orders[oid][1] = max(0, orders[oid][1] - e["cents"])
            elif e["type"] == "cancel":
                orders[oid][1] = 0
                orders[oid][2] = True
    totals = {}
    for customer, amount, _ in orders.values():
        totals[customer] = totals.get(customer, 0) + amount
    rows = [(c, t) for c, t in totals.items() if t > 0]
    rows.sort(key=lambda r: (-r[1], first_buy[r[0]], r[0]))
    return rows[:k]
'''

ITEMS.append({
    "id": "C22",
    "kind": "aggregation",
    "difficulty": "hard",
    "entry_point": "top_spenders",
    "prompt": r"""Write a Python function `top_spenders(events: list[dict], k: int) -> list[tuple[str, int]]` that ranks customers by money spent, from a log of shop events.

Each event is a dict with keys:
- `"ts"`: integer timestamp;
- `"type"`: `"buy"`, `"refund"` or `"cancel"`;
- `"order"`: order id (str);
- `"customer"`: customer name (str) - present on `"buy"` events only;
- `"cents"`: positive integer amount - present on `"buy"` and `"refund"` events only.

The list is NOT necessarily in time order. Process the events in ascending `ts`; events with equal `ts` are processed in the order they appear in the list.

- `buy`: if this order id has not been seen in an earlier buy, it creates the order for that customer with that amount. A buy whose order id already exists is ignored completely (even if that order was cancelled).
- `refund`: reduces the order's amount by `cents`, but never below 0. Ignored if the order does not exist (yet) or has been cancelled.
- `cancel`: sets the order's amount to 0 and marks it cancelled for good. Ignored if the order does not exist (yet).

A customer's total is the sum of the current amounts of their orders. Customers whose total is 0 are left out.

Ranking: total descending; ties by the timestamp of the customer's earliest accepted buy event, ascending (it counts even if that order was later refunded or cancelled); remaining ties by customer name ascending.

Return the first `k` entries of the ranking as `(customer, total_cents)` tuples (`k >= 0`; if `k` exceeds the number of ranked customers, return them all).

Example: with events
`[{"ts": 1, "type": "buy", "order": "o1", "customer": "ann", "cents": 500}, {"ts": 3, "type": "refund", "order": "o1", "cents": 800}, {"ts": 2, "type": "buy", "order": "o2", "customer": "bob", "cents": 100}, {"ts": 4, "type": "buy", "order": "o3", "customer": "ann", "cents": 100}]`
and `k = 5` the result is `[("ann", 100), ("bob", 100)]` (ann's first order was refunded down to 0; the tie at 100 is won by ann, whose first buy was earlier).""" + _TAIL,
    "reference": _REF_C22,
    "tests": r'''
def _b(ts, order, customer, cents):
    return {"ts": ts, "type": "buy", "order": order, "customer": customer, "cents": cents}
def _r(ts, order, cents):
    return {"ts": ts, "type": "refund", "order": order, "cents": cents}
def _c(ts, order):
    return {"ts": ts, "type": "cancel", "order": order}
_E = [_b(1, "o1", "ann", 500), _b(2, "o2", "bob", 700), _b(3, "o3", "ann", 300)]
assert top_spenders([], 3) == []
assert top_spenders(_E, 5) == [("ann", 800), ("bob", 700)]
assert top_spenders(_E, 1) == [("ann", 800)] and top_spenders(_E, 0) == []
assert top_spenders([_b(1, "o1", "ann", 500), _r(3, "o1", 800), _b(2, "o2", "bob", 100), _b(4, "o3", "ann", 100)], 5) == [("ann", 100), ("bob", 100)]
assert top_spenders([_r(1, "o1", 50), _b(2, "o1", "cy", 80)], 5) == [("cy", 80)]
assert top_spenders([_b(5, "o1", "cy", 80), _r(9, "o1", 30), _r(1, "o1", 30)], 5) == [("cy", 50)]
assert top_spenders([_b(1, "o1", "dee", 100), _c(2, "o1"), _r(3, "o1", 10), _b(4, "o2", "eve", 10)], 5) == [("eve", 10)]
assert top_spenders([_b(1, "o1", "ann", 100), _b(2, "o1", "bob", 999)], 5) == [("ann", 100)]
assert top_spenders([_b(1, "o1", "ann", 100), _c(2, "o1"), _b(3, "o1", "ann", 100)], 5) == []
assert top_spenders([_b(1, "o1", "zed", 100), _b(1, "o2", "amy", 100)], 5) == [("amy", 100), ("zed", 100)]
assert top_spenders([_b(5, "o1", "ann", 100), _c(5, "o1")], 5) == [] and top_spenders([_c(5, "o1"), _b(5, "o1", "ann", 100)], 5) == [("ann", 100)]
assert top_spenders([_b(1, "o1", "bob", 50), _c(2, "o1"), _b(10, "o2", "bob", 70), _b(5, "o3", "ann", 70)], 5) == [("bob", 70), ("ann", 70)]
assert top_spenders([_b(9, "o9", "ann", 40), _b(1, "o1", "bob", 100), _r(2, "o1", 30), _r(3, "o1", 30), _b(4, "o4", "cy", 41)], 2) == [("cy", 41), ("bob", 40)]
''',
    "wrong": _mut(_REF_C22, 'orders[oid][1] = max(0, orders[oid][1] - e["cents"])', 'orders[oid][1] = orders[oid][1] - e["cents"]'),
})


_REF_C23 = r'''
def curve_grades(scores):
    present = [v for v in scores.values() if v is not None]
    n = len(present)
    a_max = (2 * n + 9) // 10
    b_max = (5 * n + 9) // 10
    c_max = (8 * n + 9) // 10
    grades = {}
    for name, value in scores.items():
        if value is None:
            grades[name] = "X"
            continue
        rank = 1 + sum(1 for other in present if other > value)
        if rank <= a_max:
            grades[name] = "A"
        elif rank <= b_max:
            grades[name] = "B"
        elif rank <= c_max:
            grades[name] = "C"
        else:
            grades[name] = "D"
    return grades
'''

ITEMS.append({
    "id": "C23",
    "kind": "aggregation",
    "difficulty": "medium",
    "entry_point": "curve_grades",
    "prompt": r"""Write a Python function `curve_grades(scores: dict) -> dict` that grades an exam "on the curve".

`scores` maps a student name (str) to an integer score, or to `None` if the student was absent. Return a dict mapping every name to a one-letter grade.

- Absent students get `"X"` and are ignored for everything else.
- Let `n` be the number of present students. The rank of a present student is 1 + the number of present students with a strictly higher score (students with equal scores share a rank).
- Grade by rank:
  - `"A"` if rank <= ceil(0.2 * n);
  - otherwise `"B"` if rank <= ceil(0.5 * n);
  - otherwise `"C"` if rank <= ceil(0.8 * n);
  - otherwise `"D"`.
  Here ceil is the mathematical ceiling of the exact value (e.g. for n = 15 the three limits are exactly 3, 8 and 12). Compute the limits with integer arithmetic so that floating-point rounding cannot shift them.

An empty dict returns `{}`.

Example: `curve_grades({"ana": 90, "ben": 80, "cat": 80, "dov": 70, "eli": 60, "fay": None})` returns `{"ana": "A", "ben": "B", "cat": "B", "dov": "C", "eli": "D", "fay": "X"}` (n = 5, limits 1, 3, 4; ranks 1, 2, 2, 4, 5).""" + _TAIL,
    "reference": _REF_C23,
    "tests": r'''
assert curve_grades({}) == {}
assert curve_grades({"ana": 90, "ben": 80, "cat": 80, "dov": 70, "eli": 60, "fay": None}) == {"ana": "A", "ben": "B", "cat": "B", "dov": "C", "eli": "D", "fay": "X"}
assert curve_grades({"a": None, "b": None}) == {"a": "X", "b": "X"}
assert curve_grades({"solo": 0}) == {"solo": "A"}
assert curve_grades({"a": 5, "b": 5, "c": 5, "d": 5}) == {"a": "A", "b": "A", "c": "A", "d": "A"}
assert curve_grades({"hi": 2, "lo": 1}) == {"hi": "A", "lo": "C"}
_g15 = curve_grades(dict(("s%02d" % i, 100 - i) for i in range(15)))
assert [_g15["s%02d" % i] for i in range(15)] == list("AAABBBBBCCCCDDD")
_g35 = curve_grades(dict(("s%02d" % i, 100 - i) for i in range(35)))
assert "".join(_g35["s%02d" % i] for i in range(35)) == "A" * 7 + "B" * 11 + "C" * 10 + "D" * 7
_t = curve_grades(dict(zip("abcdefghij", [9, 9, 9, 5, 5, 5, 5, 5, 1, 1])))
assert "".join(_t[k] for k in "abcdefghij") == "AAABBBBBDD"
_u = curve_grades({"p": 10, "q": None, "r": 10, "s": 3, "t": -4, "u": None})
assert _u == {"p": "A", "q": "X", "r": "A", "s": "C", "t": "C", "u": "X"}
_g10 = curve_grades(dict(("s%d" % i, -i) for i in range(10)))
assert "".join(_g10["s%d" % i] for i in range(10)) == "AABBBCCCDD"
assert curve_grades({"a": 3, "b": 2, "c": 1}) == {"a": "A", "b": "B", "c": "C"}
''',
    "wrong": _mut(_REF_C23, "if other > value)", "if other >= value)"),
})


_REF_C24 = r'''
def session_report(events, gap):
    by_user = {}
    for user, t, action in events:
        by_user.setdefault(user, []).append((t, action))
    rows = []
    for user, evs in by_user.items():
        evs.sort(key=lambda e: e[0])
        count = 0
        longest = 0
        start = prev_t = prev_action = None
        for t, action in evs:
            if start is None or t - prev_t > gap or prev_action == "logout":
                count += 1
                start = t
            longest = max(longest, t - start)
            prev_t, prev_action = t, action
        rows.append((user, count, longest))
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return rows
'''

ITEMS.append({
    "id": "C24",
    "kind": "aggregation",
    "difficulty": "hard",
    "entry_point": "session_report",
    "prompt": r"""Write a Python function `session_report(events: list[tuple[str, int, str]], gap: int) -> list[tuple[str, int, int]]` that groups activity events into sessions.

Each event is `(user, time, action)` with an integer time and an action string such as `"login"`, `"view"`, `"logout"`. The list is in no particular order. `gap` is a non-negative integer.

For each user separately, put that user's events in ascending time order; events with the same time keep their relative order from the input list. Then walk through them:
- The first event starts a session.
- A later event starts a NEW session if (a) its time minus the previous event's time is strictly greater than `gap`, or (b) the previous event's action is exactly `"logout"`. Otherwise it belongs to the current session.
- The length of a session is the time of its last event minus the time of its first event (0 for a single-event session).

Return one tuple `(user, session_count, longest_session_length)` per user, sorted by session_count descending, then longest_session_length descending, then user name ascending. No events -> `[]`.

Example: `session_report([("ann", 0, "login"), ("ann", 20, "view"), ("ann", 25, "logout"), ("ann", 26, "login"), ("bob", 5, "view"), ("ann", 100, "view")], 30)` returns `[("ann", 3, 25), ("bob", 1, 0)]` (ann's sessions are 0..25, then 26 alone because it follows a logout, then 100 alone because 100 - 26 > 30).""" + _TAIL,
    "reference": _REF_C24,
    "tests": r'''
assert session_report([], 10) == []
assert session_report([("ann", 0, "login"), ("ann", 20, "view"), ("ann", 25, "logout"), ("ann", 26, "login"), ("bob", 5, "view"), ("ann", 100, "view")], 30) == [("ann", 3, 25), ("bob", 1, 0)]
assert session_report([("u", 10, "logout"), ("u", 10, "login")], 5) == [("u", 2, 0)]
assert session_report([("u", 10, "login"), ("u", 10, "logout")], 5) == [("u", 1, 0)]
assert session_report([("u", 0, "a"), ("u", 10, "a"), ("u", 20, "a")], 10) == [("u", 1, 20)]
assert session_report([("u", 0, "a"), ("u", 10, "a"), ("u", 21, "a")], 10) == [("u", 2, 10)]
assert session_report([("u", 50, "view"), ("u", 0, "view"), ("u", 40, "view"), ("u", 5, "view")], 9) == [("u", 3, 5)]
assert session_report([("u", 3, "x"), ("u", 3, "x"), ("u", 3, "x")], 0) == [("u", 1, 0)]
assert session_report([("u", 0, "x"), ("u", 1, "x")], 0) == [("u", 2, 0)]
assert session_report([("b", 0, "x"), ("a", 0, "x"), ("c", 0, "x"), ("c", 7, "x")], 10) == [("c", 1, 7), ("a", 1, 0), ("b", 1, 0)]
assert session_report([("a", 0, "x"), ("a", 100, "x"), ("b", 0, "x"), ("b", 9, "x"), ("b", 100, "x"), ("c", 0, "logout"), ("c", 1, "Logout"), ("c", 2, "x")], 10) == [("b", 2, 9), ("c", 2, 1), ("a", 2, 0)]
assert session_report([("u", 0, "login"), ("u", 5, "logout"), ("u", 5, "logout"), ("u", 6, "view"), ("u", 30, "view")], 100) == [("u", 3, 24)]
assert session_report([("u", 9, "view"), ("u", 5, "logout"), ("u", 1, "login")], 100) == [("u", 2, 4)]
''',
    "wrong": _mut(_REF_C24, "evs.sort(key=lambda e: e[0])", "evs.sort()"),
})


_REF_C25 = r'''
def runoff_winner(ballots):
    candidates = {c for ballot in ballots for c in ballot}
    if not candidates:
        raise ValueError("no candidates")
    alive = set(candidates)
    eliminated = []
    first_round = None
    while True:
        tally = {c: 0 for c in alive}
        active = 0
        for ballot in ballots:
            for c in ballot:
                if c in alive:
                    tally[c] += 1
                    active += 1
                    break
        if first_round is None:
            first_round = dict(tally)
        for c in alive:
            if 2 * tally[c] > active:
                return (c, eliminated)
        if len(alive) == 1:
            return (next(iter(alive)), eliminated)
        low = min(tally.values())
        tied = [c for c in alive if tally[c] == low]
        fewest = min(first_round[c] for c in tied)
        loser = max(c for c in tied if first_round[c] == fewest)
        alive.remove(loser)
        eliminated.append(loser)
'''

ITEMS.append({
    "id": "C25",
    "kind": "aggregation",
    "difficulty": "very hard",
    "entry_point": "runoff_winner",
    "prompt": r"""Write a Python function `runoff_winner(ballots: list[list[str]]) -> tuple[str, list[str]]` that runs a ranked-choice election and returns `(winner, eliminated)`, where `eliminated` lists the eliminated candidates in the order they were eliminated.

Each ballot is a list of distinct candidate names in order of preference (most preferred first); a ballot may be empty. The candidates are all names that appear on at least one ballot. If there are no candidates at all, raise `ValueError`.

The count proceeds in rounds. In each round:
1. Every ballot counts as one vote for the first candidate on it who has not been eliminated. A ballot on which every candidate has been eliminated (or which is empty) is "exhausted" and does not count in this round.
2. If some candidate has strictly more than half of the non-exhausted ballots of this round, that candidate wins.
3. Otherwise, if only one candidate is left, that candidate wins.
4. Otherwise one candidate is eliminated, and the next round starts:
   - it is the remaining candidate with the fewest votes in this round (remaining candidates with 0 votes are included);
   - if several are tied for fewest, the one among them who had the fewest votes in ROUND 1 is eliminated;
   - if that is still a tie, the one among those whose name comes LAST alphabetically is eliminated.

Examples:
- `runoff_winner([["a", "b"], ["b", "a"], ["c", "b"], ["b"], ["a", "c"]])` returns `("b", ["c"])`: round 1 is a 2, b 2, c 1 (nobody above 2.5); c is eliminated and its ballot moves to b, giving b 3 of 5.
- `runoff_winner([["x"], ["y"], ["z"]])` returns `("x", ["z", "y"])`.""" + _TAIL,
    "reference": _REF_C25,
    "tests": _RAISES + r'''
assert runoff_winner([["a", "b"], ["b", "a"], ["c", "b"], ["b"], ["a", "c"]]) == ("b", ["c"])
assert runoff_winner([["x"], ["y"], ["z"]]) == ("x", ["z", "y"])
assert runoff_winner([["q"]]) == ("q", [])
assert runoff_winner([[], ["m"]]) == ("m", [])
assert runoff_winner([["a"]] * 3 + [["c", "a"]] * 2 + [["d", "c", "e"]] + [["e"]] * 4) == ("e", ["d", "c", "a"])
assert runoff_winner([["a", "b"], ["a", "c"], ["d"], ["d"]]) == ("a", ["c", "b", "d"])
assert runoff_winner([["a"], ["a"], ["b"], ["c"]]) == ("a", ["c"])
assert runoff_winner([["a", "b"], ["a", "b"], ["b"], ["b"], ["c", "b"]]) == ("b", ["c"])
assert runoff_winner([["k", "z"], ["k", "z"], ["k"]]) == ("k", [])
assert runoff_winner([["a", "c"], ["a", "c"], ["a", "c"], ["b", "c"], ["b", "c"], ["c", "b"], ["c", "b"], ["d", "b"]]) == ("b", ["d", "c"])
assert runoff_winner([["b", "a"], ["a", "b"]]) == ("a", ["b"])
assert runoff_winner([["n1", "w"], ["n2", "w"], ["n3", "w"], ["w"], ["w"]]) == ("w", ["n3"])
assert _raises(runoff_winner, []) and _raises(runoff_winner, [[], []])
''',
    "wrong": _mut(_REF_C25, "loser = max(c for c in tied if first_round[c] == fewest)", "loser = max(tied)"),
})


# ---------------------------------------------------------------------------
# Kind 6: small graph / grid algorithms with a twist (C26-C30)
# ---------------------------------------------------------------------------

_REF_C26 = r'''
from collections import deque

def tide_crossing(grid):
    h, w = len(grid), len(grid[0])

    def dry(r, c, t):
        ch = grid[r][c]
        if ch == "#":
            return False
        if ch in "2345":
            return t % int(ch) != 0
        return True

    seen = {(0, 0, 0)}
    queue = deque([(0, 0, 0)])
    while queue:
        r, c, t = queue.popleft()
        if (r, c) == (h - 1, w - 1):
            return t
        for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and dry(rr, cc, t + 1):
                key = (rr, cc, (t + 1) % 60)
                if key not in seen:
                    seen.add(key)
                    queue.append((rr, cc, t + 1))
    return -1
'''

ITEMS.append({
    "id": "C26",
    "kind": "graph",
    "difficulty": "very hard",
    "entry_point": "tide_crossing",
    "prompt": r"""Write a Python function `tide_crossing(grid: list[str]) -> int` that finds the earliest time at which a walker can cross a tidal flat.

`grid` is a non-empty list of equal-length, non-empty strings. Cells:
- `.` sand: always safe;
- `#` rock: can never be entered;
- a digit `2`, `3`, `4` or `5`: a tidal cell with period k (the digit). It is flooded at every time t that is a multiple of k (t = 0, k, 2k, ...), and safe at all other times.

The walker starts on the top-left cell at time 0 and wants to reach the bottom-right cell. Both of those cells are always `.`. In each time unit the walker either moves to one of the 4 orthogonally adjacent cells or stays where they are; either way the time increases by 1. The walker must never be on a flooded cell: being on a tidal cell with period k at time t (whether arriving at t or having waited there) requires `t % k != 0`.

Return the smallest time at which the walker can be on the bottom-right cell, or -1 if that is impossible. A 1x1 grid returns 0.

Examples:
- `tide_crossing([".32."])` returns 4: wait one time unit on the start, then step right at times 2, 3 and 4 (the `3` cell is entered at time 2, the `2` cell at time 3). Leaving immediately fails because the `2` cell would be entered at time 2.
- `tide_crossing([".22."])` returns -1.""" + _TAIL,
    "reference": _REF_C26,
    "tests": r'''
assert tide_crossing(["."]) == 0
assert tide_crossing([".32."]) == 4
assert tide_crossing([".22."]) == -1
assert tide_crossing([".2."]) == 2 and tide_crossing([".3."]) == 2
assert tide_crossing([".23."]) == 3 and tide_crossing([".42."]) == 4
assert tide_crossing([".#."]) == -1 and tide_crossing([".#", "#."]) == -1
assert tide_crossing(["..", ".."]) == 2
assert tide_crossing([".#.", ".2.", ".#."]) == 5
assert tide_crossing(["..2.", ".#2.", "...."]) == 5
assert tide_crossing([".5555."]) == 5 and tide_crossing([".55555."]) == -1
assert tide_crossing([".2#", "#3.", "##."]) == 4
assert tide_crossing([".4.3.", "##.##", ".5.2."]) == 6
assert tide_crossing([".2345.", "#####.", ".5432."]) == 7
assert tide_crossing([".3", "2."]) == 2 and tide_crossing([".2", "2."]) == 2 and tide_crossing([".", "2", "3", "."]) == 3
''',
    "wrong": _mut(_REF_C26, "key = (rr, cc, (t + 1) % 60)", "key = (rr, cc)"),
})


_REF_C27 = r'''
def plan_rounds(deps, capacity):
    if capacity < 1:
        raise ValueError("capacity must be positive")
    dependents = {task: 0 for task in deps}
    for task, prereqs in deps.items():
        for p in prereqs:
            if p not in deps:
                raise ValueError("unknown prerequisite: %r" % (p,))
            dependents[p] += 1
    done = set()
    rounds = []
    while len(done) < len(deps):
        ready = [t for t in deps if t not in done and all(p in done for p in deps[t])]
        if not ready:
            raise ValueError("cycle")
        ready.sort(key=lambda t: (-dependents[t], t))
        chosen = ready[:capacity]
        rounds.append(chosen)
        done.update(chosen)
    return rounds
'''

ITEMS.append({
    "id": "C27",
    "kind": "graph",
    "difficulty": "hard",
    "entry_point": "plan_rounds",
    "prompt": r"""Write a Python function `plan_rounds(deps: dict, capacity: int) -> list[list[str]]` that schedules tasks into rounds.

`deps` maps each task name (str) to the list of its prerequisite task names (no duplicates in a list). Every task is a key of `deps`. `capacity` is the maximum number of tasks that can run in one round.

Validation: `capacity < 1` raises `ValueError`. A prerequisite name that is not a key of `deps` raises `ValueError`.

Scheduling, round by round, until every task has run:
1. A task is "ready" if it has not run yet and all of its prerequisites ran in EARLIER rounds (a task never runs in the same round as one of its prerequisites).
2. If no task is ready although tasks remain (a dependency cycle, including a task that lists itself), raise `ValueError`.
3. Sort the ready tasks by their number of direct dependents, highest first; ties by task name ascending. The number of direct dependents of a task X is the number of tasks in `deps` that list X as a prerequisite - a fixed number that does not change as tasks run.
4. The first `capacity` tasks of that sorted list (or all of them, if fewer) run in this round. The round is recorded as the list of those task names in that sorted order.

Return the list of rounds. An empty `deps` returns `[]`.

Example: with `deps = {"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"], "e": []}`:
- `plan_rounds(deps, 2)` returns `[["a", "e"], ["b", "c"], ["d"]]`;
- `plan_rounds(deps, 1)` returns `[["a"], ["b"], ["c"], ["d"], ["e"]]` (after "a", the ready tasks are b and c with 1 dependent each and e with 0).""" + _TAIL,
    "reference": _REF_C27,
    "tests": _RAISES + r'''
_D = {"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"], "e": []}
assert plan_rounds({}, 3) == []
assert plan_rounds(_D, 2) == [["a", "e"], ["b", "c"], ["d"]]
assert plan_rounds(_D, 1) == [["a"], ["b"], ["c"], ["d"], ["e"]]
assert plan_rounds(_D, 5) == [["a", "e"], ["b", "c"], ["d"]]
assert plan_rounds({"z": [], "y": [], "x": []}, 2) == [["x", "y"], ["z"]]
assert plan_rounds({"m": [], "n": [], "o": ["n"], "p": ["n"], "q": ["m"]}, 1) == [["n"], ["m"], ["o"], ["p"], ["q"]]
assert plan_rounds({"m": [], "n": [], "o": ["n"], "p": ["n"], "q": ["m"]}, 2) == [["n", "m"], ["o", "p"], ["q"]]
assert plan_rounds({"a": [], "b": ["a"], "c": ["b"], "d": [], "e": ["d"], "f": ["d"], "g": ["c", "f"]}, 2) == [["d", "a"], ["b", "f"], ["c", "e"], ["g"]]
assert plan_rounds({"only": []}, 1) == [["only"]]
assert _raises(plan_rounds, {"a": ["b"], "b": ["a"]}, 2)
assert _raises(plan_rounds, {"a": [], "b": ["b"]}, 2)
assert _raises(plan_rounds, {"a": ["ghost"]}, 2)
assert _raises(plan_rounds, {"a": []}, 0)
assert _raises(plan_rounds, {"a": [], "b": ["a", "c"], "c": ["d"], "d": ["c"]}, 1)
''',
    "wrong": _mut(_REF_C27, "ready.sort(key=lambda t: (-dependents[t], t))", "ready.sort()"),
})


_REF_C28 = r'''
def pond_regions(grid):
    if not grid:
        return (0, 0)
    h, w = len(grid), len(grid[0])
    seen = set()
    count = 0
    best = 0
    for r in range(h):
        for c in range(w):
            if grid[r][c] != "~" or (r, c) in seen:
                continue
            count += 1
            size = 0
            stack = [(r, c)]
            seen.add((r, c))
            while stack:
                y, x = stack.pop()
                size += 1
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dy == 0 and dx == 0:
                            continue
                        ny, nx = y + dy, x + dx
                        if not (0 <= ny < h and 0 <= nx < w):
                            continue
                        if grid[ny][nx] != "~" or (ny, nx) in seen:
                            continue
                        if dy != 0 and dx != 0 and grid[y][nx] == "#" and grid[ny][x] == "#":
                            continue
                        seen.add((ny, nx))
                        stack.append((ny, nx))
            best = max(best, size)
    return (count, best)
'''

ITEMS.append({
    "id": "C28",
    "kind": "graph",
    "difficulty": "hard",
    "entry_point": "pond_regions",
    "prompt": r"""Write a Python function `pond_regions(grid: list[str]) -> tuple[int, int]` that analyses a map and returns `(number_of_ponds, size_of_largest_pond)`.

`grid` is a list of equal-length strings (possibly an empty list). Cells: `~` water, `.` sand, `#` rock.

Two water cells are directly connected if
- they are orthogonally adjacent (share an edge), or
- they are diagonally adjacent AND the diagonal is not "pinched": a diagonal step between two water cells is pinched when BOTH of the two other cells of that 2x2 block (the two cells orthogonally adjacent to both water cells) are rock `#`. If at least one of those two cells is sand or water, the diagonal connection exists.

A pond is a maximal set of water cells connected directly or through chains of direct connections. The size of a pond is its number of cells.

Return `(0, 0)` if there is no water (including for an empty grid).

Examples:
- `pond_regions(["~.", ".~"])` returns `(1, 2)` (diagonal through sand).
- `pond_regions(["~#", "#~"])` returns `(2, 1)` (pinched between two rocks).
- `pond_regions(["~#", ".~"])` returns `(1, 2)` (only one rock, so not pinched).""" + _TAIL,
    "reference": _REF_C28,
    "tests": r'''
assert pond_regions([]) == (0, 0) and pond_regions(["...", ".#."]) == (0, 0)
assert pond_regions(["~.", ".~"]) == (1, 2)
assert pond_regions(["~#", "#~"]) == (2, 1)
assert pond_regions(["~#", ".~"]) == (1, 2) and pond_regions(["~.", "#~"]) == (1, 2)
assert pond_regions([".~", "~."]) == (1, 2) and pond_regions(["#~", "~#"]) == (2, 1)
assert pond_regions(["~"]) == (1, 1)
assert pond_regions(["~~.", "..#", ".#~"]) == (2, 2)
assert pond_regions(["~#~", "#~#", "~#~"]) == (5, 1)
assert pond_regions(["~#~", ".~#", "~#~"]) == (3, 3)
assert pond_regions(["~~~~", "####", "~..~"]) == (3, 4)
assert pond_regions(["~#~", "#~~"]) == (2, 3)
assert pond_regions(["~#.#~", "#~#~#", ".#~#."]) == (5, 1)
assert pond_regions(["~#.#~", "#~.~#", ".#~#."]) == (3, 3)
assert pond_regions(["~.~.~", ".....", "~.~.~"]) == (6, 1)
''',
    "wrong": _mut(_REF_C28, 'grid[y][nx] == "#" and grid[ny][x] == "#"', 'grid[y][nx] == "#" or grid[ny][x] == "#"'),
})


_REF_C29 = r'''
import heapq

def relay_costs(links, fees, source, budget):
    adj = {}
    for a, b, cost in links:
        adj.setdefault(a, []).append((b, cost))
        adj.setdefault(b, []).append((a, cost))
    if source not in adj:
        return []
    dist = {source: 0}
    heap = [(0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        base = d if u == source else d + fees.get(u, 0)
        for v, cost in adj[u]:
            nd = base + cost
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    out = [(node, d) for node, d in dist.items() if node != source and d <= budget]
    out.sort(key=lambda item: (item[1], item[0]))
    return out
'''

ITEMS.append({
    "id": "C29",
    "kind": "graph",
    "difficulty": "hard",
    "entry_point": "relay_costs",
    "prompt": r"""Write a Python function `relay_costs(links: list[tuple[str, str, int]], fees: dict, source: str, budget: int) -> list[tuple[str, int]]` that computes cheapest message routes in a relay network.

- Each link `(a, b, cost)` connects stations `a` and `b` in both directions with an integer cost >= 0. There may be several links between the same pair of stations (any of them may be used), and links from a station to itself (useless, but allowed).
- `fees` maps a station name to its relay fee (integer >= 0). Stations missing from `fees` have fee 0.
- The cost of a route from `source` to some destination is the sum of the costs of the links used PLUS the relay fee of every intermediate station the route passes through. The fees of the source and of the destination itself are not charged.

For every station other than `source` that can be reached, find the minimum route cost. Return the stations whose minimum cost is at most `budget`, as a list of `(station, cost)` tuples sorted by cost ascending, then station name ascending.

If `source` does not occur in any link, return `[]`.

Example: `relay_costs([("a", "b", 2), ("b", "c", 2), ("a", "c", 9)], {"b": 4}, "a", 10)` returns `[("b", 2), ("c", 8)]` (to c via b costs 2 + 4 + 2 = 8, cheaper than the direct link; with `{"b": 6}` the answer for c would be 9).""" + _TAIL,
    "reference": _REF_C29,
    "tests": r'''
_L = [("a", "b", 2), ("b", "c", 2), ("a", "c", 9)]
assert relay_costs(_L, {"b": 4}, "a", 10) == [("b", 2), ("c", 8)]
assert relay_costs(_L, {"b": 6}, "a", 10) == [("b", 2), ("c", 9)]
assert relay_costs(_L, {"b": 4}, "a", 7) == [("b", 2)] and relay_costs(_L, {"b": 4}, "a", 8) == [("b", 2), ("c", 8)]
assert relay_costs(_L, {"a": 100, "c": 50}, "a", 10) == [("b", 2), ("c", 4)]
assert relay_costs(_L, {"b": 4}, "c", 100) == [("b", 2), ("a", 8)]
assert relay_costs(_L, {}, "zz", 5) == [] and relay_costs([], {}, "a", 5) == []
assert relay_costs([("a", "b", 5), ("b", "a", 3), ("a", "b", 4)], {}, "a", 3) == [("b", 3)]
assert relay_costs([("s", "y", 1), ("s", "x", 1)], {}, "s", 1) == [("x", 1), ("y", 1)]
assert relay_costs([("a", "b", 1), ("b", "c", 1), ("c", "d", 1)], {"b": 2, "c": 3, "d": 9}, "a", 100) == [("b", 1), ("c", 4), ("d", 8)]
assert relay_costs([("a", "b", 0)], {}, "a", 0) == [("b", 0)] and relay_costs([("a", "b", 1)], {}, "a", 0) == []
assert relay_costs([("a", "a", 1), ("a", "b", 2)], {"a": 7}, "a", 9) == [("b", 2)]
assert relay_costs([("a", "b", 1), ("b", "d", 1), ("a", "c", 2), ("c", "d", 2), ("d", "e", 1)], {"b": 5, "d": 1}, "a", 99) == [("b", 1), ("c", 2), ("d", 4), ("e", 6)]
assert relay_costs([("a", "b", 1), ("b", "c", 1), ("a", "c", 7)], {"b": 5}, "b", 99) == [("a", 1), ("c", 1)]
''',
    "wrong": _mut(_REF_C29, "base = d if u == source else d + fees.get(u, 0)", "base = d + fees.get(u, 0)"),
})


_REF_C30 = r'''
def kin_distance(parents, a, b):
    def ancestors(x):
        dist = {x: 0}
        frontier = [x]
        d = 0
        while frontier:
            d += 1
            nxt = []
            for person in frontier:
                for parent in parents.get(person, []):
                    if parent not in dist:
                        dist[parent] = d
                        nxt.append(parent)
            frontier = nxt
        return dist

    da, db = ancestors(a), ancestors(b)
    best_key = None
    best = None
    for person in da:
        if person in db:
            key = (da[person] + db[person], da[person])
            if best_key is None or key < best_key:
                best_key = key
                best = (da[person], db[person])
    return best
'''

ITEMS.append({
    "id": "C30",
    "kind": "graph",
    "difficulty": "hard",
    "entry_point": "kin_distance",
    "prompt": r"""Write a Python function `kin_distance(parents: dict, a: str, b: str)` that measures how two people in a family record are related.

`parents` maps a person's name to the list of that person's known parents (0, 1 or 2 names). A person who is not a key of `parents` has no known parents. The record contains no cycles, but it may contain marriages between relatives, so the same ancestor can be reachable along several lines of different length.

Definitions:
- Every person is their own ancestor at distance 0; their parents are ancestors at distance 1; parents of parents at distance 2; and so on. If an ancestor can be reached along several lines, their distance is the SMALLEST such number.
- A common ancestor of `a` and `b` is a person who is an ancestor (in this sense, distance 0 allowed) of both.

Among all common ancestors c, pick the one that minimises `da + db`, where `da` is c's distance from `a` and `db` is c's distance from `b`. If several have the same minimal sum, pick the one with the smallest `da`. Return the tuple `(da, db)`. If there is no common ancestor, return `None`.

Names that do not occur anywhere in `parents` are simply people without known parents (so `kin_distance(parents, "nobody", "nobody")` is `(0, 0)`).

Examples, with `parents = {"kid": ["mum", "dad"], "cousin": ["aunt"], "mum": ["gran"], "aunt": ["gran"]}`:
- `kin_distance(parents, "kid", "cousin")` returns `(2, 2)` (via gran);
- `kin_distance(parents, "kid", "gran")` returns `(2, 0)`;
- `kin_distance(parents, "dad", "aunt")` returns `None`.""" + _TAIL,
    "reference": _REF_C30,
    "tests": r'''
_P = {"kid": ["mum", "dad"], "cousin": ["aunt"], "mum": ["gran"], "aunt": ["gran"]}
_P2 = {"a": ["p", "m"], "m": ["q"], "b": ["q", "n"], "n": ["p"]}
_P3 = {"x": ["y", "z"], "y": ["z"], "w": ["z"], "v": ["y"]}
assert kin_distance(_P, "kid", "cousin") == (2, 2)
assert kin_distance(_P, "kid", "gran") == (2, 0) and kin_distance(_P, "gran", "kid") == (0, 2)
assert kin_distance(_P, "dad", "aunt") is None
assert kin_distance(_P, "kid", "kid") == (0, 0) and kin_distance(_P, "nobody", "nobody") == (0, 0)
assert kin_distance(_P, "nobody", "kid") is None and kin_distance({}, "a", "b") is None
assert kin_distance(_P, "kid", "mum") == (1, 0) and kin_distance(_P, "mum", "aunt") == (1, 1)
assert kin_distance(_P, "cousin", "mum") == (2, 1)
assert kin_distance(_P2, "a", "b") == (1, 2)
assert kin_distance(_P2, "b", "a") == (1, 2)
assert kin_distance(_P2, "m", "n") is None and kin_distance(_P2, "m", "b") == (1, 1)
assert kin_distance(_P3, "x", "w") == (1, 1)
assert kin_distance(_P3, "x", "v") == (1, 1) and kin_distance(_P3, "w", "v") == (1, 2)
assert kin_distance({"s": ["t"], "t": ["u"], "u": ["r"], "c": ["r"]}, "s", "c") == (3, 1)
''',
    "wrong": _mut(_REF_C30, "key = (da[person] + db[person], da[person])", "key = (da[person] + db[person], db[person])"),
})

# ---------------------------------------------------------------------------
# Kind 7: numeric / combinatorial routines with exact arithmetic (C31-C35)
# ---------------------------------------------------------------------------

_REF_C31 = r'''
def shelf_code(n):
    if n < 1:
        raise ValueError("n must be positive")
    alphabet = "ABCDEFGHJKLMNPRSTUVWXYZ"
    values = []
    while n > 0:
        n, r = divmod(n - 1, 23)
        values.append(r + 1)
    check = sum(v * (i + 2) for i, v in enumerate(values)) % 23
    body = "".join(alphabet[v - 1] for v in reversed(values))
    return body + "-" + alphabet[check]
'''

ITEMS.append({
    "id": "C31",
    "kind": "numeric",
    "difficulty": "medium",
    "entry_point": "shelf_code",
    "prompt": r"""Write a Python function `shelf_code(n: int) -> str` that converts a positive integer into a warehouse shelf code of the form `BODY-C`.

Alphabet: the 23 letters `ABCDEFGHJKLMNPRSTUVWXYZ` (the usual alphabet without I, O and Q). The letters have the values 1..23 in that order: A = 1, B = 2, ..., H = 8, J = 9, ..., Z = 23.

BODY: `n` written in "bijective base 23" with these letters - there is no zero digit. A body with letter values d_k ... d_2 d_1 (d_1 rightmost) stands for the number d_1 + d_2 * 23 + d_3 * 23^2 + ... . So 1 -> `A`, 23 -> `Z`, 24 -> `AA`, 25 -> `AB`, 46 -> `AZ`, 47 -> `BA`, 552 -> `ZZ`, 553 -> `AAA`. Every positive integer has exactly one such body.

Check letter C: number the body's letters from the right; the rightmost letter has weight 2, the next one weight 3, the next weight 4, and so on. Let s be the sum of (letter value * weight). The check letter is the letter whose value is `(s mod 23) + 1`.

The result is BODY, a hyphen, and the check letter. `n < 1` raises `ValueError`. The function must be exact for very large n (e.g. 10**30).

Examples:
- `shelf_code(1)` returns `"A-C"` (s = 1*2 = 2, letter value 3).
- `shelf_code(24)` returns `"AA-F"` (s = 1*2 + 1*3 = 5, letter value 6).
- `shelf_code(23)` returns `"Z-A"` (s = 46, 46 mod 23 = 0, letter value 1).""" + _TAIL,
    "reference": _REF_C31,
    "tests": _RAISES + r'''
assert shelf_code(1) == "A-C"
assert shelf_code(24) == "AA-F"
assert shelf_code(23) == "Z-A"
assert shelf_code(9) == "J-V"
assert shelf_code(25) == "AB-H"
assert shelf_code(46) == "AZ-D" and shelf_code(47) == "BA-J"
assert shelf_code(552) == "ZZ-A" and shelf_code(553) == "AAA-K"
assert shelf_code(8) == "H-T" and shelf_code(11) == "L-Z" and shelf_code(12) == "M-B"
assert shelf_code(23 ** 3 + 23 ** 2 + 23) == "ZZZ-A" and shelf_code(23 ** 3 + 23 ** 2 + 24) == "AAAA-R"
assert shelf_code(10 ** 30) == "ABGSAALYHVXKZKLUUFWMZPB-W"
assert shelf_code(10 ** 30 + 1) == "ABGSAALYHVXKZKLUUFWMZPC-Y"
assert shelf_code(2 * 23 ** 2 + 14 * 23 + 20) == "BPW-Y"
assert _raises(shelf_code, 0) and _raises(shelf_code, -5)
''',
    "wrong": _mut(_REF_C31, "v * (i + 2)", "v * (i + 1)"),
})


_REF_C32 = r'''
def split_cents(total, weights):
    if total < 0 or not weights or any(w < 0 for w in weights) or sum(weights) == 0:
        raise ValueError("bad input")
    whole = sum(weights)
    shares = [total * w // whole for w in weights]
    left = total - sum(shares)
    order = sorted(range(len(weights)),
                   key=lambda i: (-(total * weights[i] % whole), -weights[i], i))
    for i in order[:left]:
        shares[i] += 1
    return shares
'''

ITEMS.append({
    "id": "C32",
    "kind": "numeric",
    "difficulty": "hard",
    "entry_point": "split_cents",
    "prompt": r"""Write a Python function `split_cents(total: int, weights: list[int]) -> list[int]` that splits an amount of money (in whole cents) among people in proportion to integer weights, so that the shares add up to exactly `total`.

Validation - raise `ValueError` if `total < 0`, if `weights` is empty, if any weight is negative, or if all weights are 0.

Let W be the sum of the weights. Person i's exact share is `total * w_i / W`.
1. Everyone first receives the floor of their exact share.
2. The cents still undistributed (`total` minus the sum of the floors) are handed out one cent per person, in this priority order:
   - larger fractional part of the exact share first (equivalently: larger remainder `(total * w_i) mod W`);
   - ties: larger weight first;
   - remaining ties: lower index first.

Return the list of shares in the order of `weights`. All arithmetic must be exact integer arithmetic - `total` can be as large as 10**30, where floating point is not accurate enough.

Examples:
- `split_cents(100, [1, 1, 1])` returns `[34, 33, 33]`.
- `split_cents(100, [2, 1, 1, 3])` returns `[29, 14, 14, 43]` (floors 28, 14, 14, 42 with remainders 4, 2, 2, 6 out of 7; the two spare cents go to the last and the first person).""" + _TAIL,
    "reference": _REF_C32,
    "tests": _RAISES + r'''
assert split_cents(100, [1, 1, 1]) == [34, 33, 33]
assert split_cents(100, [2, 1, 1, 3]) == [29, 14, 14, 43]
assert split_cents(2, [1, 4, 1]) == [0, 2, 0]
assert split_cents(5, [3, 1, 1, 1]) == [2, 1, 1, 1]
assert split_cents(1, [1, 1]) == [1, 0] and split_cents(0, [3, 4]) == [0, 0]
assert split_cents(10, [0, 5, 0]) == [0, 10, 0]
assert split_cents(7, [1]) == [7]
assert split_cents(10, [1, 2, 3, 4]) == [1, 2, 3, 4]
assert split_cents(3, [1, 1, 1, 1, 1]) == [1, 1, 1, 0, 0]
assert split_cents(4, [1, 3, 1, 3]) == [0, 2, 0, 2]
assert split_cents(10 ** 30 + 1, [1, 1, 1]) == [(10 ** 30 - 1) // 3 + 1, (10 ** 30 - 1) // 3 + 1, (10 ** 30 - 1) // 3]
assert split_cents(10 ** 30, [10 ** 18, 10 ** 18 + 1]) == [499999999999999999750000000000, 500000000000000000250000000000]
assert _raises(split_cents, -1, [1]) and _raises(split_cents, 5, [])
assert _raises(split_cents, 5, [0, 0]) and _raises(split_cents, 5, [2, -1])
''',
    "wrong": _mut(_REF_C32, "(-(total * weights[i] % whole), -weights[i], i)", "(-(total * weights[i] % whole), i)"),
})


_REF_C33 = r'''
def coin_total(amounts):
    unit_value = {"g": 493, "s": 17, "c": 1}
    total = 0
    for text in amounts:
        negative = text.startswith("-")
        body = text[1:] if negative else text
        last = -1
        value = 0
        for term in body.split(" "):
            if len(term) < 2 or term[-1] not in "gsc" or any(ch not in "0123456789" for ch in term[:-1]):
                raise ValueError("bad term: %r" % (term,))
            position = "gsc".index(term[-1])
            if position <= last:
                raise ValueError("units out of order")
            last = position
            value += int(term[:-1]) * unit_value[term[-1]]
        total += -value if negative else value
    negative = total < 0
    total = abs(total)
    gilts, rest = divmod(total, 493)
    shards, chips = divmod(rest, 17)
    parts = [str(v) + u for v, u in ((gilts, "g"), (shards, "s"), (chips, "c")) if v]
    if not parts:
        return "0c"
    return ("-" if negative else "") + " ".join(parts)
'''

ITEMS.append({
    "id": "C33",
    "kind": "numeric",
    "difficulty": "hard",
    "entry_point": "coin_total",
    "prompt": r"""Write a Python function `coin_total(amounts: list[str]) -> str` that adds up amounts of an old currency and returns the total in normalised form.

Currency: 1 gilt (`g`) = 29 shards (`s`); 1 shard = 17 chips (`c`). So 1 gilt = 493 chips.

Format of an input amount:
- an optional leading `-`, which negates the whole amount;
- then one, two or three terms separated by exactly one space;
- each term is a non-negative integer written with digits 0-9, immediately followed by one unit letter `g`, `s` or `c` (e.g. `12g`, `0s`, `40c`; leading zeros as in `007c` are allowed);
- the units must appear in the order g, s, c and each at most once (any of them may be left out). Counts are NOT limited to the unit size (`40c` and `100s 100c` are fine).
Anything else - empty string, extra or missing spaces, a `+` sign, a space after the `-`, a unit without a number, a decimal point, wrong unit order, a repeated unit - raises `ValueError`.

Output: the sum of all amounts (an empty list sums to zero), normalised:
- work with the absolute value of the total and express it as gilts, shards (0..28) and chips (0..16);
- write the non-zero terms in the order g, s, c separated by single spaces, e.g. `2g 6c`;
- if the total is negative, put `-` directly in front (e.g. `-26s`);
- a total of zero is written `0c` (never with a minus sign).

Examples:
- `coin_total(["1g 28s 16c", "1c"])` returns `"2g"`.
- `coin_total(["3s", "-1g"])` returns `"-26s"` (51 chips minus 493 chips = -442 chips = -(26 shards)).""" + _TAIL,
    "reference": _REF_C33,
    "tests": _RAISES + r'''
assert coin_total([]) == "0c" and coin_total(["0g"]) == "0c" and coin_total(["-0c"]) == "0c"
assert coin_total(["1g 28s 16c", "1c"]) == "2g"
assert coin_total(["3s", "-1g"]) == "-26s"
assert coin_total(["40c"]) == "2s 6c" and coin_total(["1g 1c"]) == "1g 1c"
assert coin_total(["5c", "-5c"]) == "0c"
assert coin_total(["1g", "-1c"]) == "28s 16c" and coin_total(["1c", "-1g"]) == "-28s 16c"
assert coin_total(["100g 100s 100c"]) == "103g 18s 15c"
assert coin_total(["-2g 5s", "1g 0s 3c"]) == "-1g 4s 14c"
assert coin_total(["0g 0s 17c", "28s"]) == "1g"
assert coin_total(["-1c", "-16c"]) == "-1s" and coin_total(["007c"]) == "7c"
assert coin_total(["12345678901234567890g 1c"]) == "12345678901234567890g 1c"
assert _raises(coin_total, ["1c 1g"]) and _raises(coin_total, ["1g 1g"]) and _raises(coin_total, [""])
assert _raises(coin_total, ["1 g"]) and _raises(coin_total, ["g"]) and _raises(coin_total, ["1g  2c"])
assert _raises(coin_total, ["+1g"]) and _raises(coin_total, ["1.5g"]) and _raises(coin_total, ["- 1g"])
assert _raises(coin_total, ["1g", "1g "]) and _raises(coin_total, ["1g 2s 3c 4c"]) and _raises(coin_total, ["-"])
''',
    "wrong": _mut(_REF_C33, "    negative = total < 0\n    total = abs(total)\n", "    negative = False\n"),
})


_REF_C34 = r'''
def kth_badge(length, k):
    letters = "ABCD"

    def allowed(prev, ch):
        return prev != ch and not (prev == "A" and ch == "D")

    # count[i][ch] = number of valid badges of length i that start with ch
    count = [None, {ch: 1 for ch in letters}]
    for i in range(2, length + 1):
        count.append({ch: sum(count[i - 1][nx] for nx in letters if allowed(ch, nx))
                      for ch in letters})
    if k < 1 or k > sum(count[length].values()):
        raise ValueError("k out of range")
    out = []
    prev = ""
    for pos in range(length):
        remaining = length - pos
        for ch in letters:
            if prev and not allowed(prev, ch):
                continue
            block = count[remaining][ch]
            if k <= block:
                out.append(ch)
                prev = ch
                break
            k -= block
    return "".join(out)
'''

ITEMS.append({
    "id": "C34",
    "kind": "numeric",
    "difficulty": "very hard",
    "entry_point": "kth_badge",
    "prompt": r"""Write a Python function `kth_badge(length: int, k: int) -> str`.

A badge is a string of exactly `length` letters (`length >= 1`) over the alphabet `A`, `B`, `C`, `D`. A badge is valid if
1. no two adjacent letters are equal, and
2. the letter `D` never comes immediately after the letter `A` (the substring `AD` does not occur; `DA` is fine).

Consider all valid badges of the given length sorted in ordinary alphabetical (lexicographic) order. Return the k-th one, counting from k = 1. If `k < 1` or `k` is larger than the number of valid badges of that length, raise `ValueError`.

`length` can be up to 60, where the number of valid badges is astronomically large, so generating them one by one is not feasible; `k` can be a very large integer.

Example: for `length = 2` the valid badges in order are AB, AC, BA, BC, BD, CA, CB, CD, DA, DB, DC (11 of them). So `kth_badge(2, 1)` returns `"AB"`, `kth_badge(2, 3)` returns `"BA"`, `kth_badge(2, 11)` returns `"DC"`, and `kth_badge(2, 12)` raises `ValueError`.""" + _TAIL,
    "reference": _REF_C34,
    "tests": _RAISES + r'''
assert [kth_badge(1, k) for k in (1, 2, 3, 4)] == ["A", "B", "C", "D"]
assert _raises(kth_badge, 1, 5) and _raises(kth_badge, 1, 0) and _raises(kth_badge, 3, -2)
assert [kth_badge(2, k) for k in range(1, 12)] == ["AB", "AC", "BA", "BC", "BD", "CA", "CB", "CD", "DA", "DB", "DC"]
assert _raises(kth_badge, 2, 12)
assert [kth_badge(3, k) for k in (1, 2, 3, 4, 5, 6)] == ["ABA", "ABC", "ABD", "ACA", "ACB", "ACD"]
assert [kth_badge(3, k) for k in (7, 8, 9, 14, 15)] == ["BAB", "BAC", "BCA", "BDC", "CAB"]
assert kth_badge(3, 30) == "DCD" and _raises(kth_badge, 3, 31)
assert kth_badge(4, 1) == "ABAB" and kth_badge(4, 2) == "ABAC" and kth_badge(4, 3) == "ABCA"
assert kth_badge(60, 1) == "AB" * 30
assert kth_badge(60, 2) == "AB" * 29 + "AC"
assert kth_badge(60, 227584141531731224728436736) == "DC" * 30
assert _raises(kth_badge, 60, 227584141531731224728436737)
assert kth_badge(60, 10 ** 20) == "ABABABABABABABDBCACABACDCBCDACDCBDABCDCBACABDBDABDCDBCDABCDA"
assert kth_badge(25, 123456789) == "ABABABCDBDCDBABDBCDCDCABD"
''',
    "wrong": _mut(_REF_C34, 'return prev != ch and not (prev == "A" and ch == "D")', "return prev != ch"),
})


_REF_C35 = r'''
import math

def root_digits(n, places):
    if n < 0 or places < 0:
        raise ValueError("negative argument")
    rounded = (math.isqrt(4 * n * 10 ** (2 * places)) + 1) // 2
    digits = str(rounded)
    if places == 0:
        return digits
    digits = digits.rjust(places + 1, "0")
    return digits[:-places] + "." + digits[-places:]
'''

ITEMS.append({
    "id": "C35",
    "kind": "numeric",
    "difficulty": "medium",
    "entry_point": "root_digits",
    "prompt": r"""Write a Python function `root_digits(n: int, places: int) -> str` that returns the square root of the non-negative integer `n` as a decimal string, correctly ROUNDED TO NEAREST at `places` digits after the decimal point.

- The result has an integer part without leading zeros (a single `0` if the root is below 1), and exactly `places` digits after the decimal point. If `places == 0` there is no decimal point at all.
- Rounding is to the nearest value with that many decimals (an exact tie cannot occur for an integer `n`, so no tie rule is needed). Rounding may carry into the integer part: the square root of 999999 is 999.9995 (rounded to 4 places: 999.9995), which rounded to 2 places is `1000.00`.
- The result must be exact for large inputs: `n` can be as large as 10**60 and `places` as large as 80, so ordinary floating point is not sufficient.
- `n < 0` or `places < 0` raises `ValueError`.

Examples:
- `root_digits(2, 5)` returns `"1.41421"`.
- `root_digits(3, 0)` returns `"2"` (1.732... rounds up), and `root_digits(2, 0)` returns `"1"`.
- `root_digits(0, 3)` returns `"0.000"`.""" + _TAIL,
    "reference": _REF_C35,
    "tests": _RAISES + r'''
assert root_digits(2, 5) == "1.41421"
assert root_digits(3, 0) == "2" and root_digits(2, 0) == "1" and root_digits(9, 0) == "3"
assert root_digits(0, 3) == "0.000" and root_digits(0, 0) == "0" and root_digits(1, 3) == "1.000"
assert root_digits(15, 1) == "3.9" and root_digits(7, 3) == "2.646"
assert root_digits(999999, 2) == "1000.00" and root_digits(999999, 3) == "999.999" and root_digits(999999, 4) == "999.9995"
assert root_digits(2, 50) == "1.41421356237309504880168872420969807856967187537695"
assert root_digits(10 ** 60, 2) == "1" + "0" * 30 + ".00"
assert root_digits(10 ** 60 - 1, 3) == "1" + "0" * 30 + ".000"
assert root_digits(10 ** 60 - 1, 0) == "1" + "0" * 30
assert root_digits(10 ** 60 - 10 ** 30, 0) == "9" * 30 and root_digits(10 ** 60 - 10 ** 30, 1) == "9" * 30 + ".5"
assert root_digits(6, 0) == "2" and root_digits(7, 0) == "3" and root_digits(12, 0) == "3" and root_digits(13, 0) == "4"
assert root_digits(5, 80) == "2.23606797749978969640917366873127623544061835961152572427089724541052092563780490"
assert _raises(root_digits, -1, 2) and _raises(root_digits, 2, -1)
''',
    "wrong": _mut(_REF_C35, "(math.isqrt(4 * n * 10 ** (2 * places)) + 1) // 2", "math.isqrt(n * 10 ** (2 * places))"),
})


# ---------------------------------------------------------------------------
# Kind 8: small stateful classes (C36-C40)
# ---------------------------------------------------------------------------

_REF_C36 = r'''
class BulkCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self._data = {}          # key -> [value, size]; dict order = insertion order

    def put(self, key, value, size):
        if size > self.capacity:
            return False
        if key in self._data:
            self._data[key][0] = value
            self._data[key][1] = size
        else:
            self._data[key] = [value, size]
        while self.used() > self.capacity:
            victim = None
            for other, (_, other_size) in self._data.items():
                if other == key:
                    continue
                if victim is None or other_size > self._data[victim][1]:
                    victim = other
            del self._data[victim]
        return True

    def get(self, key, default=None):
        if key in self._data:
            return self._data[key][0]
        return default

    def keys(self):
        return list(self._data)

    def used(self):
        return sum(size for _, size in self._data.values())
'''

ITEMS.append({
    "id": "C36",
    "kind": "class",
    "difficulty": "hard",
    "entry_point": "BulkCache",
    "prompt": r"""Write a Python class `BulkCache` - a cache whose capacity is measured in total size, with an unusual eviction rule.

- `BulkCache(capacity: int)` - `capacity` is a positive integer: the maximum total size of all stored entries.
- `put(key, value, size: int) -> bool` - `size` is a positive integer.
  1. If `size > capacity`, the call is rejected: return `False` and change nothing (if `key` was already stored, its old value and size stay).
  2. Otherwise, if `key` is already stored, replace its value and size; the entry KEEPS its original position in the insertion order (its "age" does not change). If `key` is new, it is stored as the newest entry.
  3. Then, while the total size of all entries exceeds `capacity`, evict one entry: the entry with the LARGEST size; among entries of equal largest size, the OLDEST (earliest inserted). The key that was just put is never evicted by this call - it is excluded from the choice.
  4. Return `True`.
- `get(key, default=None)` - return the stored value, or `default` if the key is not stored. Reading does not affect age or anything else.
- `keys() -> list` - the stored keys in insertion order, oldest first.
- `used() -> int` - the total size of the stored entries.

Example:

    c = BulkCache(10)
    c.put("a", 1, 4); c.put("b", 2, 4); c.put("c", 3, 3)

After the third put the total would be 11, so one entry is evicted: "a" and "b" are tied for largest size (4) and "a" is older. Now `c.keys() == ["b", "c"]` and `c.used() == 7`. Then `c.put("b", 9, 6)` gives total 9 with no eviction, and `c.keys()` is still `["b", "c"]`.""" + _TAIL,
    "reference": _REF_C36,
    "tests": r'''
c = BulkCache(10)
assert c.put("a", 1, 4) is True and c.put("b", 2, 4) is True and c.put("c", 3, 3) is True
assert c.keys() == ["b", "c"] and c.used() == 7
assert c.get("a") is None and c.get("a", "gone") == "gone" and c.get("b") == 2
assert c.put("b", 9, 6) is True and c.keys() == ["b", "c"] and c.used() == 9 and c.get("b") == 9
assert c.put("d", 4, 5) is True and c.keys() == ["c", "d"] and c.used() == 8
assert c.put("e", 5, 11) is False and c.keys() == ["c", "d"] and c.used() == 8
assert c.put("c", 33, 11) is False and c.get("c") == 3 and c.used() == 8
x = BulkCache(10)
x.put("x", 1, 2)
assert x.put("y", 2, 9) is True and x.keys() == ["y"] and x.used() == 9
z = BulkCache(10)
z.put("a", 1, 3); z.put("b", 2, 3)
assert z.put("a", 7, 8) is True and z.keys() == ["a"] and z.get("a") == 7
w = BulkCache(10)
w.put("a", 1, 2); w.put("b", 2, 3); w.put("c", 3, 3); w.put("d", 4, 2)
assert w.keys() == ["a", "b", "c", "d"] and w.used() == 10
assert w.put("a", 10, 4) is True and w.keys() == ["a", "c", "d"] and w.used() == 9
assert w.put("e", 5, 6) is True and w.keys() == ["d", "e"] and w.used() == 8
v = BulkCache(5)
v.put("p", 1, 1); v.put("q", 2, 1); v.put("p", 3, 1); v.put("r", 4, 4)
assert v.keys() == ["q", "r"] and v.used() == 5
assert BulkCache(3).keys() == [] and BulkCache(3).used() == 0 and BulkCache(3).put("k", 0, 3) is True
''',
    "wrong": _mut(_REF_C36, "            self._data[key][0] = value\n            self._data[key][1] = size\n",
                  "            del self._data[key]\n            self._data[key] = [value, size]\n"),
})


_REF_C37 = r'''
class BurstGate:
    def __init__(self, limit, window, strikes, cooldown):
        self.limit = limit
        self.window = window
        self.strikes = strikes
        self.cooldown = cooldown
        self._accepted = {}
        self._strikes = {}
        self._locked_until = {}

    def allow(self, key, t):
        if key in self._locked_until and t < self._locked_until[key]:
            return False
        recent = [x for x in self._accepted.get(key, []) if x > t - self.window]
        self._accepted[key] = recent
        if len(recent) < self.limit:
            recent.append(t)
            self._strikes[key] = 0
            return True
        self._strikes[key] = self._strikes.get(key, 0) + 1
        if self._strikes[key] >= self.strikes:
            self._locked_until[key] = t + self.cooldown
            self._strikes[key] = 0
        return False
'''

ITEMS.append({
    "id": "C37",
    "kind": "class",
    "difficulty": "very hard",
    "entry_point": "BurstGate",
    "prompt": r"""Write a Python class `BurstGate` - a per-key rate limiter with a lock-out for clients that keep hammering.

- `BurstGate(limit: int, window: int, strikes: int, cooldown: int)` - all positive integers.
- `allow(key: str, t: int) -> bool` - a request for `key` at integer time `t`. The caller supplies the clock: across all calls, `t` never decreases. Returns `True` if the request is accepted, `False` if rejected.

Each key is handled independently and has: its list of accepted request times, a strike counter (initially 0), and possibly a lock.

`allow(key, t)` does the following, in this order:
1. If the key is locked at time `t`, return `False`. Nothing else happens: no strike is counted and the lock is not extended. A lock created at time `u` covers the times `u <= t < u + cooldown`; at time `u + cooldown` the key is no longer locked.
2. Otherwise count the key's accepted requests with a time strictly greater than `t - window` (a request accepted exactly `window` time units ago no longer counts). If that count is less than `limit`: the request is accepted - record `t` as an accepted time, reset the key's strike counter to 0, and return `True`.
3. Otherwise the request is rejected: add 1 to the key's strike counter. If the counter has now reached `strikes`, lock the key starting now (until `t + cooldown`) and reset the strike counter to 0. Return `False`.

Example with `g = BurstGate(limit=2, window=10, strikes=2, cooldown=20)` and key "k":
`allow("k", 0)` True, `allow("k", 1)` True, `allow("k", 2)` False (strike 1), `allow("k", 3)` False (strike 2: locked until 23), `allow("k", 15)` False (still locked, although the window is empty by then), `allow("k", 23)` True.""" + _TAIL,
    "reference": _REF_C37,
    "tests": r'''
g = BurstGate(limit=2, window=10, strikes=2, cooldown=20)
assert [g.allow("k", t) for t in (0, 1, 2, 3)] == [True, True, False, False]
assert g.allow("k", 15) is False and g.allow("k", 22) is False
assert g.allow("k", 23) is True and g.allow("k", 24) is True
assert g.allow("k", 25) is False
assert g.allow("k", 33) is True and g.allow("k", 34) is True
assert g.allow("k", 35) is False
assert g.allow("other", 35) is True
assert g.allow("k", 44) is True
h = BurstGate(1, 5, 1, 10)
assert [h.allow("a", t) for t in (0, 1, 10, 11, 16)] == [True, False, False, True, True]
assert [h.allow("b", t) for t in (16, 20, 21, 30, 31)] == [True, False, False, True, False]
j = BurstGate(1, 100, 1, 10)
assert [j.allow("a", t) for t in (0, 1, 5, 10, 11, 20, 21)] == [True, False, False, False, False, False, False]
assert j.allow("a", 99) is False and j.allow("a", 100) is False and j.allow("a", 108) is False and j.allow("a", 109) is True
m = BurstGate(3, 4, 3, 5)
assert [m.allow("x", t) for t in (0, 0, 0, 0, 0, 3, 4, 4, 4, 4)] == [True, True, True, False, False, False, False, False, False, False]
assert [m.allow("x", t) for t in (7, 8, 8, 8, 8)] == [False, True, True, True, False]
n = BurstGate(1, 3, 2, 50)
assert [n.allow("x", t) for t in (0, 1, 3, 4, 5, 6, 7)] == [True, False, True, False, False, False, False]
''',
    "wrong": _mut(_REF_C37, "            recent.append(t)\n            self._strikes[key] = 0\n", "            recent.append(t)\n"),
})


_REF_C38 = r'''
class DraftPad:
    def __init__(self):
        self._text = ""
        self._undo = []
        self._redo = []
        self._typing = False

    def type(self, s):
        if not self._typing:
            self._undo.append(self._text)
            self._typing = True
        self._text += s
        self._redo.clear()

    def erase(self, n):
        self._typing = False
        if not self._text:
            return
        self._undo.append(self._text)
        self._text = self._text[:max(0, len(self._text) - n)]
        self._redo.clear()

    def mark(self):
        self._typing = False

    def undo(self):
        self._typing = False
        if not self._undo:
            return False
        self._redo.append(self._text)
        self._text = self._undo.pop()
        return True

    def redo(self):
        self._typing = False
        if not self._redo:
            return False
        self._undo.append(self._text)
        self._text = self._redo.pop()
        return True

    def text(self):
        return self._text
'''

ITEMS.append({
    "id": "C38",
    "kind": "class",
    "difficulty": "hard",
    "entry_point": "DraftPad",
    "prompt": r"""Write a Python class `DraftPad` - a text buffer with grouped undo and redo. It starts with empty text.

Methods:
- `type(s: str)` - append the non-empty string `s` to the end of the text.
- `erase(n: int)` - remove the last `n` characters (`n >= 1`); if the text has fewer than `n` characters, remove them all.
- `mark()` - closes the current typing group (see below); changes nothing else.
- `undo() -> bool` - revert the most recent edit group that has not been undone; return `True`. If there is nothing to undo, return `False`.
- `redo() -> bool` - re-apply the most recently undone edit group; return `True`. If there is nothing to redo, return `False`.
- `text() -> str` - the current text.

Edit groups:
- Consecutive `type` calls form ONE group (a "typing group"), which is undone and redone as a whole. The typing group is closed by any call to `erase`, `mark`, `undo` or `redo`; the next `type` call then starts a new group. Calling `text()` does not close it.
- Each `erase` call that removes at least one character is a group of its own. Undoing it puts the removed characters back.
- An `erase` call on an empty text removes nothing: it creates no group and leaves the redo history untouched.
- Any new edit (a `type` call, or an `erase` call that removes at least one character) discards the redo history: afterwards `redo()` returns `False` until something is undone again.
- Several undos in a row walk back through the groups, most recent first; several redos walk forward again in the opposite order.

Example:

    p = DraftPad()
    p.type("ab"); p.type("cd"); p.mark(); p.type("e"); p.erase(2)

Now `p.text() == "abc"`. `p.undo()` -> True, text `"abcde"`; `p.undo()` -> True, text `"abcd"`; `p.undo()` -> True, text `""`; `p.undo()` -> False. `p.redo()` -> True, text `"abcd"`. After `p.type("X")` the text is `"abcdX"` and `p.redo()` returns False.""" + _TAIL,
    "reference": _REF_C38,
    "tests": r'''
p = DraftPad()
p.type("ab"); p.type("cd"); p.mark(); p.type("e"); p.erase(2)
assert p.text() == "abc"
assert p.undo() is True and p.text() == "abcde"
assert p.undo() is True and p.text() == "abcd"
assert p.undo() is True and p.text() == ""
assert p.undo() is False and p.text() == ""
assert p.redo() is True and p.text() == "abcd"
p.type("X")
assert p.text() == "abcdX" and p.redo() is False
assert p.undo() is True and p.text() == "abcd" and p.undo() is True and p.text() == ""
assert p.redo() is True and p.redo() is True and p.redo() is False and p.text() == "abcdX"
q = DraftPad()
q.type("a"); q.type("b"); q.undo()
assert q.text() == "" and q.redo() is True and q.text() == "ab"
q.type("c")
assert q.text() == "abc" and q.undo() is True and q.text() == "ab"
r = DraftPad()
r.type("abc"); r.erase(10)
assert r.text() == "" and r.undo() is True and r.text() == "abc" and r.redo() is True and r.text() == ""
u = DraftPad()
u.type("a"); u.undo(); u.erase(1)
assert u.redo() is True and u.text() == "a"
v = DraftPad()
v.type("a"); v.text(); v.type("b"); v.undo()
assert v.text() == "" and v.undo() is False and DraftPad().redo() is False
w = DraftPad()
w.type("hello"); w.erase(1); w.erase(1); w.type("p"); w.type("!")
assert w.text() == "help!" and w.undo() is True and w.text() == "hel" and w.undo() is True and w.text() == "hell"
''',
    "wrong": _mut(_REF_C38, "        if not self._typing:\n            self._undo.append(self._text)\n            self._typing = True\n",
                  "        self._undo.append(self._text)\n"),
})


_REF_C39 = r'''
class HoldDesk:
    def __init__(self, stock, ttl):
        self._stock = dict(stock)
        self._ttl = ttl
        self._holds = {}
        self._next_id = 1

    def _active(self, hold, t):
        return hold["state"] == "held" and t < hold["t"] + self._ttl

    def available(self, item, t):
        if item not in self._stock:
            return 0
        held = sum(h["qty"] for h in self._holds.values()
                   if h["item"] == item and self._active(h, t))
        return self._stock[item] - held

    def hold(self, item, qty, t):
        if item not in self._stock or self.available(item, t) < qty:
            return None
        hold_id = self._next_id
        self._next_id += 1
        self._holds[hold_id] = {"item": item, "qty": qty, "t": t, "state": "held"}
        return hold_id

    def confirm(self, hold_id, t):
        hold = self._holds.get(hold_id)
        if hold is None or not self._active(hold, t):
            return False
        hold["state"] = "confirmed"
        self._stock[hold["item"]] -= hold["qty"]
        return True

    def release(self, hold_id, t):
        hold = self._holds.get(hold_id)
        if hold is None or not self._active(hold, t):
            return False
        hold["state"] = "released"
        return True
'''

ITEMS.append({
    "id": "C39",
    "kind": "class",
    "difficulty": "hard",
    "entry_point": "HoldDesk",
    "prompt": r"""Write a Python class `HoldDesk` that manages stock with temporary holds (reservations that expire).

- `HoldDesk(stock: dict, ttl: int)` - `stock` maps item name to the number of units on hand; `ttl` is a positive integer. The dict passed in must not be modified.

Every method takes the current time `t` (an integer) from the caller; across all calls `t` never decreases.

- `hold(item: str, qty: int, t: int)` - try to reserve `qty` units (`qty >= 1`). If `item` is unknown, or `available(item, t) < qty`, return `None`. Otherwise create a hold and return its id. Ids are the integers 1, 2, 3, ... in order of creation; a failed attempt does not use up an id.
- A hold created at time `t0` is ACTIVE at time `t` if `t < t0 + ttl` and it has been neither confirmed nor released. From time `t0 + ttl` on it is expired (unless it was confirmed before that).
- `confirm(hold_id: int, t: int) -> bool` - if the hold exists and is active at `t`: its units are permanently removed from the stock on hand, the hold ends, return `True`. In every other case (unknown id, expired, already confirmed, released) return `False`.
- `release(hold_id: int, t: int) -> bool` - if the hold exists and is active at `t`: it is cancelled, its units become available again, return `True`. Otherwise return `False`.
- `available(item: str, t: int) -> int` - units on hand (after confirmed holds were removed) minus the units of all holds on that item that are active at `t`. Unknown item: 0.

Example with `d = HoldDesk({"bolt": 5}, 10)`:
`d.hold("bolt", 3, 0)` -> 1; `d.hold("bolt", 3, 1)` -> None; `d.available("bolt", 5)` -> 2; `d.hold("bolt", 2, 5)` -> 2; `d.available("bolt", 9)` -> 0; `d.available("bolt", 10)` -> 3 (hold 1 has just expired); `d.confirm(1, 10)` -> False; `d.confirm(2, 14)` -> True; `d.available("bolt", 100)` -> 3.""" + _TAIL,
    "reference": _REF_C39,
    "tests": r'''
_s = {"bolt": 5, "nut": 1}
d = HoldDesk(_s, 10)
assert d.available("bolt", 0) == 5 and d.available("gear", 0) == 0 and d.hold("gear", 1, 0) is None
assert d.hold("bolt", 3, 0) == 1 and d.hold("bolt", 3, 1) is None
assert d.available("bolt", 5) == 2 and d.hold("bolt", 2, 5) == 2
assert d.available("bolt", 9) == 0 and d.available("bolt", 10) == 3
assert d.confirm(1, 10) is False and d.release(1, 10) is False
assert d.confirm(2, 14) is True and d.confirm(2, 14) is False and d.release(2, 14) is False
assert d.available("bolt", 14) == 3 and d.available("bolt", 100) == 3
assert d.hold("nut", 1, 100) == 3 and d.available("nut", 100) == 0 and d.hold("nut", 1, 101) is None
assert d.release(3, 105) is True and d.available("nut", 105) == 1 and d.release(3, 105) is False and d.confirm(3, 106) is False
assert d.confirm(99, 106) is False and d.release(0, 106) is False
assert d.hold("bolt", 4, 106) is None and d.hold("bolt", 3, 106) == 4 and d.available("bolt", 115) == 0
assert d.hold("bolt", 3, 116) == 5 and d.confirm(5, 125) is True and d.available("bolt", 999) == 0
assert _s == {"bolt": 5, "nut": 1}
e = HoldDesk({"pin": 2}, 1)
assert e.hold("pin", 2, 7) == 1 and e.confirm(1, 8) is False and e.hold("pin", 2, 8) == 2 and e.confirm(2, 8) is True and e.available("pin", 8) == 0
''',
    "wrong": _mut(_REF_C39, 't < hold["t"] + self._ttl', 't <= hold["t"] + self._ttl'),
})


_REF_C40 = r'''
class TickScheduler:
    def __init__(self):
        self._now = 0
        self._tasks = {}        # name -> [next_time, every, add_sequence]
        self._seq = 0

    def add(self, name, at, every=None):
        if at < self._now:
            raise ValueError("cannot schedule in the past")
        self._seq += 1
        self._tasks[name] = [at, every, self._seq]

    def cancel(self, name):
        return self._tasks.pop(name, None) is not None

    def run_until(self, t):
        if t < self._now:
            raise ValueError("time cannot go backwards")
        fired = []
        while True:
            due = [(v[0], v[2], name) for name, v in self._tasks.items() if v[0] <= t]
            if not due:
                break
            at, _, name = min(due)
            fired.append((at, name))
            if self._tasks[name][1] is None:
                del self._tasks[name]
            else:
                self._tasks[name][0] = at + self._tasks[name][1]
        self._now = t
        return fired

    def pending(self):
        return sorted(self._tasks)
'''

ITEMS.append({
    "id": "C40",
    "kind": "class",
    "difficulty": "hard",
    "entry_point": "TickScheduler",
    "prompt": r"""Write a Python class `TickScheduler` - a scheduler driven by an explicit clock. A new scheduler has current time 0 and no tasks.

- `add(name: str, at: int, every=None)` - schedule the task `name` to fire at time `at`. If `at` is earlier than the current time, raise `ValueError` (`at` equal to the current time is allowed). If `every` is given it is a positive integer and the task repeats: each time it fires at some time x it is scheduled again for x + every. Without `every` the task fires once and is then removed. If a task with this name is already scheduled, the new call replaces it completely (new time, new `every`), and the task counts as newly added for the tie rule below.
- `cancel(name: str) -> bool` - remove the task; return `True` if it was scheduled, `False` otherwise.
- `run_until(t: int) -> list[tuple[int, str]]` - if `t` is earlier than the current time, raise `ValueError` (and change nothing). Otherwise fire every scheduled firing whose time is <= `t`, in order of firing time, including the further firings of repeating tasks that also fall at or before `t`. Firings at the same time are ordered by when their task was (most recently) added with `add`: earlier-added task first. Return the list of `(firing_time, name)` in firing order, and set the current time to `t`.
- `pending() -> list[str]` - names of the tasks currently scheduled, sorted alphabetically.

Example:

    s = TickScheduler()
    s.add("a", 5, every=10); s.add("b", 15); s.add("c", 5)

`s.run_until(15)` returns `[(5, "a"), (5, "c"), (15, "a"), (15, "b")]`; afterwards `s.pending()` is `["a"]` (next firing at 25). If you then call `s.add("d", 25)` and `s.add("a", 25)`, `s.run_until(30)` returns `[(25, "d"), (25, "a")]` (the re-added "a" now counts as added after "d", and no longer repeats).""" + _TAIL,
    "reference": _REF_C40,
    "tests": _RAISES + r'''
s = TickScheduler()
s.add("a", 5, every=10); s.add("b", 15); s.add("c", 5)
assert s.pending() == ["a", "b", "c"] and s.run_until(4) == []
assert s.run_until(15) == [(5, "a"), (5, "c"), (15, "a"), (15, "b")]
assert s.pending() == ["a"]
assert _raises(s.run_until, 14) and _raises(s.add, "z", 14) and s.pending() == ["a"]
s.add("d", 25); s.add("a", 25)
assert s.run_until(30) == [(25, "d"), (25, "a")] and s.pending() == []
s.add("r", 30, every=3); s.add("x", 33)
assert s.run_until(30) == [(30, "r")] and s.pending() == ["r", "x"]
assert s.cancel("x") is True and s.cancel("x") is False and s.cancel("nope") is False
assert s.run_until(37) == [(33, "r"), (36, "r")]
assert s.cancel("r") is True and s.run_until(1000) == [] and s.pending() == []
u = TickScheduler()
u.add("z", 0, every=4); u.add("m", 4, every=2); u.add("b", 8)
assert u.run_until(8) == [(0, "z"), (4, "z"), (4, "m"), (6, "m"), (8, "z"), (8, "m"), (8, "b")]
u.add("z", 10)
assert u.run_until(12) == [(10, "m"), (10, "z"), (12, "m")] and u.pending() == ["m"]
assert TickScheduler().run_until(0) == [] and TickScheduler().pending() == []
''',
    "wrong": _mut(_REF_C40, "due = [(v[0], v[2], name) for name, v in self._tasks.items() if v[0] <= t]",
                  "due = [(v[0], 0, name) for name, v in self._tasks.items() if v[0] <= t]"),
})


# ---------------------------------------------------------------------------
# Pilot items (throwaway, same style): CP1-CP3
# ---------------------------------------------------------------------------

_REF_CP1 = r'''
def watershed_sizes(heights):
    if not heights:
        return []
    h, w = len(heights), len(heights[0])

    def downhill(r, c):
        best = None
        for dr, dc in ((-1, 0), (0, 1), (1, 0), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and heights[rr][cc] < heights[r][c]:
                if best is None or heights[rr][cc] < heights[best[0]][best[1]]:
                    best = (rr, cc)
        return best

    counts = {}
    for r in range(h):
        for c in range(w):
            cur = (r, c)
            while True:
                nxt = downhill(cur[0], cur[1])
                if nxt is None:
                    break
                cur = nxt
            counts[cur] = counts.get(cur, 0) + 1
    rows = [(r, c, k) for (r, c), k in counts.items()]
    rows.sort(key=lambda x: (-x[2], x[0], x[1]))
    return rows
'''

ITEMS.append({
    "id": "CP1",
    "kind": "graph",
    "difficulty": "medium",
    "entry_point": "watershed_sizes",
    "prompt": r"""Write a Python function `watershed_sizes(heights: list[list[int]]) -> list[tuple[int, int, int]]`.

`heights` is a rectangular grid of integer terrain heights (a list of equal-length rows; possibly an empty list). Rain falling on a cell flows as follows:
- Look at the cell's 4 orthogonal neighbours that are STRICTLY lower than the cell. If there are none, the cell is a sink and the water stays there.
- Otherwise the water flows to the lowest of them. If several of those neighbours share the lowest height, the first one in the order north (row - 1), east (col + 1), south (row + 1), west (col - 1) is chosen.
- The water keeps flowing from cell to cell by the same rule until it reaches a sink.

For every sink, count the cells whose water ends in it (the sink itself included). Return a list of `(row, col, count)` tuples, one per sink, sorted by count descending, then row ascending, then col ascending. An empty grid returns `[]`.

Examples:
- `watershed_sizes([[1, 5, 1]])` returns `[(0, 2, 2), (0, 0, 1)]` (the middle cell has two equally low neighbours and east comes before west).
- `watershed_sizes([[3, 2, 3], [2, 1, 2], [3, 2, 3]])` returns `[(1, 1, 9)]`.""" + _TAIL,
    "reference": _REF_CP1,
    "tests": r'''
assert watershed_sizes([]) == []
assert watershed_sizes([[5]]) == [(0, 0, 1)]
assert watershed_sizes([[1, 2, 3]]) == [(0, 0, 3)]
assert watershed_sizes([[1, 5, 1]]) == [(0, 2, 2), (0, 0, 1)]
assert watershed_sizes([[1], [5], [1]]) == [(0, 0, 2), (2, 0, 1)]
assert watershed_sizes([[3, 2, 3], [2, 1, 2], [3, 2, 3]]) == [(1, 1, 9)]
assert watershed_sizes([[2, 2], [2, 2]]) == [(0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1)]
assert watershed_sizes([[1, 9, 2]]) == [(0, 0, 2), (0, 2, 1)]
assert watershed_sizes([[9, 8, 7], [2, 9, 6], [3, 4, 5]]) == [(1, 0, 9)]
assert watershed_sizes([[0, 5, 0], [5, 9, 5], [0, 5, 0]]) == [(0, 2, 4), (0, 0, 2), (2, 2, 2), (2, 0, 1)]
''',
    "wrong": _mut(_REF_CP1, "heights[rr][cc] < heights[best[0]][best[1]]", "heights[rr][cc] <= heights[best[0]][best[1]]"),
})


_REF_CP2 = r'''
def stock_tag(name, qty, unit_cents):
    if qty < 0 or unit_cents < 0:
        raise ValueError("negative input")
    label = "-".join(name.split()).upper()
    if len(label) > 10:
        label = label[:9] + "+"
    if qty == 0:
        return label + ": none"

    def money(cents):
        return "%d.%02d" % (cents // 100, cents % 100)

    if qty == 1:
        return label + " @ " + money(unit_cents)
    return "%s x%d @ %s = %s" % (label, qty, money(unit_cents), money(qty * unit_cents))
'''

ITEMS.append({
    "id": "CP2",
    "kind": "parsing",
    "difficulty": "medium",
    "entry_point": "stock_tag",
    "prompt": r"""Write a Python function `stock_tag(name: str, qty: int, unit_cents: int) -> str` that formats a shelf tag.

1. If `qty < 0` or `unit_cents < 0`, raise `ValueError`.
2. Label: remove leading/trailing whitespace from `name`, replace every run of whitespace inside it by a single hyphen `-`, and convert to upper case. If the label is then longer than 10 characters, keep its first 9 characters and append `+`.
3. Money is written as whole units, a dot, and exactly two digits of cents, with no thousands separators: 5 -> `0.05`, 123456 -> `1234.56`.
4. Result:
   - `qty == 0`: `LABEL: none`
   - `qty == 1`: `LABEL @ UNIT`
   - `qty >= 2`: `LABEL xQTY @ UNIT = TOTAL` where TOTAL is `qty * unit_cents` as money.

Examples:
- `stock_tag("  brass hinge ", 3, 250)` returns `"BRASS-HIN+ x3 @ 2.50 = 7.50"`.
- `stock_tag("bolt", 1, 5)` returns `"BOLT @ 0.05"`.""" + _TAIL,
    "reference": _REF_CP2,
    "tests": _RAISES + r'''
assert stock_tag("  brass hinge ", 3, 250) == "BRASS-HIN+ x3 @ 2.50 = 7.50"
assert stock_tag("bolt", 1, 5) == "BOLT @ 0.05"
assert stock_tag("bolt", 0, 5) == "BOLT: none"
assert stock_tag("wing  nut", 12, 1999) == "WING-NUT x12 @ 19.99 = 239.88"
assert stock_tag("abcdefghij", 2, 100) == "ABCDEFGHIJ x2 @ 1.00 = 2.00"
assert stock_tag("abcdefghijk", 1, 0) == "ABCDEFGHI+ @ 0.00"
assert stock_tag("a\tb\n c", 2, 123456) == "A-B-C x2 @ 1234.56 = 2469.12"
assert _raises(stock_tag, "bolt", -1, 5) and _raises(stock_tag, "bolt", 1, -5)
assert stock_tag("long name here", 0, 1) == "LONG-NAME+: none"
''',
    "wrong": _mut(_REF_CP2, 'label = label[:9] + "+"', 'label = label[:10] + "+"'),
})


_REF_CP3 = r'''
class RingLog:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._entries = []
        self._total = 0

    def add(self, msg):
        self._total += 1
        if self._entries and self._entries[-1][0] == msg:
            self._entries[-1][1] += 1
            return
        self._entries.append([msg, 1])
        if len(self._entries) > self._capacity:
            del self._entries[0]

    def dump(self):
        return [m if k == 1 else "%s (x%d)" % (m, k) for m, k in self._entries]

    def total(self):
        return self._total
'''

ITEMS.append({
    "id": "CP3",
    "kind": "class",
    "difficulty": "medium",
    "entry_point": "RingLog",
    "prompt": r"""Write a Python class `RingLog` - a bounded log that collapses immediate repeats.

- `RingLog(capacity: int)` - maximum number of entries kept. `capacity < 1` raises `ValueError`.
- `add(msg: str)` - if the log is not empty and `msg` is equal to the message of the MOST RECENT entry, that entry's repeat count goes up by 1 and no new entry is created. Otherwise a new entry with count 1 is appended; if the log then holds more than `capacity` entries, the oldest entry is dropped. (Only the most recent entry is compared - an equal message further back does not matter.)
- `dump() -> list[str]` - the entries, oldest first: just the message if its count is 1, otherwise the message followed by a space and `(xN)`, e.g. `"disk full (x3)"`.
- `total() -> int` - the number of `add` calls made so far (dropped entries and repeats all count).

Example: after `r = RingLog(3)` and adding "a", "a", "b", "a": `r.dump()` is `["a (x2)", "b", "a"]` and `r.total()` is 4. After also adding "c": `r.dump()` is `["b", "a", "c"]`.""" + _TAIL,
    "reference": _REF_CP3,
    "tests": _RAISES + r'''
r = RingLog(3)
assert r.dump() == [] and r.total() == 0
for _m in ("a", "a", "b", "a"):
    r.add(_m)
assert r.dump() == ["a (x2)", "b", "a"] and r.total() == 4
r.add("c")
assert r.dump() == ["b", "a", "c"] and r.total() == 5
r.add("c"); r.add("c")
assert r.dump() == ["b", "a", "c (x3)"] and r.total() == 7
r.add("b")
assert r.dump() == ["a", "c (x3)", "b"]
o = RingLog(1)
o.add("x"); o.add("y")
assert o.dump() == ["y"]
o.add("y")
assert o.dump() == ["y (x2)"] and o.total() == 3
assert _raises(RingLog, 0) and _raises(RingLog, -2)
t = RingLog(2)
t.add("p"); t.add("q"); t.add("p"); t.add("q")
assert t.dump() == ["p", "q"] and t.total() == 4
''',
    "wrong": _mut(_REF_CP3, "        if self._entries and self._entries[-1][0] == msg:\n            self._entries[-1][1] += 1\n            return\n",
                  "        for entry in self._entries:\n            if entry[0] == msg:\n                entry[1] += 1\n                return\n"),
})


def _self_check(verbose=False):
    import time
    ok = 0
    problems = []
    seen_ids = set()
    for item in ITEMS:
        iid = item["id"]
        errs = []
        if iid in seen_ids:
            errs.append("duplicate id")
        seen_ids.add(iid)
        for key in ("id", "kind", "difficulty", "entry_point", "prompt", "reference", "tests", "wrong"):
            if key not in item:
                errs.append("missing key " + key)
        if not item["prompt"].rstrip("\n").endswith(
                "Reply with one Python code block containing the complete solution. Standard library only."):
            errs.append("prompt tail missing")
        if item["entry_point"] not in item["prompt"]:
            errs.append("entry point not named in prompt")
        n_asserts = sum(1 for line in item["tests"].splitlines() if line.startswith("assert "))
        if not 8 <= n_asserts <= 15:
            errs.append("assert count %d outside 8..15" % n_asserts)
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
            print("%s %-8s %-9s asserts=%2d %.3fs %s" % (
                iid, item["kind"], item["difficulty"], n_asserts, dt, "; ".join(errs) or "ok"))
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
