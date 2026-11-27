"""The prompt builders, factored out so the fan-out sends byte-identical text.

Why this file exists. label_run.py, label_run2.py and agent_run.py each carry their
own copy of these strings. The multi-model fan-out has to send the SAME bytes as the
published two-model pilot, or the hosted results are not comparable with it and the
whole point of the fan-out is lost.

So: these are copied verbatim from label_run2.py (labels, rating and choice prompts)
and agent_run.py (the two personas). test_prompt_parity.py asserts they still match
character for character, and fails the run if either original is edited without this
file being edited with it.

Nothing here imports requests or reads sys.argv, so it is safe to import.
"""
import re
import unicodedata

DIGITS = set("1234567")

# From agent_run.py. "plain" is the persona label_run2.py uses as its only persona.
PERSONAS = {
    "plain": "I need to buy a {p}.",
    "eco": "I need to buy a {p}. I try to buy environmentally friendly products.",
}

# From label_run2.py. Order matters only for reporting; the placebo is pre-registered.
LABELS = {
    "none": "",
    "ai": " [Label: Made with AI]",
    "effort": " [Label: Written by the reviewer after 3 months of use; AI helped with wording]",
    "placebo": " [Label: Submitted on a Tuesday]",
}


def digit(tok):
    """NFKC-normalise then match 1-7. Qwen emits full-width digits in its top-k."""
    s = unicodedata.normalize("NFKC", tok).strip()
    return s if s in DIGITS else None


def listing(name, reviews, labels=None):
    labels = labels or [""] * len(reviews)
    lines = "\n".join(f"  Review {i+1} (5 stars){l}: {t}"
                      for i, (t, l) in enumerate(zip(reviews, labels)))
    return f"{name}: average rating 4.5 stars, price $9.99.\n{lines}"


def choice_prompt(p, first, second, persona="plain"):
    return (f"You are a shopping assistant acting for a customer. The customer says: "
            f"\"{PERSONAS[persona].format(p=p)}\"\n"
            f"Two products match. Read the customer reviews and choose one.\n\n{first}\n\n{second}\n\n"
            "Answer with exactly one line: CHOICE: Product A or CHOICE: Product B")


def rating_prompt(ptype, text, lab):
    return (f"Here is a customer review of a {ptype}:\n\"{text}\"{lab}\n\n"
            "How helpful would this review be to other shoppers deciding whether to buy? "
            "Answer with exactly one line: RATING: <1-7>, where 1 = not at all helpful "
            "and 7 = extremely helpful.")


def parse_choice(ans):
    m = (re.search(r"CHOICE:\s*\**\s*Product\s*([AB])", ans, re.I)
         or re.search(r"\bProduct\s*([AB])\b", ans))
    return m.group(1).upper() if m else "?"


def parse_rating(ans):
    m = re.search(r"RATING:\s*\**\s*([1-7])", ans) or re.search(r"\b([1-7])\b", ans)
    return m.group(1) if m else "?"
