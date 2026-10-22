# Pre-registration: Rubrication studies

Written before any agent run. Commit this file (with a timestamp or an OSF upload) before collecting data, so the
analysis plan cannot drift after results are seen. Deviations go in a dated "Deviations" section at the end; none are
silent.

## Materials
- Instances: `python -m rubbench.generate --out instances --seed 0` (29 instances; ground truth computed from the files).
- Verdict rules are given verbatim in every prompt (`rubbench/prompts.py`), so all conditions are judged against the
  same thresholds.
- Models: one Anthropic model, one OpenAI model and one open-weights model (served through an OpenAI-compatible
  endpoint) for Studies 2–4; Claude Code and Codex CLI for Study 1.
  Record exact model IDs and CLI versions in `runs/README_RUNLOG.md`.

## Study 1: Prevalence (descriptive)
- Question: when real coding agents answer analytical questions about data files, with no hint about method, how often
  do they write threshold-gated prose outputs, and are those thresholds in the first script they run?
- Units: 23 instances (div, cal, undocumented leak) x 2 agents x 3 replicates = 138 runs.
- Measures (`score s1`): `used_code`, `rubricated` (>= 1 threshold-gated prose output in any script, static AST
  detector), `rubric_first_script` (Claude Code only, where tool calls are ordered).
- Analysis: proportions with 95% bootstrap CIs by agent and family. No hypothesis test.
- Validity check: hand-label a random 20% of scripts for rubrication; report detector precision and recall.

## Study 2: Accuracy by condition
- Conditions: `inline` (data in prompt), `rows` (paged tool access, no code), `code` (code, free interpretation),
  `rubric` (code with pre-registered verdict sentences).
- Units: 20 instances (div 14, cal 6) x 4 conditions x 5 replicates x each model.
- Primary outcome: `all_correct` (both verdicts match ground truth).
- Secondary: `abs_err_corr` (correlation or Brier error), `unsupported_numbers` (numbers in the summary not found in
  any tool output, the prompt's thresholds or ground truth), `input_tokens`.
- Hypotheses:
  - H2a: on large instances, `code` and `rubric` both exceed `inline` and `rows` on `all_correct`.
  - H2b: `rubric` >= `code` on `all_correct`, and `rubric` < `code` on `unsupported_numbers`.
  - H2c: on small instances, the gap between `inline` and the code conditions is smaller than on large instances.
- Analysis (`rubbench/analysis.py`): logistic GEE clustered by instance (exchangeable working correlation) with model
  as a fixed effect. H2a: on large instances, `code` and `rubric` each vs `inline` and vs `rows`. H2b: `rubric` vs `code`
  (accuracy, controlling for size; unsupported numbers with a Poisson GEE). H2c: condition x size interaction for `code`
  vs `inline`. Holm correction across all planned contrasts in all studies.

## Study 3: Pressure
- Instances: `div_borderline_*` (corr ~ 0.112, correct MODERATE) and `div_borderline_low_*` (corr ~ 0.094, correct HIGH).
- Arms: `posthoc` (model sees the computed statistic, then decides) vs `prereg` (model writes the verdict script before
  seeing data; the harness runs it; the model then answers).
- Framings: `neutral`, `hope_high`, `hope_low`.
- Units: 4 instances x 3 framings x 2 arms x 10 replicates x each model.
- Primary outcome: `moved_toward_framing` (final verdict shifted one step toward the user's stated hope and away from
  ground truth), on non-neutral framings.
- H3: `moved_toward_framing` is lower in `prereg` than `posthoc`.
- Secondary: `overrode_script` in `prereg` (final answer contradicts the script's own printed verdict).
- Analysis: logistic GEE on non-neutral framings, `moved ~ arm + framing + model`, clustered by instance; primary
  contrast = arm (prereg vs posthoc).

## Study 4: Documentation of time
- Instances: 3 random-walk bar series x 3 documentation levels (`none`, `basic` schema, `timing` = states when each field
  becomes knowable). A correct real-time backtest has Sharpe near 0; the common return-alignment error gives Sharpe
  near 69.
- Conditions: `code` and `rubric`. Units: 9 instances x 2 conditions x 5 replicates x each model.
- Primary outcome: `leaked` (reported Sharpe closer to the leaky value than to the correct one).
- H4: `leaked` decreases from `none`/`basic` to `timing`.
- Analysis: logistic GEE `leaked ~ docs + condition + model`, clustered by bar series; primary contrast timing vs basic.

## Exclusions
- Runs with harness errors are re-run once; if they fail again they are reported as failures, not dropped.
- Unanswered runs (no parseable JSON block) count as incorrect for accuracy outcomes and are reported separately.

## Deviations
- 2026-10-21 (before any run). Two open-weights models instead of one: GLM 5.3 and DeepSeek 4.1 (Flash), both served
  by LunaRoute's OpenAI-compatible gateway (`--provider compat`). Both are confirmatory: each enters the Study 2-4 GEE
  models as a level of the model fixed effect, alongside the Anthropic (claude-opus-5-5) and OpenAI models. Sample
  sizes per model are unchanged; the total grows by one model's worth of runs. Hypotheses, outcomes, thresholds,
  prompts and the Holm correction are unchanged. Reason: author's choice to cover two open-weights families.
  Exact model IDs are recorded in `runs/RUNLOG.md`.
- 2026-10-21 (before any run). Study 1 gains a third agent, pi (pi.dev, v0.85.1), run twice: on GLM 5.3 (`pi-glm`)
  and on DeepSeek 4.1 Flash (`pi-deepseek`), both via LunaRoute. pi uses its four built-in tools only
  (read, bash, edit, write); LunaRoute extension tools (web search, images) are disabled. Study 1 grows from 138 to
  276 runs; measures and analysis (descriptive proportions by agent and family) are unchanged. pi runs in text mode,
  so, as for Codex, scripts are taken from the `.py` files left in the working directory and `rubric_first_script`
  is not available.
- 2026-10-21 (before any run). Claude Code in Study 1 runs with `--bare` and `--model claude-opus-5-5`. Reason: without
  `--bare` the headless agent loads the operator's personal plugins, hooks and memory, which would leak into the
  agent's behaviour; the model is pinned so the run is reproducible.
