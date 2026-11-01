"""Feasibility analysis for the 'Promise or proof?' idea.
Usage: python -I analyse.py <data_dir>
"""
import glob, json, os, sys
import numpy as np, pandas as pd
import statsmodels.formula.api as smf

D = sys.argv[1]
CUTOFF_MS = 1_695_000_000_000  # ~mid-Sept 2023, end of the Amazon Reviews'23 crawl
pd.set_option("display.width", 200)

summ = [json.load(open(p)) for p in glob.glob(os.path.join(D, "*_summary.json"))]
df = pd.concat([pd.read_csv(p) for p in glob.glob(os.path.join(D, "*_kept.csv.gz"))], ignore_index=True)

print("=== 1. Prevalence (full category files) ===")
for s in summ:
    n = s["n_reviews"]; c = s["counts"]; v = s["with_vote"]
    print(f"\n{s['cat']}: {n:,} reviews; {v['all']/n:.1%} have >=1 helpful vote")
    for k in ["generic", "specific", "evidence", "scep", "any"]:
        vv = f"; {v[k]:,} with >=1 vote ({v[k]/max(c[k],1):.1%})" if k in v else ""
        print(f"  {k:9s} {c[k]:>9,} ({c[k]/n:.3%}){vv}")

df["age_days"] = ((CUTOFF_MS - df["ts"]) / 86_400_000).clip(lower=1)
df["log_age"] = np.log(df["age_days"]); df["log_words"] = np.log(df["n_words"].clip(lower=1))
df["rating_c"] = df["rating"].astype(int).astype(str)
df["any_vote"] = (df["helpful_vote"] > 0).astype(int)
# mutually exclusive tiers for modelling: evidence > specific > generic-only
df["tier"] = np.select([df.evidence == 1, df.specific == 1, df.generic == 1], ["evidence", "specific", "generic"], "none")
flag = df[df.sampled == 0].copy()

print("\n=== 2. Mutually exclusive tiers among flagged reviews ===")
print(flag.groupby(["cat", "tier"]).agg(n=("helpful_vote", "size"), any_vote=("any_vote", "mean"),
      mean_votes=("helpful_vote", "mean"), med_words=("n_words", "median"), scep=("scep", "mean")).round(3))

# products with both a generic-only and an evidence/specific review
g = flag.groupby("parent_asin")["tier"].agg(lambda s: set(s))
both = g[g.apply(lambda s: "generic" in s and ("evidence" in s or "specific" in s))]
print(f"\nProducts with both generic-only and specific/evidence reviews: {len(both):,}")
fe = flag[flag.parent_asin.isin(both.index)]
print(f"Reviews in those products: {len(fe):,}; with >=1 vote: {fe.any_vote.sum():,}")

print("\n=== 3. Calibration (known effect): longer reviews get more votes, random 2% sample ===")
samp = df[df.sampled == 1]
m0 = smf.negativebinomial("helpful_vote ~ log_words + C(rating_c) + verified + log_age + C(cat)", data=samp).fit(disp=0, maxiter=200)
print(m0.params[["log_words", "log_age", "verified"]].round(3).to_string(), "\np(log_words) =", f"{m0.pvalues['log_words']:.2g}", f"N={int(m0.nobs):,}")

print("\n=== 4a. Pooled negative binomial, flagged reviews (base = generic-only) ===")
m1 = smf.negativebinomial("helpful_vote ~ C(tier, Treatment('generic')) + scep + log_words + C(rating_c) + verified + log_age + C(cat)",
                          data=flag).fit(disp=0, maxiter=200)
keep = [p for p in m1.params.index if "tier" in p or p in ("scep", "log_words")]
print(pd.DataFrame({"coef": m1.params[keep], "IRR": np.exp(m1.params[keep]), "p": m1.pvalues[keep]}).round(4), f"\nN={int(m1.nobs):,}")

print("\n=== 4b. Within-product fixed effects (linear, log1p votes), products with both tiers ===")
fe = fe.copy(); fe["y"] = np.log1p(fe["helpful_vote"])
fe["evid_or_spec"] = fe.tier.isin(["evidence", "specific"]).astype(int)
fe["is_evidence"] = (fe.tier == "evidence").astype(int)
cols = ["y", "any_vote", "evid_or_spec", "is_evidence", "scep", "log_words", "verified", "log_age", "rating"]
dm = fe[cols] - fe.groupby("parent_asin")[cols].transform("mean")
dm["pid"] = fe["parent_asin"].values
for dv in ["y", "any_vote"]:
    m2 = smf.ols(f"{dv} ~ evid_or_spec + is_evidence + scep + log_words + verified + log_age + rating - 1", data=dm).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(dm["pid"])[0]})
    k = ["evid_or_spec", "is_evidence", "scep", "log_words"]
    print(f"\nDV={dv}:\n", pd.DataFrame({"coef": m2.params[k], "se": m2.bse[k], "p": m2.pvalues[k]}).round(4).to_string(), f"\nN={int(m2.nobs):,}")

print("\n=== 5. Random texts for a precision spot check ===")
for t in ["generic", "specific", "evidence"]:
    s = flag[flag.tier == t].sample(12, random_state=1)
    print(f"\n--- {t} ---")
    for txt in s["text"]:
        print(" *", txt[:260])
s = flag[flag.scep == 1].sample(12, random_state=1)
print("\n--- scepticism ---")
for txt in s["text"]:
    print(" *", txt[:260])
