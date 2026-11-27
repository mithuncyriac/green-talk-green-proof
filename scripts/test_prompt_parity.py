"""Fail if prompts.py has drifted from label_run2.py or agent_run.py.

The multi-model fan-out is only comparable with the published two-model pilot if it
sends the same bytes. prompts.py is a copy, and copies rot. This test lifts the
original functions straight out of the original files and compares the strings they
produce, character for character.

It cannot simply import those files: both read sys.argv and open a stimuli path at
module level, so importing them runs them. Instead it parses each file with `ast`,
compiles only the definitions it needs, and calls those.

Run: python scripts/test_prompt_parity.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prompts as P  # noqa: E402


def lift(filename, names):
    """Exec only the named top-level functions and assignments from a module file."""
    src = open(os.path.join(HERE, filename), encoding="utf-8").read()
    tree = ast.parse(src)
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            keep.append(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in names:
                    keep.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # Only the stdlib imports these functions actually need.
            mods = [a.name.split(".")[0] for a in node.names]
            if all(m in ("re", "json", "math", "unicodedata", "os", "sys", "csv", "time")
                   for m in mods):
                keep.append(node)
    ns = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), filename, "exec"), ns)
    missing = [n for n in names if n not in ns]
    if missing:
        raise AssertionError("%s: could not lift %s" % (filename, missing))
    return ns


REVIEWS = ["first review text", "second one", "a third", "and a fourth", "fifth here"]
LABELLED = ["", "", " [Label: Made with AI]", "", ""]
FAILURES = []


def check(label, got, want):
    if got != want:
        FAILURES.append("%s\n   fanout: %r\n   origin: %r" % (label, got, want))


def main():
    v2 = lift("label_run2.py", {"listing", "choice_prompt", "rating_prompt",
                                "parse_choice", "digit", "LABELS", "PERSONA", "DIGITS"})
    v1 = lift("agent_run.py", {"listing", "choice_prompt", "PERSONAS"})

    # 1. The four label strings, including the pre-registered placebo.
    check("LABELS dict", P.LABELS, v2["LABELS"])

    # 2. Both personas.
    check("PERSONAS dict", P.PERSONAS, v1["PERSONAS"])
    check("plain persona matches label_run2's single PERSONA",
          P.PERSONAS["plain"], v2["PERSONA"])

    # 3. Listings, with and without labels.
    check("listing, unlabelled",
          P.listing("Product A", REVIEWS), v2["listing"]("Product A", REVIEWS))
    check("listing, labelled",
          P.listing("Product A", REVIEWS, LABELLED),
          v2["listing"]("Product A", REVIEWS, LABELLED))
    check("listing matches agent_run's (no-label form)",
          P.listing("Product B", REVIEWS[:4]), v1["listing"]("Product B", REVIEWS[:4]))

    # 4. Rating prompts, every label condition.
    for cond, lab in P.LABELS.items():
        check("rating_prompt[%s]" % cond,
              P.rating_prompt("shampoo", "a review body", lab),
              v2["rating_prompt"]("shampoo", "a review body", lab))

    # 5. Choice prompts. label_run2 is plain-persona only; agent_run covers both.
    a = P.listing("Product A", REVIEWS, LABELLED)
    b = P.listing("Product B", REVIEWS[:4])
    check("choice_prompt, plain, vs label_run2",
          P.choice_prompt("shampoo", a, b, "plain"),
          v2["choice_prompt"]("shampoo", a, b))
    for persona in P.PERSONAS:
        check("choice_prompt, %s, vs agent_run" % persona,
              P.choice_prompt("shampoo", a, b, persona),
              v1["choice_prompt"]("shampoo", persona, a, b))

    # 6. Parsers agree, including the awkward cases the originals handle.
    for ans in ["CHOICE: Product A", "choice:  **Product b**", "I pick Product B.",
                "no idea", "CHOICE: Product A\nbecause..."]:
        check("parse_choice(%r)" % ans, P.parse_choice(ans), v2["parse_choice"](ans))

    # 7. Full-width digits still normalise. Qwen's top-k contains U+FF15.
    for tok in ["5", "５", " 7 ", "x", "8", "０"]:
        check("digit(%r)" % tok, P.digit(tok), v2["digit"](tok))

    if FAILURES:
        print("PROMPT PARITY FAILED -- %d difference(s).\n" % len(FAILURES))
        for f in FAILURES:
            print(" -", f)
        print("\nThe fan-out would send different text from the published pilot, so the\n"
              "hosted results would not be comparable with it. Fix prompts.py (or, if the\n"
              "originals changed on purpose, update this test and say so in the README).")
        sys.exit(1)
    print("prompt parity OK: prompts.py is byte-identical to label_run2.py and agent_run.py")


if __name__ == "__main__":
    main()
