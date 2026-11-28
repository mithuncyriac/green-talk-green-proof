#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export every SVG in artefacts/ to artefacts/png/ at its own declared size.

    python export_png.py                 # all of them, at 2x
    python export_png.py --scale=1       # at the SVG's own pixel size
    python export_png.py 09-equivalence  # one, by stem

WHY A BROWSER AND NOT A LIBRARY

Three Python routes were tried on this machine on 27 Nov 2026 and all three
failed, so they are recorded here rather than tried again:

    cairosvg            installs, will not import: no cairo DLL on Windows
    svglib + reportlab  both import; reportlab 5 needs rlPyCairo to write PNG
    rlPyCairo + pycairo installs, will not import, same missing native library

Chrome is already on this machine and is the reference renderer for SVG: it
resolves the Calibri / Segoe UI font stack these figures ask for, which a
library substituting fonts would not. So the export is a headless screenshot at
the SVG's own pixel size, which is what the earlier hand-made PNGs were.

WHY EXPORT ALL OF THEM, NOT JUST THE MISSING ONES

Before this script, eight of the ten PNGs were made by hand and two were never
made at all. Hand-made exports have no provenance and at least one was wrong:
04-sipoc.png was 1180x390 against a 1180x412 drawing, so the bottom 22 pixels
of the figure had been cropped off and nobody noticed. One command for the whole
set means the PNGs cannot drift from the SVGs again.

The SVGs themselves are generated from the result files by make_visuals.py in
the green-talk-green-proof repository. This script only changes format.
"""

import glob
import io
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artefacts")
OUT = os.path.join(ART, "png")

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def browser():
    for p in CHROME:
        if os.path.exists(p):
            return p
    sys.exit("no Chrome or Edge found. Paths tried:\n  " + "\n  ".join(CHROME))


def declared_size(path):
    """The width and height the drawing itself states, in pixels."""
    head = io.open(path, encoding="utf-8").read(600)
    w = re.search(r'width="(\d+)"', head)
    h = re.search(r'height="(\d+)"', head)
    if not (w and h):
        return None
    return int(w.group(1)), int(h.group(1))


def png_size(path):
    with open(path, "rb") as fh:
        return struct.unpack(">II", fh.read(24)[16:24])


def main():
    exe = browser()
    argv = [a for a in sys.argv[1:] if not a.startswith("--scale")]
    scale = 2
    for a in sys.argv[1:]:
        if a.startswith("--scale="):
            scale = int(a.split("=", 1)[1])
    wanted = argv
    svgs = sorted(glob.glob(os.path.join(ART, "*.svg")))
    if wanted:
        svgs = [p for p in svgs
                if os.path.basename(p)[:-4] in wanted]
        if not svgs:
            sys.exit("no SVG matched %s" % wanted)
    if not os.path.isdir(OUT):
        os.makedirs(OUT)

    print("renderer: %s\n" % exe)
    print("rendering at %dx device scale\n" % scale)
    print("%-28s %-12s %-12s %s" % ("figure", "declared", "rendered", ""))
    print("-" * 66)
    bad = []
    for src in svgs:
        stem = os.path.basename(src)[:-4]
        size = declared_size(src)
        if not size:
            print("%-28s %-12s %-12s no width/height in the SVG" % (stem, "?", "-"))
            bad.append(stem)
            continue
        w, h = size
        dest = os.path.join(OUT, stem + ".png")
        before = png_size(dest) if os.path.exists(dest) else None
        rc = subprocess.call(
            [exe, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--default-background-color=ffffff",
             "--force-device-scale-factor=%d" % scale,
             "--window-size=%d,%d" % (w, h),
             "--screenshot=%s" % dest,
             "file:///" + src.replace("\\", "/")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if rc != 0 or not os.path.exists(dest):
            print("%-28s %-12s %-12s FAILED (exit %s)"
                  % (stem, "%dx%d" % (w, h), "-", rc))
            bad.append(stem)
            continue
        gw, gh = png_size(dest)
        note = "ok"
        if (gw, gh) != (w * scale, h * scale):
            note = "SIZE MISMATCH"
            bad.append(stem)
        elif before is None:
            note = "new"
        elif before != (gw, gh):
            # Say WHAT changed. The first version called any change a crop, which
            # was wrong for the Washmen set: those had been exported at 1.33x, so
            # they were larger, not cropped. A label that is wrong in one of two
            # directions is worse than no label.
            ow, oh = before
            if ow < w * scale and oh < h * scale and ow * h != oh * w:
                note = "was %dx%d, cropped before" % before
            elif ow * h == oh * w:
                note = "was %dx%d, %.2fx scale before" % (ow, oh, float(ow) / w)
            else:
                note = "was %dx%d" % before
        print("%-28s %-12s %-12s %s"
              % (stem, "%dx%d" % (w, h), "%dx%d" % (gw, gh), note))

    print("\n%d figure(s) in %s" % (len(svgs), OUT))
    if bad:
        print("problems: %s" % ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
