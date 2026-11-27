#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Does every number in the Green Talk article still come out of the result files?

    python scripts/check_published_numbers.py

WHY THIS EXISTS

03-before-you-publish.md names "you have not run the scripts yourself" as one of
three things blocking publication, on the rule that the numbers you quote should
be numbers you produced. Checking that by reading two drafts against three result
files is how a transcription error survives. This makes it one command.

It also applies the gate's own decision table to the latest rerun, so the question
"what do I publish if the rerun disagrees" is answered by the script rather than
re-litigated at the moment it matters.

WHAT IT READS

    results/findings.json                             label audit, position bias, calibration
    results/diagnosticity-2026-11-26/FINDING.md       the badge result
    results/02_ftc_bamboo_event_study.txt             the failed regulator study

WHAT IT CANNOT CHECK

The equivalence p-values (.041 and .032) and the 5-percentage-point bound, which
live in the study-3 summary text rather than in a result file this script parses.
They are listed at the end as unchecked rather than silently passed.
"""

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "results")

# What the two drafts actually say, transcribed once, here, on purpose.
PUBLISHED = [
    # (label, published value, tolerance)
    ("qwen ai minus none, -0.14", -0.14, 0.005),
    ("llama ai minus none, +0.19", 0.19, 0.005),
    ("qwen effort minus ai, +0.25", 0.25, 0.005),
    ("llama effort minus ai, +0.25", 0.25, 0.005),
    ("llama picks first shown, 94.0%", 94.0, 0.05),
    ("qwen picks first shown, 70.6%", 70.6, 0.05),
    ("prompts in the label audit plus badge test, 2,760", 2760, 0),
    ("badge, qwen +0.53", 0.526, 0.005),
    ("badge, llama +0.54", 0.542, 0.005),
    ("FTC any_scep, +0.275 pp", 0.275, 0.001),
]


def grab(path, pattern, group=1, cast=float):
    """First regex hit in a text file, or None."""
    if not os.path.exists(path):
        return None
    m = re.search(pattern, io.open(path, encoding="utf-8", errors="replace").read())
    return cast(m.group(group)) if m else None


def main():
    fp = os.path.join(RES, "findings.json")
    if not os.path.exists(fp):
        sys.exit("no results/findings.json. Run: python scripts/build_findings.py")
    f = json.load(io.open(fp, encoding="utf-8"))

    eff = f["reproduction"]["effects"]["original"]
    s3 = f["study3_green_claims"]["models"]
    s4 = f["study4_ai_label"]
    diag = os.path.join(RES, "diagnosticity-2026-11-26", "FINDING.md")
    ftc = os.path.join(RES, "02_ftc_bamboo_event_study.txt")

    found = {
        "qwen ai minus none, -0.14": eff["qwen"]["ai_minus_none"],
        "llama ai minus none, +0.19": eff["llama"]["ai_minus_none"],
        "qwen effort minus ai, +0.25": eff["qwen"]["effort_minus_ai"],
        "llama effort minus ai, +0.25": eff["llama"]["effort_minus_ai"],
        "llama picks first shown, 94.0%": 100.0 * s3["llama"]["picks_first_shown"],
        "qwen picks first shown, 70.6%": 100.0 * s3["qwen"]["picks_first_shown"],
        "prompts in the label audit plus badge test, 2,760":
            f["reproduction"]["rows_matched"] + 800,
        "badge, qwen +0.53": grab(diag, r"Qwen \+([0-9.]+)"),
        "badge, llama +0.54": grab(diag, r"Llama \+([0-9.]+)"),
        "FTC any_scep, +0.275 pp": grab(ftc, r"any_scep\s+coef=\+([0-9.]+) pp"),
    }

    print("=" * 74)
    print("PUBLISHED NUMBERS AGAINST THE RESULT FILES")
    print("=" * 74)
    bad = []
    for label, want, tol in PUBLISHED:
        got = found.get(label)
        if got is None:
            print("  ?     %-52s not found in its source file" % label)
            bad.append(label)
            continue
        ok = abs(got - want) <= tol
        print("  %s  %-52s file says %s" % ("OK  " if ok else "FAIL", label, got))
        if not ok:
            bad.append(label)

    # --- the gate's decision table, applied to the latest rerun ---------------
    print("\n" + "=" * 74)
    print("THE REPRODUCTION, AGAINST THE GATE'S OWN DECISION TABLE")
    print("=" * 74)
    rep = f["reproduction"]
    re_eff = rep["effects"].get("rerun")
    print("  rerun directory : %s" % rep.get("rerun_dir"))
    print("  rows matched    : %s" % rep.get("rows_matched"))
    if not re_eff:
        print("  no rerun recorded. Run: python scripts/rerun_label_audit.py")
        return 1 if bad else 0

    cal = f.get("study4_rerun", {}).get("calibration", {})
    cal_ok = all(v >= 0.90 for v in cal.values()) if cal else False
    print("  calibration     : %s  %s"
          % (cal, "pass" if cal_ok else "FAIL, publish nothing and fix the harness"))

    flips, weak = [], []
    for m in ("qwen", "llama"):
        a, b = eff[m]["ai_minus_none"], re_eff[m]["ai_minus_none"]
        same = (a > 0) == (b > 0)
        print("  %-5s ai-none    : original %+.2f, rerun %+.2f  %s"
              % (m, a, b, "sign holds" if same else "SIGN FLIPPED"))
        if not same:
            flips.append(m)
    gap = f.get("study4_rerun", {}).get("bootstrap", {}).get("effects", {}).get("gap")
    if gap:
        clear = gap["ci"][0] > 0 or gap["ci"][1] < 0
        print("  gap             : %+.2f, 95%% CI %s  %s"
              % (gap["point"], gap["ci"],
                 "clear of zero" if clear else "includes zero"))
        if not clear:
            weak.append("gap")

    print("\n  VERDICT, per 03-before-you-publish.md section 2:")
    if not cal_ok:
        print("    Publish nothing. Fix the harness first.")
    elif flips:
        print("    A sign flipped (%s). The piece becomes \"I could not replicate my"
              % ", ".join(flips))
        print("    own result three weeks later\", which is a better article than the")
        print("    one drafted, and every figure is kept.")
    elif weak:
        print("    Signs hold, gap not clear of zero. Publish with the headline")
        print("    softened to \"the two models disagreed in my runs, and the")
        print("    disagreement is not stable\".")
    else:
        print("    Both signs hold and the gap is clear of zero. Publish the piece")
        print("    as drafted.")

    print("\n" + "=" * 74)
    print("NOT CHECKED BY THIS SCRIPT")
    print("  The equivalence result: within 5 percentage points, p = .041 and .032.")
    print("  Those sit in the study-3 summary text, not in a parsed result file.")
    print("  Read results/03_agent_audit_summary.txt before quoting them.")
    print("=" * 74)
    if bad:
        print("\n%d published figure(s) did not reproduce: %s" % (len(bad), ", ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
