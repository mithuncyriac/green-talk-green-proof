"""Collapse every result file into one findings.json, so no figure is hand-typed.

Reads whatever exists:
    results/03_agent_audit_*.csv            green-claims agent audit (study 3)
    results/04_label_audit_*.csv            AI-label audit, original run (study 4)
    results/rerun-*/04_label_audit_*.csv    the same audit, rerun later
    results/rerun-*/rerun.log               wall-clock per model, for the value stream map

Writes results/findings.json. make_visuals.py draws from that file and nothing else.

Usage: python build_findings.py [results_dir]
"""
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

RES = sys.argv[1] if len(sys.argv) > 1 else "results"
SHORT = {"qwen2.5:7b": "qwen", "llama3.1:8b": "llama"}
CONDS = ["none", "ai", "effort"]
NBOOT = 2000


def load(pattern):
    out = []
    for p in sorted(glob.glob(pattern)):
        d = pd.read_csv(p)
        d["model"] = d.model.map(lambda m: SHORT.get(m, m))
        out.append(d)
    return pd.concat(out, ignore_index=True) if out else None


def helpfulness(d):
    h = d[(d.kind == "helpfulness") & (d.answer != "?")].copy()
    h["item"] = h.ptype + "_" + h.task.astype(str)
    h["y"] = h.answer.astype(float)
    return h


def label_block(d):
    """Everything the AI-label audit says, for one run of it."""
    h = helpfulness(d)
    out = {"n_ratings": int(len(h)), "n_items": int(h.item.nunique()), "models": {}}

    for mdl, s in h.groupby("model"):
        hist = s.y.value_counts().reindex(range(1, 8)).fillna(0).astype(int)
        out["models"][mdl] = {
            "means": {c: round(float(s[s.cond == c].y.mean()), 3) for c in CONDS},
            "hist": {c: s[s.cond == c].y.value_counts()
                     .reindex(range(1, 8)).fillna(0).astype(int).tolist() for c in CONDS},
            "scale_points_used": [int(v) for v in sorted(s.y.unique())],
            "highest_emitted": int(s.y.max()),
            "share_at_own_max": round(float((s[s.cond == "none"].y == s.y.max()).mean()), 3),
            "hist_all": hist.tolist(),
        }

    # pooled condition x model interaction, item FE, SEs clustered by item
    key = ("C(cond, Treatment('none'))[T.ai]:C(model, Treatment('qwen'))[T.llama]")
    for tag, col in [("raw", "y"), ("standardised", "z")]:
        if col == "z":
            h["z"] = h.groupby("model").y.transform(lambda v: (v - v.mean()) / v.std(ddof=0))
        m = smf.ols(f"{col} ~ C(cond, Treatment('none')) * C(model, Treatment('qwen')) + C(item)",
                    h).fit(cov_type="cluster",
                           cov_kwds={"groups": pd.factorize(h["item"])[0]})
        ci = m.conf_int().loc[key]
        out[f"interaction_{tag}"] = {
            "coef": round(float(m.params[key]), 4),
            "se": round(float(m.bse[key]), 4),
            "p": float(m.pvalues[key]),
            "ci": [round(float(ci[0]), 4), round(float(ci[1]), 4)],
        }

    # item-cluster bootstrap of each model's effect and of the gap
    def eff(frame):
        w = frame.pivot_table(index=["model", "item"], columns="cond",
                              values="y", aggfunc="mean")
        if not set(CONDS).issubset(w.columns):
            return None
        g = w.groupby("model")
        e = {}
        for mdl in ["qwen", "llama"]:
            if mdl not in g.groups:
                return None
            gm = g.get_group(mdl)
            e[f"{mdl}_ai"] = float((gm["ai"] - gm["none"]).mean())
            e[f"{mdl}_effort"] = float((gm["effort"] - gm["ai"]).mean())
        e["gap"] = e["llama_ai"] - e["qwen_ai"]
        return e

    point = eff(h)
    items = h.item.unique()
    by_item = {k: v for k, v in h.groupby("item")}
    rng = np.random.default_rng(1)
    draws = []
    for _ in range(NBOOT):
        pick = rng.choice(items, size=len(items), replace=True)
        rep = pd.concat([by_item[i].assign(item=f"{i}__{j}") for j, i in enumerate(pick)],
                        ignore_index=True)
        e = eff(rep)
        if e:
            draws.append(e)
    b = pd.DataFrame(draws)
    out["bootstrap"] = {"n": len(b), "effects": {}}
    for k, v in point.items():
        lo, hi = np.percentile(b[k], [2.5, 97.5])
        out["bootstrap"]["effects"][k] = {"point": round(v, 4),
                                          "ci": [round(float(lo), 4), round(float(hi), 4)]}
    out["bootstrap"]["share_signs_hold"] = round(
        float(((b.qwen_ai < 0) & (b.llama_ai > 0)).mean()), 4)

    # choice task: how much variance is left after position bias
    c = d[(d.kind == "choice") & (d.answer != "?")].copy()
    c["y"] = c.answer.astype(float)
    out["choice"] = {}
    for mdl, s in c.groupby("model"):
        first = ((s.order == "A_first") & (s.y == 1) |
                 (s.order == "A_second") & (s.y == 0)).mean()
        out["choice"][mdl] = {
            "picks_first_shown": round(float(first), 4),
            "p_choose_a": {k: round(float(v), 4)
                           for k, v in s.groupby("cond").y.mean().items()},
        }

    dom = d[d.kind == "dominance"]
    out["calibration"] = {mdl: round(float(s.answer.astype(int).mean()), 4)
                          for mdl, s in dom.groupby("model")}
    out["unparseable"] = int((d.answer == "?").sum())
    out["n_prompts"] = int(len(d))
    return out


