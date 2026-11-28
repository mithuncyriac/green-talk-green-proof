# What the providers actually did

Written 28 November 2026, from the fan-out result files themselves. Every figure
here is a count over `results/fanout/fanout_*.csv`, so it is re-derivable with
`python scripts/dedupe_fanout.py --check` and a column count.

---

## In short

- **Cerebras returns token logprobs. Groq does not.** That was the open question
  and it is settled.
- **But Cerebras does not return them reliably.** On `qwen-3.8-27b` the logprobs
  flicker on and off call by call: 65 of the first 175 calls came back without
  them, scattered rather than in a block.
- **That breaks an assumption in the pre-registration**, which routes
  logprob-less models to the secondary analysis. It anticipated whole models
  being in or out, not one model's rows splitting at random. Section 3.
- **A hosted model disagreed with itself** on 13 of 175 repeated identical
  prompts, 7.4%, against 0.25% to 0.75% for the local models run back to back.
- **Nothing here changes the Green Talk article**, which uses the two local
  models only.

---

## 1 · Scoring mode by model

| Model | Rows | logprob | emitted_only | error |
|---|---|---|---|---|
| `ollama / llama3.1-8b` | 400 | **400** | 0 | 0 |
| `ollama / qwen2.5-7b` | 400 | **400** | 0 | 0 |
| `groq / gpt-oss-120b` | 400 | 0 | **400** | 0 |
| `groq / gpt-oss-20b` | 400 | 0 | **400** | 0 |
| `cerebras / gpt-oss-120b` | 400 | **397** | 1 | 2 |
| `cerebras / qwen-3.8-27b` | 175 so far | 110 | **65** | 0 |

Groq is consistent in refusing logprobs. The two local models are consistent in
returning them. Cerebras is the interesting one and not in a good way.

## 2 · The three bad rows on `cerebras / gpt-oss-120b`

Out of 400, three are unusable and they are in the file rather than hidden:

| task | condition | mode | what happened |
|---|---|---|---|
| 3 | placebo | `emitted_only` | the reply came back empty, so there was no token to score |
| 4 | effort | `error` | `ERROR_RETRIES`, every retry exhausted |
| 4 | placebo | `error` | `ERROR_RETRIES`, every retry exhausted |

So this model contributes **397 usable rows of 400**, not 400. Any analysis
pooling it should say 397.

## 3 · The flicker, and why it matters more than the count

`cerebras / qwen-3.8-27b` does not fail to return logprobs. It returns them
most of the time and silently omits them the rest, interleaved call by call:

```
logprob x11  emitted_only x1  logprob x1  emitted_only x2  logprob x6
emitted_only x2  logprob x2  emitted_only x2  logprob x1  emitted_only x4 ...
```

**37% of calls, in no pattern this file can see.**

The pre-registration's rule is that models returning no logprobs enter the
secondary analysis only. That rule assumed a model is either a logprob model or
it is not. Here one model is both, call by call, and applying the rule literally
splits a single model's 400 rows between the primary and the secondary analysis
on a basis that has nothing to do with the stimuli.

**Three options, and the choice has to be written down before the numbers are
looked at:**

1. **Model-level**: if any row from a model lacks logprobs, the whole model goes
   to the secondary analysis. Conservative, loses 110 good rows.
2. **Row-level**: each row goes where its own scoring mode puts it. Keeps
   everything, but the primary analysis then rests on a non-random subset of a
   model's items, and nobody can say what selects them.
3. **Re-ask**: re-run the 65 and keep only cells where logprobs were returned on
   a defined number of attempts. Costs calls, and it is the only option that
   ends with a clean denominator.

Nothing here picks one. It is a pre-registration deviation and belongs in
`prereg/` with a date on it, not in a results note.

## 4 · A test-retest sample nobody designed

Two `fanout_run.py` processes wrote `fanout_cerebras_gpt-oss-120b.csv` at the
same time on 27 November, so 175 cells were asked twice, hours apart, at the
same settings. That is a defect in how the runs were launched and it produced
the only repeat-measurement data in this project.

| | |
|---|---|
| Repeated cells | 175 |
| Same printed rating | 162 |
| Different printed rating | **13, 7.43%** |
| Identical expected rating | 160 |
| Different expected rating | 14 |

Figures and eight example disagreements: `repeats_cerebras_gpt-oss-120b.json`.
The repeat rows themselves: `repeats_cerebras_gpt-oss-120b.csv`.

**For comparison**, the two local models run back to back on one Ollama binary
differed on 0.25% to 0.75% of printed ratings. So the same instability is
roughly ten times larger on the hosted model.

**The honest limit on that comparison.** The local test was two passes back to
back on one binary with the weights pinned. This one is two passes hours apart
against a provider whose backend is not visible, so routing, batching or a
model update could all contribute and none of them can be ruled out from here.
It is a reason to measure your own retest rate on a hosted model, not a
published property of this one.

## 5 · What this does not touch

The Green Talk article uses `ollama / llama3.1-8b` and `ollama / qwen2.5-7b`
only. None of the above changes a number in it. The article's determinism
passage now cites the 7.4% figure as a contrast, and that is the only crossing
point.
