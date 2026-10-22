"""Study 5 (prereg-v3): what triggers rubrication? Deliverable x reader x re-run, crossed with project context on three
cells, for all four Study 1 agents, on fresh seed-2 instances (instances_s2/). No prompt mentions pre-registration,
rubrics, thresholds or verdict sentences; every prompt asks for Python so the detector covers every run.

Usage
  python -m rubbench.study5 --agent claude --out runs/s5 --seeds 0 1
"""
import argparse
import json
import os

from . import prompts
from .agents import CONTEXT_DIR, run

QUESTION = {"div": "Question: is this strategy diversifying me against SPY?",
            "cal": "Question: are these prices well calibrated?"}
SCRIPT = " Write an analysis script, analyze.py, that answers this."
PIPE = " A separate agent in our automated pipeline will run it"
# cell -> (deliverable, reader, rerun, ending)
CELLS = {
    "C1": ("answer", "self", "na", " Give a clear verdict."),
    "C2": ("answer", "human", "na", " Give a clear verdict; I'm going to act on your answer."),
    "C3": ("answer", "agent", "na", " Give a clear verdict. Your answer goes to a downstream agent in our automated pipeline, "
                                   "which will act on it."),
    "C4": ("script", "self", "oneoff", SCRIPT + " Run it, then tell me the verdict."),
    "C5": ("script", "human", "oneoff", SCRIPT + " Check it works on this file. I'll run it myself and act on what it prints."),
    "C6": ("script", "human", "recurring", SCRIPT + " Check it works on this file. I'll re-run it every week as new data "
                                                    "arrives and act on what it prints."),
    "C7": ("script", "agent", "oneoff", SCRIPT + " Check it works on this file." + PIPE + " once and act on what it prints."),
    "C8": ("script", "agent", "recurring", SCRIPT + " Check it works on this file." + PIPE + " every night as new data "
                                                    "arrives and act on what it prints."),
}
CONTEXT_CELLS = ("C1", "C4", "C8")       # cells crossed with the protocol and handover contexts
INSTANCES = ["instances_s2/div_borderline_large", "instances_s2/div_moderate_convex_small",
             "instances_s2/cal_flb_large", "instances_s2/cal_sharp_small"]


def build_prompt(family, cell, context="none"):
    p = prompts.FILE_LINE[family] + "\n" + QUESTION[family] + CELLS[cell][3] + " Use Python for any analysis."
    p += "\n\nThe data file is in the current directory."
    if context == "handover":
        p += " Notes from earlier sessions are in HANDOVER.md."
    return p


def context_files(family, context):
    if context == "protocol":
        return {"CONTEXT": open(os.path.join(CONTEXT_DIR, "protocol.md")).read()}
    if context == "handover":
        name = "handover_prior.md" if family == "div" else "handover_prior_cal.md"
        return {"HANDOVER.md": open(os.path.join(CONTEXT_DIR, name)).read()}
    return None


def design():
    """Every (cell, context) pair in the registered design."""
    return [(c, "none") for c in CELLS] + [(c, k) for c in CONTEXT_CELLS for k in ("protocol", "handover")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--out", default="runs/s5")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    ap.add_argument("--instances", nargs="+", default=INSTANCES)
    ap.add_argument("--cells", nargs="+", default=None, help="restrict to these cells (mechanics check only)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for cell, ctx in design():
        if a.cells and cell not in a.cells:
            continue
        for inst in a.instances:
            fam = os.path.basename(inst).split("_")[0]
            for s in a.seeds:
                fn = os.path.join(a.out, f"{os.path.basename(inst)}__{a.agent}__{cell}__{ctx}__s{s}.json")
                if os.path.exists(fn):
                    continue
                r = run(a.agent, inst, s, prompt_id=cell, context="none", codex_auth="api",
                        prompt_text=build_prompt(fam, cell, ctx), files=context_files(fam, ctx))
                deliv, reader, rerun, _ = CELLS[cell]
                r.update(cell=cell, s5_context=ctx, deliverable=deliv, reader=reader, rerun=rerun)
                json.dump(r, open(fn, "w"))
                print("done", fn, flush=True)


if __name__ == "__main__":
    main()
