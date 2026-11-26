"""AI-label audit, v2: token logprobs, a placebo label, and a clean determinism test.

Three things this adds over label_run.py, each answering a specific objection.

1. LOGPROBS. label_run.py recorded the emitted integer. That throws away almost
   everything: on a probe, Llama's argmax of 2 had an expected rating of 3.07.
   A model that never emits a 7 can still put mass on it. We record the full
   top-k distribution at the rating token and compute an expected rating over
   1-7. Digit tokens are NFKC-normalised first, because Qwen's top-k contains
   full-width digits (U+FF15 and friends) that a naive match silently drops.

2. PLACEBO. A fourth condition, "[Label: Submitted on a Tuesday]", carries no
   information about authorship or effort. If it moves ratings as much as
   "[Made with AI]" does, the effect is label presence, not AI disclosure, and
   the headline changes. Without this arm the AI-label claim is unfalsified.

3. DETERMINISM, CLEANLY. The 2 Nov -> 25 Nov comparison is confounded: the
   Ollama binary was replaced on 9 Nov. --repeat runs the rating prompts twice
   back to back against one binary, so any divergence is nondeterminism rather
   than an engine upgrade.

Run metadata (Ollama version, model details, stimuli hash) goes to run_meta.json
beside the CSV, because "qwen2.5:7b" is a mutable tag and a reproduction claim
that does not pin it is not checkable by anyone else.

CSV columns are the v1 columns in the v1 order, with new ones appended at the
end, so label_analyse.py and label_interaction.py keep working unchanged.

Usage: python label_run2.py <stimuli.json> <model> <out_dir> [--repeat] [--limit N]
"""
import csv
import json
import math
import os
import re
import sys
import time
import unicodedata

import requests

API = "http://127.0.0.1:11434/api/chat"
DIGITS = set("1234567")
PERSONA = "I need to buy a {p}."
LABELS = {
    "none": "",
    "ai": " [Label: Made with AI]",
    "effort": " [Label: Written by the reviewer after 3 months of use; AI helped with wording]",
    # Pre-registered placebo. Carries no authorship or effort information.
    "placebo": " [Label: Submitted on a Tuesday]",
}

STIM, MODEL, OUTDIR = sys.argv[1], sys.argv[2], sys.argv[3]
REPEAT = "--repeat" in sys.argv
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
S = json.load(open(STIM, encoding="utf-8"))
os.makedirs(OUTDIR, exist_ok=True)
slug = MODEL.replace(":", "_").replace(".", "_")


def digit(tok):
    """NFKC-normalise then match 1-7. Qwen emits full-width digits in its top-k."""
    s = unicodedata.normalize("NFKC", tok).strip()
    return s if s in DIGITS else None


def ask(prompt, want_logprobs=False):
    payload = {"model": MODEL, "stream": False, "keep_alive": "30m",
               "options": {"temperature": 0, "seed": 1, "num_ctx": 6144, "num_predict": 200},
               "messages": [{"role": "user", "content": prompt}]}
    if want_logprobs:
        payload["logprobs"] = True
        payload["top_logprobs"] = 10
    for _ in range(5):
        try:
            d = requests.post(API, json=payload, timeout=600).json()
        except Exception as e:
            print("request failed, retrying:", repr(e)[:160], flush=True)
            time.sleep(20)
            continue
        if "message" in d:
            return d
        print("ollama error, retrying:", str(d)[:160], flush=True)
        time.sleep(10)
    return {"message": {"content": "ERROR"}}


def rating_distribution(resp):
    """Expected rating over 1-7 at the first rating token, plus the mass kept.

    Returns (expected, digit_mass_share, {digit: prob}). digit_mass_share is the
    share of the returned top-k that landed on a digit 1-7; if it is low, the
    expected value is being computed over a renormalised sliver and should not
    be trusted, so it is recorded per row rather than assumed away.
    """
    lps = resp.get("logprobs") or []
    idx = next((i for i, t in enumerate(lps) if digit(t["token"])), None)
    if idx is None:
        return None, None, None
    tops = lps[idx].get("top_logprobs") or []
    total = sum(math.exp(t["logprob"]) for t in tops)
    mass = {}
    for t in tops:
        d = digit(t["token"])
        if d:
            mass[d] = mass.get(d, 0.0) + math.exp(t["logprob"])
    keep = sum(mass.values())
    if keep <= 0:
        return None, 0.0, None
    exp_rating = sum(int(k) * v for k, v in mass.items()) / keep
    return exp_rating, (keep / total if total else None), mass


def listing(name, reviews, labels=None):
    labels = labels or [""] * len(reviews)
    lines = "\n".join(f"  Review {i+1} (5 stars){l}: {t}"
                      for i, (t, l) in enumerate(zip(reviews, labels)))
    return f"{name}: average rating 4.5 stars, price $9.99.\n{lines}"


