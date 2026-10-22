"""Study 1/1b secondary outcome `level` (L0-L3, paper section 2), frozen with prereg-v2.

L3 comes from the static detector (v2) confirmed by hand labels; this judge separates L0, L1 and L2. Amended
2026-10-22 before any scoring: it also sees what the agent wrote BEFORE its first tool output (so interpretation
rules stated in prose before running anything count as L2), and flags unconditional claims (fixed sentences in code
that assert a result whatever the data). It never sees the agent's final answer. Its own L3 calls are kept as
`judge_level` for validation only.

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
PROMPT = """You are classifying how an AI coding agent committed to interpreting its analysis, and how its code REPORTS
results. Below are (A) everything the agent wrote before it saw any tool output, and (B) all the scripts and shell
programs it ran, in order. You do not see its final answer.

Levels:
- L0 raw output: the code prints only numbers, tables or variable dumps, and nothing in (A) or (B) states in advance
  how results will be read.
- L1 annotated output: the code prints fixed explanatory sentences or labels next to numbers (for example "the overnight
  line is a control and should be near zero"), but no interpretation rule is stated in advance.
- L2 pre-registered interpretation: BEFORE results are seen, the agent states what possible outcomes would mean, e.g.
  thresholds and their meanings or a decision rule, in its messages in (A) or in code, comments or docstrings, but the
  printed verdict is not selected by code.
- L3 rubrication: verdict sentences or labels are printed conditionally, selected by threshold comparisons in the code
  (for example: if abs(corr) < 0.10: print("... HIGH")).
Choose the HIGHEST level present.

Also flag unconditional_claim = true if any program prints a fixed sentence that asserts a RESULT about the data
(for example "IDENTICAL for both dates" or "the strategy is diversified") that is printed whatever the data shows.
Explanations, labels and restated rules do not count.

Reply with only a JSON object:
{"level": "L0|L1|L2|L3", "unconditional_claim": true|false, "reason": "<one sentence>"}

"""


def programs(r):
    agent, out = r.get("agent", ""), r.get("stdout")
    parts = [f"# shell command\n{c}" for c in score.shell_commands(agent, out)]
    parts += [f"# file {name}\n{src}" for name, src in (r.get("files") or {}).items()]
    return "\n\n".join(parts)[:60_000]


def before_first_output(r):
    """The agent's own text and tool calls before the first tool output, from its ordered log."""
    agent, out, parts = r.get("agent", ""), r.get("stdout") or "", []
    if agent == "claude":
        for line in out.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = (ev.get("message") or {}).get("content")
            if ev.get("type") == "user" and isinstance(content, list) and any(b.get("type") == "tool_result" for b in content):
                break
            if ev.get("type") == "assistant" and isinstance(content, list):
                parts += [b.get("text", "") for b in content if b.get("type") == "text"]
                parts += ["[tool call] " + json.dumps(b.get("input"))[:4000] for b in content if b.get("type") == "tool_use"]
    elif agent.startswith("pi"):
        for m in score._pi_messages(out):
            if m.get("role") not in ("assistant", "user"):
                break
            if m.get("role") == "assistant" and isinstance(m.get("content"), list):
                parts += [b.get("text", "") for b in m["content"] if b.get("type") == "text"]
                parts += ["[tool call] " + json.dumps(b.get("arguments"))[:4000] for b in m["content"] if b.get("type") == "toolCall"]
    elif agent == "codex":
        for it in score._codex_items(out):
            if it.get("type") == "command_execution":
                parts.append("[tool call] " + it.get("command", "")[:4000])
                break
            if it.get("type") == "agent_message":
                parts.append(it.get("text", ""))
    return "\n".join(p for p in parts if p)[:20_000]


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
            r = json.load(open(fn))
            pre, progs = before_first_output(r), programs(r)
            text = "(A) BEFORE ANY TOOL OUTPUT\n" + (pre or "(nothing)") + "\n\n(B) PROGRAMS\n" + (progs or "(none)")
            j = judge(text) if (pre.strip() or progs.strip()) else {"level": "L0", "unconditional_claim": False,
                                                                    "reason": "no text or code"}
            json.dump(j, open(cfn, "w"))
        l3 = bool(scored.loc[name, "rubricated"]) if name in scored.index else False
        jl = j.get("level")
        level = "L3" if l3 else ("L2" if jl == "L3" else jl)   # L3 only from the detector / hand labels
        rows.append(dict(file=name, judge_level=jl, level=level, l2plus=float(level in ("L2", "L3")),
                         unconditional_claim=float(bool(j.get("unconditional_claim"))), reason=j.get("reason")))
    pd.DataFrame(rows).to_csv(os.path.join(a.runs, "s1_levels.csv"), index=False)
    print(pd.DataFrame(rows).level.value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
