"""Analyse the AI-label audit as pre-registered (prereg/ai-label-2026-11-02.md).
Usage: python label_analyse.py <csv> [<csv> ...]
"""
import sys
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
for k, path in enumerate(sys.argv[1:]):
    d = pd.read_csv(path); model = d.model.iloc[0]
    dom = d[d.kind == "dominance"]
    print(f"\n=== {model} ===\ncalibration: {dom.answer.astype(int).mean():.1%} correct of {len(dom)}"
          f" -> {'PASS' if dom.answer.astype(int).mean() >= .95 else 'EXCLUDE'}")
    d = d[d.kind != "dominance"].copy()
    d["item"] = d.ptype + "_" + d.task.astype(str)
    bad = (d.answer == "?").sum(); d = d[d.answer != "?"]; d["y"] = d.answer.astype(float)
    print("unparseable:", bad)
    tests = {}
    for kind, fe in [("helpfulness", "C(item)"), ("choice", "C(item) + C(order)")]:
        s = d[d.kind == kind]
        if kind == "choice":
            print(f"position bias: first-shown product picked "
                  f"{((s.order == 'A_first') & (s.y == 1) | (s.order == 'A_second') & (s.y == 0)).mean():.1%}")
        print(kind, "means:", s.groupby("cond").y.mean().round(3).to_dict())
        for ref, other, h in [("none", "ai", "H1" if kind == "helpfulness" else "H3"),
                              ("ai", "effort", "H2" if kind == "helpfulness" else "H4")]:
            m = smf.ols(f"y ~ C(cond, Treatment('{ref}')) + {fe}", s).fit(
                cov_type="cluster", cov_kwds={"groups": pd.factorize(s["item"])[0]})
            name = f"C(cond, Treatment('{ref}'))[T.{other}]"
            tests[h] = (f"{other} - {ref}", m.params[name], m.bse[name], m.pvalues[name])
        g = s.groupby("cond").y.agg(["mean", "sem"]).reindex(["none", "ai", "effort"])
        ax = axes[0 if kind == "helpfulness" else 1]
        ax.errorbar([0, 1, 2], g["mean"], yerr=1.96 * g["sem"], marker="o", capsize=3, label=model, alpha=.85)
        ax.set_xticks([0, 1, 2], ["no label", "Made with AI", "effort label"])
        ax.set_title("Helpfulness (1–7)" if kind == "helpfulness" else "P(choose product with labelled review)")
    hs = sorted(tests); adj = multipletests([tests[h][3] for h in hs], method="holm")[1]
    for h, pa in zip(hs, adj):
        c, b, se, p = tests[h]
        print(f"  {h} {c:14s} b={b:+.3f} se={se:.3f} p={p:.4f} holm={pa:.4f}")
axes[0].legend(fontsize=8); fig.tight_layout()
fig.savefig("results/04_label_audit.png", dpi=150)
print("\nfigure: results/04_label_audit.png")
