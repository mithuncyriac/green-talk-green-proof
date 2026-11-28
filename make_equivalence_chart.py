#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The equivalence figure: a vague green claim versus a substantiated one.

The project previously said 76.7% and 77.1% were "the same number". That is a
non-significant difference, which is not evidence of equivalence, and a reviewer
would say so. This draws the actual test instead: two one-sided tests against a
pre-specified bound, with the bound on the chart.

A result is equivalent when the confidence interval sits entirely inside the
bound. Drawing the bound is the whole point, because "equivalent" is meaningless
without saying equivalent to within what.

Reads results/03_agent_audit_*.csv. Writes artefacts/09-equivalence.svg.
"""
import glob
import os
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
from scipy import stats as st

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artefacts")
RES = os.path.join(HERE, "results")
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
SURFACE, GRID, NAVY = "#fcfcfb", "#e3e2dd", "#1F3B57"
FONT = "Calibri,Segoe UI,sans-serif"
SHORT = {"qwen2.5:7b": "Qwen 2.5 7B", "llama3.1:8b": "Llama 3.1 8B"}
BOUND = 0.05


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False):
    return ('<text x="%.1f" y="%.1f" font-size="%s" fill="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", escape(str(s))))


def main():
    d = pd.concat([pd.read_csv(p) for p in glob.glob(os.path.join(RES, "03_agent_audit_*.csv"))],
                  ignore_index=True)
    d["model"] = d.model.map(lambda m: SHORT.get(m, m))
    c = d[(d.kind == "choice") & (d.answer != "?")].copy()
    c["y"] = c.answer.astype(float)
    c["item"] = c.ptype + "_" + c.task.astype(str)

    rows = []
    for persona, plab in [("eco", "shopper described as eco-minded"),
                          ("plain", "shopper described in plain terms")]:
        for model in ["Qwen 2.5 7B", "Llama 3.1 8B"]:
            s = c[(c.persona == persona) & (c.model == model)]
            if s.empty:
                continue
            w = s.pivot_table(index="item", columns="cond", values="y")
            if not {"generic", "specific"}.issubset(w.columns):
                continue
            diff = (w["specific"] - w["generic"]).dropna()
            n = len(diff)
            mean, se = diff.mean(), diff.std(ddof=1) / np.sqrt(n)
            p = (max(st.t.sf((mean + BOUND) / se, n - 1), st.t.cdf((mean - BOUND) / se, n - 1))
                 if se > 0 else 0.0)
            rows.append({"persona": persona, "plab": plab, "model": model,
                         "vague": w["generic"].mean(), "specific": w["specific"].mean(),
                         "mean": mean, "lo": mean - 1.96 * se, "hi": mean + 1.96 * se,
                         "p": p, "eq": p < .05})

    # +166, not +150: the footnote block is four lines now that the bound
    # sentence is split in two, and the fourth was landing on the third.
    W, H = 1180, 150 + len(rows) * 74 + 166
    L, R = 330, W - 215
    span = 0.12

    def X(v):
        return L + (v + span) / (2 * span) * (R - L)

    b = []
    # equivalence zone
    b.append('<rect x="%.1f" y="120" width="%.1f" height="%d" fill="%s" opacity="0.10"/>'
             % (X(-BOUND), X(BOUND) - X(-BOUND), len(rows) * 74 + 20, C[2]))
    for v in [-BOUND, BOUND]:
        b.append('<line x1="%.1f" y1="118" x2="%.1f" y2="%d" stroke="%s" stroke-width="1.6" '
                 'stroke-dasharray="5 4"/>' % (X(v), X(v), 120 + len(rows) * 74 + 20, C[2]))
    b.append(txt((X(-BOUND) + X(BOUND)) / 2, 112,
                 "equivalence zone, +/- 5 percentage points", 11.5, "#145A32", "middle", bold=True))
    b.append('<line x1="%.1f" y1="118" x2="%.1f" y2="%d" stroke="%s" stroke-width="1.4"/>'
             % (X(0), X(0), 120 + len(rows) * 74 + 20, INK2))

    for i, r in enumerate(rows):
        y = 158 + i * 74
        col = C[0] if "Qwen" in r["model"] else C[1]
        b.append(txt(L - 20, y - 4, r["model"], 13, col, "end", bold=True))
        b.append(txt(L - 20, y + 13, r["plab"], 10.5, MUTED, "end"))
        b.append(txt(L - 20, y + 29, "vague %.1f%%  vs  specific %.1f%%"
                     % (r["vague"] * 100, r["specific"] * 100), 10.5, INK2, "end"))
        b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="3.2"/>'
                 % (X(r["lo"]), y, X(r["hi"]), y, col))
        for v in (r["lo"], r["hi"]):
            b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="3.2"/>'
                     % (X(v), y - 7, X(v), y + 7, col))
        b.append('<circle cx="%.1f" cy="%d" r="6.5" fill="%s"/>' % (X(r["mean"]), y, col))
        verdict = "EQUIVALENT" if r["eq"] else "inconclusive"
        b.append(txt(R + 8, y + 4, "%s  p=%.3f" % (verdict, r["p"]), 11.5,
                     "#145A32" if r["eq"] else C[7], "start", bold=r["eq"]))

    yax = 120 + len(rows) * 74 + 20
    for g in [-0.10, -0.05, 0, 0.05, 0.10]:
        b.append(txt(X(g), yax + 20, "%+.0f pp" % (g * 100) if g else "0", 11, MUTED, "middle"))
    b.append(txt(L, yax + 42, "difference in the chance of choosing the product, "
                              "specific claim minus vague claim", 11.5, INK2))

    note = ("A non-significant difference is not evidence of equivalence. This is the test that "
            "is: two one-sided tests against a bound fixed before looking.")
    # Split in two. As one line it is about 200 characters, roughly 1230px at
    # 12.3px on a 1180px canvas, so it reached the right frame edge and the last
    # words sat on it. Found 28 Nov 2026 by check_figures.py.
    note2 = ("The bound matters. Five points is a quarter of the ~20-point lift the models "
             "show for having any green claim at all,")
    note2b = ("so equivalence within 5 points means the substantiation is worth little next "
              "to the claim.")
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
           'font-family="%s">' % (W, H, W, H, FONT),
           '<rect width="%d" height="%d" fill="%s"/>' % (W, H, SURFACE),
           txt(40, 36, "Can the agent tell a substantiated claim from an empty one?",
               21, NAVY, bold=True),
           txt(40, 58, "Same product, same price, same star rating. Only the wording of one "
                       "extra review changes.", 13, INK2),
           "\n".join(b),
           txt(40, H - 62, note, 11.5, MUTED),
           txt(40, H - 46, note2, 11.5, MUTED),
           txt(40, H - 30, note2b, 11.5, MUTED),
           txt(40, H - 14, "Paired by task, both display orders. Generated from "
                           "results/03_agent_audit_*.csv.", 11.5, MUTED),
           "</svg>"]
    os.makedirs(ART, exist_ok=True)
    p = os.path.join(ART, "09-equivalence.svg")
    open(p, "w", encoding="utf-8").write("\n".join(out))
    print("wrote", p)
    for r in rows:
        print("  %-14s %-34s %+.2f pp  [%+.2f,%+.2f]  p=%.4f  %s"
              % (r["model"], r["plab"], r["mean"] * 100, r["lo"] * 100, r["hi"] * 100,
                 r["p"], "EQUIVALENT" if r["eq"] else "inconclusive"))


if __name__ == "__main__":
    main()
