#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Rerun the AI-label audit, and write the log build_findings.py needs.

    python scripts/rerun_label_audit.py
    python scripts/build_findings.py && python make_visuals.py

WHY THIS EXISTS

03-before-you-publish.md gives three commands for this rerun: two label_run.py
calls writing into results/rerun-mine/, then build_findings.py. Those commands do
not work, and they fail in the worst way.

build_findings.py only trusts a rerun directory that contains a rerun.log whose
text includes "rerun finished" (see its main, the rerun_dirs filter). label_run.py
does not write that log; the 25 November one was produced by a shell wrapper, and
the `real` / `user` / `sys` lines in it are bash `time` output.

So following the documented procedure would have written both CSVs, printed
nothing wrong, and left build_findings.py silently reading the OLD rerun. The gate
would have looked satisfied and the numbers would not have moved. A documented
procedure that quietly does nothing is the failure this whole project is about,
so it is fixed here rather than in a comment.

WHAT THIS DOES

  1. makes results/rerun-<today>/ , dated, because the loader takes the LAST
     directory in sort order and a date sorts meaningfully
  2. writes the log header with the stimuli file's sha256, so the rerun records
     which stimuli it ran against
  3. runs each model in turn, timing it, streaming the child's output
  4. writes the "rerun finished" line ONLY if every model completed, because a
     half-finished rerun that build_findings.py trusts is worse than none

It calls label_run.py as a subprocess rather than importing it, because that file
reads sys.argv at module level.
"""

import hashlib
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STIM = os.path.join(ROOT, "data_label", "label_stimuli.json")
MODELS = ["qwen2.5:7b", "llama3.1:8b"]


def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def main():
    if not os.path.exists(STIM):
        sys.exit("missing %s" % STIM)
    day = time.strftime("%Y-%m-%d")
    out_dir = os.path.join(ROOT, "results", "rerun-%s" % day)
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "rerun.log")

    sha = hashlib.sha256(open(STIM, "rb").read()).hexdigest()
    log = io.open(log_path, "w", encoding="utf-8", newline="\n")

    def say(line):
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()

    say("=== rerun started %s ===" % stamp())
    say("stimuli sha256: %s" % sha)
    say("models: %s" % ", ".join(MODELS))

    ok = True
    for model in MODELS:
        short = model.replace(":", "_").replace(".", "_")
        out_csv = os.path.join(out_dir, "04_label_audit_%s.csv" % short)
        say("--- %s ---" % model)
        t0 = time.time()
        rc = subprocess.call([sys.executable, os.path.join(HERE, "label_run.py"),
                              STIM, model, out_csv])
        dt = time.time() - t0
        if rc != 0:
            say("FAILED %s (exit %d) after %.1fs" % (model, rc, dt))
            ok = False
            break
        say("done %s %s" % (model, time.strftime("%H:%M")))
        say("")
        say("real\t%dm%.3fs" % (int(dt // 60), dt % 60))

    if ok:
        # The sentinel build_findings.py looks for. Written last, and only on a
        # clean sweep, so a broken rerun is never trusted.
        say("=== rerun finished %s ===" % stamp())
    else:
        say("=== rerun INCOMPLETE %s ===" % stamp())
    log.close()

    print("\nwrote %s" % log_path)
    if ok:
        print("now: python scripts/build_findings.py && python make_visuals.py")
    else:
        sys.exit("rerun incomplete; build_findings.py will ignore this directory "
                 "and keep using the previous rerun, which is the correct "
                 "behaviour. Fix the failure and run this again.")


if __name__ == "__main__":
    main()
