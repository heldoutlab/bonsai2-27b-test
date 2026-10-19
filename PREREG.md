# Pre-registration — Bonsai 2 27B "near-lossless"

Written 2026-10-05, before any test model was downloaded or run.
Brief: `../../briefs/2026-10-05-brief.md`. Decisions below were delegated to Claude ("use recommended decisions"); each can be overwritten by the author up to the moment the main run starts, and not after.

## Claim under test
"Bonsai 2 27B is near-lossless: a 5.9 GB, 1.76-bit file keeps 98.2% of full-precision Qwen3.8 27B."
Vendor's model card (read 2026-10-05): 14-benchmark thinking-mode average FP16 86.32, UD-Q4_K_XL 85.18, Bonsai 2 84.78. So the vendor also claims Bonsai 2 is within 0.4 points of the 4-bit file used here as arm A.

## Arms
All three run on the same binary, the PrismML llama.cpp fork, release `prism-b10754-2459f68`, macOS arm64 (sha256 of the archive: e411342cf017a9a3399cc242d45176acc025ecae1ec426c678bc6a9120432036).

| Arm | File | Size | sha256 |
|---|---|---|---|
| A | unsloth/Qwen3.8-27B-GGUF `Qwen3.8-27B-UD-Q4_K_XL.gguf` | 17.56 GB | 3f227079…8bc8b01e |
| B | prism-ml/Ternary-Bonsai-2-27B-gguf `Ternary-Bonsai-2-27B-PTQ1_0.gguf` | 5.95 GB | 53107f53…1fe33ee3 |
| C | unsloth/gemma-4-12b-it-GGUF `gemma-4-12b-it-IQ4_XS.gguf` | 6.38 GB | b0037d0e…0cd76774 |

Full hashes are in `harness/config.py`; the runner refuses to start if a file does not match.

Changes from the brief, and why:
- **Arm A is UD-Q4_K_XL, not Q4_K_M.** It is the exact 4-bit file in the vendor's own table, so its distance from FP16 (−1.14 points) and from Bonsai 2 (+0.40) are the vendor's numbers, not an assumption. FP16 (53.8 GB) does not fit in 32 GB.
- **Arm C is IQ4_XS (6.38 GB).** The brief left the size unverified. No 4-bit Gemma 4 12B file is as small as 5.95 GB; IQ4_XS is the closest (Q4_K_M is 7.12 GB). The control therefore has a 7% size advantage.
- **If the fork cannot run arm A or C** (to be learned in the pilot), that arm runs on stock llama.cpp (Homebrew build 10964) and the write-up says so.

## Items
120 items written for this test and never published: 40 multi-step reasoning (one checkable answer), 40 small coding tasks (hidden unit tests), 40 multi-step tool-call tasks (mock tools, graded on final state). Text only. Plus 10 throwaway pilot items used only for timing.
Every answer key is verified by code: a brute-force solver per reasoning item; a reference solution that passes and a wrong solution that fails for each coding item; a reference action sequence that passes and a trap sequence that fails for each tool task.
Item file hashes are recorded at the bottom of this file once the items are frozen. No item is edited after the first test model sees it. If an item is later found to be broken (ambiguous or wrong key), it is dropped for all arms and listed in the write-up; it is never re-keyed in favour of an arm.

## Settings
- System prompt "You are a helpful assistant"; chat template from the GGUF (`--jinja`); context 32768; one slot.
- Arms A and B: vendor card sampler — temperature 1.0, top_p 0.95, top_k 20, min_p 0.05. Arm C: Gemma card sampler — temperature 1.0, top_p 0.95, top_k 64 — with thinking enabled.
- Main run: reasoning effort `medium`, 8192 output tokens per turn, seed 1001. An answer cut off by the token limit counts as wrong; the number of such cases is reported per arm.
- Tool tasks: at most 20 assistant turns (raised from 12 before any run: reference solutions need up to 8 calls); reasoning is not echoed back into the conversation (vendor guidance).
- xhigh check: 12 items (4 per family) on arms A and B at `xhigh`, 16384 output tokens.
- Noise re-run: 40 items (13 reasoning, 13 coding, 14 tools) on arms A and B with seed 2002.
- Subsets and the 90-item fallback are the first items of each family in sha256-of-id order, fixed in `harness/config.py`.
- The 8192-token cap may be changed once, after the pilot and before the main run, if the pilot shows more than 1 in 10 pilot answers truncated on arm A. The change is recorded here.
- If the pilot projects more than 60 machine-hours in total, the main run uses the 90-item fallback (30 per family).

## Scoring
- Reasoning: last `ANSWER:` line of the visible reply, normalised, exact match.
- Coding: last Python code block, run with the hidden tests under Python 3.12, 10 s limit, no network.
- Tools — strict: final state correct and no repair was needed. Lenient: final state correct, where the runner may (a) repair malformed argument JSON by fixed rules, (b) recover a call printed as text, (c) retry once after a server error. The brief proposed hand repair; this replaces it with fixed automatic rules so no judgement enters after the run. Both scores are reported; the rule below uses strict.
- Headline numbers: percent correct per family and overall; paired difference A−B with a stratified bootstrap 95% interval (10,000 resamples); retention B÷A.
- Noise floor: for each family and overall, the larger of arm A's and arm B's absolute change in percent correct between seed 1001 and seed 2002 on the re-run items.

## Pass/fail rule (fixed)
Let gap = arm A − arm B in percentage points, strict scoring, main run.
- **"Not near-lossless"** if the overall gap is 10 points or more and its 95% interval excludes zero.
- **"No large loss found"** if the overall gap is 5 points or less and the gap in every family is 10 points or less.
- **"Not resolved"** otherwise. This includes an overall gap between 5 and 10 points.
- Separately, **"worth running over a same-size conventional model"** if arm B beats arm C by more than the noise floor in at least two of the three families.

