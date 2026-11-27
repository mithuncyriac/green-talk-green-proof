# Provider assignment for the fan-out, fixed before any hosted call

Written 27 November 2026, **after** `fanout-generalisation-2026-11-27.md` (SHA `01cefad5…`)
was hashed and **before** any hosted model was called. This file changes no prediction. It
fixes one operational choice that could otherwise be made after seeing results.

Hashed separately so the record is clean: the predictions and this assignment are two dated
documents, not one document edited twice.

## The problem this solves

The hashed prediction file locks a **model set**: `qwen2.5:7b` and `llama3.1:8b` locally, plus
`openai/gpt-oss-120b`, `openai/gpt-oss-20b` and `qwen/qwen3.8-27b` hosted. It was written
assuming one provider, Groq.

Key discovery on 27 November changed that: **five providers answered, and the same locked
models are reachable through more than one of them.**

| Locked model | Reachable via |
|---|---|
| `gpt-oss-120b` | OpenRouter, Hugging Face, Cerebras |
| `gpt-oss-20b` | OpenRouter, Hugging Face |
| `qwen3.8-27b` | Cerebras (as `qwen-3.8-27b`) |

So "run the locked model" is now ambiguous, and the ambiguity is the kind that gets resolved
after the fact in whichever direction suits the result. It is resolved here instead.

## The assignment

**Primary provider per locked model.** These rows, and only these, enter P1 to P5.

| Locked model | Primary provider | Exact id |
|---|---|---|
| `gpt-oss-120b` | **OpenRouter** | `openai/gpt-oss-120b` |
| `gpt-oss-20b` | **OpenRouter** | `openai/gpt-oss-20b` |
| `qwen3.8-27b` | **Cerebras** | `qwen-3.8-27b` |
| `qwen2.5:7b` | local Ollama | `qwen2.5:7b` |
| `llama3.1:8b` | local Ollama | `llama3.1:8b` |

**Why OpenRouter is primary for the two gpt-oss models:** it returned the largest catalogue
(441 models, 430 usable), so a single provider covers both, which keeps the serving stack
constant across the two sizes. Holding the provider fixed while varying size is what P4, the
scaling prediction, actually requires.

**Why Cerebras for qwen3.8-27b:** it is the only one of the five that offers it.

**Groq, if its key arrives,** does not displace any assignment above. It becomes an additional
provider under the exploratory heading below.

## Everything else is exploratory, and labelled so

The five providers expose roughly fifteen usable models between them. Every model that is not
in the table above is **exploratory**: reported separately, never pooled into P1 to P5, and
never used to adjust a conclusion about them. This is the same rule the hashed file already
states for models added after it.

## One genuinely new question this creates, registered now

The same locked model is reachable on three providers. **The same weights served by different
infrastructure need not behave identically** — quantisation, sampling defaults and serving
stack all vary, and none of that is visible to the caller.

**Prediction E1, exploratory and labelled as such:** `gpt-oss-120b` run through OpenRouter,
Hugging Face and Cerebras on the identical 400 prompts will **not** produce identical condition
effects. Specifically, at least one pairwise difference in `effort − ai` across providers will
exceed 0.05 on the expected-rating scale.

*Falsifier:* all three providers agree within 0.05, which would mean provider choice is
immaterial and the model id is a sufficient description of what was run.

**Why it is worth having.** If E1 holds, then "we evaluated gpt-oss-120b" is an incomplete
statement of method throughout this literature, and pinning the model id is not enough. That is
a methodological claim about everyone's evaluations, not just mine. It costs 800 extra calls.

E1 is exploratory because it was conceived after the main predictions were hashed. It does not
enter P1 to P5 and will not be presented as confirmatory.

## What this file cannot do

- It cannot change P1 to P5. Those are sealed in `01cefad5…`.
- It cannot make a post-hoc provider swap legitimate. If a primary provider becomes
  unreachable, the substitution is reported as a deviation, with the date and the reason.
- It is hashed locally and not registered externally at the time of writing, the same
  qualification that applies to every other pre-registration in this project.