def reproduction(orig, rerun):
    """Did the later run give the same answers? Compared row by row, not in aggregate."""
    keys = ["model", "kind", "ptype", "task", "cond", "order"]
    a = orig.copy()
    b = rerun.copy()
    for f in (a, b):
        f["order"] = f["order"].fillna("")
        f["cond"] = f["cond"].fillna("")
    m = a.merge(b, on=keys, suffixes=("_1", "_2"))
    out = {"rows_matched": int(len(m)), "by_kind": {}}
    for kind, s in m.groupby("kind"):
        same = (s.answer_1.astype(str) == s.answer_2.astype(str)).mean()
        out["by_kind"][kind] = {"n": int(len(s)), "identical": round(float(same), 4)}
    h1, h2 = helpfulness(orig), helpfulness(rerun)
    out["effects"] = {}
    for tag, f in [("original", h1), ("rerun", h2)]:
        out["effects"][tag] = {}
        for mdl, s in f.groupby("model"):
            w = s.pivot_table(index="item", columns="cond", values="y", aggfunc="mean")
            out["effects"][tag][mdl] = {
                "ai_minus_none": round(float((w["ai"] - w["none"]).mean()), 4),
                "effort_minus_ai": round(float((w["effort"] - w["ai"]).mean()), 4),
            }
    return out


def green_block(d):
    """Study 3: green claims x persona, the design-switch evidence."""
    c = d[(d.kind == "choice") & (d.answer != "?")].copy()
    c["y"] = c.answer.astype(float)
    out = {"n_prompts": int(len(d)), "models": {}}
    for mdl, s in c.groupby("model"):
        first = ((s.order == "A_first") & (s.y == 1) |
                 (s.order == "A_second") & (s.y == 0)).mean()
        out["models"][mdl] = {
            "picks_first_shown": round(float(first), 4),
            "by_persona": {p: {k: round(float(v), 4) for k, v in
                               g.groupby("cond").y.mean().items()}
                           for p, g in s.groupby("persona")},
        }
    h = d[(d.kind == "helpfulness") & (d.answer != "?")].copy()
    h["y"] = h.answer.astype(float)
    for mdl, s in h.groupby("model"):
        out["models"][mdl]["helpfulness"] = {
            k: round(float(v), 3) for k, v in s.groupby("cond").y.mean().items()}
    dom = d[d.kind == "dominance"]
    out["calibration"] = {mdl: round(float(s.answer.astype(int).mean()), 4)
                          for mdl, s in dom.groupby("model")}
    return out


def timings(logpath):
    """Wall clock per model, straight out of the rerun log. The one measured cycle time."""
    if not os.path.exists(logpath):
        return None
    txt = open(logpath, encoding="utf-8", errors="replace").read()
    out = {}
    # "--- qwen2.5:7b ---" ... "real 12m34.5s"  (bash `time`)
    blocks = re.split(r"^--- (\S+) ---\s*$", txt, flags=re.M)
    for i in range(1, len(blocks) - 1, 2):
        mdl = SHORT.get(blocks[i], blocks[i])
        m = re.search(r"real\s+(?:(\d+)m)?([\d.]+)s", blocks[i + 1])
        if m:
            mins = int(m.group(1) or 0)
            out[mdl] = {"wall_clock_min": round(mins + float(m.group(2)) / 60.0, 1)}
    m = re.search(r"stimuli sha256:\s*([0-9a-f]{64})", txt)
    if m:
        out["stimuli_sha256"] = m.group(1)
    return out or None


def main():
    # Relative, never absolute: this file is published, and an absolute path
    # would put the author's machine and username in a public artefact.
    f = {"generated_from": os.path.relpath(RES).replace(os.sep, "/")}

    g = load(os.path.join(RES, "03_agent_audit_*.csv"))
    if g is not None:
        f["study3_green_claims"] = green_block(g)

    orig = load(os.path.join(RES, "04_label_audit_*.csv"))
    if orig is not None:
        f["study4_ai_label"] = label_block(orig)

    # Only trust a rerun whose log says it finished. The run streams rows as it
    # goes, so a half-written CSV would quietly become a "reproduction failure".
    rerun_dirs = [d for d in sorted(glob.glob(os.path.join(RES, "rerun-*")))
                  if os.path.exists(os.path.join(d, "rerun.log"))
                  and "rerun finished" in open(os.path.join(d, "rerun.log"),
                                               encoding="utf-8", errors="replace").read()]
    if rerun_dirs:
        rd = rerun_dirs[-1]
        re_d = load(os.path.join(rd, "04_label_audit_*.csv"))
        if re_d is not None and orig is not None:
            f["reproduction"] = reproduction(orig, re_d)
            f["reproduction"]["rerun_dir"] = os.path.basename(rd)
            f["reproduction"]["models_rerun"] = sorted(re_d.model.unique())
            f["study4_rerun"] = label_block(re_d)
        t = timings(os.path.join(rd, "rerun.log"))
        if t:
            f["measured_run_time"] = t

    at = os.path.join(RES, "analysis_timings.json")
    if os.path.exists(at):
        with open(at, encoding="utf-8") as fh:
            f["measured_analysis_time"] = json.load(fh)

    os.makedirs(RES, exist_ok=True)
    out = os.path.join(RES, "findings.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(f, fh, indent=1)
    print("wrote", out)
    for k in f:
        print("  ", k)


if __name__ == "__main__":
    main()
