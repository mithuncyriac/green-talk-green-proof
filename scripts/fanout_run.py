"""Run the label audit across many hosted models, resumably, inside free-tier caps.

WHY THIS EXISTS. Every blind reviewer of this project named the same limitation: two
quantised 7B/8B models is n=2 at the model level, so nothing here generalises. This
machine has 8,192 MiB of VRAM and cannot hold anything bigger, so the fix is not a
better local model, it is the same study run against hosted ones -- including a
~100B open-weight model -- through the OpenAI-compatible endpoint every provider now
speaks, Ollama included.

FOUR THINGS THIS HAS TO GET RIGHT, because it runs for days unattended.

1. RESUMABLE. Free tiers cap tokens per DAY, so one model takes more than one day and
   the whole fan-out takes weeks. Every row is appended with a deterministic cell id.
   On restart the runner reads the CSV, skips every cell already present, and carries
   on. Killing it with Ctrl-C loses at most the call in flight.

2. BUDGETED. Requests per minute, requests per day and tokens per day are enforced in
   here, against the caps in providers.json, with the daily counters persisted so they
   survive a restart. When a provider's day is spent the runner says so and moves on
   rather than burning the account to rate-limit errors.

3. HONEST ABOUT SCORING. The published pilot scored an expected rating over the token
   logprob distribution, not the emitted digit. Not every provider returns logprobs.
   Where they are missing the runner records score_mode=emitted_only PER ROW, so the
   analysis can pool emitted ratings across all models and expected ratings only across
   the subset that actually returned distributions. A missing distribution is never
   silently treated as a present one.

4. BYTE-IDENTICAL PROMPTS. The hosted runs are only comparable with the published pilot
   if the text is the same. Prompts come from prompts.py, and test_prompt_parity.py
   fails if that file drifts from label_run2.py or agent_run.py.

SUGGESTED ORDER OF WORK. Run --kinds helpfulness across every model first: it is 400
calls a model and carries the hypotheses the fan-out exists to test (cost blindness,
the null label, the effort channel). Choice is 800 calls a model and mostly re-tests
position bias, which Allouah et al. (arXiv:2508.02630) already published on frontier
models. Spend the cheap budget on the new question.

USAGE
  python fanout_run.py --dry-run                      # plan + token estimate, zero calls
  python fanout_run.py --probe                        # 1 call per model: reachable? logprobs? format?
  python fanout_run.py --kinds helpfulness            # the half that matters, every enabled model
  python fanout_run.py --kinds helpfulness,choice,dominance --persona plain,eco
  python fanout_run.py --only groq:gpt-oss-120b --limit 10
"""
import argparse
import csv
import collections
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompts as P  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CFG = os.path.join(HERE, "providers.json")
STIM_DEFAULT = os.path.join(ROOT, "data_label", "label_stimuli.json")
OUT_DIR = os.path.join(ROOT, "results", "fanout")

COLUMNS = [
    # label_run2.py's columns, in label_run2.py's order, so a single-model slice of this
    # CSV can be fed to label_analyse.py and label_interaction.py unchanged.
    "model", "kind", "ptype", "task", "cond", "order", "answer", "raw",
    "pass", "ev_rating", "digit_mass_share", "dist_json",
    # Appended at the end only, same discipline as v1 -> v2.
    "provider", "model_id", "persona", "score_mode", "prompt_sha1",
    "tok_in", "tok_out", "ts", "cell",
]


# --------------------------------------------------------------------------- budget

