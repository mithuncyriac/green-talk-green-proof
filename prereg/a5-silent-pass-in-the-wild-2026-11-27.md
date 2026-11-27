# Pre-registration: does the silent-pass rate appear in real frontier-agent traces?

Written 27 November 2026, **before any outcome was computed.** The SHA-256 of this file is
logged in `prereg/a5-silent-pass-in-the-wild-2026-11-27.sha256`. Hashed locally, **not
uploaded to OSF**, so this is not pre-registration in the registered sense and will not be
described as such.

This is hypothesis **A5** of Paper A, *The Silent Pass*.

## The claim being tested

My own measurement, by fault injection on an agent I built: injected hard errors terminate the
run in **44 of 44** cases, while injected plausible-but-wrong tool values complete in all 44
and are **silently wrong in 33, 75 per cent**. Two seeded schedules disagree, 46 against 28
per cent.

That is one agent, one domain, 44 runs, and a 30 per cent injected fault rate **chosen for
signal rather than estimated from production**. A5 asks whether the phenomenon exists in
traces of real agents that nobody injected anything into.

## Data

**AgentLogs** (Richards, J. et al., 2026, arXiv:2608.29204), Hugging Face
`risenlab/agentlogs`, **CC-BY-4.0**, 5,714 downloads, last modified 26 November 2026.
Activity on GitHub's cloud coding-agent platform across public repositories, which the authors
state deliberately includes **failed executions** that earlier datasets omit.

Only the `agent_sessions` configuration is used: 3 parquet parts, about 243 MB. The
`agent_session_logs` configuration is 63 GB against 57 GB of free disk and is **not** used, so
nothing here depends on message-level content.

Fields relied on, confirmed from the schema before writing this file: `state`, `error`,
`log_found`, `pull_request_artifact`, `model`, `premium_requests`, `completed_at`.

## A definitional risk, stated before the fact

I have read the schema but **not the distribution of `state` values.** I therefore cannot name
the success states in advance. The rule fixed here instead:

- Each distinct `state` value will be classified as **terminal-success**, **terminal-failure**
  or **non-terminal** **from its literal name alone**, and the full classification table will
  be published with the result.
- The classification is written down **before** any cross-tabulation of `state` against
  `error`.
- An "error-carrying" session is one whose `error` field is non-null and not an empty string.

If a state name is genuinely ambiguous it goes to **non-terminal** and the ambiguity is
reported, because the alternative is choosing the reading that suits the prediction.

## Predictions

**A5a — loud failures dominate.**
Among error-carrying sessions, **more than 50 per cent** are in a terminal-failure state.
*Falsifier:* most error-carrying sessions are in a terminal-success state.

**A5b — the silent pass occurs in the wild.**
**More than 5 per cent** of error-carrying sessions are nonetheless in a terminal-success
state.
*Falsifier:* under 5 per cent. That would mean the phenomenon I measured by injection
describes my harness and not agent systems generally, and Paper A's central number would have
to be restated as a property of one agent.

**A5c — failure without any error record, which is the worse case.**
Among sessions with **no** recorded error, **more than 20 per cent** produced no
`pull_request_artifact`.
*Falsifier:* under 20 per cent, which would mean the error field is a reliable failure signal
on this platform and the silent-failure worry is overstated here.

**A5d — my own headline number does not transfer.**
The in-the-wild silent-pass share differs from my injected **75 per cent** by **more than 20
percentage points**.
*Falsifier:* it lands within 20 points of 75 per cent.
This predicts against my own result on purpose. A 30 per cent injected fault rate was chosen
to produce signal, so a matching rate in the wild would be a coincidence rather than a
confirmation, and I would rather say so in advance than be asked.

## Analysis

- Counts and proportions only. No model. **Wilson 95 per cent intervals** on every proportion.
- Every N reported, including the denominator for each proportion.
- The `state` classification table published in full.
- **No sampling.** The whole `agent_sessions` table is used.
- Sessions with a null `state` are excluded and counted.
- `log_found` is reported but not used as a filter, since a missing log is itself a candidate
  silent failure and filtering on it would select on the outcome.

## What this cannot show, in advance

- **This is one platform.** GitHub's cloud agent product, public repositories only.
- **`error` and `state` are the platform's own fields.** Whether a session was *substantively*
  wrong is not observable here; what is observable is whether the platform recorded a problem
  and whether the session nonetheless completed. That is a weaker construct than my injected
  measure and the write-up will say so rather than eliding it.
- **No ground truth.** A merged pull request is not a correct pull request.
- **Selection.** Public repositories on one platform, over whatever window the dataset covers.
- A5 therefore tests whether the *shape* of the finding recurs, not whether the number does,
  which is why A5d predicts the number will not.

## Command

    python scripts/a5_silent_pass.py
