# Independent verification, 26 Nov 2026

Both scripts rerun from scratch into a clean directory, hours after the runs they
check, on the same machine and the same model files.

## diagnosticity.py — REPRODUCES

Tag effect on the rating, by what the model was told the tag is worth:

| | Qwen original | Qwen rerun | Llama original | Llama rerun |
|---|---|---|---|---|
| accurate 9 in 10 | +2.1788 | +2.1785 | +0.8975 | +0.8975 |
| accurate about half | +0.6182 | +0.6180 | +0.2113 | +0.2113 |
| almost never accurate | +0.0890 | +0.0895 | -1.5577 | -1.5577 |
| **reliably marks bad** | **+0.6147** | **+0.6148** | **-1.0157** | **-1.0157** |

Llama is bit-identical on all four. Qwen's largest drift is 0.0005. The finding —
both models turning back up at the reversed condition — holds in both runs.

## label_run2.py — REPRODUCES on Qwen, NOT COMPLETED on Llama

Qwen, original v2 run against the rerun:

| | original | rerun |
|---|---|---|
| AI label, emitted | -0.1500 | -0.1500 |
| effort label, emitted | +0.0800 | +0.0800 |
| placebo, emitted | -0.0500 | -0.0500 |
| AI label, expected rating | -0.1161 | -0.1158 |
| calibration | 97.5% | 97.5% |
| within-run determinism | 0.75% | 0.75% |

Emitted ratings identical to four decimals. Expected ratings within 0.0006. The
pre-registered placebo check still holds, with the AI label doing 3.0x the work of
the meaningless one.

**Llama's half was abandoned at 259 of 1681 rows and the partial file deleted.**
Not a result, and not a failure of the script. Ollama stopped honouring
`keep_alive`, so every single call paid a full model load: measured at **42.5 s to
load against 2.1 s to evaluate**. At that rate the run needs about 19 hours instead
of 13 minutes. Nothing was resident in VRAM between calls when checked via
`/api/ps`.

Worth recording for its own sake: on this stack, a benchmark's wall-clock cost can
move by two orders of magnitude for reasons that have nothing to do with the model
or the prompts. Any timing claim needs the load state recorded alongside it, and
`run_meta.json` does not currently capture that.

## What this verification does and does not establish

It shows the numbers are stable on **this machine with these model files**. It is a
re-run, not an independent reproduction: same hardware, same author, same stack. A
stranger running this on their own machine remains the check that matters, and that
needs the repo to be public.
