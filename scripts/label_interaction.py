"""Does the AI-label effect actually DIFFER between the two models?

The pre-registered analysis (label_analyse.py) fits each model separately and
reports that Qwen's "Made with AI" effect is negative and Llama's is positive.
Two opposite signs are not a difference until the difference itself is tested.
This script runs that test, three ways, because each way answers a different
objection:

  1. POOLED INTERACTION. Both models rated the same 100 reviews, so item fixed
     effects and a condition x model interaction test the gap directly.
     Standard errors are clustered by item, which is the unit that repeats.
  2. STANDARDISED. The two models use the 1-7 scale differently (Llama sits
     around 4.8 with no label, Qwen around 6.0). A raw-point gap could be a
     scale artefact, so the same test is run on ratings standardised within
     model. If the interaction survives, it is not the scale.
  3. ITEM-CLUSTER BOOTSTRAP. p-values near .02 on 100 items invite the reply
     "that is noise". Resampling items with replacement gives a distribution
     of the gap that does not lean on the normal approximation.

It also prints the rating distribution per model and condition (to show whether
either model is at a ceiling) and confirms that the helpfulness task has no
display order at all, which is why position bias cannot contaminate H1.

Usage: python label_interaction.py <csv> <csv> [--boot N]
"""
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

args = sys.argv[1:]
nboot = 2000
if "--boot" in args:
    i = args.index("--boot")
    nboot = int(args[i + 1])
    del args[i:i + 2]
paths = [a for a in args if not a.startswith("--")]
if len(paths) != 2:
    sys.exit("need exactly two result CSVs, one per model")

SHORT = {"qwen2.5:7b": "qwen", "llama3.1:8b": "llama"}

frames = []
for p in paths:
    d = pd.read_csv(p)
    d["model"] = d.model.map(lambda m: SHORT.get(m, m))
    frames.append(d)
d = pd.concat(frames, ignore_index=True)

# ---------------------------------------------------------------- helpfulness
h = d[d.kind == "helpfulness"].copy()
h["item"] = h.ptype + "_" + h.task.astype(str)
unparsed = (h.answer == "?").sum()
h = h[h.answer != "?"].copy()
h["y"] = h.answer.astype(float)

print("=== what is being tested ===")
print(f"helpfulness ratings: {len(h)} ({unparsed} unparseable dropped)")
print("models:", sorted(h.model.unique()), "| items:", h.item.nunique(),
      "| conditions:", sorted(h.cond.unique()))
order_values = sorted(set(h.order.fillna("").astype(str)))
print("display orders present in the helpfulness task:", order_values,
      "<- no two-product layout, so order cannot contaminate H1")

print("\n=== rating distribution: do the two models even use the same scale? ===")
dist = (h.groupby(["model", "cond"]).y
        .agg(n="size", mean="mean", sd="std", lowest="min", highest="max")
        .round(3))
print(dist.to_string())
print("\nfull histogram of every rating emitted (counts out of 100 per cell):")
hist = (pd.crosstab([h.model, h.cond], h.y)
        .reindex(pd.MultiIndex.from_product([sorted(h.model.unique()),
                                             ["none", "ai", "effort"]]))
        .fillna(0).astype(int))
print(hist.to_string())
print("\nA scale point a model never emits is a point it cannot move to. Check the")
print("headroom each model actually has above its own modal answer before reading")
print("the sign of its effect as a preference.")

# 1. pooled interaction, raw points -----------------------------------------
print("\n=== 1. pooled interaction, raw 1-7 points ===")
print("y ~ cond * model + item FE, SEs clustered by item")
m = smf.ols("y ~ C(cond, Treatment('none')) * C(model, Treatment('qwen')) + C(item)",
            h).fit(cov_type="cluster",
                   cov_kwds={"groups": pd.factorize(h["item"])[0]})
rows = [c for c in m.params.index if "cond" in c and "item" not in c]
for c in rows:
    label = (c.replace("C(cond, Treatment('none'))[T.", "")
              .replace("C(model, Treatment('qwen'))[T.", "")
              .replace("]", "").replace(":", " x "))
    print(f"  {label:28s} b={m.params[c]:+.3f}  se={m.bse[c]:.3f}  p={m.pvalues[c]:.4f}")
