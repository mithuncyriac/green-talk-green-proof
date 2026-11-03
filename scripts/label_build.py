"""Build AI-label tasks from flagged Amazon reviews (pre-registration: prereg/ai-label-2026-11-02.md).
Usage: python label_build.py <data_dir> <pilot_stimuli.json> <out_json>
"""
import glob, json, os, sys
import pandas as pd

D, PILOT, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
df = pd.concat([pd.read_csv(p) for p in glob.glob(os.path.join(D, "*_kept.csv.gz"))], ignore_index=True)
df = df[~(df.scep | df.evidence | df.specific | df.generic) & df.n_words.between(30, 150) & df.rating.isin([4, 5])]
df["text"] = df["text"].str.replace("<br />", " ", regex=False).str.replace(r"\s+", " ", regex=True)
df = df[~df.text.str.contains(r"\bAI\b|artificial intelligence|chatgpt", case=False, regex=True)]

TYPES = {"shampoo": r"\bshampoo", "hand soap": r"\b(?:hand soap|soap)\b",
         "laundry detergent": r"\bdetergent", "toothbrush": r"\btoothbrush"}
N = 25
tasks = []
for ptype, pat in TYPES.items():
    sub = df[df.text.str.contains(pat, case=False, regex=True)].sample(frac=1, random_state=11)
    for i in range(N):
        rows = sub.iloc[i * 9: i * 9 + 9]
        tasks.append({"ptype": ptype, "task": i, "target": rows.iloc[0]["text"],
                      "target_votes": int(rows.iloc[0]["helpful_vote"]),
                      "a_base": rows.iloc[1:5]["text"].tolist(), "b_base": rows.iloc[5:9]["text"].tolist()})

dom = json.load(open(PILOT))["dominance"]
json.dump({"tasks": tasks, "dominance": dom}, open(OUT, "w"), indent=1)
print(len(tasks), "tasks;", len(dom), "dominance checks")
