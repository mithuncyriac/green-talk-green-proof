# Green talk vs green proof

**Do AI shopping agents read green claims and trust signals in reviews the way human shoppers do?**

An exploratory pilot: two small open models, review types from keyword dictionaries, and hypotheses written down before each run but not publicly registered. Read it as a reason for a proper study, and as a worked example of auditing an agent before deploying it, rather than as findings about production systems.

**Headline:** the same 100 reviews, carrying the same `[Made with AI]` label, made one model rate them lower and the other rate them higher. The gap is +0.33 points (p = 1.7e-05) and it survives standardising within model and a 2,000-draw bootstrap. The pre-registered rule said a result counts only with the same sign in both models, so by that rule this failed, and the failure is the output.

## What is here

| Step | Question | Scripts | Results |
|---|---|---|---|
| 1 | What do human readers reward? | `stream_flag.py`, `analyse.py` | `results/01_review_prevalence_and_votes.txt` |
| 2 | Did an FTC greenwashing case (April 2022) change reviews? | `bamboo_meta.py`, `bamboo_reviews.py`, `bamboo_analyse.py` | `results/02_ftc_bamboo_event_study.txt` |
| 3 | What do AI shopping agents choose? | `agent_build.py`, `agent_run.py`, `agent_analyse.py` | `results/03_agent_audit_*.csv`, `results/03_agent_audit_summary.txt` |
| 4 | Do agents discount "Made with AI" reviews? | `label_build.py`, `label_run.py`, `label_analyse.py` | `results/04_label_audit_*.csv`, `results/04_label_audit_summary.txt` |
| 5 | Is the cross-model gap real, or two noisy estimates? | `label_interaction.py` | inside `results/04_label_audit_summary.txt` |
| 6 | Does any of it reproduce? | rerun of step 4 | `results/rerun-2026-11-25/` |
| 7 | Figures and process artefacts | `build_findings.py`, `make_visuals.py` | `results/findings.json`, `artefacts/` |

## Main results

**1. Human readers** (Amazon Reviews 2023: Beauty & Personal Care + Health & Household; 49,542,735 reviews; 184,260 flagged as mentioning sustainability)
- **Calibration:** longer reviews get more helpful votes, as Mudambi & Schuff (2010) found. Coefficient 1.055 on log words, N = 987,316.
- **Pooled negative binomial, flagged reviews only, base = vague claims:** sceptical reviews (greenwashing, too much plastic) IRR 1.84; specific claims IRR 1.07.
- **Within the same product:** specific claims beat vague ones by about 1 percentage point on the chance of any vote. Sceptical stays ahead (+0.057 on log(1 + votes), p = 0.013).

**2. FTC bamboo/rayon event study** (8,286,747 textile reviews; 4,179 bamboo-labelled products)
- **Headline:** scepticism +0.275 pp (p = 0.018).
- **Not trusted, and kept anyway.** Every pre-event quarter coefficient is negative, the April 2021 placebo shows about half the effect, and the fibre-mention outcome fails both its pre-trend and its placebo. Reported as a failed identification.

**3. Agent audit, green claims** (Qwen 2.5 7B and Llama 3.1 8B via Ollama, temperature 0; 120 tasks)
- Two products with the same 4.5-star average and $9.99 price, four neutral reviews each. Product A gets one extra review: neutral, vague, specific or sceptical. Both display orders.
- **Calibration:** 40 dominance tasks in both orders, passed at 96.2% (Qwen) and 97.5% (Llama).
- **Eco-minded customer, share choosing Product A:**

| Extra review | Qwen | Llama |
|---|---|---|
| neutral | 56.2% | 53.3% |
| vague claim | 76.7% | 59.6% |
| specific claim | 77.1% | 60.8% |
| sceptical | 67.9% | 58.8% |

- **Plain customer:** no review type had any effect.
- **Vague and specific are the same number.** The models cannot tell a substantiated claim from an empty one.
- **Position bias:** Qwen picks the first-shown product 70.6% of the time, Llama 94.0%.

