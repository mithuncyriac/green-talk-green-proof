#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A5: does the silent-pass shape appear in real frontier-agent traces?

Predictions are hashed in prereg/a5-silent-pass-in-the-wild-2026-11-27.sha256
(SHA 8f01ed3a...) and were written before any outcome was computed.

My own number, by fault injection on an agent I built: injected hard errors terminate the
run in 44 of 44 cases; injected plausible-but-wrong tool values complete in all 44 and are
silently wrong in 33, 75 per cent. One agent, 44 runs, and a 30 per cent fault rate chosen
for signal rather than estimated from production. A5 asks whether the shape recurs where
nobody injected anything.

DATA. AgentLogs (Richards et al. 2026, arXiv:2608.29204), HF risenlab/agentlogs, CC-BY-4.0.
Only the agent_sessions config: 3 parquet parts, about 243 MB. The agent_session_logs config
is 63 GB against 57 GB free and is deliberately NOT used, so nothing here depends on
message-level content.

THE CLASSIFICATION RULE IS IN CODE, ON PURPOSE. The pre-registration promised that each
distinct `state` value would be classified from its literal name alone, before any
cross-tabulation with `error`. STATE_RULE below is that promise in executable form: it
matches on the name and nothing else, it was committed before the data was read, and any
later edit to it shows up in git. The full classification table is printed so a reader can
disagree with it.