key = "C(cond, Treatment('none'))[T.ai]:C(model, Treatment('qwen'))[T.llama]"
print(f"\n  INTERACTION (ai x llama) = the sign flip itself: b={m.params[key]:+.3f}, "
      f"p={m.pvalues[key]:.4g}")
ci = m.conf_int().loc[key]
print(f"  95% CI [{ci[0]:+.3f}, {ci[1]:+.3f}]")

# 2. standardised within model ----------------------------------------------
print("\n=== 2. same test on ratings standardised within model ===")
h["z"] = h.groupby("model").y.transform(lambda s: (s - s.mean()) / s.std(ddof=0))
mz = smf.ols("z ~ C(cond, Treatment('none')) * C(model, Treatment('qwen')) + C(item)",
             h).fit(cov_type="cluster",
                    cov_kwds={"groups": pd.factorize(h["item"])[0]})
print(f"  INTERACTION (ai x llama), in SDs: b={mz.params[key]:+.3f}, "
      f"se={mz.bse[key]:.3f}, p={mz.pvalues[key]:.4g}")
ciz = mz.conf_int().loc[key]
print(f"  95% CI [{ciz[0]:+.3f}, {ciz[1]:+.3f}]")

# 3. item-cluster bootstrap --------------------------------------------------
print(f"\n=== 3. item-cluster bootstrap, {nboot} resamples of the 100 items ===")


def effects(frame):
    """Per-model (ai - none) and (effort - ai) within-item differences."""
    w = frame.pivot_table(index=["model", "item"], columns="cond",
                          values="y", aggfunc="mean")
    if not {"none", "ai", "effort"}.issubset(w.columns):
        return None
    g = w.groupby("model")
    return {
        "qwen_ai": (g.get_group("qwen")["ai"] - g.get_group("qwen")["none"]).mean(),
        "llama_ai": (g.get_group("llama")["ai"] - g.get_group("llama")["none"]).mean(),
        "qwen_effort": (g.get_group("qwen")["effort"] - g.get_group("qwen")["ai"]).mean(),
        "llama_effort": (g.get_group("llama")["effort"] - g.get_group("llama")["ai"]).mean(),
    }


point = effects(h)
point["gap"] = point["llama_ai"] - point["qwen_ai"]

items = h.item.unique()
rng = np.random.default_rng(1)
by_item = {k: v for k, v in h.groupby("item")}
draws = []
for _ in range(nboot):
    pick = rng.choice(items, size=len(items), replace=True)
    rep = pd.concat([by_item[i].assign(item=f"{i}__{j}") for j, i in enumerate(pick)],
                    ignore_index=True)
    e = effects(rep)
    if e:
        e["gap"] = e["llama_ai"] - e["qwen_ai"]
        draws.append(e)
b = pd.DataFrame(draws)

print("  effect                  point     95% percentile CI      share of draws crossing 0")
for k, name in [("qwen_ai", "Qwen:  ai - none"), ("llama_ai", "Llama: ai - none"),
                ("qwen_effort", "Qwen:  effort - ai"), ("llama_effort", "Llama: effort - ai"),
                ("gap", "GAP:   llama - qwen")]:
    lo, hi = np.percentile(b[k], [2.5, 97.5])
    cross = (b[k] <= 0).mean() if point[k] > 0 else (b[k] >= 0).mean()
    print(f"  {name:22s} {point[k]:+.3f}   [{lo:+.3f}, {hi:+.3f}]   {cross:.3f}")

print(f"\n  draws in which Qwen is negative AND Llama is positive: "
      f"{((b.qwen_ai < 0) & (b.llama_ai > 0)).mean():.3f}")

# ------------------------------------------------------------------- choices
c = d[d.kind == "choice"].copy()
c = c[c.answer != "?"]
c["y"] = c.answer.astype(float)
print("\n=== choice task: can the instrument see a choice effect at all? ===")
for mdl, s in c.groupby("model"):
    first = ((s.order == "A_first") & (s.y == 1) | (s.order == "A_second") & (s.y == 0)).mean()
    print(f"  {mdl:6s} picks the first-shown product {first:.1%} of the time; "
          f"P(choose A) range across conditions "
          f"{s.groupby('cond').y.mean().min():.3f}-{s.groupby('cond').y.mean().max():.3f}")
print("  A model that almost always picks the first product has almost no variance")
print("  left for a label to move. Its null is uninformative, not evidence of no effect.")
