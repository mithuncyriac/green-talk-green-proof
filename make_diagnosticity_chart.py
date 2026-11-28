#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The badge figure: a volume knob for credibility, with no negative half.

Reads results/diagnosticity-2026-11-26/diagnosticity_*.csv and draws how much the
[VERIFIED PURCHASE] tag moves the rating under each stated validity. The shape is
the finding: monotonic decline across the first three conditions, then both models
turn back up when told the tag marks BAD products.

Writes artefacts/10-diagnosticity.svg. Nothing here is drawn by hand.
"""
import glob
import os
from xml.sax.saxutils import escape

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ART, RES = os.path.join(HERE, "artefacts"), os.path.join(HERE, "results")
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
SURFACE, GRID, NAVY = "#fcfcfb", "#e3e2dd", "#1F3B57"
FONT = "Calibri,Segoe UI,sans-serif"
ORDER = ["v0.9", "v0.5", "v0.0", "rev"]
LAB = {"v0.9": ["accurate", "9 times in 10"], "v0.5": ["accurate", "about half"],
       "v0.0": ["almost never", "accurate"], "rev": ["reliably marks", "BAD products"]}
SHORT = {"qwen2.5:7b": ("Qwen 2.5 7B", C[0]), "llama3.1:8b": ("Llama 3.1 8B", C[1])}


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False):
    return ('<text x="%.1f" y="%.1f" font-size="%s" fill="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", escape(str(s))))


def main():
    series = {}
    for f in sorted(glob.glob(os.path.join(RES, "diagnosticity-*", "diagnosticity_*.csv"))):
        d = pd.read_csv(f)
        d["ev"] = pd.to_numeric(d.ev_rating, errors="coerce")
        name, col = SHORT.get(d.model.iloc[0], (d.model.iloc[0], C[6]))
        pts = []
        for c in ORDER:
            w = d[d.validity == c].pivot_table(index="task", columns="tagged", values="ev")
            pts.append(float((w[1] - w[0]).dropna().mean()) if w.shape[1] > 1 else None)
        series[name] = (col, pts)
    if not series:
        raise SystemExit("no diagnosticity results found")

    # 590, not 560. The footnote sat 8px under the callout box and touched it.
    # Found 28 Nov 2026 by looking at the rendered PNG. Added 28 Nov 2026.
    W, H = 1060, 590
    L, R, TOP, BOT = 230, W - 230, 150, 400
    vals = [v for _, pts in series.values() for v in pts if v is not None]
    lo, hi = min(vals + [0]) - 0.4, max(vals) + 0.4

    def X(i):
        return L + i * (R - L) / (len(ORDER) - 1)

    def Y(v):
        return BOT - (v - lo) / (hi - lo) * (BOT - TOP)

    b = []
    for g in [-2, -1, 0, 1, 2]:
        if lo <= g <= hi:
            b.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s"%s/>'
                     % (L - 30, Y(g), R + 30, Y(g), INK2 if g == 0 else GRID,
                        ' stroke-width="1.5"' if g == 0 else ''))
            b.append(txt(L - 40, Y(g) + 4, "%+d" % g if g else "0", 11, MUTED, "end"))
    b.append(txt(L - 40, Y(0) - 18, "trusts it", 10.5, MUTED, "end"))
    b.append(txt(L - 40, Y(0) + 30, "more", 10.5, MUTED, "end"))

    for i, c in enumerate(ORDER):
        for j, line in enumerate(LAB[c]):
            bold = c == "rev"
            b.append(txt(X(i), BOT + 28 + j * 15, line, 11.5,
                         C[7] if bold else INK2, "middle", bold=bold))

    # Label positions are worked out across BOTH series before any is drawn, so two
    # that land on the same x cannot print on top of each other. At "accurate about
    # half" Qwen's +0.62 and Llama's +0.21 are 14px apart and both offset upward by
    # 14, which put one exactly over the other. Found by looking at the PNG.
    names = list(series)
    lab_y = {}
    for i in range(len(ORDER)):
        here = [(n, series[n][1][i]) for n in names if series[n][1][i] is not None]
        for n, v in here:
            lab_y[(n, i)] = Y(v) - 14 if v >= 0 else Y(v) + 24
        if len(here) == 2:
            (n1, v1), (n2, v2) = here
            lo_n, lo_v = (n1, v1) if v1 < v2 else (n2, v2)
            hi_n, hi_v = (n2, v2) if v1 < v2 else (n1, v1)
            # The clash is not label against label, it is the lower label against
            # the HIGHER SERIES' marker and line. At "accurate about half" Llama's
            # +0.21 label landed 8px from Qwen's data point and printed through
            # the blue line. Compare against the point, not the other label.
            if abs(lab_y[(lo_n, i)] - Y(hi_v)) < 18:
                lab_y[(lo_n, i)] = Y(lo_v) + 24

    for name, (col, pts) in series.items():
        path = " ".join("%s %.1f %.1f" % ("M" if i == 0 else "L", X(i), Y(v))
                        for i, v in enumerate(pts) if v is not None)
        b.append('<path d="%s" fill="none" stroke="%s" stroke-width="3"/>' % (path, col))
        for i, v in enumerate(pts):
            if v is None:
                continue
            b.append('<circle cx="%.1f" cy="%.1f" r="6" fill="%s"/>' % (X(i), Y(v), col))
            b.append(txt(X(i), lab_y[(name, i)], "%+.2f" % v, 11.5,
                         col, "middle", bold=True))
        last = next(i for i in range(len(pts) - 1, -1, -1) if pts[i] is not None)
        b.append(txt(X(last) + 16, Y(pts[last]) + 4, name, 12.5, col, "start", bold=True))

    b.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s" opacity="0.08"/>'
             % (X(2) + (X(3) - X(2)) / 2, TOP - 28, (X(3) - X(2)) / 2 + 60, BOT - TOP + 28, C[7]))
    b.append(txt(X(3), TOP - 36, "told it is a WARNING", 11.5, C[7], "middle", bold=True))

    b.append('<rect x="40" y="%d" width="%d" height="62" rx="6" fill="#FBEFEF" '
             'stroke="%s"/>' % (BOT + 76, W - 80, C[7]))
    b.append(txt(54, BOT + 98, "Both models turn back UP at the last step.", 14,
                 "#922B21", bold=True))
    b.append(txt(54, BOT + 117, "They can be told a signal is worthless. Neither could be "
                                "told a signal is a warning. These systems have a volume",
                 11.5, "#922B21"))
    b.append(txt(54, BOT + 132, "knob for credibility, not a polarity switch.",
                 11.5, "#922B21"))

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d" font-family="%s">' % (W, H, W, H, FONT),
           '<rect width="%d" height="%d" fill="%s"/>' % (W, H, SURFACE),
           txt(40, 36, "I told it the trust badge was a red flag", 21, NAVY, bold=True),
           txt(40, 58, "How much a [VERIFIED PURCHASE] tag moves the rating, by what the "
                       "model was told the tag is worth", 13, INK2),
           "\n".join(b),
           txt(40, H - 14, "50 reviews, 4 conditions, both models, 800 prompts, 2.3 minutes "
                           "of local GPU. Pilot: one tag, one wording. Generated from "
                           "results/diagnosticity-2026-11-26/.", 11, MUTED),
           "</svg>"]
    os.makedirs(ART, exist_ok=True)
    p = os.path.join(ART, "10-diagnosticity.svg")
    open(p, "w", encoding="utf-8").write("\n".join(out))
    print("wrote", p)
    for name, (_, pts) in series.items():
        print(" ", name, [None if v is None else round(v, 3) for v in pts])


if __name__ == "__main__":
    main()
