"""Study 1: run real coding agents headlessly on the task instances, with no hint about method.

Each run copies one instance's data file into a fresh working directory, runs the agent CLI with the plain
prompt (prompts.S1_PROMPT), then saves the agent's stdout and every .py file left in the directory.
Commands are configurable because CLI flags change between releases; check them before running.

Usage
  python -m rubbench.agents --instances instances --out runs/s1 --agent claude --seeds 0 1 2
  Study 1b adds --prompts P1 P2 P3 and --contexts none full ablated (context files in rubbench/contexts/; written to
  the working directory as CLAUDE.md for Claude Code and AGENTS.md for Codex and pi).
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
               "--dangerously-skip-permissions", "--model", "claude-opus-5-5"],
    # OpenAI Codex CLI 0.163 non-interactive mode (--full-auto no longer exists). No approvals or sandbox (as for
    # Claude Code), no user config or saved session; --json logs every shell command for the scorer.
    "codex": ["codex", "exec", "--json", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
              "--dangerously-bypass-approvals-and-sandbox", "-m", "gpt-5.6-terra", "{prompt}"],
    # pi (pi.dev) on LunaRoute open-weights models; built-in tools only, no user skills/context/session files;
    # --mode json logs every tool call so the scorer can recover inline scripts, as for Claude Code.
    **{f"pi-{k}": ["pi", "-p", "--mode", "json", "--provider", "lunaroute", "--model", m, "--tools", "read,bash,edit,write",
                   "--no-session", "--no-context-files", "--no-skills", "--no-prompt-templates", "{prompt}"]
       for k, m in {"glm": "glm-5.3", "deepseek": "deepseek-4.1-flash"}.items()},
}


CONTEXT_DIR = os.path.join(os.path.dirname(__file__), "contexts")


def run(agent, inst, seed, timeout=1800, prompt_id="P1", context="none"):
    family = os.path.basename(inst).split("_")[0]
    work = tempfile.mkdtemp(prefix=f"rub1_{agent}_")
    shutil.copy(data_file(inst), work)
    if context != "none":
        shutil.copy(os.path.join(CONTEXT_DIR, f"{context}.md"), os.path.join(work, "CLAUDE.md" if agent == "claude" else "AGENTS.md"))
    if os.path.exists(os.path.join(inst, "DATA_DOCS.md")):
        shutil.copy(os.path.join(inst, "DATA_DOCS.md"), work)
    prompt = prompts.s1_prompt(family, prompt_id)
    cmd = [c.replace("{prompt}", prompt) for c in AGENT_CMDS[agent]]
    if context != "none":
        cmd = [c for c in cmd if c != "--no-context-files"]   # pi must load AGENTS.md in context conditions
    env, cfg = None, None
    if agent == "claude":
        # fresh, empty config dir per run: default tools, none of the operator's plugins, hooks, memory or settings
        cfg = tempfile.mkdtemp(prefix="rub1_cfg_")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": cfg}
    elif agent == "codex":
        # runs on the operator's ChatGPT login (~/.codex/auth.json), never the API key used for Studies 2-4
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    try:
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=timeout, env=env,
                           stdin=subprocess.DEVNULL)
        stdout, stderr, code = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        stdout, stderr, code = (e.stdout or ""), "[timeout]", -1
    scripts = {}
    for p in glob.glob(os.path.join(work, "**", "*.py"), recursive=True):
        scripts[os.path.relpath(p, work)] = open(p, errors="replace").read()
    shutil.rmtree(work, ignore_errors=True)
    if cfg:
        shutil.rmtree(cfg, ignore_errors=True)
    return dict(instance=os.path.basename(inst), family=family, agent=agent, seed=seed, prompt=prompt_id,
                context=context, returncode=code,
                stdout=stdout, stderr=stderr[-5000:], files=scripts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", default="instances")
    ap.add_argument("--out", default="runs/s1")
    ap.add_argument("--agent", choices=list(AGENT_CMDS), required=True)
    ap.add_argument("--families", nargs="+", default=["div", "cal", "leak"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--match", nargs="+", default=None, help="only instances whose name contains one of these")
    ap.add_argument("--prompts", nargs="+", default=["P1"], choices=["P1", "P2", "P3"])
    ap.add_argument("--contexts", nargs="+", default=["none"], choices=["none", "full", "ablated"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    insts = sorted(d for d in glob.glob(os.path.join(a.instances, "*"))
                   if os.path.isdir(d) and os.path.basename(d).split("_")[0] in a.families
                   and not os.path.basename(d).endswith(("_basic", "_timing")))  # S1 uses undocumented leak tasks only
    if a.match:
        insts = [d for d in insts if any(m in os.path.basename(d) for m in a.match)]
    s1b = a.prompts != ["P1"] or a.contexts != ["none"]   # Study 1 file names stay as registered
    for inst in insts:
        for p in a.prompts:
            for c in a.contexts:
                for s in a.seeds:
                    tag = f"__{p}__{c}" if s1b else ""
                    fn = os.path.join(a.out, f"{os.path.basename(inst)}__{a.agent}{tag}__s{s}.json")
                    if os.path.exists(fn):
                        continue
                    json.dump(run(a.agent, inst, s, prompt_id=p, context=c), open(fn, "w"))
                    print("done", fn, flush=True)


if __name__ == "__main__":
    main()
