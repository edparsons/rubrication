# Elicitation search (exploratory; excluded from all confirmatory analysis)

Started 2026-10-22T19:18:46Z. Question: in which conditions do coding agents pre-register their OWN interpretation
(L2/L3 with an own rule, judged by rubbench/judge.py, L3 by detector v2 + my hand check) without a required planning
step and without being told to? Motivated by the gap left by Alizadeh et al. 2026 (arXiv:2606.11456), where the
pre-analysis-plan phase was imposed by the researchers.

Stopping rule (fixed before the first run): at most 8 variants; at most $30 API spend; agents Claude Code
(claude-opus-5-5) and Codex (gpt-5.6-terra, API key); instances instances_s1/div_borderline_large and
div_moderate_convex_small (seed-1 generator, never the registered set); seeds 0 and 1; 8 runs per variant.
Every variant tried is listed below with its result, including nulls. Any condition carried forward is re-tested
confirmatorily under a new pre-registration (prereg-v3) on fresh instances and seeds.

Variants (prompt texts in rubbench/elicit.py; no prompt mentions pre-registration, rubrics, thresholds or verdict sentences):
- V0 control: verdict question, no context
- V1 protocol context (research-loop paraphrase, rubbench/contexts/protocol.md) as CLAUDE.md/AGENTS.md
- V2 prior handover (rubbench/contexts/handover_prior.md) showing earlier pre-committed passes
- V3 hypothesis framing ("My hypothesis is ... Test it.")
- V4 agent cannot see the result ("Don't run it on this file - I'll run it myself ... and act on what it prints")
- V5 decision at stake ("Tell me the decision and the rule you used")
- V6-V8 reserved for combinations of variants that show any effect

## Results

### Interim, 2026-10-22T19:29:02Z (20 of 48 runs; judge + detector v2, not yet hand-checked)
| variant | Claude Code: own-rule L2+ | Codex: own-rule L2+ |
|---|---|---|
| V0 control | 0/4 | 0/4 |
| V1 protocol context | 4/4 (1 L3) | 4/4 |
| V2 prior handover | 4/4 | 0/1 (3 pending) |
Spot check (V2, div_borderline_large, Claude, s0): agent read HANDOVER.md and the data head, wrote "Following the
handover's convention, I'll write the criteria down before running anything", appended its own rule, then computed.

### V6 added (variant 7 of 8 allowed), before running it
- V6 reuse without blindness: as V4 but the agent may run the script on this file ("Check it works on this file. I'll
  re-run it every week ... and act on what it prints"). Purpose: separate "cannot see the output" from "script will
  be reused" as the trigger for V4's effect. Prompt in runs/elicitation/V6.json.
