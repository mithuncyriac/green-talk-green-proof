"""Difference-in-differences / event study around the April 2022 FTC bamboo-rayon action.
Usage: python bamboo_analyse.py <bamboo_dir>
"""
import glob, os, sys
import numpy as np, pandas as pd
import statsmodels.api as sm

D = sys.argv[1]
df = pd.concat([pd.read_csv(p) for p in glob.glob(os.path.join(D, "*_textile_reviews.csv.gz"))], ignore_index=True)
df = df.drop_duplicates(subset=["parent_asin", "user_id", "ts"])
df["date"] = pd.to_datetime(df["ts"], unit="ms")
df["month"] = df["date"].dt.to_period("M")
EVENT = pd.Period("2022-04", "M")
df["rel_m"] = (df["month"] - EVENT).apply(lambda x: x.n)
df["post"] = (df["rel_m"] >= 0).astype(int)
df["treated"] = df["bamboo_prod"].astype(int)
df["any_scep"] = ((df["doubt"] == 1) | (df["green_scep"] == 1)).astype(int)
df["log_words"] = np.log(df["n_words"].clip(lower=1))
df["rating"] = df["rating"].astype(float)

print("=== Sample ===")
print(df.groupby("treated").agg(reviews=("any_scep", "size"), products=("parent_asin", "nunique")))
print("\nShares by group and period (%):")
print((df.groupby(["treated", "post"])[["any_scep", "doubt", "fibre", "green_scep", "mentions_bamboo"]].mean() * 100).round(3))

def twfe(data, y, xcols, iters=30):
    """Two-way FE (product, month) by alternating projections; OLS with SEs clustered by product."""
    cols = [y] + xcols
    Z = data[cols].astype(float).copy()
    g1 = data["parent_asin"].values; g2 = data["month"].astype(str).values
    for _ in range(iters):
        Z = Z - Z.groupby(g1).transform("mean")
        Z = Z - Z.groupby(g2).transform("mean")
    m = sm.OLS(Z[y], Z[xcols]).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(g1)[0]})
    return m

ctrl = ["log_words", "rating", "verified"]
df["tp"] = df["treated"] * df["post"]
print("\n=== H1/H2: DiD (product + month FE) ===")
for y in ["any_scep", "fibre", "doubt", "green_scep"]:
    m = twfe(df, y, ["tp"] + ctrl)
    base = df.loc[(df.treated == 1) & (df.post == 0), y].mean()
    print(f"{y:10s} coef={m.params['tp']*100:+.3f} pp  se={m.bse['tp']*100:.3f}  p={m.pvalues['tp']:.3f}  "
          f"(treated pre mean {base*100:.3f}%)  N={int(m.nobs):,}")

print("\n=== Event study by quarter (base = quarter -1), outcome any_scep and fibre ===")
df["rel_q"] = np.floor(df["rel_m"] / 3).astype(int).clip(-6, 5)
qs = [q for q in sorted(df["rel_q"].unique()) if q != -1]
for q in qs:
    df[f"q{q}"] = ((df["rel_q"] == q) & (df["treated"] == 1)).astype(int)
qcols = [f"q{q}" for q in qs]
for y in ["any_scep", "fibre"]:
    m = twfe(df, y, qcols + ctrl)
    print(f"\n{y}:")
    for q in qs:
        c = f"q{q}"
        print(f"  q{q:+d}: {m.params[c]*100:+.3f} pp (se {m.bse[c]*100:.3f})")
    pre = [f"q{q}" for q in qs if q < -1]
    R = np.zeros((len(pre), len(m.params)));
    for i, c in enumerate(pre): R[i, list(m.params.index).index(c)] = 1
    print("  pre-trend joint test p =", f"{float(m.f_test(R).pvalue):.3f}")

print("\n=== Placebo: fake event April 2021, pre-period data only ===")
pre_df = df[df["post"] == 0].copy()
pre_df["tp_fake"] = pre_df["treated"] * (pre_df["month"] >= pd.Period("2021-04", "M")).astype(int)
for y in ["any_scep", "fibre"]:
    m = twfe(pre_df, y, ["tp_fake"] + ctrl)
    print(f"{y:10s} coef={m.params['tp_fake']*100:+.3f} pp  se={m.bse['tp_fake']*100:.3f}  p={m.pvalues['tp_fake']:.3f}")

print("\n=== Monthly any_scep share (%), treated vs control ===")
mt = df.groupby(["month", "treated"])["any_scep"].mean().unstack() * 100
print(mt.round(3).to_string())
