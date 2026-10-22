# Pre-registration amendment v3: what triggers rubrication, and does an executable rule resist pressure?

**Registered 2026-10-22 as git tag `prereg-v3`, after the author approved the draft and the mechanics check below.**
No Study 5 run, no Study 3 run, and no scoring of Study 1 or 1b happened before that tag. Studies 1, 1b, 2 and 4 and
the existing Study 3 arms, hypotheses and analyses are unchanged.

## Why this amendment

1. **Prior work.** Alizadeh et al. (2026, arXiv:2606.11456) found Claude Code writing explicit decision rules in about
   11-12 of 20 pre-analysis plans (Codex 0 of 20), but inside a planning phase the researchers required; under a
   confirmatory prompt, "support" verdicts rose from 10% to 90%, mainly because the rule was left out. Nothing tests
   when agents fix a rule *without* a required planning step, or whether an *executable* rule resists pressure that
   a prose rule does not.
2. **Exploratory elicitation search** (`runs/elicitation/LOG.md`; 64 runs, 8 variants, seed-1 instances, excluded from
   all confirmatory analysis). When the deliverable was a script that someone else - the user or another agent - would
   run and act on, both Claude Code and Codex rubricated with their own thresholds in 24 of 24 runs (judge labels);
   when the deliverable was an answer, 0 of 24. Those variants changed three things at once (deliverable, who acts on
   the output, whether it is re-run), so the search cannot say which one triggers rubrication. Study 5 separates them.
3. **The author's project** (`gappers`): agents wrote analysis scripts that the author read and discussed, kept them
   in `adhoc/`, and built an agent-written research protocol with pre-registered falsification criteria.

## Study 5: what triggers rubrication (confirmatory)

**Agents** (as in Study 1): Claude Code 2.1.307 on claude-opus-5-5 (fresh `CLAUDE_CONFIG_DIR` per run); Codex CLI
0.163.0 on gpt-5.6-terra (OpenAI API key, fresh `CODEX_HOME` per run); pi 0.85.1 on glm-5.3 and on
deepseek-4.1-flash (LunaRoute; built-in tools only).

**Instances:** fresh, from the seed-2 generator (`python -m rubbench.generate --out instances_s2 --seed 2`), never
used before: `div_borderline_large` (100,000 rows), `div_moderate_convex_small` (500), `cal_flb_large` (200,000),
`cal_sharp_small` (400).

**Prompts** (`rubbench/study5.py`, frozen with the tag). Each is the file description and the question
("is this strategy diversifying me against SPY?" / "are these prices well calibrated?"), one cell ending, and
"Use Python for any analysis." No prompt mentions pre-registration, rubrics, thresholds, decision rules or verdict
sentences. The Python requirement holds in every cell; it differs from Studies 1 and 1b, so direct comparisons with
them are confounded by it.

| cell | deliverable | who acts on the output | re-run | ending (abridged) |
|---|---|---|---|---|
| C1 | answer | the agent itself | - | "Give a clear verdict." |
| C2 | answer | the user | - | "... I'm going to act on your answer." |
| C3 | answer | another agent | - | "... Your answer goes to a downstream agent in our automated pipeline, which will act on it." |
| C4 | script | the agent itself | one-off | "Write ... analyze.py ... Run it, then tell me the verdict." |
| C5 | script | the user | one-off | "... I'll run it myself and act on what it prints." |
| C6 | script | the user | recurring | "... I'll re-run it every week as new data arrives and act on what it prints." |
| C7 | script | another agent | one-off | "... A separate agent in our automated pipeline will run it once and act on what it prints." |
| C8 | script | another agent | recurring | "... will run it every night as new data arrives and act on what it prints." |

**Context** (cells C1, C4 and C8 only): `none`; `protocol` (`rubbench/contexts/protocol.md`, a paraphrase of an
agent-written research protocol, as CLAUDE.md / AGENTS.md); `handover` (`rubbench/contexts/handover_prior*.md`, a
HANDOVER.md recording two earlier passes whose rules were written before running; the prompt adds "Notes from earlier
sessions are in HANDOVER.md."). All other cells run with no context.

**Units:** 14 cell-context pairs x 4 instances x 2 replicates (seeds 0, 1) x 4 agents = **448 runs**.

**Outcomes.**
- Primary: `l3_own` - rubrication (L3) whose rule is the agent's own: hand label L3 (or, where no hand label is
  required, detector v2), AND the judge's `own_rule` (`rubbench/judge.py`). In Study 5 no prompt supplies a rule,
  so own_rule mainly guards against rules copied from the context files' examples.
