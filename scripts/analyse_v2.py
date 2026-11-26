"""Analyse the v2 run against the hypotheses hashed before it started.

Tests, in the order the pre-registration (prereg/placebo-and-logprobs-2026-11-26.md)
states them:

  H5  placebo is inert          |placebo - none| < 0.14 in both models
  H6  the sign flip is not a    scored on EXPECTED ratings, Qwen stays negative,
      scale artefact            Llama stays positive, interaction CI excludes 0
  H7  within-binary determinism <1% of rating prompts return a different integer
                                across two back-to-back passes

Plus TOST equivalence bounds on the choice nulls, because a non-significant
difference is not evidence of equivalence and the project currently states one as
if it were.

Everything is scored twice: on the emitted integer (comparable with the 2 Nov and
25 Nov runs) and on the expected rating over the 1-7 probability mass (which is
what the logprobs were captured for).

Usage: python analyse_v2.py <v2_results_dir>
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

D = sys.argv[1] if len(sys.argv) > 1 else "results/v2-2026-11-26"
SHORT = {"qwen2.5:7b": "qwen", "llama3.1:8b": "llama"}
CONDS = ["none", "ai", "effort", "placebo"]
PREREG_THRESHOLD = 0.14          # size of the 2 Nov Qwen AI-label effect
DETERMINISM_THRESHOLD = 0.01     # H7


def load(d):
    fr = []
    for p in sorted(glob.glob(os.path.join(d, "04_label_audit_*.csv"))):
        f = pd.read_csv(p)
        f["model"] = f.model.map(lambda m: SHORT.get(m, m))
        fr.append(f)
    if not fr:
        sys.exit("no result CSVs in " + d)
    return pd.concat(fr, ignore_index=True)


def main():
    d = load(D)
    models = sorted(d.model.unique())
    print("models present:", models)
    if len(models) < 2:
        print("\n!! only one model finished. H6 needs both; H5 and H7 reported per model.\n")

    h = d[(d.kind == "helpfulness") & (d.answer != "?")].copy()
    h["item"] = h.ptype + "_" + h.task.astype(str)
    h["y"] = h.answer.astype(float)
    h["ev"] = pd.to_numeric(h.ev_rating, errors="coerce")
    p1 = h[h["pass"] == 1].copy()

    out = {"models": models, "digit_mass_min": float(h.digit_mass_share.min())}

    # ---------------------------------------------------------------- H7
    print("\n" + "=" * 66)
    print("H7  within-binary determinism (pre-registered: <1% integers differ)")
    print("=" * 66)
    out["H7"] = {}
    for m, s in h.groupby("model"):
        w = s.pivot_table(index=["item", "cond"], columns="pass", values="y")
        if w.shape[1] < 2:
            print(f"  {m}: no repeat pass"); continue
        w.columns = ["p1", "p2"]
        we = s.pivot_table(index=["item", "cond"], columns="pass", values="ev")
        we.columns = ["e1", "e2"]
        int_diff = float((w.p1 != w.p2).mean())
        ev_diff = float(((we.e1 - we.e2).abs() > 1e-9).mean())
        verdict = "HOLDS" if int_diff < DETERMINISM_THRESHOLD else "FAILS"
        out["H7"][m] = {"n": int(len(w)), "integer_differed": round(int_diff, 4),
                        "distribution_differed": round(ev_diff, 4),
                        "max_abs_ev_shift": round(float((we.e1 - we.e2).abs().max()), 4),
                        "verdict": verdict}
        print(f"  {m:6s} integers differ {int_diff*100:5.2f}%  ->  {verdict}")
        print(f"         distributions differ {ev_diff*100:5.1f}%  "
              f"(max shift {out['H7'][m]['max_abs_ev_shift']:.4f})")
    print("  Reading: nondeterminism is real underneath but rarely crosses the rounding")
    print("  boundary. The 23-day figure also contains an Ollama upgrade (binary 9 Nov).")

    # ---------------------------------------------------------------- H5
    print("\n" + "=" * 66)
    print(f"H5  placebo is inert (pre-registered: |placebo - none| < {PREREG_THRESHOLD})")
    print("=" * 66)
    out["H5"] = {}
    for m, s in p1.groupby("model"):
        out["H5"][m] = {}
        for col, lab in [("y", "emitted"), ("ev", "expected")]:
            w = s.pivot_table(index="item", columns="cond", values=col)
            if not set(CONDS).issubset(w.columns):
                continue
            eff = {c: float((w[c] - w["none"]).mean()) for c in ["ai", "effort", "placebo"]}
            out["H5"][m][lab] = {k: round(v, 4) for k, v in eff.items()}
            verdict = "HOLDS" if abs(eff["placebo"]) < PREREG_THRESHOLD else "FAILS"
            out["H5"][m][lab]["verdict"] = verdict
            ratio = abs(eff["ai"]) / abs(eff["placebo"]) if eff["placebo"] else float("inf")
            print(f"  {m:6s} {lab:9s} ai {eff['ai']:+.4f} | effort {eff['effort']:+.4f} | "
                  f"placebo {eff['placebo']:+.4f}  -> {verdict}  (AI is {ratio:.1f}x placebo)")

    # ---------------------------------------------------------------- H6
    print("\n" + "=" * 66)
    print("H6  the sign flip survives expected-rating scoring")
    print("=" * 66)
    if len(models) == 2:
        key = ("C(cond, Treatment('none'))[T.ai]:C(model, Treatment('qwen'))[T.llama]")
        out["H6"] = {}
        for col, lab in [("y", "emitted"), ("ev", "expected")]:
            s = p1[p1.cond.isin(["none", "ai"])].dropna(subset=[col])
            mod = smf.ols(f"{col} ~ C(cond, Treatment('none')) * C(model, Treatment('qwen')) "
                          "+ C(item)", s).fit(
                cov_type="cluster", cov_kwds={"groups": pd.factorize(s["item"])[0]})
            ci = mod.conf_int().loc[key]
            signs = {m: float((g.pivot_table(index="item", columns="cond", values=col)["ai"]
                               - g.pivot_table(index="item", columns="cond",
                                               values=col)["none"]).mean())
                     for m, g in s.groupby("model")}
            ok = (signs.get("qwen", 0) < 0 < signs.get("llama", 0)) and not (ci[0] <= 0 <= ci[1])
            out["H6"][lab] = {"interaction": round(float(mod.params[key]), 4),
                              "p": float(mod.pvalues[key]),
                              "ci": [round(float(ci[0]), 4), round(float(ci[1]), 4)],
                              "qwen_ai": round(signs.get("qwen", float("nan")), 4),
                              "llama_ai": round(signs.get("llama", float("nan")), 4),
                              "verdict": "HOLDS" if ok else "FAILS"}
            print(f"  {lab:9s} qwen {signs.get('qwen',float('nan')):+.4f} | "
                  f"llama {signs.get('llama',float('nan')):+.4f} | interaction "
                  f"{mod.params[key]:+.4f} p={mod.pvalues[key]:.2e} "
                  f"CI [{ci[0]:+.3f},{ci[1]:+.3f}] -> {out['H6'][lab]['verdict']}")
    else:
        print("  skipped, needs both models")

    # ------------------------------------------------- TOST on the choice nulls
    print("\n" + "=" * 66)
    print("TOST equivalence on the choice nulls (bound = 5 percentage points)")
    print("=" * 66)
    BOUND = 0.05
    c = d[(d.kind == "choice") & (d.answer != "?")].copy()
    c["y"] = c.answer.astype(float)
    c["item"] = c.ptype + "_" + c.task.astype(str)
    out["TOST"] = {}
    for m, s in c.groupby("model"):
        w = s.pivot_table(index="item", columns="cond", values="y")
        if "none" not in w.columns:
            continue
        out["TOST"][m] = {}
        for cond in ["ai", "effort", "placebo"]:
            if cond not in w.columns:
                continue
            diff = (w[cond] - w["none"]).dropna()
            mean, se, n = diff.mean(), diff.std(ddof=1) / np.sqrt(len(diff)), len(diff)
            if se == 0:
                out["TOST"][m][cond] = {"mean_pp": 0.0, "note": "zero variance"}
                print(f"  {m:6s} {cond:8s} no variance at all (position-saturated)")
                continue
            from scipy import stats as st
            t1 = (mean + BOUND) / se
            t2 = (mean - BOUND) / se
            p_tost = max(st.t.sf(t1, n - 1), st.t.cdf(t2, n - 1))
            lo, hi = mean - 1.96 * se, mean + 1.96 * se
            eq = "EQUIVALENT" if p_tost < .05 else "inconclusive"
            out["TOST"][m][cond] = {"mean_pp": round(mean * 100, 2),
                                    "ci_pp": [round(lo * 100, 2), round(hi * 100, 2)],
                                    "p_tost": float(p_tost), "verdict": eq}
            print(f"  {m:6s} {cond:8s} {mean*100:+.2f} pp  CI [{lo*100:+.2f},{hi*100:+.2f}]  "
                  f"p_TOST={p_tost:.4f}  -> {eq}")
    print("  'inconclusive' means the data cannot rule out an effect as large as the")
    print("  bound. It is NOT evidence of no effect, which is how the project currently")
    print("  reads the 76.7 vs 77.1 result.")

    with open(os.path.join(D, "v2_findings.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("\nwrote", os.path.join(D, "v2_findings.json"))


if __name__ == "__main__":
    main()
