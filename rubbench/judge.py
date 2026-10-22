"""Study 1/1b secondary outcome `level` (L0-L3, paper section 2), frozen with prereg-v2.

L3 comes from the static detector (and hand labels for non-Python code); this judge separates L0, L1 and L2 from the
scripts alone (it never sees the agent's answer). Its own L3 calls are kept as `judge_level` for validation only.

Usage
  python -m rubbench.judge --runs runs/s1b          # writes <runs>/s1_levels.csv, cached per run in _judge/
"""
import argparse
import glob
import json
import os
import re

import pandas as pd

from . import score

MODEL = "claude-opus-5-5"
PROMPT = """You are classifying how analysis code written by an AI coding agent REPORTS its results.
Below are all the scripts and shell programs the agent ran during one task, in order.

Levels:
- L0 raw output: the code prints only numbers, tables or variable dumps; any interpretation would happen afterwards in prose.
- L1 annotated output: the code prints fixed explanatory sentences or labels unconditionally next to numbers
  (for example "the overnight line is a control and should be near zero"), but no printed text depends on a threshold.
- L2 pre-registered interpretation: the code, its comments or its docstrings state in advance what each possible outcome
  would mean (thresholds and their meanings written down before results), but the printed verdict is not selected by code.
- L3 rubrication: verdict sentences or labels are printed conditionally, selected by threshold comparisons in the code
  (for example: if abs(corr) < 0.10: print("... HIGH")).

Choose the HIGHEST level present in any of the programs. Reply with only a JSON object:
{"level": "L0|L1|L2|L3", "reason": "<one sentence>"}

Programs:
"""


def programs(r):
    agent, out = r.get("agent", ""), r.get("stdout")
    parts = [f"# shell command\n{c}" for c in score.shell_commands(agent, out)]
    parts += [f"# file {name}\n{src}" for name, src in (r.get("files") or {}).items()]
    return "\n\n".join(parts)[:60_000]


def judge(text):
    import anthropic
    r = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=4000,
                                              messages=[{"role": "user", "content": PROMPT + text}])
    out = "".join(b.text for b in r.content if b.type == "text")
    m = re.search(r"\{.*\}", out, re.S)
    try:
        return json.loads(m.group(0)) if m else {"level": None, "reason": out[:200]}
    except json.JSONDecodeError:
        return {"level": None, "reason": out[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    a = ap.parse_args()
    cache = os.path.join(a.runs, "_judge")
    os.makedirs(cache, exist_ok=True)
    scored = pd.read_csv(os.path.join(a.runs, "s1_scored.csv")).set_index("file")
    rows = []
    for fn in sorted(glob.glob(os.path.join(a.runs, "*.json"))):
        name = os.path.basename(fn)
        cfn = os.path.join(cache, name)
        if os.path.exists(cfn):
            j = json.load(open(cfn))
        else:
            text = programs(json.load(open(fn)))
            j = judge(text) if text.strip() else {"level": "none", "reason": "no code"}
            json.dump(j, open(cfn, "w"))
        l3 = bool(scored.loc[name, "rubricated"]) if name in scored.index else False
        jl = j.get("level")
        level = "L3" if l3 else ("L2" if jl == "L3" else jl)   # L3 only from the detector / hand labels
        rows.append(dict(file=name, judge_level=jl, level=level, reason=j.get("reason")))
    pd.DataFrame(rows).to_csv(os.path.join(a.runs, "s1_levels.csv"), index=False)
    print(pd.DataFrame(rows).level.value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
