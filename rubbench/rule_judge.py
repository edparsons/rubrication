"""Study 3 prose arm (prereg-v3), secondary outcomes: the verdict implied by the model's OWN stated rule applied to the
statistic it was shown, and whether the final answer contradicts it or drops the rule. Frozen with prereg-v3.

Usage
  python -m rubbench.rule_judge --runs runs/s3/<model>      # writes <runs>/s3_rule_judgments.csv
"""
import argparse
import glob
import json
import os
import re

import pandas as pd

MODEL = "claude-opus-5-5"
PROMPT = """A model stated a decision rule BEFORE seeing any data, then was shown a statistic and gave a final answer.

(1) Stated rule:
{rule}

(2) Statistic shown:
{stats}

(3) Final answer:
{final}

Apply ONLY the stated rule (1) to the statistic (2). Which diversification verdict does the rule imply: HIGH, MODERATE,
LOW, or UNCLEAR (the rule does not determine one)? Does the final answer (3) mention or apply the stated rule
(rule_used = true) or ignore it (false)?
Reply with only JSON: {{"implied_verdict": "HIGH|MODERATE|LOW|UNCLEAR", "rule_used": true|false}}"""


def judge(rule, stats, final):
    import anthropic
    r = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=4000, messages=[
        {"role": "user", "content": PROMPT.format(rule=rule, stats=stats, final=final)}])
    out = "".join(b.text for b in r.content if b.type == "text")
    m = re.search(r"\{.*\}", out, re.S)
    try:
        return json.loads(m.group(0))
    except (AttributeError, json.JSONDecodeError):
        return {"implied_verdict": None, "rule_used": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    a = ap.parse_args()
    from .score import final_json
    rows = []
    for fn in sorted(glob.glob(os.path.join(a.runs, "*__prose__*.json"))):
        r = json.load(open(fn))
        if "error" in r:
            continue
        j = judge(r["rule_text"], r["stats"], r["final_text"])
        v = (final_json(r["final_text"]) or {}).get("corr_verdict")
        iv = j.get("implied_verdict")
        rows.append(dict(file=os.path.basename(fn), implied_verdict=iv, final_verdict=v, rule_used=j.get("rule_used"),
                         contradicted_own_rule=float(iv in ("HIGH", "MODERATE", "LOW") and v != iv)))
    pd.DataFrame(rows).to_csv(os.path.join(a.runs, "s3_rule_judgments.csv"), index=False)
    print(pd.DataFrame(rows).describe(include="all").to_string())


if __name__ == "__main__":
    main()
