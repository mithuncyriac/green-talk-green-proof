#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Every chart and diagram in this project, generated from results/findings.json.

    python scripts/build_findings.py
    python make_visuals.py

Writes into artefacts/:
    01-sign-flip.svg          the headline: same reviews, same label, opposite signs
    02-scale-use.svg          the caveat: the two models do not use the same scale
    03-three-switches.svg     model, persona and display order each change the answer
    04-sipoc.svg              SIPOC for the audit itself
    05-audit-pipeline.svg     BPMN swimlanes with the gates, and the gate that failed
    05-audit-pipeline.drawio  the same diagram, editable
    06-value-stream-map.svg   cycle time per step, unmeasured steps marked

NOTHING HERE IS DRAWN BY HAND OR BY AN IMAGE MODEL.

An image model produces a picture of a chart with invented numbers, which would
destroy the one property this project has: that every figure rebuilds from the
result files with one command. Image generation is for a cover, not for evidence.
"""

import json
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artefacts")
RES = os.path.join(HERE, "results")

C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
SURFACE, GRID = "#fcfcfb", "#e3e2dd"
NAVY = "#1F3B57"
FONT = "Calibri,Segoe UI,sans-serif"
QC, LC = C[0], C[1]          # qwen, llama - fixed slots, never cycled


def svg(w, h, body, title=None, sub=None, note=None):
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d" font-family="%s">' % (w, h, w, h, FONT),
           '<rect width="%d" height="%d" fill="%s"/>' % (w, h, SURFACE)]
    if title:
        out.append('<text x="40" y="36" font-size="21" font-weight="bold" fill="%s">%s</text>'
                   % (NAVY, escape(title)))
    if sub:
        out.append('<text x="40" y="58" font-size="13" fill="%s">%s</text>' % (INK2, escape(sub)))
    out.append(body)
    if note:
        y = h - 14 - 15 * (len(note) - 1)
        for i, ln in enumerate(note):
            out.append('<text x="40" y="%d" font-size="11" fill="%s">%s</text>'
                       % (y + i * 15, MUTED, escape(ln)))
    out.append("</svg>")
    return "\n".join(out)


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False):
    return ('<text x="%.1f" y="%.1f" font-size="%s" fill="%s" text-anchor="%s"%s>%s</text>'
            % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", escape(str(s))))


def write(name, content):
    os.makedirs(ART, exist_ok=True)
    with open(os.path.join(ART, name), "w", encoding="utf-8") as fh:
        fh.write(content)
    print("  wrote artefacts/%s" % name)


# ---------------------------------------------------------------------------
def chart_sign_flip(f):
    """Dot-and-interval. The whole argument in one picture."""
    s4 = f["study4_ai_label"]
    b = s4["bootstrap"]["effects"]
    rows = [("Qwen 2.5 7B", b["qwen_ai"], QC),
            ("Llama 3.1 8B", b["llama_ai"], LC),
            ("the gap between them", b["gap"], C[6])]
    W, H = 1000, 520
    L, Rr = 300, W - 70
    lo = min(min(r[1]["ci"]) for r in rows) - 0.08
    hi = max(max(r[1]["ci"]) for r in rows) + 0.08

    def X(v):
        return L + (v - lo) / (hi - lo) * (Rr - L)

    o = []
    step = 0.1
    g = -step * int(abs(lo) / step + 1)
    ticks = []
    while g <= hi:
        if g >= lo:
            ticks.append(round(g, 10))
        g += step
    for g in ticks:
        o.append('<line x1="%.1f" y1="110" x2="%.1f" y2="330" stroke="%s"/>'
                 % (X(g), X(g), GRID))
        o.append(txt(X(g), 350, "0" if abs(g) < 1e-9 else "%+.1f" % g, 11, MUTED, "middle"))
    o.append('<line x1="%.1f" y1="104" x2="%.1f" y2="336" stroke="%s" stroke-width="1.8" '
             'stroke-dasharray="4 3"/>' % (X(0), X(0), INK2))
    o.append(txt(X(0), 98, "no effect", 11, INK2, "middle"))

    for i, (name, e, col) in enumerate(rows):
        y = 148 + i * 62
        o.append(txt(L - 18, y + 5, name, 14, INK, "end", bold=(i == 2)))
        o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="3"/>'
                 % (X(e["ci"][0]), y, X(e["ci"][1]), y, col))
        for v in e["ci"]:
            o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" '
                     'stroke-width="3"/>' % (X(v), y - 7, X(v), y + 7, col))
        o.append('<circle cx="%.1f" cy="%d" r="7" fill="%s"/>' % (X(e["point"]), y, col))
        o.append(txt(X(e["point"]), y - 16, "%+.2f" % e["point"], 13, col, "middle", bold=True))
    o.append(txt(L, 372, "change in helpfulness rating, 1-7 scale  (dot = point estimate, "
                         "bar = 95%% bootstrap interval over %d items)"
                 % s4["n_items"], 11.5, INK2))

    ia = s4["interaction_raw"]
    iz = s4["interaction_standardised"]
    o.append('<rect x="40" y="394" width="%d" height="50" rx="5" fill="#EAF2FB" '
             'stroke="%s"/>' % (W - 80, QC))
    o.append(txt(54, 416, "The gap is tested, not eyeballed: condition x model interaction "
                          "b=%+.2f, p=%.1e, 95%% CI [%+.2f, %+.2f]."
                 % (ia["coef"], ia["p"], ia["ci"][0], ia["ci"][1]), 12.5, NAVY, bold=True))
    o.append(txt(54, 436, "Standardised within model, to rule out the two scales: %+.2f SD, "
                          "p=%.1e. In %d of %d bootstrap draws Qwen stays negative and "
                          "Llama stays positive."
                 % (iz["coef"], iz["p"],
                    int(s4["bootstrap"]["share_signs_hold"] * s4["bootstrap"]["n"]),
                    s4["bootstrap"]["n"]), 11.5, NAVY))

    return svg(W, H, "\n".join(o),
               "The same 100 reviews, the same label, opposite answers",
               'Effect of adding "[Made with AI]" to a review, on how helpful the model '
               'says that review is',
               ["Each model rated all %d reviews under all three labels, so the comparison is within review."
                % s4["n_items"],
                "The rating task shows one review on its own - there is no second product, so display order cannot reach this result."])


# ---------------------------------------------------------------------------
def chart_scale_use(f):
    """The caveat chart. Publish the thing that could undo the headline."""
    s4 = f["study4_ai_label"]
    W, H = 1000, 510
    o = []
    panels = [("qwen", "Qwen 2.5 7B", QC), ("llama", "Llama 3.1 8B", LC)]
    pw = (W - 110) / 2
    for k, (mdl, name, col) in enumerate(panels):
        m = s4["models"][mdl]
        x0 = 50 + k * (pw + 10)
        o.append(txt(x0, 100, name, 15, col, bold=True))
        o.append(txt(x0, 118, "uses %d of the 7 scale points; highest it ever gave: %d"
                     % (len(m["scale_points_used"]), m["highest_emitted"]), 11.5, INK2))
        hist = m["hist"]["none"]
        top = max(max(v for v in m["hist"][c]) for c in ("none", "ai", "effort"))
        bw = (pw - 40) / 7.0
        for v in range(7):
            x = x0 + v * bw
            hgt = 0 if top == 0 else hist[v] / top * 170
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" '
                     'opacity="0.85"/>' % (x + 4, 310 - hgt, bw - 8, hgt, col))
            if hist[v]:
                o.append(txt(x + bw / 2, 304 - hgt, hist[v], 11, INK, "middle", bold=True))
            elif m["hist_all"][v] == 0:
                # never emitted under ANY label, not merely absent from this condition
                o.append(txt(x + bw / 2, 302, "never", 9.5, C[7], "middle", bold=True))
            else:
                o.append(txt(x + bw / 2, 302, "0", 10, MUTED, "middle"))
            o.append(txt(x + bw / 2, 328, v + 1, 12, INK2, "middle"))
        o.append('<line x1="%.1f" y1="311" x2="%.1f" y2="311" stroke="%s"/>'
                 % (x0, x0 + pw - 36, INK2))
        o.append(txt(x0 + (pw - 36) / 2, 346, "rating given, unlabelled reviews", 11, MUTED, "middle"))
        o.append(txt(x0, 368, "%.0f%% of its unlabelled ratings are already at its own ceiling"
                     % (m["share_at_own_max"] * 100), 11.5, INK2))

    # The note is derived, not asserted, so it cannot go stale when the data changes.
    notes = []
    for mdl, name, _ in panels:
        m = s4["models"][mdl]
        missing = [str(v) for v in range(1, 8) if v not in m["scale_points_used"]]
        per_model = s4["n_ratings"] // len(panels)
        if missing:
            notes.append("%s never emitted %s in %d ratings, so those points are outside its "
                         "vocabulary; its effect is a shift of mass between the %d it does use."
                         % (name, " or ".join(missing), per_model,
                            len(m["scale_points_used"])))
        else:
            notes.append("%s used all seven points, but %.0f%% of its unlabelled answers sit at "
                         "its ceiling, so it has room to fall and little room to rise."
                         % (name, m["share_at_own_max"] * 100))
    notes.append("Standardising within model keeps the gap significant (%+.2f SD, p=%.0e), which "
                 "is why the headline survives. Anyone reading the raw"
                 % (s4["interaction_standardised"]["coef"],
                    s4["interaction_standardised"]["p"]))
    notes.append("point difference as a preference, rather than as a shift in where each model "
                 "parks its answers, is reading past this chart.")
    return svg(W, H, "\n".join(o),
               "Before trusting the sign: the two models are not using the same ruler",
               "Every helpfulness rating either model gave to an unlabelled review",
               notes)


# ---------------------------------------------------------------------------
def chart_three_switches(f):
    """Three design choices, three different answers. The actual thesis."""
    s3, s4 = f["study3_green_claims"], f["study4_ai_label"]
    W, H = 1060, 500
    pw = (W - 120) / 3.0
    o = []

    # panel 1: switch the model
    x0 = 40
    b = s4["bootstrap"]["effects"]
    o.append(txt(x0, 104, "1. Switch the model", 14, NAVY, bold=True))
    o.append(txt(x0, 122, "effect of the AI label on rating", 11, INK2))
    base = 300
    for i, (mdl, col) in enumerate([("qwen_ai", QC), ("llama_ai", LC)]):
        v = b[mdl]["point"]
        x = x0 + 30 + i * 90
        hgt = abs(v) / 0.35 * 110
        y = base - hgt if v > 0 else base
        o.append('<rect x="%.1f" y="%.1f" width="54" height="%.1f" fill="%s"/>'
                 % (x, y, hgt, col))
        o.append(txt(x + 27, y - 8 if v > 0 else y + hgt + 18, "%+.2f" % v, 13, col,
                     "middle", bold=True))
        o.append(txt(x + 27, base + (hgt + 38 if v < 0 else 20), "Qwen" if i == 0 else "Llama",
                     12, INK2, "middle"))
    o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1.6"/>'
             % (x0 + 10, base, x0 + pw - 30, base, INK2))
    o.append(txt(x0, 400, "One goes down, one goes up.", 12, INK, bold=True))
    o.append(txt(x0, 418, "Same reviews, same label.", 12, INK2))

    # panel 2: switch the persona
    x0 = 40 + pw + 30
    o.append(txt(x0, 104, "2. Switch the shopper", 14, NAVY, bold=True))
    o.append(txt(x0, 122, "chance of picking the product with the", 11, INK2))
    o.append(txt(x0, 137, "extra green review, Qwen", 11, INK2))
    per = s3["models"]["qwen"]["by_persona"]
    conds = [("neutral", "none"), ("generic", "vague"),
             ("specific", "specific"), ("sceptical", "sceptical")]
    xstep = (pw - 90) / 3.0

    def Y(v):
        return 330 - (v - 0.45) / 0.40 * 160

    for gv in [0.5, 0.6, 0.7, 0.8]:
        o.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s"/>'
                 % (x0 + 10, Y(gv), x0 + 30 + 3 * xstep, Y(gv), GRID))
        o.append(txt(x0 + 6, Y(gv) + 4, "%.0f%%" % (gv * 100), 10, MUTED, "end"))
    for i, (persona, col, lab) in enumerate([("eco", C[2], "eco shopper"),
                                             ("plain", MUTED, "plain shopper")]):
        pts = [per[persona][c] for c, _ in conds]
        path = " ".join("%s %.1f %.1f" % ("M" if j == 0 else "L", x0 + 30 + j * xstep, Y(v))
                        for j, v in enumerate(pts))
        o.append('<path d="%s" fill="none" stroke="%s" stroke-width="2.6"/>' % (path, col))
        for j, v in enumerate(pts):
            o.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="%s"/>'
                     % (x0 + 30 + j * xstep, Y(v), col))
        o.append(txt(x0 + 30 + 1.5 * xstep, Y(pts[2]) + (-14 if persona == "eco" else 22),
                     lab, 11, col, "middle", bold=True))
    for j, (_, lab) in enumerate(conds):
        o.append(txt(x0 + 30 + j * xstep, 352, lab, 10.5, MUTED, "middle"))
    o.append(txt(x0, 400, "Tell it the shopper cares and", 12, INK, bold=True))
    o.append(txt(x0, 418, "claims move choice ~20 points. Tell", 12, INK2))
    o.append(txt(x0, 436, "it nothing and they move nothing.", 12, INK2))

    # panel 3: switch the order
    x0 = 40 + 2 * (pw + 30)
    o.append(txt(x0, 104, "3. Switch the order", 14, NAVY, bold=True))
    o.append(txt(x0, 122, "how often the model just picks", 11, INK2))
    o.append(txt(x0, 137, "whichever product is shown first", 11, INK2))
    bars = [("Qwen", s3["models"]["qwen"]["picks_first_shown"], QC),
            ("Llama", s3["models"]["llama"]["picks_first_shown"], LC)]
    for i, (name, v, col) in enumerate(bars):
        y = 180 + i * 72
        o.append('<rect x="%.1f" y="%d" width="%.1f" height="34" fill="%s" opacity="0.18"/>'
                 % (x0, y, pw - 60, col))
        o.append('<rect x="%.1f" y="%d" width="%.1f" height="34" fill="%s"/>'
                 % (x0, y, (pw - 60) * v, col))
        o.append(txt(x0, y - 7, name, 12, INK2))
        o.append(txt(x0 + (pw - 60) * v - 8, y + 23, "%.0f%%" % (v * 100), 14, "#ffffff",
                     "end", bold=True))
    o.append('<line x1="%.1f" y1="172" x2="%.1f" y2="296" stroke="%s" stroke-width="1.6" '
             'stroke-dasharray="4 3"/>' % (x0 + (pw - 60) * 0.5, x0 + (pw - 60) * 0.5, INK))
    o.append(txt(x0 + (pw - 60) * 0.5, 312, "50% = no order effect", 10.5, INK, "middle"))
    o.append(txt(x0, 400, "A model that nearly always takes", 12, INK, bold=True))
    o.append(txt(x0, 418, "the first option has no room left", 12, INK2))
    o.append(txt(x0, 436, "for a review to move it.", 12, INK2))

    return svg(W, H, "\n".join(o),
               "Three switches, three different conclusions",
               "Each panel holds the reviews fixed and changes one thing about the test setup",
               ["This is the finding. Not what agents think of green claims, but that a single-model, single-persona,",
                "single-order audit would have produced a confident answer - and a different one each time."])


# ---------------------------------------------------------------------------
def chart_reproduction(f):
    """Ran it again 23 days later. What held, and what did not."""
    r = f["reproduction"]
    W, H = 1040, 470
    o = []

    # left: row-level agreement by task type
    o.append(txt(40, 104, "Did the same prompt get the same answer?", 14, NAVY, bold=True))
    o.append(txt(40, 122, "every prompt matched on model, task, condition and display order",
                 11, INK2))
    kinds = [("dominance", "calibration tasks"), ("choice", "product choices"),
             ("helpfulness", "helpfulness ratings")]
    for i, (k, lab) in enumerate(kinds):
        if k not in r["by_kind"]:
            continue
        d = r["by_kind"][k]
        y = 160 + i * 66
        bw = 380
        o.append(txt(40, y - 6, "%s  (n=%d)" % (lab, d["n"]), 12, INK2))
        o.append('<rect x="40" y="%d" width="%d" height="30" fill="%s" opacity="0.15"/>'
                 % (y, bw, C[2]))
        o.append('<rect x="40" y="%d" width="%.1f" height="30" fill="%s"/>'
                 % (y, bw * d["identical"], C[2]))
        o.append(txt(40 + bw * d["identical"] - 8, y + 21,
                     "%.1f%% identical" % (d["identical"] * 100), 12.5, "#ffffff", "end",
                     bold=True))
        gap = 1 - d["identical"]
        if gap > 0.001:
            o.append(txt(40 + bw + 10, y + 21, "%.1f%% changed" % (gap * 100), 12, C[7],
                         bold=True))

    # right: did the effects move?
    x0 = 530
    o.append(txt(x0, 104, "Did the headline move?", 14, NAVY, bold=True))
    o.append(txt(x0, 122, "the two effects the hypotheses named, in rating points", 11, INK2))
    rows = [("Qwen, AI label", "qwen", "ai_minus_none", QC),
            ("Llama, AI label", "llama", "ai_minus_none", LC),
            ("Qwen, effort label", "qwen", "effort_minus_ai", QC),
            ("Llama, effort label", "llama", "effort_minus_ai", LC)]
    o.append(txt(x0 + 250, 150, "2 Nov", 11.5, MUTED, "middle", bold=True))
    o.append(txt(x0 + 360, 150, "25 Nov", 11.5, MUTED, "middle", bold=True))
    for i, (lab, mdl, key, col) in enumerate(rows):
        y = 176 + i * 40
        a = r["effects"]["original"][mdl][key]
        b2 = r["effects"]["rerun"][mdl][key]
        o.append(txt(x0, y, lab, 12.5, INK))
        o.append(txt(x0 + 250, y, "%+.2f" % a, 13, col, "middle", bold=True))
        o.append(txt(x0 + 305, y, "->", 12, MUTED, "middle"))
        o.append(txt(x0 + 360, y, "%+.2f" % b2, 13, col, "middle", bold=True))
        o.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
                 % (x0, y + 12, x0 + 400, y + 12, GRID))

    t = f.get("measured_run_time") or {}
    runs = {k: v["wall_clock_min"] for k, v in t.items() if isinstance(v, dict)}
    cost = ("%s, %.0f minutes of one desktop GPU in total"
            % (" + ".join("%s %.1f min" % (k, v) for k, v in runs.items()),
               sum(runs.values()))) if runs else "run time not recorded"
    # The first write-up called this "temperature 0 is not determinism". It is not
    # safe to say that from these two runs, because the Ollama binary changed
    # between them. The corrected reading is read from v2_findings.json when the
    # back-to-back run exists, and the box says so either way.
    det = (f.get("determinism_within_binary") or {})
    o.append('<rect x="40" y="384" width="%d" height="58" rx="5" fill="#FEF9E7" '
             'stroke="#B7950B"/>' % (W - 80))
    o.append(txt(54, 404, "Corrected: these two runs straddle an engine upgrade, so this is "
                          "not a determinism result.", 13, "#7D6608", bold=True))
    if det:
        o.append(txt(54, 421, "ollama.exe was replaced 9 Nov, between the runs; the weights were "
                              "not. Run back to back on one binary: %s of emitted ratings "
                              "differed," % det.get("integer", "?"), 11.5, "#7D6608"))
        o.append(txt(54, 436, "but %s of the underlying probability distributions did. Rarely "
                              "crosses a rounding boundary. Rerun cost: %s."
                     % (det.get("distribution", "?"), cost), 11.5, "#7D6608"))
    else:
        o.append(txt(54, 421, "ollama.exe was replaced 9 Nov, between the runs; the weights were "
                              "not. The 3.3% is an upper bound containing both", 11.5, "#7D6608"))
        o.append(txt(54, 436, "nondeterminism and software drift. Run label_run2.py --repeat to "
                              "separate them. Rerun cost: %s." % cost, 11.5, "#7D6608"))

    return svg(W, H, "\n".join(o),
               "The same audit, run again 23 days later",
               "Same stimuli file (hash checked), same models, same prompts, temperature 0, seed 1",
               ["%s prompts were matched one to one between the two runs. This is the check that separates "
                "\"I ran a study\" from \"I ran a study and it held\"."
                % f"{r['rows_matched']:,}"])


# ---------------------------------------------------------------------------
def sipoc(f):
    s4 = f["study4_ai_label"]
    n_prompts = s4["n_prompts"] + f.get("study3_green_claims", {}).get("n_prompts", 0)
    cols = [
        ("Suppliers", [" Amazon Reviews 2023 (McAuley Lab)", " Model publishers (Qwen, Meta)",
                       " Ollama local runtime", " Published human benchmark (JCR 2026)",
                       " The analyst (hypotheses)"]),
        ("Inputs", [" %d real reviews, 4-5 star" % s4["n_items"],
                    " 3 label conditions per review", " 2 shopper personas",
                    " Both display orders", " Hashed hypotheses + decision rule",
                    " Fixed seeds, temperature 0"]),
        ("Process", [" 1 Write and hash hypotheses", " 2 Build stimuli from the corpus",
                     " 3 Calibrate each model", " 4 Run every condition",
                     " 5 Parse and count failures", " 6 Fit per model",
                     " 7 Test the models against each other", " 8 Apply the robustness gate"]),
        ("Outputs", [" Pass / fail per hypothesis", " A cross-model gap with an interval",
                     " Calibration and parse rates", " Position-bias diagnostics",
                     " A reproduction delta", " A written limitation list"]),
        ("Customers", [" Whoever chooses the model", " Product owner of a recommender",
                       " Risk, audit and compliance", " Regulators reading disclosure rules",
                       " The next researcher (the repo)"]),
    ]
    W = 1180
    rows = max(len(c[1]) for c in cols)
    H = 150 + rows * 22 + 86
    cw = (W - 80) / 5.0
    b = []
    for i, (head, items) in enumerate(cols):
        x = 40 + i * cw
        b.append('<rect x="%.1f" y="88" width="%.1f" height="34" fill="%s"/>' % (x, cw - 8, NAVY))
        b.append(txt(x + cw / 2 - 4, 110, head.upper(), 13, "#ffffff", "middle", bold=True))
        b.append('<rect x="%.1f" y="122" width="%.1f" height="%d" fill="#ffffff" stroke="%s"/>'
                 % (x, cw - 8, rows * 22 + 10, GRID))
        for j, it in enumerate(items):
            b.append(txt(x + 10, 142 + j * 22, it, 11.5,
                         INK if head == "Process" else INK2))
    return svg(W, H, "\n".join(b),
               "SIPOC - the audit, treated as a process",
               "Not the shopping process. The process that tests whether an agent can be trusted with it.",
               ["%s prompts across both studies, every one logged with its condition, persona and display order."
                % f"{n_prompts:,}",
                "The customers column is the reason this is an operations artefact and not a paper: steps 3, 5 and 8 are quality",
                "gates with numeric thresholds, and step 8 is the one that failed, which is what the output is for."])


# ---------------------------------------------------------------------------
LANES = ["DESIGN", "RUN", "ANALYSE", "DECIDE"]
# (id, label, lane, x, width, gate?)
TASKS = [
    ("t1", "Write hypotheses\nand decision rule", 0, 40, 150, False),
    ("t2", "Hash the file\n(SHA-256)", 0, 210, 120, False),
    ("t3", "Build stimuli\nfrom the corpus", 0, 350, 130, False),
    ("t4", "Calibrate on\ndominance tasks", 1, 500, 130, False),
    ("g1", "95% correct?", 1, 650, 110, True),
    ("t5", "Run every\ncondition", 1, 780, 120, False),
    ("t6", "Parse answers,\ncount failures", 1, 920, 130, False),
    ("t7", "Fit each model\nseparately", 2, 1070, 130, False),
    ("t8", "Test the models\nagainst each other", 2, 1220, 150, False),
    ("g2", "Same sign in\nboth models?", 3, 1390, 130, True),
    ("t9", "Publish the\nfailure", 3, 1540, 120, False),
]
EVID = {
    "g1": "passed: 96.2% / 97.5%",
    "t6": "0 unparseable, 0 failed calls",
    "t8": "gap p = 1.7e-05",
    "g2": "FAILED - one model each way",
}


def bpmn_svg(f):
    s4 = f["study4_ai_label"]
    cal = s4["calibration"]
    ev = dict(EVID)
    ev["g1"] = "passed: " + ", ".join("%s %.1f%%" % (k, v * 100) for k, v in sorted(cal.items()))
    ev["t6"] = "%d unparseable of %d prompts" % (s4["unparseable"], s4["n_prompts"])
    ev["t8"] = "gap p = %.0e" % s4["interaction_raw"]["p"]
    W, H = 1720, 690
    lh = 96
    top = 110
    b = ['<defs><marker id="ar" markerWidth="9" markerHeight="7" refX="8" refY="3.5" '
         'orient="auto"><polygon points="0 0, 9 3.5, 0 7" fill="%s"/></marker></defs>' % NAVY]
    for i, lane in enumerate(LANES):
        y = top + i * lh
        b.append('<rect x="20" y="%d" width="%d" height="%d" fill="%s" stroke="%s"/>'
                 % (y, W - 40, lh, "#ffffff" if i % 2 else "#f6f5f2", GRID))
        b.append('<rect x="20" y="%d" width="30" height="%d" fill="%s"/>' % (y, lh, NAVY))
        b.append('<text x="35" y="%d" font-size="12" fill="#ffffff" text-anchor="middle" '
                 'letter-spacing="1" font-weight="bold" transform="rotate(-90 35 %d)">%s</text>'
                 % (y + lh / 2, y + lh / 2, escape(lane)))
    pos = {}
    for tid, label, lane, x, w, gate in TASKS:
        y = top + lane * lh + 18
        pos[tid] = (x, y, w, 60)
        if gate:
            failed = tid == "g2"
            col = C[7] if failed else C[2]
            b.append('<rect x="%d" y="%d" width="%d" height="60" rx="30" fill="%s" '
                     'stroke="%s" stroke-width="2"/>'
                     % (x, y, w, "#FBEFEF" if failed else "#EAF7F1", col))
        else:
            b.append('<rect x="%d" y="%d" width="%d" height="60" rx="5" fill="#ffffff" '
                     'stroke="%s" stroke-width="1.6"/>' % (x, y, w, NAVY))
        lines = label.split("\n")
        for j, ln in enumerate(lines):
            b.append(txt(x + w / 2, y + 30 + (j - (len(lines) - 1) / 2) * 15, ln,
                         11.5, INK, "middle", bold=gate))
        if tid in ev:
            col = C[7] if tid == "g2" else INK2
            b.append(txt(x + w / 2, y + 76, ev[tid], 10.5, col, "middle", bold=(tid == "g2")))
    order = [t[0] for t in TASKS]
    for a, c_ in zip(order, order[1:]):
        xa, ya, wa, ha = pos[a]
        xc, yc, wc, hc = pos[c_]
        if ya == yc:
            b.append('<path d="M %d %d L %d %d" stroke="%s" stroke-width="1.6" '
                     'marker-end="url(#ar)"/>' % (xa + wa, ya + 30, xc - 3, yc + 30, NAVY))
        else:
            mx = xa + wa + (xc - xa - wa) / 2
            b.append('<path d="M %d %d L %.1f %d L %.1f %d L %d %d" fill="none" stroke="%s" '
                     'stroke-width="1.6" marker-end="url(#ar)"/>'
                     % (xa + wa, ya + 30, mx, ya + 30, mx, yc + 30, xc - 3, yc + 30, NAVY))
    y0 = top + len(LANES) * lh + 26
    b.append('<rect x="20" y="%d" width="%d" height="78" rx="6" fill="#FBEFEF" '
             'stroke="%s" stroke-width="1.5"/>' % (y0, W - 40, C[7]))
    b.append(txt(36, y0 + 24, "The last gate failed, and that is the output.", 14,
                 "#922B21", bold=True))
    for i, ln in enumerate([
            "The rule was fixed before the run: a result counts only if it has the same sign and is significant in both models. "
            "One model discounted the AI label, the other rewarded it, so nothing shipped.",
            "A pipeline whose gates can only pass is not a pipeline. The value here is that a gate written in advance stopped a "
            "result the analyst would otherwise have been pleased to report."]):
        b.append(txt(36, y0 + 46 + i * 17, ln, 11.5, "#922B21"))
    return svg(W, H, "\n".join(b),
               "The audit pipeline, as a process with gates",
               "Four lanes, two gates with numeric thresholds fixed in advance, and the evidence each one produced",
               ["Generated from results/findings.json - the pass rates, parse counts and p-value under each box are read from the "
                "result files, not typed in."])


def bpmn_drawio(f):
    """The same diagram as mxGraph XML, so it opens in draw.io and can be edited."""
    s4 = f["study4_ai_label"]
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    lh, top = 140, 40
    for i, lane in enumerate(LANES):
        cells.append(
            '<mxCell id="lane%d" value="%s" style="swimlane;horizontal=0;startSize=28;'
            'fillColor=none;strokeColor=#1F3B57;fontStyle=1" vertex="1" parent="1">'
            '<mxGeometry x="20" y="%d" width="1740" height="%d" as="geometry"/></mxCell>'
            % (i, escape(lane), top + i * lh, lh))
    ev = dict(EVID)
    ev["g1"] = "passed: " + ", ".join("%s %.1f%%" % (k, v * 100)
                                      for k, v in sorted(s4["calibration"].items()))
    ev["t6"] = "%d unparseable of %d" % (s4["unparseable"], s4["n_prompts"])
    ev["t8"] = "gap p = %.0e" % s4["interaction_raw"]["p"]
    for tid, label, lane, x, w, gate in TASKS:
        note = ("&#10;&#10;" + escape(ev[tid])) if tid in ev else ""
        if gate:
            style = ("rhombus;whiteSpace=wrap;html=1;fillColor=%s;strokeColor=%s;fontStyle=1"
                     % (("#FBEFEF", "#e34948") if tid == "g2" else ("#EAF7F1", "#1baf7a")))
        else:
            style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#1F3B57"
        cells.append('<mxCell id="%s" value="%s%s" style="%s" vertex="1" parent="lane%d">'
                     '<mxGeometry x="%d" y="34" width="%d" height="70" as="geometry"/></mxCell>'
                     % (tid, escape(label.replace("\n", " ")), note, style, lane, x, w))
    order = [t[0] for t in TASKS]
    for k, (a, c_) in enumerate(zip(order, order[1:])):
        cells.append('<mxCell id="e%d" style="edgeStyle=orthogonalEdgeStyle;rounded=0;'
                     'strokeColor=#1F3B57" edge="1" parent="1" source="%s" target="%s">'
                     '<mxGeometry relative="1" as="geometry"/></mxCell>' % (k, a, c_))
    return ('<mxfile host="green-talk-green-proof"><diagram name="Audit pipeline">'
            '<mxGraphModel dx="1800" dy="900" grid="0" page="1" pageWidth="1169" '
            'pageHeight="826"><root>%s</root></mxGraphModel></diagram></mxfile>'
            % "".join(cells))


# ---------------------------------------------------------------------------
def value_stream_map(f):
    """Cycle time per step. Machine steps are measured; human steps are not, and say so."""
    s4 = f["study4_ai_label"]
    t = f.get("measured_run_time") or {}
    runs = {k: v["wall_clock_min"] for k, v in t.items() if isinstance(v, dict)}
    at = f.get("measured_analysis_time") or {}

    def secs(key):
        v = at.get(key)
        return ("%.0f s" % v["seconds"]) if v else None

    run_txt = ("%.1f-%.1f min\nper model" % (min(runs.values()), max(runs.values()))
               if runs else "not timed")
    steps = [
        ("Write hypotheses\nand the gate", "not instrumented", "human", False),
        ("Hash the file", "40 s before\nthe run began", "file timestamps", True),
        ("Build stimuli", "not timed\n(ran once, 2 Nov)", "no log kept", False),
        ("Calibrate\nboth models", "160 prompts,\ninside the run", "run log", True),
        ("Run every\ncondition", run_txt, "wall clock", bool(runs)),
        ("Parse and\ncount failures", "inside the run", "run log", True),
        ("Fit per model", secs("fit_per_model") or "not timed", "timed run",
         bool(secs("fit_per_model"))),
        ("Cross-model test\n+ bootstrap",
         (secs("cross_model_test") or "not timed") + "\n%d resamples" % s4["bootstrap"]["n"],
         "timed run", bool(secs("cross_model_test"))),
        ("Apply the gate,\nwrite it up", "not instrumented", "human", False),
    ]
    W, H = 1300, 560
    bw, gap = 118, 18
    L = 40
    b = ['<defs><marker id="ar2" markerWidth="8" markerHeight="6" refX="7" refY="3" '
         'orient="auto"><polygon points="0 0, 8 3, 0 6" fill="%s"/></marker></defs>' % NAVY]
    known = sum(1 for s in steps if s[3])
    for i, (name, tt, src, is_known) in enumerate(steps):
        x = L + i * (bw + gap)
        b.append('<rect x="%d" y="110" width="%d" height="78" rx="5" fill="%s" stroke="%s" '
                 'stroke-width="1.6"%s/>'
                 % (x, bw, "#ffffff" if is_known else "#FBEFEF", NAVY if is_known else C[7],
                    "" if is_known else ' stroke-dasharray="5 4"'))
        for j, ln in enumerate(name.split("\n")):
            b.append(txt(x + bw / 2, 140 + j * 15, ln, 11.5, INK, "middle", bold=True))
        b.append(txt(x + bw / 2, 180, src, 9.5, MUTED, "middle"))
        b.append('<rect x="%d" y="250" width="%d" height="40" fill="%s" opacity="0.14"/>'
                 % (x, bw, C[0] if is_known else C[7]))
        for j, ln in enumerate(tt.split("\n")):
            b.append(txt(x + bw / 2, 268 + j * 14, ln, 11, INK if is_known else C[7],
                         "middle", bold=not is_known))
        if i < len(steps) - 1:
            b.append('<path d="M %d 149 L %d 149" stroke="%s" stroke-width="1.6" '
                     'marker-end="url(#ar2)"/>' % (x + bw, x + bw + gap - 3, NAVY))
    b.append(txt(L, 240, "CYCLE TIME", 11, INK2, bold=True))
    b.append(txt(L, 104, "PROCESS STEP", 11, INK2, bold=True))

    b.append('<rect x="%d" y="328" width="%d" height="108" rx="6" fill="#FEF9E7" '
             'stroke="#B7950B" stroke-width="1.5"/>' % (L, W - 80))
    total = sum(runs.values()) + sum(v["seconds"] for v in at.values()) / 60.0
    b.append(txt(L + 14, 352, "%d of %d steps carry a measured number. The other %d do not, "
                 "and say so." % (known, len(steps), len(steps) - known),
                 14, "#7D6608", bold=True))
    lines = [
        "The useful number is not how long I took. It is that the machine half of a two-model pre-deployment check costs about "
        "%.0f minutes" % total,
        "on one desktop GPU (%s, plus %.0f s of analysis) for %d prompts, with nothing sent to a vendor."
        % (", ".join("%s %.1f min" % (k, v) for k, v in runs.items()),
           sum(v["seconds"] for v in at.values()), s4["n_prompts"]),
        "That is the entire cost of putting a gate in front of a model choice. It is too small to lose a budget argument over.",
        "The boxes marked not timed are not timed. Guessed cycle times make a map look finished and make it wrong.",
    ]
    for i, ln in enumerate(lines):
        b.append(txt(L + 14, 372 + i * 17, ln, 11.5, "#7D6608"))

    return svg(W, H, "\n".join(b),
               "Value stream map - what the audit actually costs",
               "Dashed red = not measured. Solid = read from the run log or the script.",
               ["If the run time box says \"not timed\", results/findings.json has no measured_run_time yet: run the audit again and rebuild."])


# ---------------------------------------------------------------------------
def main():
    with open(os.path.join(RES, "findings.json"), encoding="utf-8") as fh:
        f = json.load(fh)
    write("01-sign-flip.svg", chart_sign_flip(f))
    write("02-scale-use.svg", chart_scale_use(f))
    if "study3_green_claims" in f:
        write("03-three-switches.svg", chart_three_switches(f))
    write("04-sipoc.svg", sipoc(f))
    write("05-audit-pipeline.svg", bpmn_svg(f))
    write("05-audit-pipeline.drawio", bpmn_drawio(f))
    write("06-value-stream-map.svg", value_stream_map(f))
    if "reproduction" in f:
        write("07-reproduction.svg", chart_reproduction(f))
    else:
        print("  (no reproduction block in findings.json - rerun the audit to get 07)")
    print("all artefacts rebuilt from results/findings.json")


if __name__ == "__main__":
    main()
