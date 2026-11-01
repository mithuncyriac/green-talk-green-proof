# Green talk vs green proof

**Do AI shopping agents read green claims in reviews the way human shoppers do?**

This is a pilot: two small open models, keyword-based review types, and hypotheses written down before each run but not registered publicly. Read the results as a reason for a proper study, not as findings.

## What is here

| Step | Question | Scripts | Results |
|---|---|---|---|
| 1 | What do human readers reward? | `stream_flag.py`, `analyse.py` | `results/01_review_prevalence_and_votes.txt` |
| 2 | Did an FTC greenwashing case (April 2022) change reviews? | `bamboo_meta.py`, `bamboo_reviews.py`, `bamboo_analyse.py` | `results/02_ftc_bamboo_event_study.txt` |
| 3 | What do AI shopping agents choose? | `agent_build.py`, `agent_run.py`, `agent_analyse.py` | `results/03_agent_audit_*.csv`, `results/03_agent_audit_summary.txt` |

## Main results

**1. Human readers** (Amazon Reviews 2023: Beauty & Personal Care + Health & Household; 49,542,735 reviews; 184,260 flagged as mentioning sustainability)
- **Calibration:** longer reviews get more helpful votes, as Mudambi & Schuff (2010) found.
- **Pooled negative binomial, flagged reviews only, base = vague claims:**
  - sceptical reviews (greenwashing, too much plastic): IRR 1.84
  - specific claims: IRR 1.07
- **Within the same product:** specific claims beat vague ones by only about 1 percentage point in the chance of any vote. Sceptical reviews stay ahead (+0.057 on log(1 + votes), p = 0.013).

**2. FTC bamboo/rayon event study** (8,286,747 textile reviews; 4,179 bamboo-labelled products)
- **Headline:** scepticism +0.275 pp (p = 0.018).
- **Not trusted.** Every pre-event quarter coefficient is negative, the April 2021 placebo shows about half the effect, and the fibre-mention outcome fails both its pre-trend and placebo checks.

**3. Agent audit** (Qwen 2.5 7B and Llama 3.1 8B via Ollama, temperature 0; 120 tasks)
- **Task design:** two products with the same 4.5-star average and $9.99 price, four neutral reviews each. Product A gets one extra review: neutral, vague, specific or sceptical.
- **Calibration:** 40 dominance tasks, each run in both orders. Passed at 96.2% (Qwen) and 97.5% (Llama).
- **Eco-minded customer, share choosing Product A:**

| Extra review | Qwen | Llama |
|---|---|---|
| neutral | 56.2% | 53.3% |
| vague claim | 76.7% | 59.6% |
| specific claim | 77.1% | 60.8% |
| sceptical | 67.9% | 58.8% |

- **Plain customer:** no review type had any effect.
- **Helpfulness ratings (1–7):** neither model rated sceptical reviews higher than vague ones; Qwen rated them lowest (5.86 vs 6.36).

## Limits

- Only two small open models.
- Strong position bias: Qwen picked the first product shown 70.6% of the time, Llama 94.0%. The design counterbalances order, but few of Llama's choices could move.
- Review types come from keyword dictionaries. A spot check found the "observable evidence" tier unreliable, so it was dropped from the audit.
- The sceptical reviews were 4–5-star reviews, so they were mostly positive overall.
- Human helpful votes and agent choices are different measures. Compare them in direction only.
- Not pre-registered on OSF.

## Reproduce

Requirements: Python 3.11+, `pip install -r requirements.txt`. Step 3 needs [Ollama](https://ollama.com) with `qwen2.5:7b` and `llama3.1:8b`, which fit an 8 GB GPU with `num_ctx` 6144.

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

# 3. agent audit
python scripts/agent_build.py data agent/stimuli.json
python scripts/agent_run.py agent/stimuli.json qwen2.5:7b agent/out_qwen2_5_7b.csv
python scripts/agent_run.py agent/stimuli.json llama3.1:8b agent/out_llama3_1_8b.csv
python scripts/agent_analyse.py agent
```

The stimuli file is not included, because it contains review text. `agent_build.py` rebuilds it from the data with fixed random seeds.

## Data and terms

- **Source:** Amazon Reviews 2023 (McAuley Lab, UC San Diego; Hou et al., 2024, arXiv:2403.03952), streamed from the lab's public server.
- **Research use only.** This repo holds no review text, no reviewer IDs and no raw data, only scripts and aggregate results.
- **Model terms:** Qwen 2.5 and Llama 3.1 are used under their own licences.

## Status

- AI-assisted build: the code was written with an AI coding assistant and run by the author.
- The whole repo is a pilot: not peer reviewed, and not pre-registered on OSF.
- Licence: MIT (code). Author: Mithun Cyriac.

## References

- Hou, Y., et al. (2024). Bridging language and items for retrieval and recommendation. arXiv:2403.03952.
- Mudambi, S. M., & Schuff, D. (2010). What makes a helpful online review? A study of customer reviews on Amazon.com. *MIS Quarterly*, 34(1), 185–200.
- US Federal Trade Commission (2022). Settlements with Kohl's and Walmart over bamboo textile claims, April 2022.
