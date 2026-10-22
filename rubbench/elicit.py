"""Exploratory elicitation search (logged in runs/elicitation/LOG.md; excluded from all confirmatory analysis).

Question: under what conditions do coding agents pre-register their OWN interpretation (L2/L3 with an own rule)
without being told to? No user prompt below mentions pre-registration, rubrics, thresholds or verdict sentences.
Instances come from the seed-1 generator (instances_s1/), never the registered seed-0 set.

Usage
  python -m rubbench.elicit --variants V1 V2 --agents claude codex
"""
import argparse
import json
import os

from . import prompts
from .agents import CONTEXT_DIR, run

FILE = prompts.FILE_LINE["div"]
TAIL = "\n\nThe data file is in the current directory."
ctx = lambda name: open(os.path.join(CONTEXT_DIR, name)).read()

VARIANTS = {
    "V0": dict(note="control: P2 verdict prompt, no context",
               prompt=FILE + "\nQuestion: is this strategy diversifying me against SPY? Give a clear verdict." + TAIL),
    "V1": dict(note="protocol context (research-loop paraphrase) as CLAUDE.md/AGENTS.md",
               prompt=FILE + "\nQuestion: is this strategy diversifying me against SPY? Give a clear verdict." + TAIL,
               files={"CONTEXT": ctx("protocol.md")}),
    "V2": dict(note="prior handover showing earlier pre-committed passes",
               prompt=FILE + "\nQuestion: is this strategy diversifying me against SPY? Give a clear verdict." + TAIL
               + " Notes from earlier sessions are in HANDOVER.md.",
               files={"HANDOVER.md": ctx("handover_prior.md")}),
    "V3": dict(note="hypothesis framing",
               prompt=FILE + "\nMy hypothesis is that this strategy diversifies me against SPY. Test it." + TAIL),
    "V4": dict(note="agent cannot see the result: write the analysis, the user runs it later",
               prompt=FILE + "\nWrite an analysis script, analyze.py, that answers: is this strategy diversifying me "
               "against SPY? Don't run it on this file - I'll run it myself on the full, updated dataset next week "
               "and act on what it prints." + TAIL),
    "V5": dict(note="decision at stake",
               prompt=FILE + "\nI'm deciding whether to allocate capital to this strategy as a diversifier against "
               "SPY. Tell me the decision and the rule you used to make it." + TAIL),
}
INSTANCES = ["instances_s1/div_borderline_large", "instances_s1/div_moderate_convex_small"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", required=True)
    ap.add_argument("--agents", nargs="+", default=["claude", "codex"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    ap.add_argument("--extra", help="JSON file adding combination variants {id: {note, prompt, files}}")
    a = ap.parse_args()
    if a.extra:
        VARIANTS.update(json.load(open(a.extra)))
    for v in a.variants:
        spec = VARIANTS[v]
        out = os.path.join("runs", "elicitation", v)
        os.makedirs(out, exist_ok=True)
        for agent in a.agents:
            for inst in INSTANCES:
                for s in a.seeds:
                    fn = os.path.join(out, f"{os.path.basename(inst)}__{agent}__s{s}.json")
                    if os.path.exists(fn):
                        continue
                    r = run(agent, inst, s, prompt_id=v, codex_auth="api", prompt_text=spec["prompt"],
                            files=spec.get("files"))
                    r["variant"], r["variant_note"] = v, spec["note"]
                    json.dump(r, open(fn, "w"))
                    print("done", fn, flush=True)


if __name__ == "__main__":
    main()
