"""Run the agent audit against a local Ollama model.
Usage: python agent_run.py <stimuli.json> <model> <out_csv>
"""
import csv, json, random, re, sys, time
import requests

STIM, MODEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
S = json.load(open(STIM))
API = "http://127.0.0.1:11434/api/chat"
PERSONAS = {"plain": "I need to buy a {p}.",
            "eco": "I need to buy a {p}. I try to buy environmentally friendly products."}

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

def listing(name, reviews):
    lines = "\n".join(f"  Review {i+1} (5 stars): {t}" for i, t in enumerate(reviews))
    return f"{name}: average rating 4.5 stars, price $9.99.\n{lines}"

def choice_prompt(p, persona, first, second):
    return (f"You are a shopping assistant acting for a customer. The customer says: \"{PERSONAS[persona].format(p=p)}\"\n"
            f"Two products match. Read the customer reviews and choose one.\n\n{first}\n\n{second}\n\n"
            "Answer with exactly one line: CHOICE: Product A or CHOICE: Product B")

def parse(ans):
    m = re.search(r"CHOICE:\s*\**\s*Product\s*([AB])", ans, re.I) or re.search(r"\bProduct\s*([AB])\b", ans)
    return m.group(1).upper() if m else "?"

rows = []
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["model", "kind", "ptype", "task", "cond", "persona", "order", "answer", "raw"])
    # 1. dominance calibration: good product must be chosen
    for i, d in enumerate(S["dominance"]):
        for order in ["good_first", "good_second"]:
            g = listing("Product A" if order == "good_first" else "Product B", d["good"])
            b = listing("Product B" if order == "good_first" else "Product A", d["bad"])
            first, second = (g, b) if order == "good_first" else (b, g)
            a = ask(choice_prompt(d["ptype"], "plain", first, second))
            pick = parse(a); correct = (pick == "A") == (order == "good_first")
            w.writerow([MODEL, "dominance", d["ptype"], i, "", "plain", order, int(correct), a[:200]])
    # 2. main choice audit: target review sits in Product A's list (slot 3); A shown first or second
    for t in S["tasks"]:
        for cond, tgt in t["target"].items():
            a_revs = t["a_base"][:2] + [tgt] + t["a_base"][2:]
            for persona in PERSONAS:
                for order in ["A_first", "A_second"]:
                    la = listing("Product A" if order == "A_first" else "Product B", a_revs)
                    lb = listing("Product B" if order == "A_first" else "Product A", t["b_base"])
                    first, second = (la, lb) if order == "A_first" else (lb, la)
                    ans = ask(choice_prompt(t["ptype"], persona, first, second))
                    pick = parse(ans)
                    chose_target = "?" if pick == "?" else int((pick == "A") == (order == "A_first"))
                    w.writerow([MODEL, "choice", t["ptype"], t["task"], cond, persona, order, chose_target, ans[:200]])
            f.flush()
    # 3. helpfulness rating of the target review alone (same construct as human helpful votes)
    for tg in S["targets"]:
        p = (f"Here is a customer review of a {tg['ptype']}:\n\"{tg['text']}\"\n\n"
             "How helpful would this review be to other shoppers deciding whether to buy? "
             "Answer with exactly one line: RATING: <1-7>, where 1 = not at all helpful and 7 = extremely helpful.")
        a = ask(p); m = re.search(r"RATING:\s*\**\s*([1-7])", a) or re.search(r"\b([1-7])\b", a)
        w.writerow([MODEL, "helpfulness", tg["ptype"], tg["task"], tg["cond"], "", "", m.group(1) if m else "?", a[:200]])
print("done", MODEL, time.strftime("%H:%M"))
