"""Read the rate limits YOUR account actually has, from the provider's own headers.

WHY. providers.json ships conservative guesses, because a docs page cannot tell you
your own limits. Groq's rate-limits page lists gpt-oss-120b at 1,000 requests a day
and in the same breath says those are base limits for the Developer plan, without
labelling a free-tier table. Planning a three-week run on a number like that is how
you discover on day four that it was wrong.

Every OpenAI-compatible provider returns the real figures in response headers on every
call. This makes one 1-token call per model, prints every `x-ratelimit-*` header
verbatim, and infers each limit's WINDOW from its paired reset duration rather than
assuming which header means per-minute and which means per-day.

Nothing is guessed: a header this script cannot classify is printed and left alone.
The API key is read from the environment and never printed.

  python fanout_limits.py                      # read-only, every enabled provider
  python fanout_limits.py --provider groq      # one provider
  python fanout_limits.py --provider groq --write   # update providers.json
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "providers.json")


def parse_duration(s):
    """'2m59.56s' / '1h30m' / '860ms' / '7.66s' -> seconds. None if unparseable."""
    if s is None:
        return None
    s = str(s).strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):       # bare number: providers mean seconds
        return float(s)
    total, found = 0.0, False
    for val, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)", s):
        found = True
        total += float(val) * {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}[unit]
    return total if found else None


WINDOWS = ((60.0, "minute"), (3600.0, "hour"), (86400.0, "day"))


def window_of(reset_seconds, limit=None, used=None):
    """Infer a limit's window from the REFILL arithmetic, not from the reset size.

    This was wrong on the first attempt and the fix is worth explaining, because the
    naive reading inverts both of Groq's numbers.

    These are token buckets. `reset` is not "time until the window ends"; it is "time to
    refill what you have just used". A bucket of `limit` units per window `W` refills at
    limit/W per second, so after spending `used` units:

        reset = (used / limit) * W        =>        W = reset * limit / used

    Worked on real Groq headers, 27 Nov 2026:
      requests: reset 86.4 s, limit 1000, used 1   -> W = 86.4 * 1000 / 1   = 86400 s = a DAY
      tokens:   reset 0.547 s, limit 8000, used 73 -> W = 0.547 * 8000 / 73 =    59.9 s = a MINUTE

    So limit-requests 1000 is requests per DAY and limit-tokens 8000 is tokens per
    MINUTE. Reading 86.4 s as "about a minute" and 0.547 s as "about a minute" classified
    them as 1000 rpm and 8000 tpm, which is wrong in both directions: it would have
    disabled the pacer and then hammered an 8k-per-minute cap.

    Falls back to "unknown" when `used` is zero or missing, because the arithmetic needs it.
    """
    if reset_seconds is None or not limit or not used:
        return "unknown", None
    w = reset_seconds * float(limit) / float(used)
    # Snap to the nearest standard window, but only if it is genuinely close.
    best, name = min(((abs(w - sec) / sec, nm) for sec, nm in WINDOWS), key=lambda x: x[0])
    return (name if best < 0.35 else "unknown"), w


def probe(name, cfg, model_id):
    """One minimal call. Returns (headers dict, error string or None)."""
    key = os.environ.get(cfg["key_env"]) if cfg.get("key_env") else None
    if cfg.get("key_env") and not key:
        return {}, "%s is not set in the environment" % cfg["key_env"]
    h = {"Authorization": "Bearer " + key} if key else {}
    body = {"model": model_id, "max_tokens": 1, "temperature": 0,
            "messages": [{"role": "user", "content": "ok"}]}
    try:
        r = requests.post(cfg["base_url"].rstrip("/") + "/chat/completions",
                          json=body, headers=h, timeout=60)
    except Exception as e:
        return {}, "network: %s" % repr(e)[:120]
    rl = {k.lower(): v for k, v in r.headers.items() if "ratelimit" in k.lower()}
    if r.status_code != 200 and not rl:
        # A 429 still carries the headers, which is the thing we came for.
        return rl, "HTTP %d and no rate-limit headers" % r.status_code
    return rl, None


SUFFIX = {"minute": "pm", "hour": "ph", "day": "pd"}


def classify_explicit(rl):
    """Headers that name their own window, e.g. x-ratelimit-limit-requests-day.

    Cerebras does this and it is the honest design: no refill arithmetic needed, the window
    is in the key. My first parser looked only for the bare `x-ratelimit-limit-requests`
    form and reported "nothing classifiable" against a provider that was telling us the
    answer in plain text. Mistral uses a third spelling again, `-req-minute`.

    Returns {} when no explicit-window header is present, so the caller falls back to the
    refill arithmetic.
    """
    out, notes = {}, []
    for kind, short in (("requests", "r"), ("req", "r"), ("tokens", "t"), ("tok", "t")):
        for win, sfx in (("minute", "pm"), ("hour", "ph"), ("day", "pd")):
            v = rl.get("x-ratelimit-limit-%s-%s" % (kind, win))
            if v is None:
                continue
            try:
                n = int(float(str(v).replace(",", "")))
            except ValueError:
                continue
            key = short + sfx
            if n <= 0:
                notes.append("limit-%s-%s = %s. A cap of zero means the account has no quota "
                             "on this model: activate or verify the account with the provider."
                             % (kind, win, n))
                continue
            # Several spellings can map to one key; keep the smallest, never overwrite with
            # a larger one, because over-spending gets the account throttled.
            if key not in out or n < out[key]:
                out[key] = n
    if out:
        notes.insert(0, "window named in the header itself, so no refill arithmetic needed")
    return out, notes


def classify(rl):
    """Map the headers onto rpm / rpd / tpm / tpd. Explicit-window headers win."""
    explicit, notes = classify_explicit(rl)
    if explicit:
        return explicit, notes
    out, notes = {}, []
    for kind, short in (("requests", "r"), ("tokens", "t")):
        raw_limit = rl.get("x-ratelimit-limit-" + kind)
        raw_rem = rl.get("x-ratelimit-remaining-" + kind)
        reset = parse_duration(rl.get("x-ratelimit-reset-" + kind))
        if raw_limit is None:
            continue
        try:
            limit = int(float(str(raw_limit).replace(",", "")))
            used = limit - int(float(str(raw_rem).replace(",", ""))) if raw_rem is not None else None
        except ValueError:
            notes.append("could not read limit-%s=%r / remaining=%r" % (kind, raw_limit, raw_rem))
            continue
        win, inferred = window_of(reset, limit, used)
        if win == "unknown":
            notes.append("limit-%s=%s, remaining=%s, reset=%r -> window not inferable%s. "
                         "Set it by hand from your account's limits page."
                         % (kind, limit, raw_rem, rl.get("x-ratelimit-reset-" + kind),
                            "" if inferred is None else " (arithmetic gave %.0f s)" % inferred))
            continue
        notes.append("limit-%s=%s used=%s reset=%.3fs -> window = %.3f * %d / %d = %.0f s, "
                     "a %s -> %s%s=%d"
                     % (kind, limit, used, reset, reset, limit, used, inferred, win,
                        short, SUFFIX[win], limit))
        out[short + SUFFIX[win]] = limit
    if "rpd" in out and "rpm" not in out:
        notes.append("no per-minute REQUEST cap in the headers. Groq's docs table lists 30 RPM "
                     "for these models; that figure is unverified for your plan, so the "
                     "existing providers.json rpm is kept rather than overwritten.")
    if "tpm" in out and "tpd" not in out:
        notes.append("no per-day TOKEN cap in the headers. Groq's docs table lists 200K TPD; "
                     "unverified for your plan, so the existing tpd is kept.")
    return out, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None)
    ap.add_argument("--write", action="store_true",
                    help="write discovered limits into providers.json")
    ap.add_argument("--enable", action="store_true",
                    help="with --write, also set enabled=true for the probed provider, "
                         "but only if real limits came back from its headers")
    args = ap.parse_args()

    doc = json.load(open(CFG, encoding="utf-8"))
    provs = doc["providers"]

    def reachable(c):
        """Has models configured, and either is local or has its key in the environment.

        This used to require enabled=true, which was a chicken-and-egg bug: --enable exists
        precisely to turn a provider ON after reading its limits, but the provider could
        never be probed in the first place because it was still off. A newly configured
        provider was silently skipped, which is how five working providers got missed.
        """
        if not c.get("models"):
            return False
        env = c.get("key_env")
        return (not env) or bool(os.environ.get(env))

    targets = [(n, c) for n, c in provs.items()
               if (args.provider == n) or (args.provider is None and reachable(c))]
    if not targets:
        sys.exit("nothing to probe. Every provider either has no models configured or no key "
                 "in the environment. Run check_keys.py --discover --write first. "
                 "Names: %s" % ", ".join(provs))
    if args.provider is None:
        skipped = [n for n, c in provs.items() if not reachable(c) and n not in dict(targets)]
        if skipped:
            print("skipping (no models configured, or key not in this shell): %s\n"
                  % ", ".join(skipped))

    changed = False
    # Which cap keys, per provider, have been set from real response headers in this run.
    header_backed = {}
    for name, cfg in targets:
        print("\n=== %s ===" % name)
        if not cfg.get("models"):
            print("  no models listed. Add at least one model id first.")
            continue
        for short, mid in cfg["models"].items():
            rl, err = probe(name, cfg, mid)
            if err and not rl:
                print("  %-16s FAILED: %s" % (short, err))
                continue
            print("  %-16s headers as returned:" % short)
            for k in sorted(rl):
                print("      %-34s %s" % (k, rl[k]))
            found, notes = classify(rl)
            for n in notes:
                print("      NOTE: %s" % n)
            if not found:
                print("      nothing classifiable; leaving providers.json alone")
                continue
            cur = {k: cfg.get(k) for k in ("rpm", "rpd", "tpm", "tpd") if k in cfg}
            print("      classified: %s   (currently in providers.json: %s)" % (found, cur))
            if args.write:
                # Two rules, and the first one was missing on the first attempt.
                #
                # 1. A value read from headers ALWAYS replaces a value that was not. The
                #    naive "keep the smallest" rule compared a real 2,400-a-day cap against
                #    my own placeholder of 100 and kept the placeholder, which would have
                #    turned a one-day run into four.
                # 2. Among values read from headers in THIS run, keep the smallest, because
                #    caps differ per model on some providers and under-spending is
                #    recoverable while over-spending gets the account throttled.
                from_headers = header_backed.setdefault(name, set())
                for k, v in found.items():
                    if k not in from_headers:
                        cfg[k] = v                      # rule 1: supersede any guess
                        from_headers.add(k)
                        changed = True
                    elif v < cfg[k]:
                        cfg[k] = v                      # rule 2: tightest real cap wins
                        changed = True
                cfg["limits_read_from_headers"] = dt.datetime.now(
                    dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if args.enable and not cfg.get("enabled"):
                    # Only ever enabled off the back of real headers, never on a guess.
                    cfg["enabled"] = True
                    changed = True
                    print("      enabled=true (limits came from this account's headers)")

    if args.write and changed:
        doc["providers"] = provs
        tmp = CFG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        os.replace(tmp, CFG)
        print("\nproviders.json updated. The smallest limit seen per provider was kept.")
        print("Re-read it before a long run: a limit can change when a plan changes.")
    elif args.write:
        print("\nnothing to change; providers.json already matches or nothing was "
              "classifiable.")
    else:
        print("\nread-only. Add --write to put these into providers.json.")


if __name__ == "__main__":
    main()
