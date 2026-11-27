# Pre-registration: do the label-study results survive outside two 7B models?

Written 27 November 2026, **before any fan-out data exists.** The SHA-256 of this file is
logged in `prereg/fanout-generalisation-2026-11-27.sha256`. It is hashed locally and **not
uploaded to OSF**, so this is not pre-registration in the registered sense and will not be
described as such.

## The objection this answers

Every reviewer of this project named the same limitation: two quantised 7B/8B open models is
n = 2 at the model level, so nothing generalises. This machine has 8,192 MiB of VRAM and
cannot hold anything larger, so the test is the same study against hosted models through
`scripts/fanout_run.py`.

This file covers the **helpfulness half only** — 4 label conditions × 100 items = 400 calls
per model. The choice half costs 949 tokens a call against this half's 180 and is
pre-registered separately when it is run.

## What the pilot found, which is what is being tested

On `qwen2.5:7b` and `llama3.1:8b`, scored as expected ratings over token logprobs:

| Contrast | Qwen | Llama |
|---|---|---|
| `ai` − `none` | −0.14, CI [−0.22, −0.07] | +0.19, CI [0.09, 0.31] |
| `effort` − `ai` | +0.25, CI [0.16, 0.34] | +0.25, CI [0.14, 0.37] |
| `placebo` − `none` | −0.05 | +0.08 |

Human benchmark: Carney, Riveros & Tully (2026), *Made With AI: Consumer Engagement With
Social Media Containing AI Disclosures*, *Journal of Consumer Research*,
doi:10.1093/jcr/ucag013. Disclosures reduce engagement, and the channel is **reduced
parasocial connection** — a one-sided bond with a creator — not quality concerns, not AI
aversion. Effort signals soften the drop because effort feeds that bond.

A language model has no such bond. That asymmetry is what generates P2 and P3 below.

## Predictions

Each is directional and each names what would falsify it. "In every model" means every model
in the locked set that returns a parseable rating on at least 90% of its calls.

**P1 — the null label stays inert.**
`|placebo − none| < |ai − none|` in at least 80% of models.
*Falsifier:* the placebo moves ratings as much as or more than the AI label in most models.
Then the pilot's effect is label presence, not disclosure, and the headline is wrong.

**P2 — the effort channel transfers.**
`effort − ai > 0` in **every** model, and significant at α = .05 after Holm correction in at
least 80% of them.
*Falsifier:* the sign is inconsistent across models, or it fails significance in most.
P2 is the pilot's only result that survived the both-models rule, and it is the papers' own
moderation claim rather than mine, so it is the single most important line here.

**P3 — the disclosure penalty does not transfer consistently.**
`sign(ai − none)` is **not** the same across all models.
*Falsifier:* every model agrees in sign. That would mean the Qwen/Llama split was a
small-model artefact and a real, generalisable machine-side penalty exists — a better result
than the one predicted, and it would be reported as such.

**P4 — scale does not rescue it.**
Across the locked set spanning roughly 7B to 120B parameters, neither `|effort − ai|` nor
`sign(ai − none)` is monotone in parameter count.
*Falsifier:* a monotone trend in either. Then these are capacity limitations that scale away,
which is a different and more hopeful paper, and the claim becomes a statement about small
models only.

**P5 — logprob scoring earns its complexity.**
Within each model returning logprobs, the spread of condition effects computed on `ev_rating`
exceeds the spread computed on the emitted integer.
*Falsifier:* emitted integers are equally sensitive. Then the logprob machinery buys nothing
and should be dropped from the method.

## The model set, locked now

**Locked (the pilot, already run):** `qwen2.5:7b`, `llama3.1:8b`, local via Ollama.

**Locked (intended hosted):** `openai/gpt-oss-120b`, `openai/gpt-oss-20b`,
`qwen/qwen3.8-27b`.

**The rule that stops model-shopping:** any model added after this file is hashed is reported
**separately, as exploratory**, and does not enter P1 to P5. A locked model that cannot be
reached is reported as unreached, not quietly dropped.

**Exclusion:** a model is excluded only for returning an unparseable rating on more than 10%
of its calls, and the exclusion is reported with that rate.

## Analysis

- **Primary outcome:** expected rating over the token logprob distribution across 1–7,
  NFKC-normalised, as in `label_run2.py`. Available only where `score_mode == "logprob"`.
- **Secondary outcome:** the emitted integer. Available for every model, so it is what the
  cross-model comparison uses when a provider returns no logprobs.
- **Per model:** OLS of rating on condition dummies with `none` as base, item fixed effects,
  standard errors clustered by item. Holm across the three contrasts within each model.
- **Pooled:** rating ~ condition × model with item fixed effects and item-clustered errors,
  standardised within model, because models use the 1–7 scale differently and unstandardised
  comparison would confuse scale use with effect size.
- Two-sided tests, α = .05. Unparseable answers excluded and counted.
- **Models returning `emitted_only` enter the secondary analysis only.** Decided here so
  there is no choice about it after seeing the numbers.

## What this phase cannot say, stated in advance

- **No calibration gate.** The 40-item dominance check is part of the choice phase, not this
  one, so a model that cannot do the easy task is not excluded here. That is a real weakness
  of running the cheap half first, and the writeup says so.
- **One analyst**, as throughout. Review tiers come from keyword dictionaries with no second
  coder.
- **The effort label is confounded**: it signals effort *and* three months of use. Two cues,
  one string. P2 therefore tests whether *something* in that string transfers, not which cue.
  The wording ablation that separates them is a separate run and is not pre-registered here.
- Free-tier providers may log prompts. The stimuli are public Amazon Reviews 2023 text, so
  this costs nothing in confidentiality. This file is never sent to any provider.

## Stopping rule

The phase is complete when every locked model has 400 rows, or when access to a provider
ends. Partial models are reported with their n rather than extrapolated.

Run command, fixed here so it is not tuned later:

    python scripts/test_prompt_parity.py
    python scripts/fanout_run.py --kinds helpfulness