Downloads land in data_agentlogs/, which is gitignored and holds no scripts. Run this with
plain `python` (not `-I`), because pandas and pyarrow live in user site-packages.
"""
import io
import json
import os
import subprocess
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data_agentlogs")
OUT = os.path.join(ROOT, "results", "a5-2026-11-27")
REPO = "risenlab/agentlogs"
CONFIG = "agent_sessions"
UA = "green-talk-a5/1.0"

# Name-only classification, fixed before the data was read. Order matters: the first
# matching bucket wins, so failure words are checked before completion words to stop
# "completed_with_errors" being read as a success.
STATE_RULE = [
    ("terminal-failure", ("fail", "error", "cancel", "abort", "timeout", "timed_out",
                          "rejected", "crash")),
    ("terminal-success", ("complet", "success", "succeed", "merged", "done", "finished")),
    ("non-terminal", ("queue", "pend", "progress", "running", "in_progress", "created",
                      "started", "active", "waiting", "stale", "unknown")),
]


def classify(state):
    if state is None or (isinstance(state, float) and pd.isna(state)):
        return "null"
    s = str(state).strip().lower()
    if not s:
        return "null"
    for bucket, words in STATE_RULE:
        if any(w in s for w in words):
            return bucket
    # Deliberately NOT guessed. The prereg says an ambiguous name goes to non-terminal and
    # the ambiguity gets reported.
    return "non-terminal (unmatched, reported)"


def wilson(k, n, z=1.96):
    """Wilson 95% interval. Proportions near 0 or 1 are the whole point here, and the
    normal approximation is wrong exactly there."""
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / float(n)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def pct(t):
    p, lo, hi = t
    return "%5.1f%% [%4.1f, %4.1f]" % (100 * p, 100 * lo, 100 * hi)


def sh(url):
    return subprocess.run(["curl", "-sSL", "-A", UA, url], capture_output=True,
                          encoding="utf-8", errors="replace", timeout=120).stdout or ""


def fetch():
    os.makedirs(DATA, exist_ok=True)
    tree = json.loads(sh("https://huggingface.co/api/datasets/%s/tree/main/%s" % (REPO, CONFIG)))
    files = sorted(f["path"] for f in tree if f.get("type") == "file"
                   and f["path"].endswith(".parquet"))
    if not files:
        sys.exit("no parquet files listed for %s/%s" % (REPO, CONFIG))
    local = []
    for path in files:
        dest = os.path.join(DATA, os.path.basename(path))
        local.append(dest)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            print("  have   %-34s %7.1f MB" % (os.path.basename(path),
                                               os.path.getsize(dest) / 1e6))
            continue
        url = "https://huggingface.co/datasets/%s/resolve/main/%s" % (REPO, path)
        print("  fetch  %-34s ..." % os.path.basename(path), end="", flush=True)
        r = subprocess.run(["curl", "-sSL", "-A", UA, "-o", dest, url], timeout=1800)
        if r.returncode != 0 or not os.path.exists(dest):
            sys.exit("\ndownload failed for %s" % path)
        print(" %7.1f MB" % (os.path.getsize(dest) / 1e6))
    return local


def main():
    print("A5 - silent-pass shape in real agent traces")
    print("prereg SHA 8f01ed3af2271d67c937d2b917767e79df5d99cb597366e0bcecd459d7a354f2\n")
    print("Fetching %s / %s (CC-BY-4.0):" % (REPO, CONFIG))
    files = fetch()

    cols = ["id", "state", "error", "log_found", "pull_request_artifact", "model",
            "premium_requests", "completed_at"]
    frames = []
    for f in files:
        frames.append(pd.read_parquet(f, columns=cols))
    d = pd.concat(frames, ignore_index=True)
    print("\nloaded %s sessions, %d columns" % (f"{len(d):,}", len(d.columns)))

    # --- the classification table, printed before anything is crossed with `error` ---
    d["bucket"] = d["state"].map(classify)
    print("\n=== every distinct `state` value, and its name-only classification ===")
    tab = (d.groupby(["state", "bucket"], dropna=False).size()
             .reset_index(name="n").sort_values("n", ascending=False))
    for _, r in tab.iterrows():
        print("  %-28s -> %-34s %s" % (str(r["state"])[:28], r["bucket"], f"{r['n']:,}"))
    print("\n  bucket totals:")
    for b, n in d["bucket"].value_counts().items():
        print("    %-38s %s" % (b, f"{n:,}"))

    nulls = int((d["bucket"] == "null").sum())
    d = d[d["bucket"] != "null"].copy()
    print("\n  excluded for a null state: %s   analysed: %s" % (f"{nulls:,}", f"{len(d):,}"))

    # --- the two groups ---
    def has_err(x):
        return x is not None and not (isinstance(x, float) and pd.isna(x)) and str(x).strip() != ""
    d["err"] = d["error"].map(has_err)
    d["has_pr"] = d["pull_request_artifact"].map(
        lambda x: x is not None and not (isinstance(x, float) and pd.isna(x)))

    err = d[d["err"]]
    noerr = d[~d["err"]]
    print("\n  error-carrying sessions: %s   no recorded error: %s"
          % (f"{len(err):,}", f"{len(noerr):,}"))

    # --- predictions ---
    print("\n=== scored against the hashed predictions ===")
    a = wilson(int((err["bucket"] == "terminal-failure").sum()), len(err))
    print("  A5a  error-carrying AND terminal-failure   %s   (predicted >50%%)  %s"
          % (pct(a), "HOLDS" if a[0] > 0.50 else "FAILS"))

    b = wilson(int((err["bucket"] == "terminal-success").sum()), len(err))
    print("  A5b  error-carrying AND terminal-success   %s   (predicted  >5%%)  %s"
          % (pct(b), "HOLDS" if b[0] > 0.05 else "FAILS"))

    c = wilson(int((~noerr["has_pr"]).sum()), len(noerr))
    print("  A5c  no error AND no pull request          %s   (predicted >20%%)  %s"
          % (pct(c), "HOLDS" if c[0] > 0.20 else "FAILS"))

    gap = abs(100 * b[0] - 75.0)
    print("  A5d  gap from my injected 75%%              %5.1f points        (predicted >20)  %s"
          % (gap, "HOLDS" if gap > 20 else "FAILS"))

    # --- context, not predictions ---
    print("\n=== context (not pre-registered, reported for completeness) ===")
    lf = wilson(int((~d["log_found"].fillna(False)).sum()), len(d))
    print("  sessions with no log found                 %s" % pct(lf))
    print("  overall terminal-success share             %s"
          % pct(wilson(int((d["bucket"] == "terminal-success").sum()), len(d))))
    print("  overall sessions producing a pull request  %s"
          % pct(wilson(int(d["has_pr"].sum()), len(d))))
    top = d["model"].value_counts(dropna=True).head(6)
    if len(top):
        print("  most common models:")
        for m, n in top.items():
            print("    %-44s %s" % (str(m)[:44], f"{n:,}"))

    os.makedirs(OUT, exist_ok=True)
    res = {
        "prereg_sha256": "8f01ed3af2271d67c937d2b917767e79df5d99cb597366e0bcecd459d7a354f2",
        "dataset": {"repo": REPO, "config": CONFIG, "licence": "CC-BY-4.0",
                    "note": "agent_session_logs (63 GB) deliberately not used"},
        "n_sessions_loaded": int(len(d) + nulls),
        "n_excluded_null_state": nulls,
        "n_analysed": int(len(d)),
        "n_error_carrying": int(len(err)),
        "n_no_error": int(len(noerr)),
        "state_classification": [
            {"state": None if pd.isna(r["state"]) else str(r["state"]),
             "bucket": r["bucket"], "n": int(r["n"])} for _, r in tab.iterrows()],
        "A5a_error_and_failure": {"p": a[0], "ci": [a[1], a[2]], "holds": bool(a[0] > 0.50)},
        "A5b_error_and_success": {"p": b[0], "ci": [b[1], b[2]], "holds": bool(b[0] > 0.05)},
        "A5c_noerror_and_no_pr": {"p": c[0], "ci": [c[1], c[2]], "holds": bool(c[0] > 0.20)},
        "A5d_gap_from_injected_75": {"gap_points": gap, "holds": bool(gap > 20)},
    }
    with io.open(os.path.join(OUT, "a5_results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print("\nwrote %s" % os.path.join(OUT, "a5_results.json"))


if __name__ == "__main__":
    main()
