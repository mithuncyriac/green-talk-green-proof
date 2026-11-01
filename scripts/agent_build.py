"""Build agent choice tasks from flagged Amazon reviews.
Usage: python agent_build.py <data_dir> <out_json>
"""
import glob, json, os, random, sys
import pandas as pd

D, OUT = sys.argv[1], sys.argv[2]
random.seed(7)
df = pd.concat([pd.read_csv(p) for p in glob.glob(os.path.join(D, "*_kept.csv.gz"))], ignore_index=True)
df["tier"] = df.apply(lambda r: "sceptical" if r.scep else "evidence" if r.evidence else "specific" if r.specific
                      else "generic" if r.generic else "neutral", axis=1)
df = df[df.n_words.between(30, 150) & df.rating.isin([4, 5])]
df["text"] = df["text"].str.replace("<br />", " ", regex=False).str.replace(r"\s+", " ", regex=True)

TYPES = {"shampoo": r"\bshampoo", "hand soap": r"\b(?:hand soap|soap)\b",
         "laundry detergent": r"\bdetergent", "toothbrush": r"\btoothbrush"}
CONDS = ["neutral", "generic", "specific", "sceptical"]  # 'evidence' tier skipped: dictionary precision too low
N_TASKS = 30

tasks, targets = [], []
for ptype, pat in TYPES.items():
    sub = df[df.text.str.contains(pat, case=False, regex=True)]
    pools = {c: sub[sub.tier == c].sample(frac=1, random_state=1) for c in CONDS}
    base = pools["neutral"]
    for i in range(N_TASKS):
        a_base = base.iloc[i * 9: i * 9 + 4]["text"].tolist()
        b_base = base.iloc[i * 9 + 4: i * 9 + 8]["text"].tolist()
        tgt = {c: pools[c].iloc[i]["text"] if c != "neutral" else base.iloc[i * 9 + 8]["text"] for c in CONDS}
        for c in CONDS:
            targets.append({"ptype": ptype, "task": i, "cond": c, "text": tgt[c]})
        tasks.append({"ptype": ptype, "task": i, "a_base": a_base, "b_base": b_base, "target": tgt})

# dominance checks: A gets 5 positive reviews, B gets 5 one/two-star reviews (from the 2% random sample)
neg = pd.concat([pd.read_csv(p) for p in glob.glob(os.path.join(D, "*_kept.csv.gz"))])
neg = neg[(neg.sampled == 1) & neg.rating.isin([1, 2]) & neg.n_words.between(30, 150)]
dom = []
for ptype, pat in TYPES.items():
    nsub = neg[neg.text.str.contains(pat, case=False, regex=True)].sample(frac=1, random_state=2)
    psub = df[(df.tier == "neutral") & df.text.str.contains(pat, case=False, regex=True)].sample(frac=1, random_state=3)
    for i in range(10):
        dom.append({"ptype": ptype, "good": psub.iloc[i*5:i*5+5]["text"].tolist(), "bad": nsub.iloc[i*5:i*5+5]["text"].tolist()})

json.dump({"tasks": tasks, "targets": targets, "dominance": dom}, open(OUT, "w"), indent=1)
print(len(tasks), "tasks;", len(targets), "target reviews;", len(dom), "dominance checks")
