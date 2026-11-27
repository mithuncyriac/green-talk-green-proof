Smoke test of fanout_run.py, 26 Nov 2026. NOT study data.

3 tasks x 4 label conditions x 2 local models = 24 real calls, kept as evidence the
harness works end to end: logprobs arrive through Ollama's OpenAI-compatible /v1
endpoint, the budget state persists, and a rerun skips completed cells.

Moved out of the run directory so it can never be mistaken for the 100-task study.
A full run writes fresh files one level up.

What it established:
- score_mode=logprob on both local models through /v1 (digit_mass_share 1.0)
- expected ratings separate conditions in the 4th decimal where emitted integers tie
- pre-warming with keep_alive=60m takes llama3.1:8b from 49.2 s a call to a 0.96 s
  median, which is the 19-hour stall from 25 Nov, fixed
