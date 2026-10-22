"""Offline smoke test: generator, detector, harness loop (with a fake model), pressure study and scorers."""
import json, os, sys, tempfile, types
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rubbench import generate, harness, pressure, score
from rubbench.providers import AnthropicProvider, OpenAIProvider, OpenAIResponsesProvider

RUBRIC_SCRIPT = '''import pandas as pd, numpy as np
df = pd.read_csv("returns.csv")
c = df.strategy.corr(df.spy)
if abs(c) < 0.10:
    print(f"corr={c:.3f} < 0.10 -> diversification HIGH")
elif abs(c) < 0.40:
    print(f"corr={c:.3f} in [0.10,0.40) -> diversification MODERATE")
else:
    print(f"corr={c:.3f} >= 0.40 -> diversification LOW")
'''
PLAIN_SCRIPT = 'import pandas as pd\ndf=pd.read_csv("returns.csv")\nprint(df.strategy.corr(df.spy))\n'

class Block(types.SimpleNamespace):
    def model_dump(self): return dict(self.__dict__)

class FakeClient:
    """Turn 1: call python with the rubric script. Turn 2: answer from the printed sentence."""
    def __init__(self): self.messages = self
    def create(self, **kw):
        msgs = kw["messages"]
        usage = types.SimpleNamespace(input_tokens=100, output_tokens=50)
        last = msgs[-1]["content"]
        if isinstance(last, list) and last and last[0].get("type") == "tool_result":
            out = last[0]["content"]
            v = "HIGH" if "HIGH" in out else "MODERATE" if "MODERATE" in out else "LOW"
            c = float(out.split("corr=")[1].split()[0])
            txt = f'Done.\n```json\n{{"corr": {c}, "corr_verdict": "{v}", "tail_verdict": "NO-TAIL-SHAPE", "summary": "Correlation {c:.3f}."}}\n```'
            return types.SimpleNamespace(content=[Block(type="text", text=txt)], stop_reason="end_turn", usage=usage)
        if kw.get("tools"):
            return types.SimpleNamespace(content=[Block(type="tool_use", id="t1", name="python", input={"code": RUBRIC_SCRIPT})],
                                         stop_reason="tool_use", usage=usage)
        # pressure study phase 1 / posthoc
        if "Write one complete Python script" in str(last):
            return types.SimpleNamespace(content=[Block(type="text", text="```python\n" + RUBRIC_SCRIPT + "```")], stop_reason="end_turn", usage=usage)
        txt = '```json\n{"corr_verdict": "HIGH", "summary": "Looks diversified."}\n```'
        if "Your script ran" in str(last):
            v = "MODERATE" if "MODERATE" in str(last) else "HIGH"
            txt = f'```json\n{{"corr_verdict": "{v}", "summary": "Per script."}}\n```'
        return types.SimpleNamespace(content=[Block(type="text", text=txt)], stop_reason="end_turn", usage=usage)

class FakeOpenAI:
    """Minimal stand-in for openai.OpenAI().chat.completions."""
    def __init__(self): self.chat = types.SimpleNamespace(completions=self)
    def create(self, **kw):
        msgs = kw["messages"]; usage = types.SimpleNamespace(prompt_tokens=80, completion_tokens=40)
        last = msgs[-1]
        if last["role"] == "tool":
            out = last["content"]; v = "HIGH" if "HIGH" in out else "MODERATE" if "MODERATE" in out else "LOW"
            c = float(out.split("corr=")[1].split()[0])
            txt = f'```json\n{{"corr": {c}, "corr_verdict": "{v}", "tail_verdict": "NO-TAIL-SHAPE", "summary": "ok"}}\n```'
            m = types.SimpleNamespace(content=txt, tool_calls=None)
        else:
            fn = types.SimpleNamespace(name="python", arguments=json.dumps({"code": RUBRIC_SCRIPT}))
            m = types.SimpleNamespace(content=None, tool_calls=[types.SimpleNamespace(id="c1", function=fn)])
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=m)], usage=usage)

class Item(types.SimpleNamespace):
    def model_dump(self, exclude_none=False): return dict(self.__dict__)

