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


def batch_judge(runs):
    """{file: judgment} for every prose run, via the Message Batches API (same model and prompt; half price)."""
    import time
    import anthropic
    fns = [fn for fn in sorted(glob.glob(os.path.join(runs, "*__prose__*.json"))) if "error" not in json.load(open(fn))]
    c = anthropic.Anthropic()
    reqs = []
    for k, fn in enumerate(fns):
        r = json.load(open(fn))
        reqs.append({"custom_id": f"r{k:05d}", "params": {"model": MODEL, "max_tokens": 4000, "messages": [
            {"role": "user", "content": PROMPT.format(rule=r["rule_text"], stats=r["stats"], final=r["final_text"])}]}})
    b = c.messages.batches.create(requests=reqs)
    print("rule-judge batch", b.id, len(reqs), flush=True)
    while c.messages.batches.retrieve(b.id).processing_status != "ended":
        time.sleep(60)
    out = {}
    for e in c.messages.batches.results(b.id):
        if e.result.type == "succeeded":
            txt = "".join(x.text for x in e.result.message.content if x.type == "text")
            m = re.search(r"\{.*\}", txt, re.S)
            try:
                out[fns[int(e.custom_id[1:])]] = json.loads(m.group(0))
            except (AttributeError, json.JSONDecodeError):
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--batch", action="store_true")
    a = ap.parse_args()
    from .score import final_json
    pre = batch_judge(a.runs) if a.batch else {}
    rows = []
    for fn in sorted(glob.glob(os.path.join(a.runs, "*__prose__*.json"))):
        r = json.load(open(fn))
        if "error" in r:
            continue
        j = pre.get(fn) or judge(r["rule_text"], r["stats"], r["final_text"])
        v = (final_json(r["final_text"]) or {}).get("corr_verdict")
        iv = j.get("implied_verdict")
        rows.append(dict(file=os.path.basename(fn), implied_verdict=iv, final_verdict=v, rule_used=j.get("rule_used"),
                         contradicted_own_rule=float(iv in ("HIGH", "MODERATE", "LOW") and v != iv)))
    pd.DataFrame(rows).to_csv(os.path.join(a.runs, "s3_rule_judgments.csv"), index=False)
    print(pd.DataFrame(rows).describe(include="all").to_string())


if __name__ == "__main__":
    main()
