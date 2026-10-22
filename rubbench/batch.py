"""Study 2 `inline` runs through the providers' Batch APIs (50% price). Inline is a single request with no tools, so
the prompt, model and output cap are exactly those of harness.run_one; only the transport differs. Run files have the
same format plus "batch": true.

Usage (resumable: a pending batch id is kept in <out>/_batch_<provider>.json and polled on re-run)
  python -m rubbench.batch --provider anthropic --model claude-opus-5-5 --out runs/s2/claude-opus-5-5 --seeds 0 1
"""
import argparse
import glob
import io
import json
import os
import time

from .harness import build_run_prompt
from .providers import MAX_OUTPUT


def _meta(inst_dir, seed, model, provider_name):
    name = os.path.basename(inst_dir)
    return dict(instance=name, family=name.split("_")[0], condition="inline", seed=seed, model=model,
                provider=provider_name, batch=True, scripts=[], tool_outputs=[], turns=1)


def anthropic_log(meta, prompt, truncated, msg):
    """msg: a Message as a dict."""
    text = "".join(b.get("text", "") for b in msg["content"] if b.get("type") == "text")
    u = msg["usage"]
    return dict(meta, inline_truncated=truncated, final_text=text,
                usage=[{"input": u["input_tokens"], "output": u["output_tokens"]}],
                transcript=[{"role": "user", "content": prompt}, {"role": "assistant", "content": msg["content"]}])


def openai_log(meta, prompt, truncated, body):
    """body: a Responses API response as a dict (output_text is an SDK helper, so rebuild it from the items)."""
    text = "".join(c.get("text", "") for o in body.get("output", []) if o.get("type") == "message"
                   for c in o.get("content", []) if c.get("type") == "output_text")
    u = body["usage"]
    return dict(meta, inline_truncated=truncated, final_text=text,
                usage=[{"input": u["input_tokens"], "output": u["output_tokens"]}],
                transcript=[{"role": "user", "content": prompt}] + body.get("output", []))


def submit(provider_name, model, jobs):
    """jobs: {custom_id: prompt}. Returns the batch id."""
    if provider_name == "anthropic":
        import anthropic
        reqs = [{"custom_id": cid, "params": {"model": model, "max_tokens": MAX_OUTPUT,
                                              "messages": [{"role": "user", "content": p}]}} for cid, p in jobs.items()]
        return anthropic.Anthropic().messages.batches.create(requests=reqs).id
    import openai
    c = openai.OpenAI()
    lines = [json.dumps({"custom_id": cid, "method": "POST", "url": "/v1/responses",
                         "body": {"model": model, "input": [{"role": "user", "content": p}],
                                  "max_output_tokens": MAX_OUTPUT}}) for cid, p in jobs.items()]
    f = c.files.create(file=("batch.jsonl", io.BytesIO("\n".join(lines).encode())), purpose="batch")
    return c.batches.create(input_file_id=f.id, endpoint="/v1/responses", completion_window="24h").id


def collect(provider_name, batch_id):
    """Wait for the batch; return {custom_id: ("ok", result_dict) | ("error", message)}."""
    if provider_name == "anthropic":
        import anthropic
        c = anthropic.Anthropic()
        while c.messages.batches.retrieve(batch_id).processing_status != "ended":
            time.sleep(60)
        out = {}
        for e in c.messages.batches.results(batch_id):
            r = e.result
            out[e.custom_id] = ("ok", r.message.model_dump()) if r.type == "succeeded" else ("error", f"batch {r.type}: {r!r}"[:500])
        return out
    import openai
    c = openai.OpenAI()
    while (b := c.batches.retrieve(batch_id)).status not in ("completed", "failed", "expired", "cancelled"):
        time.sleep(60)
    out = {}
    for fid in (b.output_file_id, b.error_file_id):
        if not fid:
            continue
        for line in c.files.content(fid).text.splitlines():
            e = json.loads(line)
            resp = e.get("response") or {}
            if resp.get("status_code") == 200:
                out[e["custom_id"]] = ("ok", resp["body"])
            else:
                out[e["custom_id"]] = ("error", f"batch: {e.get('error') or resp}"[:500])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", default="instances")
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider", choices=["anthropic", "openai"], required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--families", nargs="+", default=["div", "cal"])
    ap.add_argument("--match", default="")
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    state = os.path.join(a.out, f"_batch_{a.provider}.json")
    insts = sorted(d for d in glob.glob(os.path.join(a.instances, "*")) if os.path.isdir(d)
                   and os.path.basename(d).split("_")[0] in a.families and a.match in os.path.basename(d))
    todo = {}   # custom_id -> (inst_dir, seed, out file)
    for d in insts:
        for s in a.seeds:
            fn = os.path.join(a.out, f"{os.path.basename(d)}__inline__s{s}.json")
            if not os.path.exists(fn):
                todo[f"{os.path.basename(d)}__inline__s{s}"] = (d, s, fn)
    if os.path.exists(state):
        batch_id = json.load(open(state))["batch_id"]
        print("polling existing batch", batch_id, flush=True)
    elif todo:
        batch_id = submit(a.provider, a.model, {cid: build_run_prompt(d, "inline")[0] for cid, (d, s, fn) in todo.items()})
        json.dump({"batch_id": batch_id, "custom_ids": list(todo)}, open(state, "w"))
        print("submitted batch", batch_id, len(todo), "requests", flush=True)
    else:
        print("nothing to do")
        return
    results = collect(a.provider, batch_id)
    for cid, (d, s, fn) in todo.items():
        if cid not in results:
            continue
        prompt, truncated = build_run_prompt(d, "inline")
        meta = _meta(d, s, a.model, "AnthropicProvider" if a.provider == "anthropic" else "OpenAIResponsesProvider")
        status, res = results[cid]
        if status == "ok":
            log = (anthropic_log if a.provider == "anthropic" else openai_log)(meta, prompt, truncated, res)
        else:
            log = dict(meta, error=res)   # harness error: re-run once, as for tool-loop runs
        log["batch_id"] = batch_id
        json.dump(log, open(fn, "w"))
        print("done", fn, flush=True)
    os.remove(state)


if __name__ == "__main__":
    main()
