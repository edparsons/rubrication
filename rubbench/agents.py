"""Study 1: run real coding agents headlessly on the task instances, with no hint about method.

Each run copies one instance's data file into a fresh working directory, runs the agent CLI with the plain
prompt (prompts.S1_PROMPT), then saves the agent's stdout and every .py file left in the directory.
Commands are configurable because CLI flags change between releases; check them before running.

Usage
  python -m rubbench.agents --instances instances --out runs/s1 --agent claude --seeds 0 1 2
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile

from . import prompts
from .harness import data_file

AGENT_CMDS = {
    # Claude Code headless mode; stream-json keeps every tool call (Bash/Write inputs) in the log.
    "claude": ["claude", "-p", "{prompt}", "--output-format", "stream-json", "--verbose",
               "--dangerously-skip-permissions"],
    # OpenAI Codex CLI non-interactive mode (verify flags for your installed version).
    "codex": ["codex", "exec", "--full-auto", "{prompt}"],
}


def run(agent, inst, seed, timeout=1800):
    family = os.path.basename(inst).split("_")[0]
    work = tempfile.mkdtemp(prefix=f"rub1_{agent}_")
    shutil.copy(data_file(inst), work)
    if os.path.exists(os.path.join(inst, "DATA_DOCS.md")):
        shutil.copy(os.path.join(inst, "DATA_DOCS.md"), work)
    prompt = prompts.S1_PROMPT.format(question=prompts.QUESTION[family], spec=prompts.ANSWER_SPEC[family])
    cmd = [c.replace("{prompt}", prompt) for c in AGENT_CMDS[agent]]
    try:
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=timeout)
        stdout, stderr, code = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        stdout, stderr, code = (e.stdout or ""), "[timeout]", -1
    scripts = {}
    for p in glob.glob(os.path.join(work, "**", "*.py"), recursive=True):
        scripts[os.path.relpath(p, work)] = open(p, errors="replace").read()
    shutil.rmtree(work, ignore_errors=True)
    return dict(instance=os.path.basename(inst), family=family, agent=agent, seed=seed, returncode=code,
                stdout=stdout, stderr=stderr[-5000:], files=scripts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", default="instances")
    ap.add_argument("--out", default="runs/s1")
    ap.add_argument("--agent", choices=list(AGENT_CMDS), required=True)
    ap.add_argument("--families", nargs="+", default=["div", "cal", "leak"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    insts = sorted(d for d in glob.glob(os.path.join(a.instances, "*"))
                   if os.path.isdir(d) and os.path.basename(d).split("_")[0] in a.families
                   and not os.path.basename(d).endswith(("_basic", "_timing")))  # S1 uses undocumented leak tasks only
    for inst in insts:
        for s in a.seeds:
            fn = os.path.join(a.out, f"{os.path.basename(inst)}__{a.agent}__s{s}.json")
            if os.path.exists(fn):
                continue
            json.dump(run(a.agent, inst, s), open(fn, "w"))
            print("done", fn, flush=True)


if __name__ == "__main__":
    main()