**4. AI-label audit** (100 real reviews, 3 within-item label conditions, 1,960 prompts, 0 unparseable)
- Hypotheses written and SHA-256 hashed at 05:05:42 on 2 Nov 2026; the run started at 05:06:22. **Hashed locally. Never uploaded to OSF.**
- H1, "Made with AI" lowers helpfulness: **Qwen -0.14 (p_holm = .014), Llama +0.19 (p_holm = .023).** Opposite signs.
- H2, the effort label beats the AI label: **+0.25 in both** (p_holm < .001 and .002).
- H3 and H4, choice: all four null. Llama picks the first-shown product 99.8% of the time here, so its choice null is uninformative rather than evidence of no effect.
- **The pre-registered robustness rule (same sign and significant in both models) fails for H1.**

**5. Is the gap real?** (`label_interaction.py`, added 25 Nov 2026)

Two opposite signs are not a difference until the difference is tested. Both models rated the same 100 reviews, so the comparison is within review, with errors clustered by review.

| Test | Result |
|---|---|
| Label x model interaction, raw points | **+0.330, p = 1.7e-05, 95% CI [0.180, 0.480]** |
| Same, standardised within model | **+0.264 SD, p = 1.4e-05, 95% CI [0.145, 0.383]** |
| Item-cluster bootstrap, 2,000 draws | Qwen negative and Llama positive in **2,000 of 2,000** |

The standardised version matters because the two models do not use the same scale. Qwen uses all seven points and parks 50% of its unlabelled answers at 7. Llama never emitted a 7 in 300 ratings and shifts mass between 4 and 6 instead. Opposite headroom could produce opposite signs on its own; standardising removes that explanation and the gap stays.

The helpfulness task shows one review alone, with no second product, so display order cannot reach this result. That objection applies to the choice tasks only.

**6. Reproduction** (25 Nov 2026, 23 days later, same stimuli file with its hash checked, same models, temperature 0, seed 1)

| | 2 Nov | 25 Nov |
|---|---|---|
| Qwen, AI label | -0.14 | -0.15 |
| Llama, AI label | +0.19 | +0.20 |
| Qwen, effort label | +0.25 | +0.24 |
| Llama, effort label | +0.25 | +0.26 |
| Cross-model gap | +0.33 (p = 1.7e-05) | +0.35 (p = 7.1e-07) |

1,960 prompts matched one to one. **Temperature 0 is not determinism:** 3.3% of helpfulness ratings, 1.2% of choices and 0.6% of calibration answers came back different with nothing changed in the inputs. The effects were stable; the individual answers were not. Those are different claims.

Cost of the whole rerun: 6.9 minutes of local GPU for Qwen, 9.3 for Llama, plus 203 seconds of analysis.

## Artefacts

Generated by `make_visuals.py` from `results/findings.json`. Nothing is drawn by hand or by an image model, because a generated chart invents its numbers and that would destroy the one property this repo has.

| File | What it shows |
|---|---|
| `01-sign-flip.svg` | The headline, with bootstrap intervals and the tested gap |
| `02-scale-use.svg` | Every rating either model gave, and why the standardised test exists |
| `03-three-switches.svg` | Model, persona and display order each changing the answer |
| `04-sipoc.svg` | SIPOC of the audit itself |
| `05-audit-pipeline.svg` / `.drawio` | BPMN swimlanes, two numeric gates, and the gate that failed |
| `06-value-stream-map.svg` | Cycle time per step; the steps that were not timed say so |
| `07-reproduction.svg` | What held between the two runs and what did not |

The process mapped is the audit, not the shopping journey. The recommender's internal trust path and a firm's assurance process would both be invented, because neither was observed. The audit pipeline is the only process actually operated.

## Limits

- Only two small open models, running locally. Not production recommenders.
- Strong position bias: Qwen 70.6%, Llama 94.0% in the green-claims audit, Llama 99.8% in the label audit. The design counterbalances order, but few of Llama's choices could move.
- Review types come from keyword dictionaries. A spot check found the "observable evidence" tier unreliable, so it was dropped from the audit. The remaining tiers have not been checked against a human coder.
- The effort label is confounded: it signals effort and also signals 3 months of real use. The next version has to split those.
- The sceptical reviews were 4 and 5 star reviews, so they were mostly positive overall.
- Human helpful votes and agent choices are different measures. Compare direction only.
- Not pre-registered on OSF.
- One person wrote the hypotheses, ran the study, judged the result and ran the reproduction.