class Budget:
    """Requests/minute, requests/day and tokens/day, persisted across restarts.

    The daily counters are keyed by UTC date because that is what providers reset on,
    and because a local-midnight key would double-count on a timezone change.
    """

    def __init__(self, path):
        self.path = path
        self.state = {}
        if os.path.exists(path):
            try:
                self.state = json.load(open(path, encoding="utf-8"))
            except Exception:
                self.state = {}
        # One rolling-window ledger per provider per cap: prov -> cap key -> deque of
        # (timestamp, amount). Covers rpm, rph, tpm and tph with the same code.
        #
        # The HOURLY caps are here because Cerebras exposed a trap: gpt-oss-120b allows
        # 5 requests a minute but only 150 an hour. Pacing on the minute alone lets you
        # issue 300 in an hour and start collecting 429s at call 151, half an hour in.
        # The binding constraint is whichever window runs out first, so all four are
        # enforced and the arithmetic reports which one actually binds.
        self.win = collections.defaultdict(lambda: collections.defaultdict(collections.deque))
        self.spent_today = set()

    @staticmethod
    def _day():
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    def _cell(self, prov):
        return self.state.setdefault(self._day(), {}).setdefault(prov, {"req": 0, "tok": 0})

    def remaining(self, prov, cfg):
        """Requests and tokens left today, or None where the provider states no cap.

        A missing or null cap means "not stated", not "zero", and is treated the
        same way _roll treats a missing rolling limit: no wall. Until 27 Nov 2026
        this read cfg["tpd"] directly, so an unverified figure copied from a
        vendor docs table behaved exactly like a measured one. Groq's headers
        report a per-MINUTE token limit and no daily one, and the 200,000 daily
        figure in providers.json stopped a run at 266 of 400 rows with the server
        still reporting 783 requests remaining. The rule this project already
        uses for caps applies here too: a header-derived number supersedes a
        guess, and a guess must not be enforced as a hard limit.
        """
        c = self._cell(prov)
        rpd, tpd = cfg.get("rpd"), cfg.get("tpd")
        return (None if not rpd else rpd - c["req"],
                None if not tpd else tpd - c["tok"])

    def room_for(self, prov, cfg, est_tokens):
        """True if one more call of roughly est_tokens fits in today's allowance."""
        req_left, tok_left = self.remaining(prov, cfg)
        if req_left is not None and req_left <= 0:
            return False
        if tok_left is not None and tok_left < est_tokens:
            return False
        return True

    def _roll(self, prov, key, limit, seconds, amount, record):
        """Block until `amount` fits in the rolling window, then optionally record it.

        Sleeps in short steps so Ctrl-C still lands promptly.
        """
        if not limit:
            return
        q = self.win[prov][key]
        while True:
            now = time.time()
            while q and now - q[0][0] > seconds:
                q.popleft()
            used = sum(a for _, a in q)
            if used + amount <= limit or not q:
                if record:
                    q.append((now, amount))
                return
            time.sleep(min(2.0, seconds - (now - q[0][0]) + 0.05))

    def pace(self, prov, cfg):
        """Hold until this call fits every REQUEST window the provider publishes."""
        self._roll(prov, "rpm", cfg.get("rpm"), 60.0, 1, True)
        self._roll(prov, "rph", cfg.get("rph"), 3600.0, 1, True)

    def pace_tokens(self, prov, cfg, need):
        """Hold until `need` tokens fit every TOKEN window.

        Recorded on charge() rather than here, because the estimate is crude and the
        provider's own usage figure is what should be counted.
        """
        self._roll(prov, "tpm", cfg.get("tpm"), 60.0, need, False)
        self._roll(prov, "tph", cfg.get("tph"), 3600.0, need, False)

    def charge(self, prov, tok_in, tok_out):
        n = int(tok_in or 0) + int(tok_out or 0)
        c = self._cell(prov)
        c["req"] += 1
        c["tok"] += n
        now = time.time()
        self.win[prov]["tpm"].append((now, n))
        self.win[prov]["tph"].append((now, n))

    def save(self):
        # Keep only the last 14 days so the file does not grow without bound.
        keep = sorted(self.state)[-14:]
        self.state = {k: self.state[k] for k in keep}
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)


# ----------------------------------------------------------------------- scoring

