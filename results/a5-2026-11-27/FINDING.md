# A5: the silent pass is invisible to platform telemetry, and that is the finding

Run 27 November 2026. Predictions hashed beforehand in
`prereg/a5-silent-pass-in-the-wild-2026-11-27.sha256`, SHA `8f01ed3a…`.

**Two of four predictions failed. One of those failures is a flaw in my own pre-registration,
and it is reported here rather than quietly dropped.**

---

## What was run

AgentLogs (Richards et al. 2026, arXiv:2608.29204), Hugging Face `risenlab/agentlogs`,
**CC-BY-4.0**. The `agent_sessions` table only: 3 parquet files, 243 MB. The 63 GB
`agent_session_logs` table was deliberately not used.

**635,886 sessions. 0 excluded for a null state.** Real frontier models, not a sandbox:

| Model | Sessions |
|---|---|
| `sweagent-capi:claude-sonnet-4.6` | 155,572 |
| `claude-sonnet-4.5` | 104,537 |
| `sweagent-capi:gpt-5.3-codex` | 59,223 |
| `sweagent-capi:claude-opus-4.6` | 32,441 |
| `sweagent-capi:gpt-5.4` | 27,145 |
| `sweagent-capi:claude-opus-4.5` | 10,982 |

State classification, by the keyword rule committed before the data was read:

| State | Bucket | n |
|---|---|---|
| `completed` | terminal-success | 582,289 |
| `cancelled` | terminal-failure | 25,450 |
| `failed` | terminal-failure | 25,064 |
| `timed_out` | terminal-failure | 2,426 |
| `queued` | non-terminal | 456 |
| `waiting_for_user` | non-terminal | 189 |
| `in_progress` | non-terminal | 12 |

## Scored against the hashed predictions

| | Prediction | Result | Verdict |
|---|---|---|---|
| **A5a** | >50% of error-carrying sessions in a terminal-failure state | **100.0%** [100.0, 100.0] | **HOLDS, and it is uninformative. See below** |
| **A5b** | >5% of error-carrying sessions in a terminal-success state | **0.0%** [0.0, 0.0] | **FAILS** |
| **A5c** | >20% of no-error sessions produced no pull request | **9.8%** [9.8, 9.9] | **FAILS** |
| **A5d** | the injected 75% differs from the in-the-wild share by >20 points | **75.0 points** against A5b, **65.2** against A5c | **HOLDS on either comparator** |

## A5a holds for the wrong reason, and A5b was untestable

The cross-tabulation I should have run before registering:

| State | no error | has error |
|---|---|---|
| `completed` | 582,283 | **6** |
| `cancelled` | 1,500 | 23,950 |
| `failed` | 1,300 | 23,764 |
| `timed_out` | 2,179 | 247 |

**`error` is not an independent signal on this platform. It is the failure label.** It is
populated on 90.6% of failure-state sessions and on 6 of 582,289 completed ones. So A5a could
hardly have come out below 99%, and **A5b could not have exceeded about 0.001% whatever agents
do.**

That is a design error in my pre-registration: I registered a test of something this dataset
cannot measure. I did not discover it by inspecting the data first, because the registration
rule forbade that, and the trade was worth it — the cost is one wasted hypothesis, and the
alternative is a hypothesis quietly reshaped after seeing the answer.

The error strings make the same point. The eight most common are *"The session was cancelled by
the user"*, *"Copilot has encountered an error"*, *"you've hit a rate limit"*, *"you've used up
the 300 premium requests"*, *"Changes were pushed to Copilot's branch while it was working"*,
*"an unknown Git error"* and *"had to stop work due to a timeout"*.

**Every one is an infrastructure or quota failure. Not one is a wrong answer.** The field
records when the run broke, never when the run finished and the output was wrong. Which is
exactly why the second kind is the dangerous kind.

## What the data does show, at scale

**57,179 sessions reached `state = completed` and produced no pull request. 9.8%.**

The platform says those succeeded. No error was recorded. Nothing came out. That is the closest
observable analogue to a silent pass in this dataset, and it is not a rounding error — it is
roughly 57,000 sessions across six frontier models.

Context, not pre-registered: overall terminal-success 91.6%, overall pull-request rate 90.2%,
and `log_found` false in 0.0% of sessions.

## The conclusion, which strengthens the method rather than the number

Three statements, in order of confidence:

1. **When this platform's agents break, they break loudly.** 100% of error-carrying sessions
   terminate in a failure state. GitHub's harness surfaces hard failures reliably, and that is
   a genuine positive result about a production system.
2. **The silent kind cannot be estimated from this telemetry at all.** A silent pass is an
   output that is wrong and unflagged. A field that is only written when the run breaks cannot
   see it. No volume of production logging fixes this, because the thing is defined by not
   being logged.
3. **So fault injection is not a weaker substitute for observational data. It is the only
   instrument that reaches this class of failure.** My 75% figure describes a failure mode that
   635,886 real sessions are structurally unable to report.

**A5d holds on either comparator**, which matters: the conclusion does not depend on which
number I compare against. 75 points against A5b's 0.0%, 65.2 against A5c's 9.8%. The injected
rate does not transfer, as predicted, and a 30% injected fault rate chosen for signal was never
going to match a production base rate.

## What this costs Paper A, honestly

- **The headline number stays local.** 33 of 44, 75%, is a property of one agent under a chosen
  fault rate. A5 does not generalise it and the paper must not imply otherwise.
- **A5 as registered is half a failure.** Two predictions failed, one of them because I tested
  an unmeasurable quantity.
- **The replacement claim is narrower and better defended:** the construct is unavailable in
  observational data, which is an argument for the method and against anyone claiming production
  telemetry is sufficient oversight.
- **What would settle it properly:** a dataset where agent outputs are independently judged for
  correctness, so "completed but wrong" is observable. AgentLogs is not that dataset. Whether
  one exists is the next search, and if it does not, that absence is itself worth reporting.

## Reproduce

    python scripts/a5_silent_pass.py

243 MB download, about 80 seconds end to end. Results in `a5_results.json` beside this file.
