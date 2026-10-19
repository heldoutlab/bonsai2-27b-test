# Pre-registration, round 2 — Bonsai 2 27B on harder items

Written 2026-10-08, after round 1 was complete and before any round-2 item was shown to either test model.
Round 1 (`PREREG.md`, `results/report.json`) stands as reported: 4-bit 95.8%, Bonsai 2 94.1%, gap 1.7 points [−2.5, 6.7], "no large loss found". Round 2 does not replace it; both are reported.

## Why a second round
Round 1 was too easy. The 4-bit model scored 95.8%, so about eight of 119 items could separate the two models at all. Round 2 asks the same question where there is room for a loss to show.

## What is the same as round 1
Arms A (Qwen3.8 27B UD-Q4_K_XL) and B (Bonsai 2 PTQ1_0): same files, same hashes, same binary, same sampler, same system prompt, reasoning effort `medium`, 16,384 output tokens per turn, seed 1001, same graders, same scoring definitions, same bootstrap.

## What is different
- **No Gemma arm.** Round 1 answered that question and Gemma was the slowest arm.
- **Items:** 90 new items (30 reasoning, 30 coding, 30 tool-call), written to be harder, using round 1's results only as a difficulty guide (which round-1 items the 27B models failed). No round-1 item is reused or varied.
- **Difficulty check on an outside model.** 18 extra calibration items of the same kind (6 per family) are run on Muse Glimmer 30B Q4_K_M, a model that is not in the comparison. The 90 test items are shown to no model before the main run. Target: the outside model scores between 30% and 75% on the calibration items. If it scores above 75%, the item set is made harder (and re-verified) before freezing; if below 30%, easier. Calibration items are never scored for the test models.
- **Tool tasks:** up to 30 assistant turns (tasks need 9–16 calls). No task requires a JSON null argument: in round 1 both Qwen-derived arms sent the string "null", which says nothing about the question.
- **Noise re-run:** 18 items (6 per family), seed 2002, both arms.
- **xhigh check:** 18 items (9 reasoning, 9 coding), reasoning effort `xhigh`, 32,768 output tokens, context 49,152, both arms. Round 1's 12-item xhigh subset was confounded by the 16,384 cap. No tool tasks: round 1 showed no xhigh difference there.
- **Time rule:** if the calibration run projects more than 60 machine-hours in total, the main run uses 60 items (the first 20 per family in sha256-of-id order).

## Pass/fail rule (unchanged)
Gap = arm A − arm B in percentage points, strict scoring, main run.
- "Not near-lossless": overall gap of 10 points or more and its 95% interval excludes zero.
- "No large loss found": overall gap of 5 points or less and no family gap above 10.
- "Not resolved": otherwise.

Added for the xhigh check (descriptive only, 18 items): report accuracy, truncations and tokens for both arms; call it "a difference worth a dedicated test" if arm A leads by 4 or more of 18 items.

Limits known in advance: with 90 items near 60% accuracy the interval on the gap is about ±9–10 points. This round can catch a loss of roughly 10 points or more. It cannot confirm 1.5.

Coding answers are re-graded after the runs, from the saved replies, with the machine idle (`harness/regrade.py`); the idle result is the score. Several round-2 hidden tests are timing-sensitive (inputs sized so that a naive solution exceeds the 10-second limit), and during a run the model server competes for the CPU. Both results are kept and any item whose result changes is listed.

Broken items: same rule as round 1. An item found ambiguous or mis-keyed is dropped for both arms and listed; never re-keyed in favour of an arm. Any item both arms fail is inspected for defects before the result is reported.

## Prediction
Drafted by Claude on 2026-10-08, again at the author's delegation ("use recommended decisions"). The round-1 prediction, also Claude's, was wrong. Author: replace this before the main run if you disagree.

