"""Does the model weight a trust cue by how INFORMATIVE it is, or by what it looks like?

This is the test two blind reviewers independently asked for, and it is the one that
could move this work from "an audit" to "a theory test".

THE THEORY. Signalling theory says a signal only carries information if it is costly
to fake or possible to verify. A rational reader should weight a cue in proportion to
how well it predicts quality. If the cue predicts nothing, it should be ignored.

THE TEST. Put a "[VERIFIED PURCHASE]" tag on a review, and vary, in context, how well
that tag has historically predicted a good product:

    validity 0.9   the tag was right 9 times out of 10
    validity 0.5   the tag was right half the time, i.e. it tells you nothing
    validity 0.0   the tag was never right
    reversed       the tag reliably predicted a BAD product

PREDICTIONS, fixed before running:
  H8  DIAGNOSTIC USE. The weight the tag carries scales with its stated validity:
      strongly positive at 0.9, near zero at 0.5 and 0.0, negative when reversed.
      A regression of tag effect on validity gives a clearly positive slope.
  H9  PRIOR-DRIVEN USE. The weight is flat across all four conditions. The model
      responds to the tag's appearance, not its stated informativeness.

DECISION RULE. A flat slope (CI including zero) supports the framing that LLM
evaluators weight trust cues by absorbed priors rather than by diagnosticity. A
clearly positive slope falsifies it. Either outcome is reportable; the framing only
survives if H9 wins.

This is a PILOT. 50 items, two local quantised models, one prompt wording. It cannot
settle the question. It can show whether the effect is worth a proper study.

Usage: python diagnosticity.py <stimuli.json> <model> <out_dir> [--n 50]
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

HISTORY = {
    "v0.9": ("In this store, past audits found that reviews carrying the VERIFIED "
             "PURCHASE tag described the product accurately 9 times out of 10. "
             "Reviews without the tag were accurate about half the time."),
    "v0.5": ("In this store, past audits found that reviews carrying the VERIFIED "
             "PURCHASE tag described the product accurately about half the time. "
             "Reviews without the tag were also accurate about half the time."),
    "v0.0": ("In this store, past audits found that reviews carrying the VERIFIED "
             "PURCHASE tag were almost never accurate. Reviews without the tag were "
             "accurate about half the time."),
    "rev": ("In this store, past audits found that reviews carrying the VERIFIED "
            "PURCHASE tag reliably described products that turned out to be poor "
            "quality. Reviews without the tag were accurate about half the time."),
}
TAG = " [VERIFIED PURCHASE]"

STIM, MODEL, OUTDIR = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 50
os.makedirs(OUTDIR, exist_ok=True)
slug = MODEL.replace(":", "_").replace(".", "_")


def digit(tok):
    s = unicodedata.normalize("NFKC", tok).strip()
    return s if s in DIGITS else None


def ask(prompt):
    for _ in range(5):
        try:
            d = requests.post(API, json={
                "model": MODEL, "stream": False, "keep_alive": "30m",
                "options": {"temperature": 0, "seed": 1, "num_ctx": 6144,
                            "num_predict": 120},
                "logprobs": True, "top_logprobs": 10,
                "messages": [{"role": "user", "content": prompt}]}, timeout=600).json()
        except Exception as e:
            print("retry:", repr(e)[:120], flush=True); time.sleep(15); continue
        if "message" in d:
            return d
        time.sleep(10)
    return {"message": {"content": "ERROR"}}


def expected_rating(resp):
    lps = resp.get("logprobs") or []
    idx = next((i for i, t in enumerate(lps) if digit(t["token"])), None)
    if idx is None:
        return None
    mass = {}
    for t in lps[idx].get("top_logprobs") or []:
        d = digit(t["token"])
        if d:
            mass[d] = mass.get(d, 0.0) + math.exp(t["logprob"])
    keep = sum(mass.values())
    return (sum(int(k) * v for k, v in mass.items()) / keep) if keep > 0 else None


def prompt_for(history, ptype, text, tagged):
    return (f"{history}\n\n"
            f"Here is a customer review of a {ptype}:\n"
            f"\"{text}\"{TAG if tagged else ''}\n\n"
            "How helpful would this review be to a shopper deciding whether to buy? "
            "Answer with exactly one line: RATING: <1-7>, where 1 = not at all "
            "helpful and 7 = extremely helpful.")


def main():
    tasks = json.load(open(STIM, encoding="utf-8"))["tasks"][:N]
    out = os.path.join(OUTDIR, f"diagnosticity_{slug}.csv")
    t0 = time.time()
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "validity", "task", "ptype", "tagged", "answer",
                    "ev_rating"])
        for cond, hist in HISTORY.items():
            for t in tasks:
                for tagged in (False, True):
                    r = ask(prompt_for(hist, t["ptype"], t["target"], tagged))
                    a = r["message"]["content"].strip()
                    m = (re.search(r"RATING:\s*\**\s*([1-7])", a)
                         or re.search(r"\b([1-7])\b", a))
                    ev = expected_rating(r)
                    w.writerow([MODEL, cond, t["task"], t["ptype"], int(tagged),
                                m.group(1) if m else "?",
                                "" if ev is None else round(ev, 4)])
                f.flush()
            print(f"  {MODEL} {cond} done ({time.time()-t0:.0f}s)", flush=True)
    print(f"done {MODEL} in {(time.time()-t0)/60:.1f} min -> {out}", flush=True)


if __name__ == "__main__":
    main()
