#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Find the two chart defects that reading an SVG's text will never show you.

    python check_figures.py                      # this folder's artefacts/
    python check_figures.py path/to/artefacts    # somewhere else

WHY THIS EXISTS

Three charts in this project shipped with defects that every text-level check
passed, because the words were right and only their positions were wrong:

  07-sector-gap        the "stars" axis label printed on top of the footnotes,
                       two pixels apart
  08-sector-trend      four labels overlapped into mush and a fifth data point,
                       Laundry Box's 2.73, was hidden underneath entirely
  04-fault-injection   a 245-character footnote on a 1000px canvas ran off the
                       right edge and ended mid-word
  10-diagnosticity     a value label printed through the other series' line

All four were found by opening the PNG and looking. That does not scale to
nineteen figures across two repositories, so the two failure modes are checked
here instead:

  OVERFLOW   a text node whose estimated width runs past the canvas edge
  OVERLAP    two text nodes whose estimated boxes intersect

WHAT IT CANNOT DO

It estimates text width from character count and font size, because measuring
properly needs a font engine. So it is approximate in both directions: it will
miss a near-miss and occasionally flag a pair that reads fine. Treat a hit as
"open this one and look", not as a verdict. It is a filter, not a judge.

It also knows nothing about whether a label sits on a LINE rather than on other
text, which is how the diagnosticity defect presented. Lines are not text nodes.
"""

import glob
import os
import re
import sys

# Rough advance width per character as a fraction of font size, for the
# Calibri / Segoe UI stack these figures use. Measured by eye against a few
# rendered labels; good enough to catch an overflow, not good enough to lay out.
CHAR_W = 0.50
LINE_H = 1.25

# Parse attributes one at a time rather than in a fixed order. The first
# version required text-anchor to follow font-size, which it does not, so every
# end-anchored label was measured as if it started at its x instead of ending
# there. That put three labels in 07-reproduction 97px to the right of where
# they are and reported an overlap that is not on the page.
TAG = re.compile(r"<text\s([^>]*)>([^<]*)</text>")
ATTR = re.compile(r'([\w-]+)="([^"]*)"')
SIZE = re.compile(r'<svg[^>]*?width="(\d+)"[^>]*?height="(\d+)"')


def boxes(svg):
    out = []
    for m in TAG.finditer(svg):
        at = dict(ATTR.findall(m.group(1)))
        s = m.group(2).strip()
        if not s or "x" not in at or "y" not in at:
            continue
        x, y = float(at["x"]), float(at["y"])
        fs = float(at.get("font-size", 12))
        anchor = at.get("text-anchor", "start")
        w = len(s) * fs * CHAR_W
        if anchor == "middle":
            x0 = x - w / 2
        elif anchor == "end":
            x0 = x - w
        else:
            x0 = x
        # y is the baseline; the box sits mostly above it
        out.append((x0, y - fs * 0.8, x0 + w, y + fs * 0.25, s, fs))
    return out


def overlap(a, b):
    """True only for an intersection too big to be the width estimate's fault.

    The first version flagged every touch, which made it cry wolf on
    07-reproduction: an in-bar label anchored to the bar's right edge, with the
    next label starting just after it, reads fine and overlapped by a few
    estimated pixels. Calibrated 28 Nov 2026 against figures already checked by
    eye. A tolerance means it will also miss a genuine near-miss, which is the
    right way round for a filter whose job is to say "open this one".
    """
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return False
    narrower = min(a[2] - a[0], b[2] - b[0])
    return ix > max(12.0, 0.22 * narrower)


def check(path):
    svg = open(path, encoding="utf-8").read()
    m = SIZE.search(svg)
    if not m:
        return ["no width/height on the <svg> element"]
    W, H = int(m.group(1)), int(m.group(2))
    bs = boxes(svg)
    issues = []
    for b in bs:
        # 4% of the canvas, not 2px. At CHAR_W=0.50 a 200-character footnote
        # carries about 50px of estimation error on its own.
        if b[2] > W * 1.04:
            issues.append("OVERFLOW  %4.0fpx past the right edge: %r"
                          % (b[2] - W, b[4][:58]))
        if b[0] < -2:
            issues.append("OVERFLOW  %4.0fpx past the left edge: %r"
                          % (-b[0], b[4][:58]))
        if b[3] > H + 2:
            issues.append("OVERFLOW  below the bottom edge: %r" % b[4][:58])
    for i in range(len(bs)):
        for j in range(i + 1, len(bs)):
            if overlap(bs[i], bs[j]):
                issues.append("OVERLAP   %r / %r" % (bs[i][4][:34], bs[j][4][:34]))
    return issues


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "artefacts")
    files = sorted(glob.glob(os.path.join(root, "*.svg")))
    if not files:
        sys.exit("no SVGs in %s" % root)
    bad = 0
    for f in files:
        issues = check(f)
        name = os.path.basename(f)
        if not issues:
            print("  ok    %s" % name)
            continue
        bad += 1
        print("  LOOK  %s" % name)
        for i in issues[:6]:
            print("          %s" % i)
        if len(issues) > 6:
            print("          ... and %d more" % (len(issues) - 6))
    print("\n%d figure(s), %d worth opening" % (len(files), bad))
    print("Width is estimated, not measured. A hit means look, not fail.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