What this design cannot do: at n = 120 the interval on the gap is roughly ±8–9 points. It can detect a loss of about 10 points. It cannot confirm the vendor's 1.5-point figure, and "no large loss found" must not be written up as "98.2% confirmed". Retention (B÷A) is reported because it is the vendor's framing, but no rule depends on it: its interval is too wide at this n.
The xhigh check has 12 items and can only show a gross change in direction; it is reported as descriptive.

## Prediction
Drafted by Claude on 2026-10-05 at the author's delegation. Author: replace this with your own before the main run if you disagree.

**What do you expect to happen?**
Bonsai 2 lands 4 to 9 points below the 4-bit file overall, so the pre-registered outcome is most likely "not resolved", with "no large loss found" second. The gap is largest on tool-call tasks under strict scoring (the vendor's own known-issues file lists malformed tool calls) and smallest on coding. Lenient scoring closes part of the tool gap but not all of it. Bonsai 2 beats Gemma 4 12B overall and in at least two families.

**What result would prove you wrong?**
An overall gap of 2 points or less, or of 15 points or more; a coding gap larger than the tool-call gap; or Gemma 4 12B matching or beating Bonsai 2 overall.

## Corrections to the brief found while preparing
- The model card's averages are 86.32 (FP16) and 84.78 (Bonsai 2); the 85.4 / 83.9 pair in the brief is from the launch post. Both give 98.2%.
- The "17–20 point gaps on agentic benchmarks" in SHORTLIST.md is not supported by the model card: the only agentic row is BFCL v3, 76.74 → 74.92.
- The vendor measured with min_p 0.0, and recommends 0.05; this test uses the recommended 0.05.
- `reasoning_effort: "high"` is not accepted by the model's template; only `medium` and `xhigh` are used.

## Frozen item hashes
Frozen 2026-10-05, before any test model was run (sha256):

    65e6c51a062ac17ba6d7bf22afa8998ddf823ec126d3c0d578c2152712a7e0cd  items/reasoning_items.py
    3b4c82eec05387ea174b3253d932685faf4c889f2a46b29a9d1b6cf40d864f84  items/reasoning_solvers.py
    59c796170a2048866b7b3c8e92ec4bf2107d69a59b857074040b1469f3bb0218  items/coding_items.py
    147311302224466f33a1ef5629cee1b9a0bf58c1b48c2b94b2bcb260da3f9c4d  items/tool_items.py
    acca17f0984d159eb4ac2b99f9a8b275746fb0304d199cc806f5585ef3e842a6  harness/config.py
    a8d706bb61f2ef34da6cf66f50ff218e1f6d804e85ef56bed22845e29a2128b8  harness/grade.py
    ec4499656416c7a19c9cd9bb7d0529149b9122d01cd7e83745ff49e4aa7847e6  harness/run.py
    fd34bad76a7f75bb93457a842cb29555d100c1e3d9c64ebd039daf63baded331  harness/analyze.py

A later change to `harness/` that does not alter scoring (for example a crash fix) is listed under deviations with its new hash.

## Pilot results and changes made before the main run (2026-10-06)
Pilot = 10 throwaway items per arm, `medium` effort, 8192-token cap. No test item had been shown to any model when these changes were made.

| Arm | Correct | Truncated at 8192 | Mean tokens | Mean seconds per item |
|---|---|---|---|---|
| B (Bonsai 2) | 10/10 | 0 | 1,161 | 137 |
| C (Gemma 4 12B) | 8/10 | 2 | 3,646 | 219 |
| A (Qwen3.8 27B 4-bit) | see below | | | |

- **Output cap raised from 8192 to 16384 tokens per turn, for every arm.** The rule above tied this change to arm A's pilot. It is made instead on arm C's pilot: Gemma has no effort setting, thinks longer, and lost 2 of 10 pilot items to the cap, which would have handicapped the control. One cap for all arms keeps the comparison even. Arms A and B rarely approach either cap, so this does not favour either.
- The fork runs the standard Gemma GGUF, so arm C stays on the same binary as arm B.
- `harness/config.py` after this change: sha256 5b1837a4cc2020f2065cadcde4e5c66c4684bee802303267262ee1e4cb9b5847
- The effort field reaches the model (outputs differ between `medium` and `xhigh`); on two pilot items the direction of the token change was mixed.

## Deviations after freezing
1. **One item dropped for every arm: T26.** Its prompt says the old notes file "should end up in the same folder as notes_old.txt"; no such file exists, and the intended meaning was "in the same folder, renamed notes_old.txt". All three models stopped and asked. Dropped under the broken-item rule above; all three arms had scored it wrong, so no gap changes (A−B stays 1.7 points). Analysis is on 119 items. The original 120-item report is kept as `results/report_before_drop.json`.
2. **`harness/analyze.py` changed after the run** to read `results/dropped_items.json`. No scoring logic changed. New sha256: aaf0b48e0a312ed275a66f808887478ac8b09119f68f183a482606d9009d708d
3. **Arm B's main run was interrupted once** (the terminal session ended at item 97 of 120 on 2026-10-06) and resumed. Completed items were kept; output is repeatable for a fixed seed.
4. **Arm A's pilot ran with the 16384-token cap**, not 8192, because the cap had already been raised (see above). 10/10 correct, none truncated, 194 s per item.
5. Two other items that both 27B arms failed were checked and kept: R30 (key re-derived independently, BACC) and T24 (the schema accepts null for "no sprint"; both Qwen-derived arms sent the string "null", Gemma sent null and passed).