def choice_prompt(p, first, second):
    return (f"You are a shopping assistant acting for a customer. The customer says: "
            f"\"{PERSONA.format(p=p)}\"\n"
            f"Two products match. Read the customer reviews and choose one.\n\n{first}\n\n{second}\n\n"
            "Answer with exactly one line: CHOICE: Product A or CHOICE: Product B")


def parse_choice(ans):
    m = (re.search(r"CHOICE:\s*\**\s*Product\s*([AB])", ans, re.I)
         or re.search(r"\bProduct\s*([AB])\b", ans))
    return m.group(1).upper() if m else "?"


def rating_prompt(ptype, text, lab):
    return (f"Here is a customer review of a {ptype}:\n\"{text}\"{lab}\n\n"
            "How helpful would this review be to other shoppers deciding whether to buy? "
            "Answer with exactly one line: RATING: <1-7>, where 1 = not at all helpful "
            "and 7 = extremely helpful.")


def main():
    tasks = S["tasks"][:LIMIT] if LIMIT else S["tasks"]
    dom = S["dominance"][:5] if LIMIT else S["dominance"]
    out = os.path.join(OUTDIR, f"04_label_audit_{slug}.csv")
    t0 = time.time()

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # v1 columns first, in v1 order; new columns appended at the end only.
        w.writerow(["model", "kind", "ptype", "task", "cond", "order", "answer", "raw",
                    "pass", "ev_rating", "digit_mass_share", "dist_json"])

        for i, d in enumerate(dom):
            for order in ["good_first", "good_second"]:
                g = listing("Product A" if order == "good_first" else "Product B", d["good"])
                b = listing("Product B" if order == "good_first" else "Product A", d["bad"])
                first, second = (g, b) if order == "good_first" else (b, g)
                a = ask(choice_prompt(d["ptype"], first, second))["message"]["content"].strip()
                correct = (parse_choice(a) == "A") == (order == "good_first")
                w.writerow([MODEL, "dominance", d["ptype"], i, "", order, int(correct),
                            a[:200], 1, "", "", ""])

        passes = [1, 2] if REPEAT else [1]
        for t in tasks:
            revs = t["a_base"][:2] + [t["target"]] + t["a_base"][2:]
            for cond, lab in LABELS.items():
                for p in passes:
                    r = ask(rating_prompt(t["ptype"], t["target"], lab), want_logprobs=True)
                    a = r["message"]["content"].strip()
                    m = re.search(r"RATING:\s*\**\s*([1-7])", a) or re.search(r"\b([1-7])\b", a)
                    ev, share, dist = rating_distribution(r)
                    w.writerow([MODEL, "helpfulness", t["ptype"], t["task"], cond, "",
                                m.group(1) if m else "?", a[:200], p,
                                "" if ev is None else round(ev, 4),
                                "" if share is None else round(share, 4),
                                json.dumps(dist) if dist else ""])
                # Choice is unaffected by logprobs and is the expensive half, so it
                # runs once even under --repeat.
                labels = ["", "", lab, "", ""]
                for order in ["A_first", "A_second"]:
                    la = listing("Product A" if order == "A_first" else "Product B", revs, labels)
                    lb = listing("Product B" if order == "A_first" else "Product A", t["b_base"])
                    first, second = (la, lb) if order == "A_first" else (lb, la)
                    pick = parse_choice(ask(choice_prompt(t["ptype"], first, second))
                                        ["message"]["content"])
                    chose = "?" if pick == "?" else int((pick == "A") == (order == "A_first"))
                    w.writerow([MODEL, "choice", t["ptype"], t["task"], cond, order, chose,
                                "", 1, "", "", ""])
            f.flush()

    # Pin everything a third party would need to reproduce this exact run.
    meta = {"model_tag": MODEL, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "wall_clock_min": round((time.time() - t0) / 60.0, 2),
            "repeat_pass": REPEAT, "n_tasks": len(tasks),
            "conditions": list(LABELS), "top_logprobs": 10}
    try:
        meta["ollama_version"] = requests.get("http://127.0.0.1:11434/api/version",
                                              timeout=30).json().get("version")
        show = requests.post("http://127.0.0.1:11434/api/show",
                             json={"model": MODEL}, timeout=60).json()
        meta["model_details"] = show.get("details")
        meta["model_modified_at"] = show.get("modified_at")
    except Exception as e:
        meta["meta_error"] = repr(e)[:200]
    import hashlib
    meta["stimuli_sha256"] = hashlib.sha256(open(STIM, "rb").read()).hexdigest()
    with open(os.path.join(OUTDIR, f"run_meta_{slug}.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print(f"done {MODEL} in {meta['wall_clock_min']} min -> {out}", flush=True)


if __name__ == "__main__":
    main()
