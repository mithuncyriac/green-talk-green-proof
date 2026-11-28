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

VALIDATED BY PLANTING THE DEFECTS BACK

A check that passes everything proves nothing until it can fail. On 28 Nov 2026
three deliberately broken copies of 10-diagnosticity.svg were made and all three
were caught by the rule meant for them:

    +0.21 moved back onto Qwen's line    -> ON A MARK
    a title shifted off the right edge   -> OVERFLOW 360px
    a title duplicated 3px below itself  -> OVERLAP

The first is the one that matters. It is the defect that passed every text-level
check in this project and was found only by opening the PNG.

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



# --- geometry -------------------------------------------------------------
# Text landing on a drawn LINE is the defect that got through every earlier
# check: in 10-diagnosticity, Llama's +0.21 printed across Qwen's blue line and
# only opening the PNG showed it. Lines are not text nodes, so the text-only
# pass could never see it.
#
# Grid lines must not be flagged or every chart lights up. The rule here is
# that a data mark is THICK (stroke-width >= 2) or a plotted point (a circle of
# r >= 4), while grid lines in these figures are 1px. That is a property of how
# make_visuals.py draws, not a universal truth, and it is the reason this check
# belongs beside those scripts rather than anywhere else.
LINE = re.compile(r"<line\s([^>]*)/>")
CIRCLE = re.compile(r"<circle\s([^>]*)/>")
POLY = re.compile(r'<polyline[^>]*points="([^"]*)"([^>]*)/>')
PATH = re.compile(r'<path[^>]*d="([^"]*)"([^>]*)/>')
NUM = re.compile(r"-?\d+\.?\d*")


def _w(attrs):
    m = re.search(r'stroke-width="([\d.]+)"', attrs)
    return float(m.group(1)) if m else (1.0 if "stroke=" in attrs else 0.0)


def marks(svg):
    """Segments and points thick enough to be data rather than grid."""
    out = []
    for m in LINE.finditer(svg):
        a = m.group(1)
        if _w(a) < 2:
            continue
        at = dict(ATTR.findall(a))
        try:
            out.append(("seg", float(at["x1"]), float(at["y1"]),
                        float(at["x2"]), float(at["y2"])))
        except KeyError:
            pass
    for m in CIRCLE.finditer(svg):
        at = dict(ATTR.findall(m.group(1)))
        try:
            r = float(at.get("r", 0))
            if r >= 4:
                out.append(("dot", float(at["cx"]), float(at["cy"]), r, 0))
        except KeyError:
            pass
    for m in POLY.finditer(svg):
        if _w(m.group(2)) < 2:
            continue
        n = [float(v) for v in NUM.findall(m.group(1))]
        for i in range(0, len(n) - 3, 2):
            out.append(("seg", n[i], n[i + 1], n[i + 2], n[i + 3]))
    for m in PATH.finditer(svg):
        if _w(m.group(2)) < 2:
            continue
        n = [float(v) for v in NUM.findall(m.group(1))]
        for i in range(0, len(n) - 3, 2):
            out.append(("seg", n[i], n[i + 1], n[i + 2], n[i + 3]))
    return out


def hits(box, mk):
    """Does this text box sit on a data mark? Sampled, not solved."""
    x0, y0, x1, y1 = box[0], box[1], box[2], box[3]
    if mk[0] == "dot":
        cx, cy, r = mk[1], mk[2], mk[3]
        nx = min(max(cx, x0), x1)
        ny = min(max(cy, y0), y1)
        return (nx - cx) ** 2 + (ny - cy) ** 2 <= r * r
    ax, ay, bx, by = mk[1], mk[2], mk[3], mk[4]
    steps = max(2, int(max(abs(bx - ax), abs(by - ay)) / 3))
    for i in range(steps + 1):
        t = i / float(steps)
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        if x0 <= px <= x1 and y0 <= py <= y1:
            return True
    return False


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
    mk = marks(svg)
    for b in bs:
        # Shrink the box a little first: a label legitimately sits close to its
        # own line, and only a real crossing is worth reporting.
        tight = (b[0] + 3, b[1] + 2, b[2] - 3, b[3] - 2)
        if tight[0] >= tight[2] or tight[1] >= tight[3]:
            continue
        for m in mk:
            if hits(tight, m):
                issues.append("ON A MARK %r sits on a data line or point" % b[4][:44])
                break
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
