# Pre-registration amendment v2: when do agents rubricate?

Registered 2026-10-22 as git tag `prereg-v2`. No Study 1 or 1b confirmatory run happens before that tag.
Studies 2-4 are unchanged by this amendment. A study of rubrication in the author's real sessions (drafted as
"Study 1c") was removed before registration and may be registered separately later.

## Why this amendment

Section 4 of the paper argues that rubrication emerges without being designed, and predicts it is more frequent
(a) when data is large relative to context, (b) when the question asks for a categorical verdict, and (c) when
tool output is truncated. The paper leaves these moderators to future work. This amendment tests them, adds two
moderators suggested by the author's own practice.

The pilot (four Study 1 runs, one instance, excluded from analysis) is the reason for some measurement changes below
(Codex computed in awk; pi ran Python inline), not for the hypotheses. All hypotheses come from section 4 of the
paper or from the author's project instructions, which were written before this study.

The author's observations come mainly from one project whose `CLAUDE.md` (context file) contains:
1. threshold-to-label tables (e.g. correlation 0.20-0.50 STRONG, 0.10-0.20 GOOD, 0.05-0.10 MODERATE, 0.02-0.05 WEAK,
   below 0.02 noise; strategy-vs-benchmark correlation 0.10-0.40), numeric sanity rules ("if a strategy shows >30%
   annualised, verify no bias") and labelled example output ("GOOD - dates match" / "BAD - future data");
2. print-style rules that prescribe status words in printed output ("OK", "WARNING:", "FAILED", "ERROR");
3. a rule that the agent must not run backtests itself ("let the user execute"), and a rule that analysis must be
   written to `.py` files in `adhoc/` rather than run inline.

Element 1 is a rubric supplied in context; 2 normalises verdict words in print statements; 3 means the human, not the
agent, often reads the output, which favours self-interpreting scripts. Rubrication observed in that project may
therefore be induced by context rather than emergent. Study 1b tests this directly.

## Measurement amendments (apply to Study 1 as registered and to 1b)

- `used_code` counts any code the agent executed, in any language, recovered from the agent's ordered tool-call log
  (Claude Code stream-json, `pi --mode json`, `codex exec --json`) plus `.py` files left in the working directory.
  A shell command counts as code if it invokes Python or one of: awk, gawk, mawk, perl, ruby, node, Rscript, R,
  julia, sqlite3, duckdb, psql, bc, dc, datamash, mlr, csvstat, csvsql, jq (`rubbench/score.py`). Commands such as
  head, wc, cat or sed -n on their own do not count.
- `rubricated` (L3) uses the registered static AST detector for Python. Non-Python programs are hand-labelled for L3
  (all of them, not a sample).
- New secondary outcome `level` (L0-L3, the paper's taxonomy, section 2), assigned per run as the highest level in
  any executed script. L3 comes from the detector (and hand labels for non-Python). L1 vs L2 vs L0 is assigned by an
  LLM judge (claude-opus-5-5, fixed prompt in `rubbench/judge.py`, written and frozen before any run) that sees the
  scripts but not the answer. The judge is validated against blind hand labels on a random 20% of runs
  (seed 20261022); report Cohen's kappa and per-level precision and recall. If kappa < 0.6, `level` is reported as
  exploratory only.

## Study 1b: moderators of rubrication (confirmatory)

Agents: Claude Code 2.1.307 on claude-opus-5-5; Codex CLI 0.163.0 on gpt-5.6-terra; pi 0.85.1 on glm-5.3; pi 0.85.1
on deepseek-4.1-flash (all as in Study 1).

Tasks: 5 base tasks x 2 sizes = 10 instances from the seed-0 set: `div_borderline`, `div_moderate_convex`,
`div_neutral_flat`, `cal_sharp`, `cal_flb`, each `_small` and `_large`.

Factors (full factorial, between runs):
- **Prompt** (3 levels)
  - `P1 rules`: the registered Study 1 prompt (verdict question, thresholds stated, JSON answer).
  - `P2 verdict`: the same verdict question with no thresholds and no labels supplied; the agent must give a verdict
    in its own words ("Is this strategy diversifying me against SPY? Give a clear verdict." / "Are these prices well
    calibrated? Give a clear verdict."), written answer, no JSON.
  - `P3 open`: a descriptive question with no verdict requested ("Describe how this strategy's returns relate to
    SPY's." / "Describe how these prices relate to outcomes."), written answer.
- **Size** (2): small (400-500 rows) vs large (100,000-200,000 rows), via the instance.
- **Context** (3): the working directory contains
  - `none`: no context file (as in Study 1);
  - `full`: a paraphrase of the author's project context file (`rubbench/contexts/full.md`), as `CLAUDE.md` for
    Claude Code and `AGENTS.md` for Codex and pi. Proprietary detail (strategy logic, internal APIs, data schemas) is
    removed; elements 1-3 are kept with their wording and numbers, and the file keeps the original's tone and
    emphasis. It is therefore close to, not identical with, the file the author used;
  - `ablated` (`rubbench/contexts/ablated.md`): the same file with elements 1 and 2 above removed (threshold tables, numeric sanity rules, labelled
    example output, print-style status words). Everything else identical. The ablated file is about half
    the length of the full one, so length is confounded with the removed elements; H1b-4 tests the removed elements
    and their length together.
  pi runs in context conditions drop `--no-context-files` so pi loads `AGENTS.md`; nothing else changes.
- Replicates: 2.

Units: 10 instances x 3 prompts x 3 contexts x 2 replicates = 180 runs per agent, 720 runs in total.

**Study 1b-T (truncation, own harness).** The third prediction cannot be manipulated inside commercial agents, so it
is tested in the Study 2 harness: the `code` condition prompt (no hint about method) with tool output truncated at
2,000 vs 20,000 characters (`TOOL_OUT_MAX`). Models: the four Study 2-4 models. Units: 10 instances x 2 caps x
3 replicates x 4 models = 240 runs.

Primary outcome: `rubricated` (L3 in any executed script). Secondary: `rubric_first_script`, `level`, `used_code`.

Hypotheses (one-sided):
- H1b-1 (size, paper section 4a): L3 is more frequent on large than small instances.
- H1b-2 (verdict question, section 4b): L3 is more frequent for `P2 verdict` than `P3 open`.
- H1b-3 (context): L3 is more frequent with `full` context than `none`.
- H1b-4 (mechanism): L3 is more frequent with `full` than `ablated` context.
- H1b-5 (truncation, section 4c): in Study 1b-T, L3 is more frequent at the 2,000-character cap.

Exploratory (no test): `P1 rules` vs `P2 verdict` (are thresholds supplied by the user rubricated, or applied in
prose?); differences between agents; interactions.

Analysis (`rubbench/analysis.py`, functions `s1b` and `s1bt`): logistic GEE, exchangeable working correlation
clustered by instance;
1b: `rubricated ~ prompt + size + context + agent`; 1b-T: `rubricated ~ cap + model + size`. Contrasts as in
H1b-1 to H1b-5. Holm correction across these five contrasts, as a family separate from Studies 2-4 (whose
correction is unchanged). If every run in a contrast has the same outcome (e.g. no rubrication anywhere), the
contrast is reported as not estimable, with the counts.

## Cost and schedule (estimates)

Study 1b: Claude Code ~$30-50 (180 runs; the context file adds ~6k cached tokens per turn); Codex on the author's
ChatGPT login and pi on LunaRoute add no API cost (pi runs are slow: ~360 runs at one concurrent request).
Study 1b-T: ~$5-10. Judge calls: ~$5-10. Total within the approved $1,000.

## Decisions taken before registration

1. The `full` context is a paraphrase of the author's project file (see Study 1b, Context), not the file itself.
2. Judge model: claude-opus-5-5, checked by blind hand labels on 20% of runs.

## Implementation (frozen with the tag)

Prompts: `rubbench/prompts.py` (`s1_prompt`); contexts: `rubbench/contexts/{full,ablated}.md`; runner:
`python -m rubbench.agents --agent <a> --out runs/s1b --families div cal --match div_borderline_small div_borderline_large div_moderate_convex_small div_moderate_convex_large div_neutral_flat_small div_neutral_flat_large cal_sharp_small cal_sharp_large cal_flb_small cal_flb_large
--prompts P1 P2 P3 --contexts none full ablated --seeds 0 1`.
Study 1b-T: `python -m rubbench.harness --provider <p> --model <m> --out runs/s1bt/<cap>/<m> --families div cal
--match <same 10 names> --conditions code --tool-out-max 2000|20000 --seeds 0 1 2`. Scoring: `rubbench.score s1`
(with `--labels` for hand labels of non-Python code), `rubbench.score s2` for 1b-T, then `rubbench.judge` for
`level`.
