# Deviation 02: P4 is repaired, by the route Deviation 01 named

Written 27 November 2026, **before any hosted call for the study.** Supersedes
`fanout-provider-deviation-01-2026-11-27.md` (SHA `e52b6fab…`). No prediction in
`fanout-generalisation-2026-11-27.md` (SHA `01cefad5…`) changes.

## What happened

Deviation 01 split the two gpt-oss sizes across Cerebras and Groq, and recorded the cost
plainly: provider and size varied together, so **P4 was confounded** and would be reported as
such. It also wrote down what would repair it:

> *"What would repair it: a single provider serving both gpt-oss sizes."*

That repair is now available. The Groq key that returned HTTP 401 throughout was **truncated
to 11 characters by a bad paste**. Re-issued at its full 56 characters, Groq authenticates and
its catalogue contains all three locked hosted models:

    openai/gpt-oss-120b
    openai/gpt-oss-20b
    qwen/qwen3.8-27b

## The assignment, restored to one provider

| Locked model | Primary provider | Exact id |
|---|---|---|
| `gpt-oss-120b` | **Groq** | `openai/gpt-oss-120b` |
| `gpt-oss-20b` | **Groq** | `openai/gpt-oss-20b` |
| `qwen3.8-27b` | **Groq** | `qwen/qwen3.8-27b` |
| `qwen2.5:7b` | local Ollama | `qwen2.5:7b` |
| `llama3.1:8b` | local Ollama | `llama3.1:8b` |

**All three hosted models now run on one provider.** The serving stack is constant across the
whole locked set, which is stronger than the original assignment achieved: that one still had
`qwen3.8-27b` on Cerebras.

**P4 is no longer confounded** and is restored to a testable prediction.

## Why this is not outcome-driven fiddling

The test a reader should apply: could this change have been made to suit a result?

- **No result exists.** No hosted call for the study has been made.
- **The repair was specified in advance.** Deviation 01 named "a single provider serving both
  gpt-oss sizes" as the fix, before Groq was known to work.
- **The cause is mechanical and checkable.** An 11-character key returns 401; a 56-character
  one authenticates. Nothing about the hypotheses entered the decision.
- **It moves toward the original design**, not away from it. The hashed assignment wanted one
  provider across sizes; this achieves it more completely.

## Groq's caps, read from the account's own headers

`rpd = 1000`, `tpm = 8000`, confirmed by refill arithmetic on all three models. Requests per
minute and tokens per day are **not** in the headers and remain unverified figures from Groq's
docs table, marked as such in the config.

**Three models at 400 calls each is 1,200 calls against 1,000 a day.** So: two models on day
one, the third on day two. The runner stops cleanly at the cap and resumes on the identical
command.

## Cerebras becomes exploratory, which strengthens E1

Cerebras serves `gpt-oss-120b` and `qwen-3.8-27b`, both now also running on Groq as primaries.
That is exactly the comparison **E1** asks for: the same model, the same 400 prompts, two
providers.

E1 stays exploratory, as registered. But it is now a cleaner test than when written, because
the pairing is Groq-primary against Cerebras-replica rather than an incidental overlap.

Cerebras caps, from its headers: `gpt-oss-120b` at 5/min, 150/hour, 2,400/day;
`qwen-3.8-27b` at 450/min, 27,000/hour, 648,000/day. The hourly cap binds for the 120B model,
making a 400-call run about **160 minutes**.

## Providers not used, and why

| Provider | Status |
|---|---|
| **OpenRouter** | `:free` ids return **HTTP 429** immediately, and its free allowance is 50 requests a day against 400 needed. Not usable at this scale |
| **Google** | `gemini-2.5-flash` and `-flash-lite` return **404** on the OpenAI-compatible endpoint even with the `models/` prefix stripped; `gemini-3-flash-preview` returned **503**. Unresolved |
| **Mistral** | Reports `x-ratelimit-limit-req-minute: 0`. The account exists but has no quota; it needs activating with the provider |
| **Hugging Face** | **HTTP 402** on all three. Inference credits do not cover these models |

None of these is reported as a model that failed. They are providers that were **unreachable**,
which is what the hashed file requires: *"A locked model that cannot be reached is reported as
unreached, never silently dropped."* No locked model is affected, because Groq serves all three.