**What do you expect to happen?**
The 4-bit model scores 55–75% and Bonsai 2 lands 2 to 8 points below it, so the outcome is "no large loss found" or "not resolved". The gap is largest on reasoning and smallest on tool calls. At `xhigh` with the larger budget the two are within 2 items of each other out of 18.

**What result would prove you wrong?**
A gap of 10 points or more; Bonsai 2 ahead overall; a tool-call gap larger than the reasoning gap; or the 4-bit model ahead by 4 or more items at `xhigh`.

## Frozen hashes
Frozen 2026-10-08 16:20 IST, before either test model saw a round-2 item (sha256):

    d4a535ba925e63e9c8f26edc2d448aacaaa1ce47e5e62734a73ff11959849ca9  items_r2/reasoning_items.py
    5955af0c16d2ba979be5f0cd0dac32a2d2fb03ff2716cbdf3f18babd98471e1d  items_r2/reasoning_solvers.py
    686c0c48fb41f2a2702ffb65565336ba6bad5993db6332fc2a9c9690ef3eef90  items_r2/coding_items.py
    809f4f2bdeb59af15d25036f55907de40b01d9fbbcb37cd54ca4846c7df165aa  items_r2/tool_items.py
    fe02f643ed411a325cb050723c8d688e1ea3d3ee1289ccb4b7ab32669a8034bc  harness/config.py
    a8d706bb61f2ef34da6cf66f50ff218e1f6d804e85ef56bed22845e29a2128b8  harness/grade.py
    66f74117557dc4ff9339cb6fa8a51eed871753ee55b1792eece7ec4e0f26f74a  harness/run.py
    aaf0b48e0a312ed275a66f808887478ac8b09119f68f183a482606d9009d708d  harness/analyze.py
    261703c6e13128b838fbe06399ab8d1aade436c277f4c2b90cf79a637e6e9a9f  harness/regrade.py
    059a3eb8ffde5743d31660afc9e8eac4b2c5718bb75f503e5a87cf6e66a55969  queue_r2.sh

`grade.py` is unchanged from round 1.

## Calibration result and changes before the main run
Outside model (Muse Glimmer 30B Q4_K_M, stock llama.cpp) on the 18 calibration items: **13 of 18 correct (72%)** — reasoning 5/6, coding 3/6, tool calls 5/6; no truncations; mean 5,272 tokens and 962 seconds per item. That is inside the 30–75% target, so the item set is frozen unchanged. It is near the top of the range, so the test models may again score high; the set is kept as the rule says.

Time projection from the calibration speeds: about 57 machine-hours (main runs about 38), under the 60-hour limit, so the full 90 items are used.

## Deviations after freezing
1. **No item dropped.** All 15 items that both arms failed were inspected. Seven were token-cap truncations on both arms. For the rest: R06's key was re-derived by independent brute force (755); R20 and R10 were solved by one or both arms in the re-run or at `xhigh`; R01, R26 and R27 have code-verified keys and the arms gave different wrong answers; C26's failing assert tests a case the prompt specifies (a recipe with fee 0 and no ingredients costs 0); C05 fails a stated step-limit boundary; in T06 both arms reversed the genuine (lowest-id) charge, against the prompt.
2. **Idle re-grade changed nothing.** Every coding answer in every run got the same result idle as live.
3. **Total time was about 94 machine-hours, not the projected 57.** Test items ran about 30% longer than calibration items on arm A, arm B wrote more tokens than arm A, and the `xhigh` items averaged about 19,500 tokens. The 60-hour rule was applied to the projection before the run, as written; items were not cut mid-run.
4. **The Mac ran out of battery during arm A's `xhigh` run** (hibernated 14:17 to 20:35 on 2026-10-11) and resumed in place. Output is unaffected (it depends only on the seed); the wall-clock time recorded for xhigh item C03 on arm A is inflated by the outage.
5. `LOG.md`, `SHORTLIST.md` and the drafts folder were also edited by the weekly brief task and by the author during the run; none of the frozen files changed (hashes re-checked 2026-10-10 and 2026-10-13).
