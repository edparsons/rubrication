# rubbench: experiment kit for "Rubrication"

Code and protocol for the four studies in the paper. Read `PREREGISTRATION.md` first. Runners: see `HANDOVER.md`.

Providers: `--provider anthropic | openai | compat` (compat = any OpenAI-compatible endpoint, for open-weights models).

## Setup
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...      # and OPENAI_API_KEY, COMPAT_BASE_URL + COMPAT_API_KEY as needed
python tests/test_smoke.py                       # offline check, no API calls
python -m rubbench.generate --out instances --seed 0
```

## Run
```bash
# Study 1: real agents, no hint about method (check CLI flags in rubbench/agents.py first)
python -m rubbench.agents --agent claude --out runs/s1 --seeds 0 1 2
python -m rubbench.agents --agent codex  --out runs/s1 --seeds 0 1 2

# Study 2: four conditions on one harness
python -m rubbench.harness --provider anthropic --model MODEL_ID --out runs/s2/MODEL_ID --families div cal --seeds 0 1 2 3 4

# Study 3: pressure
python -m rubbench.pressure --provider anthropic --model MODEL_ID --out runs/s3/MODEL_ID --seeds 0 1 2 3 4 5 6 7 8 9

# Study 4: documentation of time (code-based conditions only)
python -m rubbench.harness --provider anthropic --model MODEL_ID --out runs/s4/MODEL_ID --families leak --conditions code rubric --seeds 0 1 2 3 4
```
Runs are resumable: existing result files are skipped.

## Score
```bash
python -m rubbench.score s1 --runs runs/s1
python -m rubbench.score s2 --runs runs/s2/MODEL_ID
python -m rubbench.score s3 --runs runs/s3/MODEL_ID
python -m rubbench.score s4 --runs runs/s4/MODEL_ID
```
Each writes a per-run CSV and prints group means with 95% bootstrap CIs. Confirmatory tests:
`python -m rubbench.analysis --s2 runs/s2_all.csv --s3 runs/s3_all.csv --s4 runs/s4_all.csv --out results`.

## Rough cost
About 730 API runs per model across Studies 2–4 (400 + 240 + 90) (most are short; `inline` on large files is the expensive cell,
capped at ~100k input tokens and flagged as truncated) plus 138 agent runs for Study 1.

## Files
- `rubbench/generate.py`: synthetic instances and exact ground truth
- `rubbench/prompts.py`: questions, verdict rules, condition wrappers, framings
- `rubbench/harness.py`: one tool loop for all API conditions (python tool, paged-rows tool, or none)
- `rubbench/pressure.py`: Study 3 two-phase protocol
- `rubbench/agents.py`: Study 1 runner for Claude Code / Codex CLI
- `rubbench/providers.py`: Anthropic, OpenAI and OpenAI-compatible adapters
- `rubbench/score.py`: deterministic scoring and the AST rubrication detector
- `rubbench/analysis.py`: pre-registered confirmatory tests (GEE, Holm)
- `tests/test_smoke.py`: offline test with a fake model
