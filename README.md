# Bonsai 2 27B: is it near-lossless?

Everything behind the post [*Bonsai 2 really does retain 98.2% of the 4-bit Qwen3.8 27B’s score. Until the tasks get harder.*](https://heldoutlab.substack.com/p/bonsai-2-27b-tested-near-lossless): the pre-registrations, every task with its answer key, the test harness, and every raw model output.

Part of [Held Out Lab](https://heldoutlab.substack.com): independent tests of AI model claims, with the rules fixed before the run. [Subscribe](https://heldoutlab.substack.com/subscribe) to get the next test, or write to hello@heldoutlab.com.

**Result in brief.** PrismML's Bonsai 2 27B (5.95 GB, ternary) against Qwen3.8 27B at 4-bit (UD-Q4_K_XL, 17.6 GB), reasoning effort `medium`:

| | Tasks | 4-bit | Bonsai 2 | Gap (95% interval) | Pre-registered verdict |
|---|---|---|---|---|---|
| Round 1 | 119 | 95.8% | 94.1% | 1.7 points (−2.5 to 6.7) | No large loss found |
| Round 2, harder | 90 | 77.8% | 67.8% | 10.0 points (1.1 to 18.9) | Not near-lossless |

On 18 round-2 tasks at reasoning effort `xhigh` with a 32k-token budget, Bonsai 2 scored 14 and the 4-bit file 13 (descriptive only).

Tested October 2026 on a MacBook Pro (M1 Pro, 32 GB) with PrismML's llama.cpp build, release `prism-b10754-2459f68`.

## What is here

| Path | Contents |
|---|---|
| `PREREG.md`, `PREREG_R2.md` | Pre-registrations: arms, settings, the pass/fail rule, the prediction, frozen file hashes, pilot or calibration results, and every deviation |
| `items/`, `items_r2/` | All tasks: reasoning items with brute-force solvers, coding tasks with hidden tests, tool-call tasks with mock environments and final-state checks |
| `harness/` | Runner, graders, analysis and idle re-grader, as they stand after round 2 |
| `harness/round1_as_frozen/` | The round-1 versions of the three harness files that were later changed (see below) |
| `results/`, `results_r2/` | One JSON line per task and run with the full model output, plus run manifests (file hashes, server command, build) and `report.json` |
| `fetch.py`, `queue2.sh`, `queue_r2.sh` | Model download (hash-checked) and the unattended run queues |

Round 1 also has a Gemma 4 12B arm (same-size control) and a 10-task pilot per arm; round 2 has an 18-task calibration run on Muse Glimmer 30B, a model outside the comparison.

## Checking the frozen hashes

Each pre-registration lists sha256 hashes recorded before its main run.

```bash
grep -E '^    [0-9a-f]{64}  ' PREREG_R2.md | sed 's/^    //' | shasum -a 256 -c
```

All round-2 files match as they are. For round 1, the item files and `grade.py` match as they are. `run.py`, `analyze.py` and `config.py` were changed after round 1 to add a round-2 mode and the dropped-item list; their round-1 versions are in `harness/round1_as_frozen/` and match the round-1 hashes exactly, including `config_before_cap_change.py`, the version frozen before the pilot-driven output-cap change recorded in `PREREG.md`.

```bash
(cd harness/round1_as_frozen && shasum -a 256 *.py)
```

What the hashes prove: the files that produced these results are the files listed in the pre-registrations. What they cannot prove: when the hash lines were written. This repository was made public after both rounds ran.

## Re-running

Needs Python 3.12, about 30 GB of disk, and the PrismML llama.cpp release binary in `bin/` (not included; macOS arm64 archive sha256 `e411342cf017a9a3399cc242d45176acc025ecae1ec426c678bc6a9120432036`, from https://github.com/PrismML-Eng/llama.cpp/releases).

```bash
python3.12 fetch.py B C A            # model files, checked against PREREG.md hashes
cd harness
python3.12 run.py --arm B --run pilot
BONSAI_ROUND=2 python3.12 run.py --arm A --run main
BONSAI_ROUND=2 python3.12 analyze.py
```

Outputs repeat exactly for a fixed seed on the same build and hardware. Expect about 50 machine-hours for round 1 and 90 for round 2 on an M1 Pro.

## Notes

- The pre-registrations mention files from my working notes (a brief, a shortlist, a log) that are not part of this repository.
- Tasks, graders and test harness were written with help from Claude (Anthropic); I reviewed them, and every answer key is verified by code. Both predictions on file were drafted by Claude and left as written; the post says so.
- Model files are not included. Bonsai 2 27B: https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf. Qwen3.8 27B and Gemma 4 12B: the unsloth GGUF repositories named in `harness/config.py`.

## License

Code (`harness/`, `fetch.py`, the queue scripts, and the solver and environment code in `items*/`) is MIT-licensed; see `LICENSE`. Task texts, results and write-ups are CC BY 4.0.
