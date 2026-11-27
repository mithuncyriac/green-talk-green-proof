#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Split a fan-out results file into one row per cell, plus the repeats.

    python scripts/dedupe_fanout.py --check          # report, change nothing
    python scripts/dedupe_fanout.py --write          # split the files

WHY THIS EXISTS, AND WHAT IT ACCIDENTALLY MEASURED

On 27 Nov 2026 two fanout_run.py processes wrote
results/fanout/fanout_cerebras_gpt-oss-120b.csv at the same time: one started
18:43 covering every provider, one started 20:23 scoped to this model. Each read
the file at its own start, computed its own to-do list, and appended. 175 cells
were therefore run twice, by two processes, hours apart.

That is a defect in how the runs were launched, not in the data. Every row is a
real completed call. And because the two passes used identical prompts on the
same model at the same settings, the overlap is a test-retest reliability
sample nobody designed: 175 cells measured twice, independently.

So this does not throw the second copy away. It writes:

    fanout_<provider>_<model>.csv          first occurrence of each cell
    repeats_<provider>_<model>.csv         every later occurrence
    repeats_<provider>_<model>.json        the agreement rate between them

The analysis uses the first file. The second is evidence about the provider,
and it belongs in the paper's limitations rather than in the bin.

THE CELL KEY

Matches cell_id in fanout_run.py: kind, ptype, task, cond, persona, order,
pass. Two rows with the same key are the same question asked twice.
"""

import argparse
import collections
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "results", "fanout")
FIELDS = ("kind", "ptype", "task", "cond", "persona", "order", "pass")


def key(r):
    return tuple(r.get(f, "") for f in FIELDS)


def load(path):
    with io.open(path, encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        return rd.fieldnames, list(rd)


def agreement(groups):
    """How often a repeated cell gave the same answer the second time."""
    same = diff = 0
    ev_same = ev_diff = 0
    examples = []
    for k, rows in groups.items():
        if len(rows) < 2:
            continue
        answers = {r.get("answer") for r in rows}
        if len(answers) == 1:
            same += 1
        else:
            diff += 1
            if len(examples) < 8:
                examples.append({"cell": dict(zip(FIELDS, k)),
                                 "answers": sorted(answers)})
        evs = {round(float(r["ev_rating"]), 4) for r in rows
               if r.get("ev_rating") not in (None, "")}
        if len(evs) > 1:
            ev_diff += 1
        elif evs:
            ev_same += 1
    n = same + diff
    return {
        "repeated_cells": n,
        "same_emitted_answer": same,
        "different_emitted_answer": diff,
        "exact_agreement_pct": round(100.0 * same / n, 2) if n else None,
        "expected_rating_identical": ev_same,
        "expected_rating_different": ev_diff,
        "disagreement_examples": examples,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="default: every fanout_*.csv")
    ap.add_argument("--write", action="store_true",
                    help="rewrite the files; without it, only report")
    ap.add_argument("--check", action="store_true", help="report only (default)")
    args = ap.parse_args()

    paths = args.files or sorted(
        p for p in (os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR))
        if os.path.basename(p).startswith("fanout_") and p.endswith(".csv"))

    dirty = False
    for path in paths:
        name = os.path.basename(path)
        fields, rows = load(path)
        groups = collections.OrderedDict()
        for r in rows:
            groups.setdefault(key(r), []).append(r)
        dupes = sum(len(v) - 1 for v in groups.values())
        print("%-44s %4d rows, %4d cells, %3d repeats"
              % (name, len(rows), len(groups), dupes))
        if not dupes:
            continue
        dirty = True
        stats = agreement(groups)
        print("     repeated cells %d: same answer %d, different %d  (%.1f%% agree)"
              % (stats["repeated_cells"], stats["same_emitted_answer"],
                 stats["different_emitted_answer"], stats["exact_agreement_pct"]))
        print("     expected rating identical %d, different %d"
              % (stats["expected_rating_identical"],
                 stats["expected_rating_different"]))
        if not args.write:
            print("     (reporting only; pass --write to split)")
            continue

        firsts = [v[0] for v in groups.values()]
        repeats = [r for v in groups.values() for r in v[1:]]
        tag = name[len("fanout_"):-len(".csv")]
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(firsts)
        rp = os.path.join(OUT_DIR, "repeats_%s.csv" % tag)
        with io.open(rp, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(repeats)
        stats["source"] = name
        stats["note"] = ("Two fanout_run.py processes wrote this model's file "
                         "concurrently on 27 Nov 2026. Every row is a real call; "
                         "the overlap is an unplanned test-retest sample.")
        jp = os.path.join(OUT_DIR, "repeats_%s.json" % tag)
        io.open(jp, "w", encoding="utf-8").write(json.dumps(stats, indent=1))
        print("     wrote %d first rows, %d repeats, and repeats_%s.json"
              % (len(firsts), len(repeats), tag))

    if dirty and not args.write:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
