"""Single tool-loop harness used for Studies 2-4, so every condition runs on the same model and scaffolding.

Conditions: inline | rows | code | rubric  (see prompts.CONDITION_PREAMBLE)

Usage
  python -m rubbench.harness --instances instances --out runs/s2 --provider anthropic --model <model-id> \
      --conditions inline rows code rubric --families div cal --seeds 0 1 2

Each run writes runs/.../<instance>__<condition>__s<seed>.json with the full transcript,
every script executed, token usage and the final text. Scoring is separate (score.py).
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from . import prompts

MAX_TURNS = 30
INLINE_MAX_CHARS = 400_000   # ~100k tokens; larger files are truncated and the run is flagged
TOOL_OUT_MAX = 20_000

TOOLS = {
    "python": {
        "name": "python",
        "description": "Run a Python 3 script in the working directory (numpy and pandas installed). Returns stdout and stderr.",
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    },
    "get_rows": {
        "name": "get_rows",
        "description": "Return rows of the data file as JSON records. limit <= 500.",
        "input_schema": {"type": "object", "properties": {"offset": {"type": "integer"}, "limit": {"type": "integer"}},
                         "required": ["offset", "limit"]},
    },
}
COND_TOOLS = {"inline": [], "rows": ["get_rows"], "code": ["python"], "rubric": ["python"]}


def data_file(inst_dir):
    for name in ("returns.csv", "contracts.csv", "bars.csv"):
        p = os.path.join(inst_dir, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(inst_dir)


def run_python(code, workdir, timeout=180):
    path = os.path.join(workdir, f"_script_{int(time.time() * 1000)}.py")
    open(path, "w").write(code)
    try:
        # model-written code runs with a stripped environment: no API keys or tokens are visible to it
        env = {"PATH": os.environ.get("PATH", ""), "HOME": workdir, "LANG": "C.UTF-8"}
        r = subprocess.run([sys.executable, "-I", path], cwd=workdir, capture_output=True, text=True,
                           timeout=timeout, env=env)
        out = (r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr else ""))
    except subprocess.TimeoutExpired:
        out = "[timeout]"
    return out[:TOOL_OUT_MAX]


def get_rows(path, offset, limit):
    import pandas as pd
    limit = max(1, min(int(limit), 500))
    df = pd.read_csv(path, skiprows=range(1, int(offset) + 1), nrows=limit)
    return json.dumps(df.to_dict(orient="records"))[:TOOL_OUT_MAX]


def build_run_prompt(inst_dir, condition):
    """The exact prompt a run sees, and whether inline data was truncated (shared with the batch runner)."""
    family = os.path.basename(inst_dir).split("_")[0]
    src = data_file(inst_dir)
    docs = os.path.join(inst_dir, "DATA_DOCS.md")
    data_text, truncated = None, False
    if condition == "inline":
        raw = open(src).read()
        truncated = len(raw) > INLINE_MAX_CHARS
        data_text = raw[:INLINE_MAX_CHARS] + ("\n[... file truncated: too large for context ...]" if truncated else "")
        if os.path.exists(docs):
            data_text = open(docs).read() + "\n\n" + data_text
    prompt = prompts.build_prompt(family, condition, data_text)
    if condition != "inline" and os.path.exists(docs):
        prompt = "A documentation file DATA_DOCS.md is in the working directory.\n" + prompt
    return prompt, truncated


def run_one(provider, inst_dir, condition, seed):
    family = os.path.basename(inst_dir).split("_")[0]
    src = data_file(inst_dir)
    work = tempfile.mkdtemp(prefix="rub_")
    shutil.copy(src, work)
    docs = os.path.join(inst_dir, "DATA_DOCS.md")
    if os.path.exists(docs):
        shutil.copy(docs, work)
    prompt, truncated = build_run_prompt(inst_dir, condition)

    tools = [TOOLS[t] for t in COND_TOOLS[condition]]
    conv = provider.start(prompt, tools)
    log = dict(instance=os.path.basename(inst_dir), family=family, condition=condition, seed=seed,
               model=provider.model, provider=type(provider).__name__,
               inline_truncated=truncated, tool_out_max=TOOL_OUT_MAX, scripts=[], tool_outputs=[], usage=[], turns=0)
    final_text = ""
    for turn in range(MAX_TURNS):
        t = conv.step()
        log["usage"].append(t.usage)
        log["turns"] = turn + 1
        if t.texts:
            final_text = t.texts[-1]
        results = []
        for cid, name, inp in t.calls:
            if name == "python":
                code = inp.get("code", "")
                out = run_python(code, work)
                log["scripts"].append({"turn": turn, "code": code})
            else:
                out = get_rows(os.path.join(work, os.path.basename(src)), inp.get("offset", 0), inp.get("limit", 500))
            log["tool_outputs"].append({"turn": turn, "tool": name, "output": out})
            results.append((cid, out))
        if t.done or not results:
            break
        conv.add_results(results)
    log["final_text"] = final_text
    log["transcript"] = conv.messages
    shutil.rmtree(work, ignore_errors=True)
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", default="instances")
    ap.add_argument("--out", default="runs/s2")
    ap.add_argument("--provider", choices=["anthropic", "openai", "compat"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--conditions", nargs="+", default=["inline", "rows", "code", "rubric"])
    ap.add_argument("--families", nargs="+", default=["div", "cal"])
    ap.add_argument("--match", default="", help="only instances whose name contains this string")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--tool-out-max", type=int, default=TOOL_OUT_MAX, help="tool output cap in characters (Study 1b-T)")
    a = ap.parse_args()
    globals()["TOOL_OUT_MAX"] = a.tool_out_max
    from .providers import make_provider
    provider = make_provider(a.provider, a.model)
    os.makedirs(a.out, exist_ok=True)
    insts = sorted(d for d in glob.glob(os.path.join(a.instances, "*")) if os.path.isdir(d)
                   and os.path.basename(d).split("_")[0] in a.families and a.match in os.path.basename(d))
    for d in insts:
        for c in a.conditions:
            for s in a.seeds:
                fn = os.path.join(a.out, f"{os.path.basename(d)}__{c}__s{s}.json")
                if os.path.exists(fn):
                    continue
                try:
                    log = run_one(provider, d, c, s)
                except Exception as e:  # record failures rather than silently dropping them
                    log = dict(instance=os.path.basename(d), family=os.path.basename(d).split("_")[0], condition=c,
                               seed=s, model=a.model, error=repr(e))
                json.dump(log, open(fn, "w"))
                print("done", fn, flush=True)


if __name__ == "__main__":
    main()
