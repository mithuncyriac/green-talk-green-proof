#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Which model providers can this machine actually reach, and what can each one run?

WHY. Six providers in providers.json need an API key (a secret string that identifies your
account to the provider, so they know whose free allowance to charge). Adding one should be
one paste and one command, not a research project. This reports which keys are present,
whether the base URL in the config is right, and -- the part that matters -- what models
each key can actually reach, asked of the provider rather than guessed by me.

  python scripts/check_keys.py                 # which keys are set, and does each endpoint answer
  python scripts/check_keys.py --discover      # also list the models each key can reach
  python scripts/check_keys.py --write         # with --discover, put a shortlist into providers.json

NOTHING IS GUESSED. Model ids come from each provider's own /models endpoint. A base URL
that 404s is reported as wrong rather than worked around, because a wrong URL quietly
failing is how you lose a day. Keys are read from the environment and never printed; only
their length is shown, which is enough to tell a paste error from a missing key.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "providers.json")
UA = "green-talk-key-check/1.0"

# Models worth having in the fan-out, in rough order of usefulness: a large open-weight
# model first, then a mid size, then anything else the key reaches. Matching is on the id
# as the provider reports it, so nothing here invents an id.
PREFER = [
    r"gpt-oss-120b", r"gpt-oss-20b", r"llama.*(70|405)b", r"qwen[\d.]*[-.]?(27|32|72)b",
    r"mistral-(large|medium)", r"magistral-(medium|small)", r"mixtral",
    r"gemini-[\d.]*-?pro", r"gemini-[\d.]*-?flash",
    r"deepseek", r"ministral-14b", r"mistral-small", r"llama.*8b", r"qwen.*7b",
]
# Anything matching these is no use for rating product-review text. Three groups:
# other modalities (audio, images, embeddings); safety classifiers; and task-specific
# models that are not general chat. The last group matters: the first run of this script
# picked "codestral" for Mistral, which is a CODE model, because nothing in PREFER matched
# Mistral's ministral/magistral/codestral naming and it fell through to alphabetical order.
# It also picked "qwen2.5-vl-72b-instruct" for OpenRouter, which is vision-language.
SKIP = re.compile(
    r"whisper|tts|audio|speech|embed|image|vision|[-/]vl[-.]|ocr|sora|dall|"
    r"guard|moderat|rerank|"
    r"codestral|devstral|voxtral|[-/]coder|[-/]code[-.]|batch",
    re.I)


def sh(url, bearer=None, extra=None):
    cmd = ["curl", "-sS", "-m", "30", "-A", UA, "-w", "\n__C__%{http_code}"]
    if bearer:
        cmd += ["-H", "Authorization: Bearer " + bearer]
    for h in (extra or []):
        cmd += ["-H", h]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                         errors="replace", timeout=60).stdout or ""
    body, _, code = out.rpartition("\n__C__")
    return code.strip(), body


def rank(mid):
    for i, pat in enumerate(PREFER):
        if re.search(pat, mid, re.I):
            return i
    return len(PREFER)


def pick_for(provider, usable):
    """Choose model ids per provider, because listing a model is not the same as being
    allowed to call it. Three lessons paid for on 27 Nov 2026:

    OpenRouter  /models lists all 441 including paid ones, and a paid id answers a
                completion request with HTTP 402 Payment Required. Only ids ending ':free'
                are free. So filter to those, and if none exist, say so rather than writing
                an id that will 402 on every call.
    Google      /models returns ids prefixed 'models/', which the OpenAI-compatible
                completion endpoint rejects with 404. Strip it. Also prefer flash over pro:
                the pro models returned 429 immediately, because their free quota is tiny.
    default     the general preference order.
    """
    if provider == "openrouter":
        free = [m for m in usable if m.endswith(":free")]
        if not free:
            print("                 NOTE: no ':free' models in this catalogue. Paid ids "
                  "return HTTP 402, so nothing was written.")
            return []
        return sorted(free, key=lambda x: (rank(x), x))[:3]

    if provider == "google":
        stripped = [m[len("models/"):] if m.startswith("models/") else m for m in usable]
        flash = [m for m in stripped if "flash" in m.lower() and "live" not in m.lower()]
        pool = flash or stripped
        return sorted(pool, key=lambda x: (rank(x), x))[:3]

    picks = [m for m in usable if rank(m) < len(PREFER)][:3]
    return picks or usable[:2]


def main():
    discover = "--discover" in sys.argv
    write = "--write" in sys.argv
    doc = json.load(open(CFG, encoding="utf-8"))
    provs = doc["providers"]

    print("%-12s %-8s %-26s %s" % ("PROVIDER", "KEY", "ENDPOINT", "RESULT"))
    print("-" * 78)
    changed = False

    for name, cfg in provs.items():
        env = cfg.get("key_env")
        key = os.environ.get(env) if env else None
        base = (cfg.get("base_url") or "").rstrip("/")

        if env and not key:
            print("%-12s %-8s %-26s set %s in the environment, then rerun"
                  % (name, "missing", base.replace("https://", "")[:26], env))
            continue
        keytag = "local" if not env else "%d ch" % len(key)

        code, body = sh(base + "/models", key)
        if code == "404":
            print("%-12s %-8s %-26s BASE URL WRONG (404 on /models). Fix base_url in "
                  "providers.json" % (name, keytag, base.replace("https://", "")[:26]))
            continue
        if code in ("401", "403"):
            print("%-12s %-8s %-26s KEY REJECTED (HTTP %s). Re-copy it, whole string, no spaces"
                  % (name, keytag, base.replace("https://", "")[:26], code))
            continue
        if code != "200":
            print("%-12s %-8s %-26s HTTP %s  %s"
                  % (name, keytag, base.replace("https://", "")[:26], code or "no reply",
                     re.sub(r"\s+", " ", body)[:40]))
            continue

        try:
            ids = [m.get("id") for m in (json.loads(body).get("data") or []) if m.get("id")]
        except Exception:
            ids = []
        usable = sorted([i for i in ids if not SKIP.search(i)], key=lambda x: (rank(x), x))
        print("%-12s %-8s %-26s OK, %d models (%d usable for text rating)"
              % (name, keytag, base.replace("https://", "")[:26], len(ids), len(usable)))

        if discover:
            for mid in usable[:10]:
                star = " <-- preferred" if rank(mid) < len(PREFER) else ""
                print("                 %s%s" % (mid, star))
            if len(usable) > 10:
                print("                 ... and %d more" % (len(usable) - 10))
            if write and usable:
                picks = pick_for(name, usable)
                cfg["models"] = {re.sub(r"[^a-z0-9.\-]+", "-", m.split("/")[-1].lower()): m
                                 for m in picks}
                changed = True
                print("                 -> wrote %d model(s) into providers.json: %s"
                      % (len(picks), ", ".join(picks)))

    if write and changed:
        tmp = CFG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        os.replace(tmp, CFG)
        print("\nproviders.json updated. Run fanout_limits.py next to read each one's real caps.")
    elif write:
        print("\nnothing written: no provider returned a usable model list.")

    print("\nReminder: providers.json stores the NAME of each environment variable, never a key.")


if __name__ == "__main__":
    main()
