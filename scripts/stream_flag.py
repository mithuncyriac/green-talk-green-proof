"""Stream one Amazon Reviews'23 category file, flag sustainability language,
keep flagged reviews plus a 2% random sample of unflagged ones.

Usage: python -I stream_flag.py <Category> <out_dir>
"""
import csv, gzip, json, random, re, sys, time, os
import requests

CAT, OUT = sys.argv[1], sys.argv[2]
URL = f"https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/{CAT}.jsonl.gz"
SAMPLE_RATE = 0.02
random.seed(20261101)

# Pilot dictionaries (v0). Tier 1 = generic claim; tier 2 = specific attribute claim;
# tier 3 = observable evidence; scep = scepticism / contradiction.
GENERIC = re.compile(r"\b(eco[- ]?friendly|environmentally[- ]friendly|earth[- ]friendly|planet[- ]friendly|"
                     r"sustainabl[ey]|sustainability|eco[- ]conscious|environmentally conscious|"
                     r"(better|good|kind|kinder) (for|to) the (environment|planet|earth))\b", re.I)
SPECIFIC = re.compile(r"\b(biodegradable|compostable|recyclable|plastic[- ]free|zero[- ]waste|"
                      r"sustainably sourced|non[- ]toxic to the (environment|planet)|carbon[- ]neutral|"
                      r"made (from|with|of) recycled|recycled (plastic|paper|material|materials|cardboard|packaging))\b", re.I)
EVIDENCE = re.compile(r"\b(cardboard (box|tube|packaging|container)|paper (packaging|wrap|wrapping|box)|"
                      r"glass (jar|bottle|container)|refill (pouch|pack|bag|bottle)|refillable|"
                      r"no plastic (packaging|wrap|in the)|minimal packaging|less plastic|"
                      r"fsc[- ]certified|b[- ]corp|ewg[- ]verified|usda organic|post[- ]consumer|"
                      r"recycling (symbol|code|number)|#\s?[1-7] plastic)\b", re.I)
SCEP = re.compile(r"\b(greenwash\w*|so much plastic|too much (plastic|packaging)|excessive packaging|"
                  r"wasteful packaging|not (really|actually|very|truly) (eco|environment\w*|sustainab\w*|biodegradable|recyclable)|"
                  r"(claims?|supposed|advertised|marketed) (to be|as) (eco|biodegradable|compostable|recyclable|sustainab\w*|plastic[- ]free))", re.I)

FIELDS = ["cat", "parent_asin", "user_id", "rating", "helpful_vote", "verified", "ts", "n_words",
          "generic", "specific", "evidence", "scep", "sampled", "text"]

def main():
    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, f"{CAT}_kept.csv.gz")
    n = 0; counts = {"generic": 0, "specific": 0, "evidence": 0, "scep": 0, "any": 0}
    voted = {"all": 0, "generic": 0, "specific": 0, "evidence": 0, "scep": 0}
    t0 = time.time()
    with requests.get(URL, stream=True, timeout=120) as r, gzip.open(out_path, "wt", newline="", encoding="utf-8") as fo:
        r.raise_for_status()
        w = csv.writer(fo); w.writerow(FIELDS)
        with gzip.GzipFile(fileobj=r.raw) as gz:
            for line in gz:
                n += 1
                d = json.loads(line)
                txt = (d.get("title") or "") + " . " + (d.get("text") or "")
                f = {"generic": bool(GENERIC.search(txt)), "specific": bool(SPECIFIC.search(txt)),
                     "evidence": bool(EVIDENCE.search(txt)), "scep": bool(SCEP.search(txt))}
                hv = int(d.get("helpful_vote") or 0)
                if hv > 0: voted["all"] += 1
                anyf = any(f.values())
                for k, v in f.items():
                    if v:
                        counts[k] += 1
                        if hv > 0: voted[k] += 1
                if anyf: counts["any"] += 1
                sampled = (not anyf) and random.random() < SAMPLE_RATE
                if anyf or sampled:
                    w.writerow([CAT, d.get("parent_asin"), d.get("user_id"), d.get("rating"), hv,
                                int(bool(d.get("verified_purchase"))), d.get("timestamp"), len(txt.split()),
                                int(f["generic"]), int(f["specific"]), int(f["evidence"]), int(f["scep"]),
                                int(sampled), txt[:2000].replace("\n", " ")])
                if n % 1_000_000 == 0:
                    print(f"{CAT}: {n:,} lines, {counts['any']:,} flagged, {time.time()-t0:.0f}s", flush=True)
    summary = {"cat": CAT, "n_reviews": n, "counts": counts, "with_vote": voted,
               "sample_rate": SAMPLE_RATE, "seconds": round(time.time() - t0)}
    with open(os.path.join(OUT, f"{CAT}_summary.json"), "w") as fs:
        json.dump(summary, fs, indent=2)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