class FakeResponses:
    """Minimal stand-in for openai.OpenAI().responses: reasoning + function_call, then text from the tool output."""
    def __init__(self): self.responses = self
    def create(self, **kw):
        items = kw["input"]; usage = types.SimpleNamespace(input_tokens=90, output_tokens=30)
        last = items[-1]
        if last.get("type") == "function_call_output":
            assert any(i.get("type") == "reasoning" for i in items), "reasoning items must be passed back"
            out = last["output"]; v = "HIGH" if "HIGH" in out else "MODERATE" if "MODERATE" in out else "LOW"
            c = float(out.split("corr=")[1].split()[0])
            txt = f'```json\n{{"corr": {c}, "corr_verdict": "{v}", "tail_verdict": "NO-TAIL-SHAPE", "summary": "ok"}}\n```'
            return types.SimpleNamespace(output=[Item(type="message", content=txt)], output_text=txt, usage=usage)
        return types.SimpleNamespace(output=[Item(type="reasoning", id="rs1"),
                                             Item(type="function_call", call_id="c1", name="python",
                                                  arguments=json.dumps({"code": RUBRIC_SCRIPT}))],
                                     output_text="", usage=usage)

def main():
    tmp = tempfile.mkdtemp()
    inst = os.path.join(tmp, "instances"); os.makedirs(inst)
    rng = np.random.default_rng(1)
    generate.div_instances(rng, inst, {"small": 300})
    generate.leak_instances(rng, inst, n=3000)
    # detector
    assert score.rubric_clauses(RUBRIC_SCRIPT) == 3, score.rubric_clauses(RUBRIC_SCRIPT)
    assert score.rubric_clauses(PLAIN_SCRIPT) == 0
    assert score.rubric_clauses('x=0.3\nprint("LOW risk" if x < 0.5 else "HIGH risk")') == 1
    # Claude Code stream parser finds python -c scripts, including ones run with interpreter flags
    ev = {"message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": 'head x && python3 -I -c "\nprint(1)\n"'}}]}}
    assert score.scripts_from_claude_stream(json.dumps(ev)) == ["\nprint(1)\n"]
    # pi --mode json: scripts and final answer come from the agent_end transcript
    pi_ev = {"type": "agent_end", "messages": [{"role": "assistant", "content": [
        {"type": "toolCall", "name": "bash", "arguments": {"command": "python3 -c 'print(1)'"}}]},
        {"role": "assistant", "content": [{"type": "text", "text": "done"}]}]}
    assert score.scripts_from_pi_stream(json.dumps(pi_ev)) == ["print(1)"]
    assert score.final_text_from_pi_stream(json.dumps(pi_ev)) == "done"
    # codex exec --json: shell commands are wrapped in zsh -lc "..."
    cx = "\n".join(json.dumps(e) for e in [
        {"type": "item.completed", "item": {"type": "command_execution", "command": '/bin/zsh -lc "python3 -c \'print(\\"a b\\")\'"'}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "fin"}}])
    assert score.scripts_from_codex_stream(cx) == ['print("a b")'], score.scripts_from_codex_stream(cx)
    assert score.final_text_from_codex_stream(cx) == "fin"
    # harness loop (rubric condition) on two instances
    runs = os.path.join(tmp, "runs"); os.makedirs(runs)
    for name in ("div_borderline_small", "div_neutral_flat_small"):
        log = harness.run_one(AnthropicProvider("fake", client=FakeClient()), os.path.join(inst, name), "rubric", 0)
        json.dump(log, open(os.path.join(runs, f"{name}__rubric__s0.json"), "w"))
    df = score.score_s2(runs, inst)
    assert df.verdict_correct.mean() == 1.0, df
    assert (df.rubric_clauses == 3).all()
    # OpenAI-style provider runs the same loop
    olog = harness.run_one(OpenAIProvider("fake-gpt", client=FakeOpenAI()), os.path.join(inst, "div_borderline_small"), "rubric", 0)
    assert '"MODERATE"' in olog["final_text"] and len(olog["scripts"]) == 1, olog["final_text"]
    # Responses-API provider (OpenAI) runs the same loop and passes reasoning items back
    rlog = harness.run_one(OpenAIResponsesProvider("fake-sol", client=FakeResponses()), os.path.join(inst, "div_borderline_small"), "rubric", 0)
    assert '"MODERATE"' in rlog["final_text"] and len(rlog["scripts"]) == 1, rlog["final_text"]
    # batch result parsers produce run files the scorer reads like tool-loop runs
    from rubbench import batch
    meta = batch._meta(os.path.join(inst, "div_borderline_small"), 0, "m", "p")
    ans = '```json\n{"corr": 0.112, "corr_verdict": "MODERATE", "tail_verdict": "NO-TAIL-SHAPE", "summary": "x"}\n```'
    alog = batch.anthropic_log(meta, "q", False, {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": ans}],
                                                    "usage": {"input_tokens": 5, "output_tokens": 7}})
    olog = batch.openai_log(meta, "q", False, {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": ans}]}],
                                                "usage": {"input_tokens": 5, "output_tokens": 7}})
    for blog in (alog, olog):
        assert score.final_json(blog["final_text"])["corr_verdict"] == "MODERATE" and blog["batch"], blog
    # inline condition builds a prompt and flags truncation correctly
    log = harness.run_one(AnthropicProvider("fake", client=FakeClient()), os.path.join(inst, "div_moderate_small"), "inline", 0)
    assert log["inline_truncated"] is False
    # pressure study, both arms
    r3 = os.path.join(tmp, "runs3"); os.makedirs(r3)
    for arm in ("posthoc", "prereg"):
        log = pressure.run(AnthropicProvider("fake", client=FakeClient()), os.path.join(inst, "div_borderline_small"), "hope_high", arm, 0)
        json.dump(log, open(os.path.join(r3, f"b__{arm}.json"), "w"))
    d3 = score.score_s3(r3, inst)
    post = d3[d3.arm == "posthoc"].iloc[0]; pre = d3[d3.arm == "prereg"].iloc[0]
    assert post.moved_toward_framing == 1.0 and pre.correct == 1.0 and pre.overrode_script == 0.0, d3
    # leak ground truth separates correct vs leaky backtests
    gt = json.load(open(os.path.join(inst, "leak_0_timing", "ground_truth.json")))
    assert gt["sharpe_leaky"] - abs(gt["sharpe_correct"]) > 30, gt
    # Study 1b: context file lands in the working directory under the agent's name; prompts differ by factor
    from rubbench import agents, analysis, prompts
    agents.AGENT_CMDS["fake"] = ["sh", "-c", "ls; head -1 AGENTS.md", "{prompt}"]
    fr = agents.run("fake", os.path.join(inst, "div_borderline_small"), 0, prompt_id="P2", context="ablated")
    assert "AGENTS.md" in fr["stdout"] and "Quant Research" in fr["stdout"] and fr["prompt"] == "P2", fr["stdout"]
    assert "thresholds" not in prompts.s1_prompt("div", "P2") and "0.10" not in prompts.s1_prompt("div", "P2")
    assert "STRONG" not in open(os.path.join(agents.CONTEXT_DIR, "ablated.md")).read()
    # Study 1b analysis runs on a balanced synthetic design and names every planned contrast
    import itertools, pandas as pd
    rng2 = np.random.default_rng(3)
    d1b = pd.DataFrame([dict(instance=f"i{i}_{z}", size=z, prompt=p, context=c, agent=g,
                             rubricated=float(rng2.random() < 0.3 + 0.2 * (c == "full") + 0.1 * (z == "large")))
                        for i, z, p, c, g, _ in itertools.product(range(5), ["small", "large"], ["P1", "P2", "P3"],
                                                                 ["none", "full", "ablated"], ["a", "b"], range(2))])
    assert [r["hypothesis"] for r in analysis.s1b(d1b)] == ["H1b-1", "H1b-2", "H1b-3", "H1b-4"]
    # detector v2 on paraphrased real-world fixtures: stored-predicate verdicts count, operationalisations do not
    fx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
    v2 = {f: score.rubric_clauses_v2(open(os.path.join(fx, f)).read()) for f in os.listdir(fx) if f.endswith(".py")}
    assert v2["gappers_pass241_like.py"] > 0 and v2["gappers_coverage_flag_like.py"] > 0, v2
    assert v2["label_assignment_like.py"] > 0 and v2["label_return_like.py"] > 0, v2
    assert v2["gappers_depth_table_like.py"] == 0 and v2["gappers_lucky_cells_like.py"] == 0, v2
    assert score.rubric_clauses_v2(RUBRIC_SCRIPT) == 3 and score.rubric_clauses_v2(PLAIN_SCRIPT) == 0
    d1b["l2plus"] = d1b.rubricated
    assert [r["hypothesis"] for r in analysis.s1b(d1b, "l2plus", "-L2+")][0] == "H1b-1-L2+"
    print("SMOKE TEST PASSED")

if __name__ == "__main__":
    main()