## Reproduce

Requirements: Python 3.11+, `pip install -r requirements.txt`. Steps 3, 4 and 6 need [Ollama](https://ollama.com) with `qwen2.5:7b` and `llama3.1:8b`, which fit an 8 GB GPU with `num_ctx` 6144.

```bash
# 1. stream two full category files (about 6 GB compressed; nothing is stored except flagged reviews and a 2% sample)
python scripts/stream_flag.py Health_and_Household data
python scripts/stream_flag.py Beauty_and_Personal_Care data
python scripts/analyse.py data

# 2. FTC bamboo event study (about 22 GB streamed)
python scripts/bamboo_meta.py meta_Home_and_Kitchen bamboo
python scripts/bamboo_meta.py meta_Clothing_Shoes_and_Jewelry bamboo
python scripts/bamboo_reviews.py Home_and_Kitchen meta_Home_and_Kitchen bamboo
python scripts/bamboo_reviews.py Clothing_Shoes_and_Jewelry meta_Clothing_Shoes_and_Jewelry bamboo
python scripts/bamboo_analyse.py bamboo

# 3. agent audit, green claims
python scripts/agent_build.py data agent/stimuli.json
python scripts/agent_run.py agent/stimuli.json qwen2.5:7b agent/out_qwen2_5_7b.csv
python scripts/agent_run.py agent/stimuli.json llama3.1:8b agent/out_llama3_1_8b.csv
python scripts/agent_analyse.py agent

# 4. AI-label audit (label_build.py needs step 1's data; label_stimuli.json is kept locally)
python scripts/label_build.py data agent/stimuli.json data_label/label_stimuli.json
python scripts/label_run.py data_label/label_stimuli.json qwen2.5:7b results/04_label_audit_qwen2_5_7b.csv
python scripts/label_run.py data_label/label_stimuli.json llama3.1:8b results/04_label_audit_llama3_1_8b.csv
python scripts/label_analyse.py results/04_label_audit_*.csv

# 5. is the cross-model gap real, or two noisy estimates
python scripts/label_interaction.py results/04_label_audit_*.csv --boot 2000

# 6. rerun to check it reproduces: the step 4 commands again, into results/rerun-<date>/

# 7. figures and process artefacts
python scripts/build_findings.py
python make_visuals.py
```

The stimuli files are not included, because they contain review text. `agent_build.py` and `label_build.py` rebuild them from the data with fixed random seeds.

## Data and terms

- **Source:** Amazon Reviews 2023 (McAuley Lab, UC San Diego; Hou et al., 2024, arXiv:2403.03952), streamed from the lab's public server.
- **Research use only.** This repo holds no review text, no reviewer IDs and no raw data. Scripts, aggregate results and figures only.
- **Model terms:** Qwen 2.5 and Llama 3.1 are used under their own licences.

## Status

- **AI-assisted build.** The code was written with an AI coding assistant. The original runs on 1 and 2 November were run by the author. The 25 November reproduction run, the cross-model test and the figure scripts were produced by an AI coding assistant working on the author's machine, under the author's direction. Saying which is which matters more than the distinction flatters either party.
- An exploratory pilot. Not peer reviewed, and not pre-registered on OSF.
- **What is not in this repo:** no review text, no reviewer IDs, no raw corpus. The model-output column in the result CSVs contains each model's own commentary on a review, not the review itself.
- Licence: MIT (code). Author: Mithun Cyriac.

## References

- Carney, Riveros & Tully (2026). AI-generated-content disclosures and consumer engagement. *Journal of Consumer Research*, doi:10.1093/jcr/ucag013.
- Hou, Y., et al. (2024). Bridging language and items for retrieval and recommendation. arXiv:2403.03952.
- Mudambi, S. M., & Schuff, D. (2010). What makes a helpful online review? A study of customer reviews on Amazon.com. *MIS Quarterly*, 34(1), 185–200.
- US Federal Trade Commission (2022). Settlements with Kohl's and Walmart over bamboo textile claims, April 2022.
