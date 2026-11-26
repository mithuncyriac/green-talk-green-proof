#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SIPOC of eval-set construction, across all three projects.

This is the map nobody draws. Every eval in this portfolio rests on a hand-made
set: 60 reviews and a 33-review holdout for the Washmen triage agent, 100 reviews
for the Green Talk label audit, 90 enquiries for the Dubai lead desk. The Suppliers
column is the point of the diagram: for all four sets the supplier of the labels is
one person, with no second coder and no agreement statistic anywhere.

Drawing it does not document a process. It exposes a single point of failure that
is common to every number in the portfolio, which is a more useful thing to show
someone than a tidy diagram.

Writes artefacts/08-eval-set-sipoc.svg. Set counts are facts from the repos:
  Washmen  eval_set.csv    60 rows   (labelled before the rules were written)
  Washmen  holdout_set.csv 33 rows   (2022-23, never tuned on)
  GreenTalk label_stimuli  100 reviews x 4 label conditions
  Dubai    test_set.json   90 enquiries scored blind
"""
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artefacts")
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
SURFACE, GRID, NAVY = "#fcfcfb", "#e3e2dd", "#1F3B57"
FONT = "Calibri,Segoe UI,sans-serif"


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False):
    return ('<text x="%.1f" y="%.1f" font-size="%s" fill="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", escape(str(s))))


COLS = [
    ("Suppliers", [
        " THE AUTHOR (all four sets)",
        " Amazon Reviews 2023 corpus",
        " Apple + Google Play feeds",
        " Dubai Land Department",
        " -- no second coder --",
        " -- no agreement statistic --",
    ]),
    ("Inputs", [
        " Raw unlabelled items",
        " A written coding rule",
        " A sampling seed",
        " Time budget of one person",
        " Prior beliefs about the answer",
    ]),
    ("Process", [
        " 1 Decide the construct",
        " 2 Sample items",
        " 3 Read and label each one",
        " 4 Hold out a slice, untouched",
        " 5 Write the system",
        " 6 Score against the labels",
        " 7 Re-check failures",
    ]),
    ("Outputs", [
        " Washmen tuning set, n=60",
        " Washmen holdout, n=33",
        " Green Talk stimuli, n=100",
        " Dubai blind set, n=90",
        " A score, and its error bars",
    ]),
    ("Customers", [
        " Whoever reads the score",
        " Whoever ships on the score",
        " A hiring manager",
        " A reviewer or examiner",
        " The author, six months on",
    ]),
]

RISKS = [
    ("Step 1", "The construct is the author's. 'Escalate' and 'sceptical' were defined by "
               "one person and never tested for agreement with anyone else."),
    ("Step 3", "One coder. No kappa anywhere in the portfolio. Every accuracy, recall and "
               "precision figure inherits this."),
    ("Step 5", "Three Washmen classifier patterns were added AFTER seeing them fail, so the "
               "tuning set is partly training data. The holdout exists for this reason."),
    ("Step 7", "Re-checking only the failures is how a tuning set quietly becomes a training "
               "set. The 78.3% to 63.6% drop on unseen data is the size of that effect."),
]


def main():
    W = 1180
    rows = max(len(c[1]) for c in COLS)
    H = 150 + rows * 22 + 60 + len(RISKS) * 34 + 70
    cw = (W - 80) / 5.0
    b = []
    for i, (head, items) in enumerate(COLS):
        x = 40 + i * cw
        fill = C[7] if head == "Suppliers" else NAVY
        b.append('<rect x="%.1f" y="88" width="%.1f" height="34" fill="%s"/>' % (x, cw - 8, fill))
        b.append(txt(x + cw / 2 - 4, 110, head.upper(), 13, "#ffffff", "middle", bold=True))
        b.append('<rect x="%.1f" y="122" width="%.1f" height="%d" fill="#ffffff" stroke="%s"/>'
                 % (x, cw - 8, rows * 22 + 10, GRID))
        for j, it in enumerate(items):
            dash = it.strip().startswith("--")
            caps = it.strip().isupper() or it.strip().startswith("THE AUTHOR")
            b.append(txt(x + 10, 142 + j * 22, it, 11.5,
                         C[7] if (dash or caps) else (INK if head == "Process" else INK2),
                         bold=caps))

    y0 = 122 + rows * 22 + 34
    b.append(txt(40, y0, "Where this process can inject an error, and what it costs",
                 14, NAVY, bold=True))
    for k, (step, text) in enumerate(RISKS):
        y = y0 + 24 + k * 34
        b.append('<rect x="40" y="%d" width="62" height="24" rx="4" fill="#FBEFEF" '
                 'stroke="%s"/>' % (y - 16, C[7]))
        b.append(txt(71, y, step, 11, C[7], "middle", bold=True))
        b.append(txt(114, y, text, 11.5, INK2))

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d" font-family="%s">' % (W, H, W, H, FONT),
           '<rect width="%d" height="%d" fill="%s"/>' % (W, H, SURFACE),
           txt(40, 36, "SIPOC - how the eval sets were made", 21, NAVY, bold=True),
           txt(40, 58, "The same process produced every labelled set behind every score in "
                       "three projects", 13, INK2),
           "\n".join(b),
           txt(40, H - 30, "The Suppliers column is the finding. One person supplied every "
                           "label, so the scores across all three projects are not four "
                           "independent measurements.", 11.5, MUTED),
           txt(40, H - 14, "Counts are from the files: eval_set.csv 60, holdout_set.csv 33, "
                           "label_stimuli.json 100, Dubai test_set.json 90.", 11.5, MUTED),
           "</svg>"]
    os.makedirs(ART, exist_ok=True)
    p = os.path.join(ART, "08-eval-set-sipoc.svg")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("wrote", p)


if __name__ == "__main__":
    main()
