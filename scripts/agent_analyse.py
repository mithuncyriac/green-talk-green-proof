"""Analyse the agent audit. Usage: python agent_analyse.py <agent_dir>"""
import glob, os, sys
import numpy as np, pandas as pd
import statsmodels.formula.api as smf

D = sys.argv[1]
df = pd.concat([pd.read_csv(p) for p in glob.glob(os.path.join(D, "out_*.csv"))], ignore_index=True)
for model, g in df.groupby("model"):
    print(f"\n################ {model} ################")
    dom = g[g.kind == "dominance"]
    print(f"Calibration: good product chosen in {dom.answer.astype(int).mean():.1%} of {len(dom)} dominance tasks (need >= 95%)")
    ch = g[(g.kind == "choice") & (g.answer != "?")].copy()
    ch["y"] = ch.answer.astype(int)
    print(f"Unparseable choice answers: {(g[g.kind=='choice'].answer=='?').mean():.1%}")
    ch["first"] = ((ch.order == "A_first") == (ch.y == 1)).astype(int)
    print(f"Picks the product shown first: {ch['first'].mean():.1%}  (position bias if far from 50%)")
    print("\nP(chooses product with the target review), %:")
    print((ch.pivot_table(index="cond", columns="persona", values="y", aggfunc="mean") * 100).round(1)
          .reindex(["neutral", "generic", "specific", "sceptical"]))
    ch["task_id"] = ch.ptype + "_" + ch.task.astype(str)
    m = smf.ols("y ~ C(cond, Treatment('neutral')) * persona + C(order) + C(task_id)", data=ch).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(ch.task_id)[0]})
    keep = [k for k in m.params.index if "cond" in k]
    print("\nLinear probability model (task FE, SE clustered by task); base = neutral, plain persona:")
    print(pd.DataFrame({"coef_pp": m.params[keep] * 100, "se_pp": m.bse[keep] * 100, "p": m.pvalues[keep]}).round(3).to_string())
    for persona in ["plain", "eco"]:
        sub = ch[ch.persona == persona]
        mg = sub[sub.cond == "generic"].groupby("task_id").y.mean(); ms = sub[sub.cond == "specific"].groupby("task_id").y.mean()
        d = (mg - ms).dropna()
        print(f"Generic minus specific choice ({persona}): {d.mean()*100:+.1f} pp (se {d.std(ddof=1)/np.sqrt(len(d))*100:.1f}, n tasks {len(d)})")
    hp = g[(g.kind == "helpfulness") & (g.answer != "?")].copy()
    if hp.empty:
        print("\n(no helpfulness ratings for this model)"); continue
    hp["r"] = hp.answer.astype(int)
    hp["task_id"] = hp.ptype + "_" + hp.task.astype(str)
    print(f"\nHelpfulness rating of the target review alone (1-7), unparseable {(g[g.kind=='helpfulness'].answer=='?').mean():.1%}:")
    print(hp.groupby("cond").r.agg(["mean", "std", "size"]).reindex(["neutral", "generic", "specific", "sceptical"]).round(2))
    mh = smf.ols("r ~ C(cond, Treatment('generic')) + C(ptype)", data=hp).fit(cov_type="HC1")
    k = [x for x in mh.params.index if "cond" in x]
    print("Rating differences vs generic:")
    print(pd.DataFrame({"coef": mh.params[k], "se": mh.bse[k], "p": mh.pvalues[k]}).round(3).to_string())