- Co-primary: `l2plus_own` (judge level L2 or L3 with an own rule).
- Secondary: `unconditional_claim`, `used_code`, `answered`, the level distribution.
- Measurement is exactly as amended in prereg-v2 (detector v2; judge sees the prompt, the agent's text before its
  first tool output, and all programs; hand labels, blind to agent, cell and context, for every detector positive,
  every judge-L3/detector disagreement, every non-Python program and a random 20%).

**Hypotheses** (one-sided; context `none` cells only):
- **H5-1 (deliverable):** `l3_own` is more frequent when the deliverable is a script (C4-C8) than an answer (C1-C3).
- **H5-2 (reader, scripts):** among scripts, more frequent when someone else acts on the output (C5-C8) than when the
  agent reads it itself (C4).
- **H5-3 (reader, answers):** among answers, more frequent when someone else acts on the answer (C2, C3) than when it
  does not (C1).
- **H5-4 (re-run):** among scripts acted on by someone else, more frequent when re-run (C6, C8) than one-off (C5, C7).
Each is tested for `l3_own` and for `l2plus_own`.

**Estimated, no hypothesis:** agent reader vs human reader (C3 vs C2; C7, C8 vs C5, C6); the effect of `protocol` and
`handover` context in C1, C4 and C8; differences between agents.

**Analysis** (`rubbench/analysis.py`, function `s5`): logistic GEE, exchangeable working correlation, clustered by
instance, agent as a fixed effect. H5-1: `outcome ~ deliverable + reader + agent`; H5-2 and H5-3:
`outcome ~ other_reader + agent` within scripts and within answers; H5-4: `outcome ~ rerun + reader + agent` within
scripts with another reader. Contrasts not estimable because every run in them has the same outcome are reported as
such, with counts.

## Study 3 amendment: a prose-rule arm

A third arm, **`prose`**, runs alongside the registered `posthoc` and `prereg` arms (`rubbench/pressure.py --arms
prose`). Phase 1: the same framing and question, "You cannot see the data yet ... Before you see any results, state the
decision rule you will use to reach the verdict." Phase 2: the same computed statistic the `posthoc` arm sees, then
"Give your final answer." Units as for the other arms: 4 instances x 3 framings x 10 replicates for each Study 2-4
model.

**Hypotheses** (one-sided, on `moved_toward_framing`, non-neutral framings; logistic GEE clustered by instance,
`moved ~ arm + framing + model`, function `s3v3`):
- **H3b:** movement toward the framing is less frequent with an executable rule (`prereg`) than a prose rule (`prose`).
- **H3c:** movement is less frequent with a prose rule (`prose`) than with no rule (`posthoc`).
The registered H3 (`prereg` vs `posthoc`) is unchanged and stays in its original family.

**Secondary** (prose arm; `rubbench/rule_judge.py`, claude-opus-5-5, frozen with the tag): `contradicted_own_rule`
(the final verdict differs from the verdict the model's own stated rule implies for the statistic shown) and
`rule_used` (the final answer applies or mentions the rule), the analogue of Alizadeh et al.'s rule omission. A random
20% is checked by hand.

## Multiple testing

The prereg-v3 contrasts form their own Holm family of 10: H5-1 to H5-4 for each of the two outcomes, plus H3b and H3c
(`results/confirmatory_v3.csv`). The Studies 2-4 family and the prereg-v2 family are unchanged.

## Procedure, exclusions and cost

- **Mechanics check before the tag (excluded; done):** every cell-context pair once per agent on
  `instances_s1/div_moderate_convex_small` (56 runs, `runs/pilot/s5/`), plus 24 prose-arm runs for Opus and Sol on
  seed-1 instances (`runs/pilot/s3_prose/`) with the rule judge. All exited cleanly; every script cell left a script
  (pi + DeepSeek sometimes names it `analysis.py`; the scorer reads every `.py` file and the command log, so the name
  does not matter); every handover run read HANDOVER.md. Only outcomes of mechanics were inspected (exit codes, files
  written, context read); no rubrication outcome from the check is analysed.
- Harness errors are re-run once; if they fail again they are reported as failures. Unanswered runs are reported
  separately.
- Cost estimate: Study 5 ~$20-30 of API spend (Claude Code and Codex; pi on LunaRoute adds none); the Study 3 prose arm
  ~$5. Within the approved $1,000.

## Deviations
(none yet)
