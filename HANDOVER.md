# Handover: running the rubrication studies

You are the harness runner for a pre-registered study. Your job is to run four studies exactly as specified, score
them, run the confirmatory analysis and hand back results. You are not designing the study; it is already fixed in
`PREREGISTRATION.md`. Ed Parsons (the author) is your point of contact for any decision this document doesn't cover.

## Ground rules

1. **Do not change the pre-registration.** Hypotheses, outcomes, sample sizes and analysis are fixed. If you must
   deviate (a bug, an API change, a model that can't do tool calls), write a dated entry under "Deviations" in
   `PREREGISTRATION.md` saying what changed and why, commit it, and tell Ed. Never deviate silently.
2. **Do not edit prompts, thresholds or instances after the pilot.** Bug fixes to harness code are allowed and must be
   logged as deviations.
3. **Never invent, round toward, or "fix" a result.** Failed runs are reported as failures. Unanswered runs count as
   incorrect, as the plan says.
4. **Keep raw runs.** Never overwrite or delete a run file except to re-run a harness *error* once (see Step 5).
5. **Ask Ed before spending more than the agreed budget** (see Step 3).
6. **Isolation.** The `python` tool runs model-written code. It already strips environment variables, but run the
   studies in a container or VM with nothing sensitive on disk.

## Step 0: publish the repo (first session only) and set up

If `github.com/edparsons/rubrication` does not exist yet, you were given this folder with its git history. Publish it
before anything else; this push is what time-stamps the pre-registration:
```bash
gh repo create edparsons/rubrication --public --source . --remote origin \
  --description "Rubrication: pre-registered verdicts for coding agents on large datasets"
git push -u origin main --tags
```
Then confirm `prereg-v1` is visible at https://github.com/edparsons/rubrication/tags. For a stronger timestamp, Ed may
also archive this tag on OSF or Zenodo.

Setup:
```bash
cd rubrication
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python tests/test_smoke.py            # must print SMOKE TEST PASSED
```
Environment variables (never commit them, never paste them into logs):
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `COMPAT_BASE_URL`, `COMPAT_API_KEY` for the open-weights model (an OpenAI-compatible endpoint that supports tool
  / function calling, e.g. vLLM, Together or Fireworks)

## Step 1: confirm the pre-registration is time-stamped

The tag `prereg-v1` must exist on GitHub and must predate every run. Check with `git tag` and
`git log -1 prereg-v1`. If it is missing, stop and tell Ed.

## Step 2: generate instances

```bash
python -m rubbench.generate --out instances --seed 0
```
This prints a ground-truth table. Check that `instances/manifest.csv` is identical to
`docs/ground_truth_seed0.csv` (`cmp` them): 29 instances; for example `div_borderline_small` corr 0.112 MODERATE, `div_borderline_low_small`
corr 0.094 HIGH; leak instances with correct Sharpe between about -1.6 and 2.1 and leaky Sharpe about 69.
If anything differs, stop: library versions may have changed the random stream (the reference was generated with the
versions in `docs/generator_versions.txt`). Record your numpy/pandas versions.

## Step 3: fix the models and start the run log

Create `runs/RUNLOG.md` and record, for each study:
- exact model IDs (e.g. the dated Claude and GPT model strings, the open-weights model name and its server),
- provider, date and time (UTC), package versions, CLI versions (`claude --version`, `codex --version`),
- the budget Ed approved.

Use one Anthropic model, one OpenAI model and one open-weights model, as pre-registered. Ask Ed which specific
models if he hasn't said.

## Step 4: pilot (results excluded from analysis)

Run a small slice of every study into `runs/pilot/`, for each provider:
```bash
P=anthropic; M=<model-id>
python -m rubbench.harness  --provider $P --model $M --out runs/pilot/s2/$M --families div cal --match borderline_small --seeds 0
python -m rubbench.harness  --provider $P --model $M --out runs/pilot/s2/$M --families cal --match sharp_small --seeds 0
python -m rubbench.pressure --provider $P --model $M --out runs/pilot/s3/$M --seeds 0
python -m rubbench.harness  --provider $P --model $M --out runs/pilot/s4/$M --families leak --match leak_0 --conditions code rubric --seeds 0
python -m rubbench.score s2 --runs runs/pilot/s2/$M
```
Check: no harness errors; the final JSON block parses (`answered` = 1); tool calls work for the provider; token use
per run. From the pilot's token counts and the provider's price list, estimate the full cost (about 730 runs per
model for Studies 2–4) and send Ed the estimate before continuing. The large `inline` cells are the expensive ones.

For Study 1, pilot one instance per agent:
```bash
python -m rubbench.agents --agent claude --out runs/pilot/s1 --families div --seeds 0
```
Check `claude -p` and `codex exec` flags in `rubbench/agents.py` against the installed versions first. If a flag
has changed, fix it and log the change as a deviation.

## Step 5: full runs

For each provider and model:
```bash
python -m rubbench.harness  --provider $P --model $M --out runs/s2/$M --families div cal --seeds 0 1 2 3 4
python -m rubbench.pressure --provider $P --model $M --out runs/s3/$M --seeds 0 1 2 3 4 5 6 7 8 9
python -m rubbench.harness  --provider $P --model $M --out runs/s4/$M --families leak --conditions code rubric --seeds 0 1 2 3 4
```
Study 1:
```bash
python -m rubbench.agents --agent claude --out runs/s1 --seeds 0 1 2
python -m rubbench.agents --agent codex  --out runs/s1 --seeds 0 1 2
```
Runs are resumable. **Harness errors** (files containing an `"error"` key, e.g. rate limits, timeouts): re-run each
once by moving the file to `runs/errors_first_attempt/` and re-running the same command. If it fails again, keep
the error file; it is reported as a failure.

## Step 6: hand-label Study 1 scripts

The plan requires checking the rubrication detector on a random 20% of Study 1 scripts.
```bash
python - <<'EOF'
import glob, json, random
random.seed(20261020)
files = sorted(glob.glob("runs/s1/*.json")); sample = random.sample(files, max(1, len(files) // 5))
json.dump(sample, open("runs/s1_label_sample.json", "w"), indent=1)
EOF
```
For each sampled run, a human (ideally Ed) labels whether any script contains a threshold-gated prose output (level
L3 in the paper), **without looking at the detector's output**. Record the labels in `runs/s1_labels.csv`
(`file,label`). If a model does the labelling instead, log that as a deviation. Then compute the detector's precision
and recall against the labels.

## Step 7: score and analyse

```bash
for M in runs/s2/*/;  do python -m rubbench.score s2 --runs $M; done
for M in runs/s3/*/;  do python -m rubbench.score s3 --runs $M; done
for M in runs/s4/*/;  do python -m rubbench.score s4 --runs $M; done
python -m rubbench.score s1 --runs runs/s1
python - <<'EOF'
import glob, pandas as pd
for s in ("s2", "s3", "s4"):
    pd.concat([pd.read_csv(f) for f in glob.glob(f"runs/{s}/*/{s}_scored.csv")]).to_csv(f"runs/{s}_all.csv", index=False)
EOF
python -m rubbench.analysis --s2 runs/s2_all.csv --s3 runs/s3_all.csv --s4 runs/s4_all.csv --out results
```

## Step 8: hand back

Commit to the repo (on a branch `results`, then open a PR for Ed):
- `runs/RUNLOG.md`, every `*_scored.csv`, `runs/*_all.csv`, `runs/s1_labels.csv`
- `results/confirmatory.csv`
- `results/SUMMARY.md` containing, for each study, the descriptive table printed by the scorer, the confirmatory
  contrasts, failure and unanswered counts, and any deviations
- raw run JSON as a compressed release asset (`runs_raw.tar.gz`), not committed to git, since transcripts are large

`results/SUMMARY.md` should map onto the four pending boxes in the paper's Results section:
- Study 1: proportions used-code / rubricated / rubricated-in-first-script by agent and family; detector precision
  and recall.
- Study 2: `all_correct`, unsupported numbers and input tokens by condition x size x family; H2a–H2c contrasts.
- Study 3: movement toward framing by arm x framing; override rate in the prereg arm; H3 contrast.
- Study 4: leak rate by documentation level x condition; H4 contrast.

Report the results whatever they show. Null or reversed results are results.
