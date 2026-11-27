# Deviation 01 from the provider assignment

Written 27 November 2026, **before any hosted call succeeded.** Logged because
`fanout-provider-assignment-2026-11-27.md` (SHA `52b788b3…`) says:

> *"If a primary provider becomes unreachable, the substitution is reported as a deviation,
> with the date and the reason."*

This is that report. No prediction changes. `fanout-generalisation-2026-11-27.md` (SHA
`01cefad5…`) is untouched.

## What changed

| Locked model | Assigned | Now | Reason |
|---|---|---|---|
| `gpt-oss-120b` | OpenRouter | **Cerebras** | OpenRouter returns **HTTP 402 Payment Required** on this id |
| `gpt-oss-20b` | OpenRouter | **Groq** | Same 402. Groq is the only remaining route |
| `qwen3.8-27b` | Cerebras | Cerebras | unchanged |
| `qwen2.5:7b`, `llama3.1:8b` | local Ollama | unchanged | already run |

## Why OpenRouter failed, precisely

Its `/models` endpoint lists 441 models, which is a **catalogue**, not an entitlement. Calling
`openai/gpt-oss-120b` returns 402: on OpenRouter only ids suffixed `:free` are free, and
**neither gpt-oss model has a `:free` variant**. The catalogue listing them was not evidence
they could be called, and treating a listing as permission was my error, caught by the first
real call rather than by reasoning.

## What this costs, stated plainly

**The assignment's stated rationale is now broken.** It read:

> *"Why OpenRouter is primary for the two gpt-oss models: … a single provider covers both,
> which keeps the serving stack constant across the two sizes. Holding the provider fixed
> while varying size is what P4, the scaling prediction, actually requires."*

**That property is lost.** `gpt-oss-120b` now runs on Cerebras and `gpt-oss-20b` on Groq, so
the 120B-to-20B comparison that P4 rests on varies **provider and size together**. Any
difference between them is confounded, and P4 cannot cleanly separate a scaling effect from a
serving-stack effect.

**P4 is therefore reported as confounded**, not as supported or refuted. That is the honest
reading and it is being written down now, before the numbers exist, rather than discovered in
the analysis.

**What would repair it:** a single provider serving both gpt-oss sizes. Hugging Face lists
both and currently returns 402; if its billing is resolved later, rerunning both sizes there
would give P4 a clean test, and that rerun would be reported as a second deviation.

## What this does not change

- P1, P2, P3 and P5 are unaffected. None of them compares across model sizes.
- E1, the exploratory provider-difference prediction, is **strengthened**: it asks whether the
  same model behaves differently on different infrastructure, and the fact that provider is now
  entangled with size in P4 is precisely why that question matters.
- The exploratory set is unchanged: every non-locked model stays exploratory.

## Provider status at the time of writing

| Provider | State |
|---|---|
| **Cerebras** | **Working.** `gpt-oss-120b` at 5 req/min, 2,400/day, 30,000 tokens/min. `qwen-3.8-27b` at 450 req/min, 648,000/day |
| **Groq** | Key re-issued at the correct length after a truncated paste returned 401. Untested at the time of writing |
| **OpenRouter** | 402 on the locked ids. Usable only for exploratory `:free` models |
| **Google** | Model ids needed the `models/` prefix stripped; pro models returned 429 immediately on their free quota. Flash models untested |
| **Mistral** | Reports a request limit of **0**: the account is not activated |
| **Hugging Face** | 402. Inference credits do not cover these models |
| **Ollama** | Both local models complete, 400 rows each |
