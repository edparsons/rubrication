"""API spend from saved run files (Studies 1-4). Prices are $ per 1M tokens, checked 2026-10-21.

Usage
  python -m rubbench.cost runs/pilot
"""
import glob
import json
import os
import sys
from collections import defaultdict

# input, output, cache read, cache write. gpt-5.6-sol: promo rate to 2026-11-21 (then 5 / 30); harness does not log
# OpenAI cached tokens, so its input is priced uncached (an upper bound). LunaRoute is a flat subscription.
PRICES = {"claude-opus-5-5": (4.0, 20.0, 0.20, 5.0), "gpt-5.6-sol": (4.0, 20.0, 4.0, 4.0)}
SOL_LONG = 272_000   # sol: prompts above this bill 2x input and 1.5x output for the whole request


def request_cost(model, u):
    if model not in PRICES:
        return 0.0
    pi, po, pr, pw = PRICES[model]
    cr, cw = u.get("cache_read", 0), u.get("cache_write", 0)
    if model == "gpt-5.6-sol" and u["input"] > SOL_LONG:
        pi, po = 2 * pi, 1.5 * po
    return ((u["input"] - cr - cw) * pi + cr * pr + cw * pw + u["output"] * po) / 1e6


def run_cost(r):
    if "agent" in r:   # Study 1: Claude Code reports its own cost; pi runs on LunaRoute; codex not priced here
        for line in (r.get("stdout") or "").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                return float(ev.get("total_cost_usd") or 0)
        return 0.0
    return sum(request_cost(r.get("model"), u) for u in r.get("usage", []))


def main(root):
    tot = defaultdict(lambda: [0, 0.0, 0, 0])   # runs, $, input tokens, output tokens
    for fn in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
        r = json.load(open(fn))
        if not isinstance(r, dict):
            continue
        study = os.path.relpath(fn, root).split(os.sep)[0]
        key = (study, r.get("model") or r.get("agent"), r.get("condition") or r.get("arm") or "")
        t = tot[key]
        t[0] += 1
        t[1] += run_cost(r)
        t[2] += sum(u.get("input", 0) for u in r.get("usage", []))
        t[3] += sum(u.get("output", 0) for u in r.get("usage", []))
    print(f"{'study':6} {'model':22} {'cond':8} {'runs':>5} {'$':>9} {'$/run':>7} {'in tok/run':>11} {'out tok/run':>11}")
    for (s, m, c), (n, d, i, o) in sorted(tot.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        print(f"{s:6} {str(m):22} {c:8} {n:5d} {d:9.2f} {d / n:7.3f} {i // n:11,d} {o // n:11,d}")
    print(f"TOTAL ${sum(t[1] for t in tot.values()):.2f} over {sum(t[0] for t in tot.values())} runs")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "runs")