def expected_rating(logprob_content):
    """Expected rating over 1-7 at the first rating token, plus the mass kept.

    OpenAI-compatible shape: choices[0].logprobs.content is a list of per-token objects,
    each with .token and .top_logprobs[{token, logprob}]. Same arithmetic as
    label_run2.rating_distribution, different wrapper.

    digit_mass_share is the share of the returned top-k that landed on a digit 1-7. A low
    share means the expectation is computed over a renormalised sliver, so it is recorded
    per row rather than assumed away.
    """
    if not logprob_content:
        return None, None, None
    idx = next((i for i, t in enumerate(logprob_content)
                if P.digit(t.get("token", ""))), None)
    if idx is None:
        return None, None, None
    tops = logprob_content[idx].get("top_logprobs") or []
    if not tops:
        return None, None, None
    total = sum(math.exp(t["logprob"]) for t in tops)
    mass = {}
    for t in tops:
        d = P.digit(t.get("token", ""))
        if d:
            mass[d] = mass.get(d, 0.0) + math.exp(t["logprob"])
    keep = sum(mass.values())
    if keep <= 0:
        return None, 0.0, None
    return sum(int(k) * v for k, v in mass.items()) / keep, (keep / total if total else None), mass


def est_tokens(prompt, out=24):
    """Rough token estimate for budgeting only: ~4 chars a token, plus the reply.

    Deliberately crude. Actual usage from the provider's response is what gets charged
    against the daily budget; this is only used to decide whether to attempt a call.
    """
    return int(len(prompt) / 4) + out


# -------------------------------------------------------------------------- client

class Client:
    def __init__(self, name, cfg, verbose=False):
        self.name, self.cfg, self.verbose = name, cfg, verbose
        self.url = cfg["base_url"].rstrip("/") + "/chat/completions"
        self.key = os.environ.get(cfg["key_env"]) if cfg.get("key_env") else None
        if cfg.get("key_env") and not self.key:
            raise RuntimeError("%s needs %s in the environment" % (name, cfg["key_env"]))
        # 'probe' resolves to yes/no on the first successful call and is then fixed.
        self.logprob_mode = cfg.get("logprobs", "no")
        self.s = requests.Session()
        if self.key:
            self.s.headers["Authorization"] = "Bearer " + self.key

    def call(self, model_id, prompt, want_logprobs):
        """One completion. Returns (text, logprob_content, tok_in, tok_out, score_mode).

        Never prints the key. Never counts a 429 or a 5xx against the daily request
        budget -- only the caller's charge() on success does that.
        """
        body = {"model": model_id, "temperature": 0, "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}]}
        if self.cfg.get("supports_seed"):
            body["seed"] = 1
        send_lp = want_logprobs and self.logprob_mode in ("yes", "probe")
        if send_lp:
            body["logprobs"] = True
            body["top_logprobs"] = 10

        for attempt in range(6):
            try:
                r = self.s.post(self.url, json=body, timeout=180)
            except Exception as e:
                self._wait(attempt, "network: %s" % repr(e)[:120])
                continue

            if r.status_code == 400 and send_lp:
                # Provider rejects logprobs. Settle it once, drop the parameter, retry.
                self.logprob_mode = "no"
                send_lp = False
                body.pop("logprobs", None)
                body.pop("top_logprobs", None)
                print("  [%s] logprobs rejected; recording emitted_only from here"
                      % self.name, flush=True)
                continue

            if r.status_code == 429 or r.status_code >= 500:
                ra = r.headers.get("Retry-After")
                self._wait(attempt, "HTTP %s" % r.status_code,
                           float(ra) if ra and ra.replace(".", "").isdigit() else None)
                continue

            if r.status_code != 200:
                return "ERROR_HTTP_%d" % r.status_code, None, 0, 0, "error"

            d = r.json()
            ch = (d.get("choices") or [{}])[0]
            text = ((ch.get("message") or {}).get("content") or "").strip()
            lpc = ((ch.get("logprobs") or {}).get("content")) if send_lp else None
            u = d.get("usage") or {}
            mode = "logprob" if lpc else "emitted_only"
            return text, lpc, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), mode

        return "ERROR_RETRIES", None, 0, 0, "error"

    def _wait(self, attempt, why, retry_after=None):
        delay = retry_after if retry_after is not None else min(60, 4 * (2 ** attempt))
        if self.verbose:
            print("  [%s] %s; sleeping %.0fs" % (self.name, why, delay), flush=True)
        time.sleep(delay)


