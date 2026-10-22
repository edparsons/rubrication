# Name tests (exploratory, 2026-10-22)

Cold-decode tests: each model (claude-opus-5-5, gpt-5.6-sol, glm-5.3, deepseek-4.1-flash) was asked, with no
definition, what a term would mean "in the context of using LLMs and coding agents for research and data analysis".
- Round 1 (`name_check.json`): 8 terms, read by hand. "rubrication" read as rubric-based evaluation by 4/4.
- Round 2 (`name_ideas.json` -> `decode2.json`): 40 model-coined candidates, 19 decoded, scored 0-2 by Opus.
  Finding: "prebaked/hardwired/precast verdicts" score high on "in advance" but are read as rigged conclusions.
- Round 3 (`name_ideas3.json` -> `decode3.json`): positive-polarity, rule-fixed brief; 21 terms incl. controls;
  each guess scored by Opus and Sol on rule_fixed / in_code / positive / bias_reading.
