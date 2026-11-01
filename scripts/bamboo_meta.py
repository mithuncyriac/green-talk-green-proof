"""Find textile products in an Amazon Reviews'23 metadata file and flag bamboo-labelled ones.
Usage: python bamboo_meta.py <meta_Category> <out_dir>
"""
import csv, gzip, json, os, re, sys, time
import requests

CAT, OUT = sys.argv[1], sys.argv[2]
URL = f"https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/meta_categories/{CAT}.jsonl.gz"

# Textile types named in the FTC bamboo/rayon cases (sheets, towels, blankets, bras) plus close siblings.
TEXTILE = re.compile(r"\b(sheets?|sheet set|pillow ?cases?|duvet cover|comforter|blankets?|throws?|"
                     r"towels?|washcloths?|bath ?robes?|robes?|pajamas?|pyjamas?|sleepwear|nightgown|"
                     r"socks|underwear|boxers?|briefs|bras?|bralette|t-?shirts?|tees?|tank tops?|leggings|"
                     r"onesies?|rompers?|swaddles?|bodysuits?|sleepers?)\b", re.I)
NOT_TEXTILE = re.compile(r"\b(rack|holder|hanger|organi[sz]er|shelf|shelves|tray|board|hook|basket|hamper|"
                         r"bar\b|stand|bin|caddy|box|ladder|clip|bag)\b", re.I)
BAMBOO = re.compile(r"\bbamboo\b", re.I)

def main():
    os.makedirs(OUT, exist_ok=True)
    n = kept = bam = 0; t0 = time.time()
    with requests.get(URL, stream=True, timeout=120) as r, \
         gzip.open(os.path.join(OUT, f"{CAT}_textiles.csv.gz"), "wt", newline="", encoding="utf-8") as fo:
        r.raise_for_status()
        w = csv.writer(fo); w.writerow(["parent_asin", "bamboo", "main_category", "title"])
        with gzip.GzipFile(fileobj=r.raw) as gz:
            for line in gz:
                n += 1
                d = json.loads(line)
                t = d.get("title") or ""
                if TEXTILE.search(t) and not NOT_TEXTILE.search(t):
                    b = int(bool(BAMBOO.search(t)))
                    w.writerow([d.get("parent_asin"), b, d.get("main_category"), t[:200]])
                    kept += 1; bam += b
                if n % 1_000_000 == 0:
                    print(f"{CAT}: {n:,} products, {kept:,} textiles, {bam:,} bamboo, {time.time()-t0:.0f}s", flush=True)
    print(json.dumps({"cat": CAT, "products": n, "textiles": kept, "bamboo": bam, "seconds": round(time.time()-t0)}))

if __name__ == "__main__":
    main()
