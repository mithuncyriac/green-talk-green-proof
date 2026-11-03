"""Run the AI-label audit against a local Ollama model (prompts as in agent_run.py).
Usage: python label_run.py <label_stimuli.json> <model> <out_csv>
"""
import csv, json, re, sys, time
import requests

STIM, MODEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
S = json.load(open(STIM))
API = "http://127.0.0.1:11434/api/chat"
PERSONA = "I need to buy a {p}."
LABELS = {"none": "", "ai": " [Label: Made with AI]",
          "effort": " [Label: Written by the reviewer after 3 months of use; AI helped with wording]"}

def ask(prompt):
    for attempt in range(5):
        try:
            r = requests.post(API, json={"model": MODEL, "stream": False, "keep_alive": "30m",
                                         "options": {"temperature": 0, "seed": 1, "num_ctx": 6144, "num_predict": 200},
                                         "messages": [{"role": "user", "content": prompt}]}, timeout=600)
            d = r.json()
        except Exception as e:
            print("request failed, retrying:", repr(e)[:200], flush=True); time.sleep(20); continue
        if "message" in d:
            return d["message"]["content"].strip()
        print("ollama error, retrying:", str(d)[:200], flush=True); time.sleep(10)
    return "ERROR"

def listing(name, reviews, labels=None):
    labels = labels or [""] * len(reviews)
    lines = "\n".join(f"  Review {i+1} (5 stars){l}: {t}" for i, (t, l) in enumerate(zip(reviews, labels)))
    return f"{name}: average rating 4.5 stars, price $9.99.\n{lines}"

def choice_prompt(p, first, second):
    return (f"You are a shopping assistant acting for a customer. The customer says: \"{PERSONA.format(p=p)}\"\n"
            f"Two products match. Read the customer reviews and choose one.\n\n{first}\n\n{second}\n\n"
            "Answer with exactly one line: CHOICE: Product A or CHOICE: Product B")

def parse(ans):
    m = re.search(r"CHOICE:\s*\**\s*Product\s*([AB])", ans, re.I) or re.search(r"\bProduct\s*([AB])\b", ans)
    return m.group(1).upper() if m else "?"

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["model", "kind", "ptype", "task", "cond", "order", "answer", "raw"])
    # 1. dominance calibration (same tasks as the 1 Nov pilot)
    for i, d in enumerate(S["dominance"]):
        for order in ["good_first", "good_second"]:
            g = listing("Product A" if order == "good_first" else "Product B", d["good"])
            b = listing("Product B" if order == "good_first" else "Product A", d["bad"])
            first, second = (g, b) if order == "good_first" else (b, g)
            a = ask(choice_prompt(d["ptype"], first, second))
            correct = (parse(a) == "A") == (order == "good_first")
            w.writerow([MODEL, "dominance", d["ptype"], i, "", order, int(correct), a[:200]])
    for t in S["tasks"]:
        revs = t["a_base"][:2] + [t["target"]] + t["a_base"][2:]
        for cond, lab in LABELS.items():
            # 2. helpfulness of the labelled target review alone
            p = (f"Here is a customer review of a {t['ptype']}:\n\"{t['target']}\"{lab}\n\n"
                 "How helpful would this review be to other shoppers deciding whether to buy? "
                 "Answer with exactly one line: RATING: <1-7>, where 1 = not at all helpful and 7 = extremely helpful.")
            a = ask(p); m = re.search(r"RATING:\s*\**\s*([1-7])", a) or re.search(r"\b([1-7])\b", a)
            w.writerow([MODEL, "helpfulness", t["ptype"], t["task"], cond, "", m.group(1) if m else "?", a[:200]])
            # 3. choice: labelled target review in slot 3 of Product A
            labels = ["", "", lab, "", ""]
            for order in ["A_first", "A_second"]:
                la = listing("Product A" if order == "A_first" else "Product B", revs, labels)
                lb = listing("Product B" if order == "A_first" else "Product A", t["b_base"])
                first, second = (la, lb) if order == "A_first" else (lb, la)
                pick = parse(ask(choice_prompt(t["ptype"], first, second)))
                chose = "?" if pick == "?" else int((pick == "A") == (order == "A_first"))
                w.writerow([MODEL, "choice", t["ptype"], t["task"], cond, order, chose, ""])
        f.flush()
print("done", MODEL, time.strftime("%H:%M"))