# ---------------------------------------------------------------------- work plan

def cell_id(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def build_plan(stim, kinds, personas, limit, dominance_n, passes):
    """Every call the fan-out would make, as dicts, before any provider is considered.

    One place builds the prompts, so the dry run costs exactly what the real run costs
    minus the network.
    """
    tasks = stim["tasks"][:limit] if limit else stim["tasks"]
    dom = stim["dominance"][:dominance_n] if dominance_n is not None else stim["dominance"]
    plan = []

    if "dominance" in kinds:
        for i, d in enumerate(dom):
            for order in ["good_first", "good_second"]:
                g = P.listing("Product A" if order == "good_first" else "Product B", d["good"])
                b = P.listing("Product B" if order == "good_first" else "Product A", d["bad"])
                first, second = (g, b) if order == "good_first" else (b, g)
                plan.append({"kind": "dominance", "ptype": d["ptype"], "task": i, "cond": "",
                             "order": order, "persona": "plain", "pass": 1,
                             "prompt": P.choice_prompt(d["ptype"], first, second, "plain"),
                             "want_logprobs": False,
                             "truth": "A" if order == "good_first" else "B"})

    for t in tasks:
        revs = t["a_base"][:2] + [t["target"]] + t["a_base"][2:]
        for cond, lab in P.LABELS.items():
            if "helpfulness" in kinds:
                for p in range(1, passes + 1):
                    plan.append({"kind": "helpfulness", "ptype": t["ptype"], "task": t["task"],
                                 "cond": cond, "order": "", "persona": "plain", "pass": p,
                                 "prompt": P.rating_prompt(t["ptype"], t["target"], lab),
                                 "want_logprobs": True, "truth": None})
            if "choice" in kinds:
                labels = ["", "", lab, "", ""]
                for persona in personas:
                    for order in ["A_first", "A_second"]:
                        la = P.listing("Product A" if order == "A_first" else "Product B",
                                       revs, labels)
                        lb = P.listing("Product B" if order == "A_first" else "Product A",
                                       t["b_base"])
                        first, second = (la, lb) if order == "A_first" else (lb, la)
                        plan.append({"kind": "choice", "ptype": t["ptype"], "task": t["task"],
                                     "cond": cond, "order": order, "persona": persona,
                                     "pass": 1,
                                     "prompt": P.choice_prompt(t["ptype"], first, second,
                                                               persona),
                                     "want_logprobs": False,
                                     "truth": "A" if order == "A_first" else "B"})
    return plan


def done_cells(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {r["cell"] for r in csv.DictReader(f) if r.get("cell")}


# ------------------------------------------------------------------------- runner

def prewarm_ollama(model_id):
    """Pin the model in VRAM before a long local run.

    The OpenAI-compatible /v1 endpoint has no keep_alive parameter, and this project has
    already lost a run to that: when keep_alive stopped holding, every call paid a 42.5 s
    model load against 2.1 s of evaluation, turning 13 minutes into about 19 hours. So we
    reach for the native endpoint once, purely to set keep_alive, then do the real work
    over /v1 like every other provider.
    """
    try:
        requests.post("http://127.0.0.1:11434/api/chat", timeout=300,
                      json={"model": model_id, "stream": False, "keep_alive": "60m",
                            "messages": [{"role": "user", "content": "ok"}],
                            "options": {"num_predict": 1}})
        print("   pre-warmed %s with keep_alive=60m" % model_id, flush=True)
    except Exception as e:
        print("   pre-warm failed (%s); expect a model load on every call"
              % repr(e)[:90], flush=True)


def score_modes(prov, short):
    """Count the score_mode column of this model's results file."""
    path = os.path.join(OUT_DIR, "fanout_%s_%s.csv" % (prov, short.replace(".", "_")))
    if not os.path.exists(path):
        return None
    counts = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            m = row.get("score_mode") or "missing"
            counts[m] = counts.get(m, 0) + 1
    return counts


def write_meta(prov, pcfg, short, model_id, client, written, already, plan,
               stop, lat, args):
    """Write the provenance record for this model.

    Called on every path, including the one where there is nothing left to call.
    Until 27 Nov 2026 run_model returned early when a model was already complete,
    so a model whose final rows landed in a run that crashed AFTER writing them
    could never have its metadata corrected: the rerun had no work to do and
    skipped the write. The record said 266 rows beside a file holding 400.
    """
    meta = {
        "provider": prov,
        "model_short": short,
        "model_id": model_id,
        # What the client resolved this session. On a run with nothing left to
        # call it stays at the configured "probe", which says only "not checked
        # here". score_modes_in_file is read back from the CSV, so the record
        # states what the rows ACTUALLY are rather than what the config hoped.
        "logprob_mode_resolved": client.logprob_mode,
        "score_modes_in_file": score_modes(prov, short),
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "rows_this_session": written,
        "rows_total": len(already) + written,
        "rows_planned": len(plan),
        "stopped_because": stop,
        # .get, not [], so a cap the provider does not state records as null
        # rather than killing the run. Retiring Groq's unverified tpd made this
        # line raise KeyError AFTER all 134 rows had been written, so the data
        # landed and its provenance record did not. A results file whose
        # metadata disagrees with it is the defect this project is about.
        "caps_used": {k: pcfg.get(k) for k in ("rpm", "rpd", "rph", "tpm", "tpd")},
        "latency_s": ({"n": len(lat),
                       "median": round(sorted(lat)[len(lat) // 2], 2),
                       "min": round(min(lat), 2),
                       "max": round(max(lat), 2)} if lat else None),
        "stimuli_sha256": args._stim_sha,
        "prompts_py_sha256": args._prompts_sha,
        "personas": args.persona.split(","),
        "kinds": args.kinds.split(","),
        "note": ("Caps are what providers.json said, not what the provider "
                 "promised. logprob_mode_resolved=no means every row from this "
                 "model is emitted_only and cannot enter an expected-rating "
                 "analysis."),
    }
    dest = os.path.join(OUT_DIR,
                        "run_meta_%s_%s.json" % (prov, short.replace(".", "_")))
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)

def run_model(prov, pcfg, short, model_id, plan, budget, args, client):
    out = os.path.join(OUT_DIR, "fanout_%s_%s.csv" % (prov, short.replace(".", "_")))
    already = done_cells(out)
    fresh = not os.path.exists(out)
    todo = []
    for row in plan:
        cid = cell_id(prov, model_id, row["kind"], row["ptype"], row["task"],
                      row["cond"], row["persona"], row["order"], row["pass"])
        if cid not in already:
            todo.append((cid, row))

    print("\n== %s / %s ==  %d calls, %d already done" % (prov, short, len(todo), len(already)),
          flush=True)
    if not todo:
        write_meta(prov, pcfg, short, model_id, client, 0, already, plan,
                   "complete", [], args)
        return 0, "complete"

    req_left, tok_left = budget.remaining(prov, pcfg)
    print("   today's allowance left: %s requests, %s tokens"
          % ("not capped" if req_left is None else req_left,
             "not capped" if tok_left is None else tok_left), flush=True)
    if prov == "ollama":
        prewarm_ollama(model_id)

    written, stop, lat = 0, "complete", []
    f = open(out, "a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if fresh:
        w.writerow(COLUMNS)
    try:
        for cid, row in todo:
            need = est_tokens(row["prompt"])
            if not budget.room_for(prov, pcfg, need):
                stop = "daily cap reached"
                break
            budget.pace(prov, pcfg)
            budget.pace_tokens(prov, pcfg, need)
            t_call = time.time()
            text, lpc, tin, tout, mode = client.call(model_id, row["prompt"],
                                                     row["want_logprobs"])
            lat.append(time.time() - t_call)
            budget.charge(prov, tin or need, tout or 0)
            # A local call that keeps taking tens of seconds means the model is being
            # reloaded per request, not that it is slow. Say so early rather than after
            # nineteen hours.
            if prov == "ollama" and len(lat) == 10:
                med = sorted(lat)[len(lat) // 2]
                if med > 10.0:
                    print("   WARNING median call %.1fs on a local model -- keep_alive is "
                          "probably not holding and this run will take ~%.1f h. Stop it, "
                          "check `ollama ps`, and restart (progress is saved)."
                          % (med, med * len(todo) / 3600.0), flush=True)

            if row["kind"] == "helpfulness":
                answer = P.parse_rating(text)
                ev, share, dist = expected_rating(lpc)
                raw = text[:200]
            else:
                pick = P.parse_choice(text)
                answer = "?" if pick == "?" else int(pick == row["truth"])
                ev, share, dist = None, None, None
                raw = text[:200] if row["kind"] == "dominance" else ""

            w.writerow([short, row["kind"], row["ptype"], row["task"], row["cond"],
                        row["order"], answer, raw, row["pass"],
                        "" if ev is None else round(ev, 4),
                        "" if share is None else round(share, 4),
                        json.dumps(dist) if dist else "",
                        prov, model_id, row["persona"], mode,
                        hashlib.sha1(row["prompt"].encode("utf-8")).hexdigest()[:12],
                        tin, tout, int(time.time()), cid])
            written += 1
            if written % 25 == 0:
                f.flush()
                budget.save()
                rl, tl = budget.remaining(prov, pcfg)
                print("   %d/%d  (left today: %s req, %s tok)" % (written, len(todo), rl, tl),
                      flush=True)
    except KeyboardInterrupt:
        stop = "interrupted"
    finally:
        f.flush()
        f.close()
        budget.save()

    write_meta(prov, pcfg, short, model_id, client, written, already, plan,
               stop, lat, args)
    print("   %s: +%d rows (%d/%d total)" % (stop, written, meta["rows_total"], len(plan)),
          flush=True)
    return written, stop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stimuli", default=STIM_DEFAULT)
    ap.add_argument("--kinds", default="helpfulness",
                    help="comma list of helpfulness,choice,dominance")
    ap.add_argument("--persona", default="plain", help="comma list of plain,eco (choice only)")
    ap.add_argument("--limit", type=int, default=None, help="first N tasks only")
    ap.add_argument("--dominance", type=int, default=None, help="first N calibration items")
    ap.add_argument("--passes", type=int, default=1, help=">1 repeats helpfulness for determinism")
    ap.add_argument("--only", default=None, help="provider or provider:model")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cfg = json.load(open(CFG, encoding="utf-8"))["providers"]
    stim = json.load(open(args.stimuli, encoding="utf-8"))
    args._stim_sha = hashlib.sha256(open(args.stimuli, "rb").read()).hexdigest()
    args._prompts_sha = hashlib.sha256(
        open(os.path.join(HERE, "prompts.py"), "rb").read()).hexdigest()
    os.makedirs(OUT_DIR, exist_ok=True)

    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]
    personas = [p.strip() for p in args.persona.split(",") if p.strip()]
    for p in personas:
        if p not in P.PERSONAS:
            sys.exit("unknown persona %r; have %s" % (p, list(P.PERSONAS)))

    plan = build_plan(stim, kinds, personas, args.limit, args.dominance, args.passes)
    tok = sum(est_tokens(r["prompt"]) for r in plan)
    print("PLAN  %d calls per model, ~%s estimated tokens per model" % (len(plan), f"{tok:,}"))
    print("      kinds=%s personas=%s tasks=%s" % (kinds, personas, args.limit or len(stim["tasks"])))

    want = [(n, c) for n, c in cfg.items() if c.get("enabled")]
    if args.only:
        pn = args.only.split(":")[0]
        want = [(n, c) for n, c in want if n == pn]
    if not want:
        sys.exit("no enabled providers match. Edit scripts/providers.json "
                 "(and set the caps from your own account page).")

    if args.dry_run:
        print("\nDRY RUN -- no calls made.\n")
        for n, c in want:
            ms = c["models"]
            if args.only and ":" in args.only:
                ms = {k: v for k, v in ms.items() if k == args.only.split(":", 1)[1]}
            if not ms:
                print("  %-12s no models configured" % n)
                continue
            # Minutes this plan needs under each published cap. The slowest wins: that is
            # the binding constraint, and naming it is the point. Cerebras taught this the
            # expensive way -- gpt-oss-120b allows 5 requests a minute but only 150 an
            # hour, so pacing on the minute alone collects 429s half an hour in.
            caps = []
            if c.get("rpm"):
                caps.append((len(plan) / float(c["rpm"]), "rpm=%s" % c["rpm"]))
            if c.get("rph"):
                caps.append((len(plan) / float(c["rph"]) * 60.0, "rph=%s" % c["rph"]))
            if c.get("tpm"):
                caps.append((tok / float(c["tpm"]), "tpm=%s" % c["tpm"]))
            if c.get("tph"):
                caps.append((tok / float(c["tph"]) * 60.0, "tph=%s" % c["tph"]))
            mins, binding = max(caps) if caps else (0.0, "no per-minute/hour cap")
            days = max(math.ceil(len(plan) / max(1, c.get("rpd") or 10 ** 9)),
                       math.ceil(tok / max(1, c.get("tpd") or 10 ** 9)))
            per_day = max(1, (c.get("rpd") or 10 ** 9) // max(1, len(plan)))
            print("  %-12s %d model(s)  rpm=%s rph=%s rpd=%s tpm=%s tph=%s tpd=%s"
                  % (n, len(ms), c.get("rpm", "-"), c.get("rph", "-"), c.get("rpd", "-"),
                     c.get("tpm", "-"), c.get("tph", "-"), c.get("tpd", "-")))
            print("               -> %s per model, binding cap is %s; %d day(s), "
                  "%d model(s) per day%s"
                  % (("%.0f min" % mins) if mins < 180 else ("%.1f h" % (mins / 60.0)),
                     binding, days, per_day,
                     "  [COSTS MONEY]" if n == "openai" else ""))
            for s, mid in ms.items():
                print("               - %-14s %s" % (s, mid))
            print("               logprobs=%s  %s" % (c.get("logprobs"), c.get("note", "")))
        total_models = sum(len(c["models"]) for _, c in want)
        print("\n  %d model(s) enabled. Longest single-model wall time above is the "
              "serial cost; providers run independently, so run them in parallel shells."
              % total_models)
        print("  Sample prompt (first call):\n")
        print("  " + plan[0]["prompt"].replace("\n", "\n  ")[:700])
        return

    budget = Budget(os.path.join(OUT_DIR, "state.json"))

    if args.probe:
        print("\nPROBE -- one call per model.\n")
        for n, c in want:
            try:
                cl = Client(n, c, args.verbose)
            except RuntimeError as e:
                print("  %-12s SKIP: %s" % (n, e))
                continue
            for s, mid in c["models"].items():
                t0 = time.time()
                text, lpc, tin, tout, mode = cl.call(mid, plan[0]["prompt"],
                                                     plan[0]["want_logprobs"])
                ok = P.parse_rating(text) if plan[0]["kind"] == "helpfulness" \
                    else P.parse_choice(text)
                budget.charge(n, tin or 0, tout or 0)
                print("  %-12s %-16s %5.1fs  score_mode=%-12s parsed=%-3s  %r"
                      % (n, s, time.time() - t0, mode, ok, text[:70]))
        budget.save()
        return

    for n, c in want:
        try:
            cl = Client(n, c, args.verbose)
        except RuntimeError as e:
            print("\n== %s ==  SKIP: %s" % (n, e))
            continue
        ms = c["models"]
        if args.only and ":" in args.only:
            ms = {k: v for k, v in ms.items() if k == args.only.split(":", 1)[1]}
        for s, mid in ms.items():
            _, stop = run_model(n, c, s, mid, plan, budget, args, cl)
            if stop == "interrupted":
                print("\nstopped. rerun the same command to resume.")
                return
            if stop == "daily cap reached":
                print("   (%s is spent for today; rerun tomorrow to continue)" % n)
                break

    print("\ndone. rerun the same command any time -- completed cells are skipped.")


if __name__ == "__main__":
    main()
