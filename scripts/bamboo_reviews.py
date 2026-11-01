"""Keep reviews of textile products (from bamboo_meta.py) posted Oct 2020 - Sep 2023, with scepticism flags.
Usage: python bamboo_reviews.py <Category> <meta_Category> <out_dir>
"""
import csv, gzip, json, os, re, sys, time
import requests

CAT, META, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
URL = f"https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/{CAT}.jsonl.gz"
T_START, T_END = 1_601_510_400_000, 1_695_000_000_000  # 1 Oct 2020 to mid-Sep 2023 (ms)

FIBRE = re.compile(r"\b(rayon|viscose|lyocell|modal)\b", re.I)
DOUBT = re.compile(r"\b(not (really |actually |truly |real |genuine |100% |pure )?bamboo|fake bamboo|so[- ]called bamboo|"
                   r"greenwash\w*|misleading|false(ly)? advertis\w*|lied about|deceptive|not as advertised)\b", re.I)
GREEN_SCEP = re.compile(r"\b(greenwash\w*|not (really|actually|very|truly) (eco|environment\w*|sustainab\w*)|"
                        r"(claims?|supposed|advertised|marketed) (to be|as) (eco|sustainab\w*|organic|natural))", re.I)
BAMBOO = re.compile(r"\bbamboo\b", re.I)

def main():
    prods = {}
    with gzip.open(os.path.join(OUT, f"{META}_textiles.csv.gz"), "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            prods[row["parent_asin"]] = row["bamboo"]
    print(f"{CAT}: {len(prods):,} textile products loaded", flush=True)
    n = kept = 0; t0 = time.time()
    with requests.get(URL, stream=True, timeout=120) as r, \
         gzip.open(os.path.join(OUT, f"{CAT}_textile_reviews.csv.gz"), "wt", newline="", encoding="utf-8") as fo:
        r.raise_for_status()
        w = csv.writer(fo)
        w.writerow(["parent_asin", "bamboo_prod", "user_id", "ts", "rating", "helpful_vote", "verified",
                    "n_words", "mentions_bamboo", "fibre", "doubt", "green_scep"])
        with gzip.GzipFile(fileobj=r.raw) as gz:
            for line in gz:
                n += 1
                d = json.loads(line)
                pa = d.get("parent_asin")
                if pa not in prods:
                    continue
                ts = d.get("timestamp") or 0
                if not (T_START <= ts < T_END):
                    continue
                txt = (d.get("title") or "") + " . " + (d.get("text") or "")
                w.writerow([pa, prods[pa], d.get("user_id"), ts, d.get("rating"), d.get("helpful_vote"),
                            int(bool(d.get("verified_purchase"))), len(txt.split()),
                            int(bool(BAMBOO.search(txt))), int(bool(FIBRE.search(txt))),
                            int(bool(DOUBT.search(txt))), int(bool(GREEN_SCEP.search(txt)))])
                kept += 1
                if n % 2_000_000 == 0:
                    print(f"{CAT}: {n:,} lines, {kept:,} kept, {time.time()-t0:.0f}s", flush=True)
    print(json.dumps({"cat": CAT, "lines": n, "kept": kept, "seconds": round(time.time()-t0)}))

if __name__ == "__main__":
    main()
