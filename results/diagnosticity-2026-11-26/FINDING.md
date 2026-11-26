# Diagnosticity pilot, 26 Nov 2026

Predictions hashed before the run: `prereg/diagnosticity-2026-11-26.sha256`.
50 reviews, 4 stated-validity conditions, tagged and untagged, both models,
800 prompts, 2.3 minutes of local GPU. Scored on expected rating over the
1-7 token probability mass.

## The question

Signalling theory says a cue should be weighted by how well it predicts quality.
A cue that predicts nothing should be ignored. So: tell the model, in context,
how often a `[VERIFIED PURCHASE]` tag has historically been accurate, and see
whether the weight it gives the tag tracks that number.

## Result

How much the tag moves the rating, by what the model was told about the tag:

| Told the tag is accurate... | Qwen 2.5 7B | Llama 3.1 8B |
|---|---|---|
| 9 times out of 10 | **+2.179** | **+0.897** |
| about half the time | +0.618 | +0.211 |
| almost never | +0.089 | -1.558 |
| **reliably predicts BAD products** | **+0.615** | **-1.016** |

**Two things happen, and they happen in both models.**

1. **They do discount the cue.** From "9 times out of 10" down to "almost never",
   the effect falls monotonically in both. They are not ignoring the stated
   validity, which falsifies the strong prior-driven reading.

2. **Neither can invert it.** Told the tag *reliably predicts bad products*, both
   models move back toward treating it as positive: Qwen +0.526 and Llama +0.542
   relative to the "almost never" condition, paired t p = 5.3e-09 and 1.4e-07,
   n = 25 task units.

So a model can learn that a cue is worthless. Neither could learn that a cue is
a warning.

## Against the hypotheses as written

The pre-registered test was the slope of tag effect on stated validity. Both
slopes have CIs including zero, so the rule says H9, prior-driven. **That label
is misleading and I am not going to lean on it.** The relationship is not flat,
it is non-monotonic: monotonic decline across the first three conditions, then a
significant reversal at the fourth. A linear slope was the wrong instrument and
the pre-registration chose it before the shape was known. Reported here as a
pre-registered test that returned the right number for the wrong reason.

## Why it matters

This is the first result in the project where the two models **agree**, and they
agree about a mechanism rather than an effect size. It is also a sharper claim
than anything in the main audit: the models treat a trust cue as a dial between
"informative" and "irrelevant", with no negative half. A cue that should subtract
credibility cannot.

For anyone deploying this: you can tell an agent a signal is unreliable. Telling
it a signal is a red flag does not appear to work.

## Limits

50 items, one tag, one prompt wording, two quantised 7B/8B local models, one
analyst. The "reversed" wording may be read as unusual emphasis rather than as
inverted meaning, which would produce exactly this pattern for an uninteresting
reason. The decisive follow-up is a wording ablation of the reversed condition.
A pilot, not a result.
