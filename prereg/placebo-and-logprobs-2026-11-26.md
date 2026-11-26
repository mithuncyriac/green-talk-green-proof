# Pre-registration: placebo label, expected-rating scoring, and a clean determinism test

Written 26 Nov 2026, before the run. SHA-256 logged in
`prereg/placebo-and-logprobs-2026-11-26.sha256`. Hashed locally, not on OSF.

## Why this run exists

Three objections to the 2 Nov AI-label audit, raised in blind review and not
answerable from the existing data.

1. **No control label.** The audit compared `[Made with AI]` against no label. Any
   bracketed string adds tokens and visual structure. Without a meaningless label
   there is no way to separate "the model reacts to AI authorship" from "the model
   reacts to a label being present at all".
2. **The emitted integer discards the distribution.** A probe on 26 Nov found Llama
   emitting 2 where the probability mass implied 3.07, and Qwen's top-k containing
   full-width digits. The reported ceiling asymmetry (Qwen parks 50% at 7, Llama
   never emitted a 7) may be an artefact of reading one sampled token.
3. **The reproduction is confounded.** The 2 Nov and 25 Nov runs straddle an Ollama
   upgrade: `ollama.exe` is dated 9 Nov 2026 and its `lib` directory 11 Nov 2026,
   while both model manifests are dated 1 Nov 2026. So the 3.3% divergence in
   helpfulness ratings cannot be attributed to nondeterminism rather than to the
   engine changing underneath.

## Design

Unchanged from 2 Nov except where stated: same 100 reviews, same stimuli file, same
two models, temperature 0, seed 1, `num_ctx` 6144.

- **Added condition:** `placebo` = `[Label: Submitted on a Tuesday]`. Carries no
  information about authorship, effort or product use. Four conditions total.
- **Added measurement:** `logprobs: true`, `top_logprobs: 10`. At the first rating
  token, digits are NFKC-normalised and an expected rating is computed over the
  mass on 1-7. The share of returned top-k mass landing on a digit is recorded per
  row, so rows where the expected value rests on a renormalised sliver are visible
  rather than hidden.
- **Added test:** `--repeat` runs each rating prompt twice back to back against one
  binary in one session.

## Hypotheses

- **H5 (placebo is inert).** |mean(placebo) − mean(none)| < 0.14 rating points in
  both models, where 0.14 is the size of the Qwen AI-label effect reported on
  2 Nov. Tested on both the emitted integer and the expected rating.
- **H6 (the sign flip is not a scale artefact).** Scored on expected ratings, the
  AI-label effect stays negative for Qwen and positive for Llama, and the pooled
  label-by-model interaction keeps a 95% CI excluding zero.
- **H7 (within-binary determinism).** Fewer than 1% of rating prompts return a
  different integer across the two back-to-back passes.

## Decision rules, fixed in advance

- **If H5 fails** — the placebo moves ratings by 0.14 or more in either model — the
  AI-label result is reinterpreted as label-presence sensitivity. The headline
  changes to that, and the phrase "AI disclosure" comes out of the title.
- **If H6 fails** — the sign flip does not survive expected-rating scoring — the
  2 Nov result is reported as a scale-use artefact. That supersedes the current
  headline and is published in its place.
- **If H7 holds** (near-zero divergence within one binary) — the 25 Nov "temperature
  0 is not determinism" claim is **withdrawn** and restated as engine drift across
  an Ollama upgrade, which is a different and less interesting claim.
- **If H7 fails** (≥1% divergence within one binary) — nondeterminism is real on this
  stack, and the 23-day figure stands as an upper bound that also includes drift.

## What this run cannot settle

Still two models, still quantised 7B/8B, still keyword-coded review tiers elsewhere
in the project, still one analyst. A placebo and a distribution do not fix n=2 at the
model level. No claim about LLMs in general follows from this run.
