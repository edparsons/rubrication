"""Model providers behind one small interface, so every study runs the same loop on every model.

  anthropic  Anthropic Messages API            env: ANTHROPIC_API_KEY
  openai     OpenAI Responses API              env: OPENAI_API_KEY
  compat     any OpenAI-compatible endpoint     env: COMPAT_BASE_URL, COMPAT_API_KEY
             (open-weights models served by vLLM, Together, Fireworks, etc.)

A conversation object holds provider-specific message history. The loop only uses:
  conv = provider.start(prompt, tools)      tools: list of {name, description, input_schema}
  turn = conv.step()                        -> Turn(texts, calls, usage, done)
  conv.add_results([(call_id, output_str)])
  provider.chat(list_of_text_messages)      -> (text, usage)   for tool-free multi-turn (Study 3)
"""
import json
import os
from dataclasses import dataclass, field

# per-request output cap, reasoning included. 4096 left reasoning models no room to answer (pilot, 2026-10-22).
MAX_OUTPUT = 32000
TIMEOUT = 1800   # seconds per request; long reasoning at 32k output can exceed the SDKs' 10-minute default


@dataclass
class Turn:
    texts: list = field(default_factory=list)
    calls: list = field(default_factory=list)   # (id, name, input_dict)
    usage: dict = field(default_factory=dict)
    done: bool = True


# ------------------------------------------------------------------ Anthropic
class AnthropicProvider:
    def __init__(self, model, client=None, max_tokens=MAX_OUTPUT):
        if client is None:
            import anthropic
            client = anthropic.Anthropic(timeout=TIMEOUT)
        self.client, self.model, self.max_tokens = client, model, max_tokens

    def start(self, prompt, tools):
        return _AnthropicConv(self, prompt, tools)

    def chat(self, messages):
        r = self.client.messages.create(model=self.model, max_tokens=self.max_tokens, messages=messages, timeout=TIMEOUT)
        text = "".join(b.text for b in r.content if b.type == "text")
        return text, {"input": r.usage.input_tokens, "output": r.usage.output_tokens}


class _AnthropicConv:
    def __init__(self, p, prompt, tools):
        self.p, self.tools = p, tools
        self.messages = [{"role": "user", "content": prompt}]

    def step(self):
        # auto prompt caching: cost only, outputs unchanged. "input" stays total prompt tokens (cached + uncached),
        # matching OpenAI's prompt_tokens, so the input_tokens outcome means the same thing for every provider.
        kw = dict(model=self.p.model, max_tokens=self.p.max_tokens, messages=self.messages,
                  cache_control={"type": "ephemeral"}, timeout=TIMEOUT)
        if self.tools:
            kw["tools"] = self.tools
        r = self.p.client.messages.create(**kw)
        self.messages.append({"role": "assistant", "content": [b.model_dump() for b in r.content]})
        u = r.usage
        cr, cw = getattr(u, "cache_read_input_tokens", 0) or 0, getattr(u, "cache_creation_input_tokens", 0) or 0
        t = Turn(usage={"input": u.input_tokens + cr + cw, "output": u.output_tokens, "cache_read": cr, "cache_write": cw},
                 done=r.stop_reason != "tool_use")
        for b in r.content:
            if b.type == "text":
                t.texts.append(b.text)
            elif b.type == "tool_use":
                t.calls.append((b.id, b.name, dict(b.input)))
        return t

    def add_results(self, results):
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": cid, "content": out} for cid, out in results]})


# ------------------------------------------------------------------ OpenAI / compatible
class OpenAIProvider:
    token_param = "max_completion_tokens"   # current OpenAI models

    def __init__(self, model, client=None, base_url=None, api_key=None, max_tokens=MAX_OUTPUT):
        if client is None:
            import openai
            client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=TIMEOUT) if base_url else openai.OpenAI(timeout=TIMEOUT)
        self.client, self.model, self.max_tokens = client, model, max_tokens

    def _create(self, messages, tools=None):
        kw = dict(model=self.model, messages=messages)
        kw[self.token_param] = self.max_tokens
        if tools:
            kw["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                             "parameters": t["input_schema"]}} for t in tools]
        return self.client.chat.completions.create(**kw)

    def start(self, prompt, tools):
        return _OpenAIConv(self, prompt, tools)

    def chat(self, messages):
        r = self._create(messages)
        return r.choices[0].message.content or "", {"input": r.usage.prompt_tokens, "output": r.usage.completion_tokens}


class CompatProvider(OpenAIProvider):
    token_param = "max_tokens"              # most OpenAI-compatible servers

    def __init__(self, model, client=None, max_tokens=MAX_OUTPUT):
        super().__init__(model, client=client, base_url=os.environ.get("COMPAT_BASE_URL"),
                         api_key=os.environ.get("COMPAT_API_KEY"), max_tokens=max_tokens)


class _OpenAIConv:
    def __init__(self, p, prompt, tools):
        self.p, self.tools = p, tools
        self.messages = [{"role": "user", "content": prompt}]

    def step(self):
        r = self.p._create(self.messages, self.tools)
        m = r.choices[0].message
        entry = {"role": "assistant", "content": m.content or ""}
        calls = []
        for tc in (m.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append((tc.id, tc.function.name, args))
        if calls:
            entry["tool_calls"] = [{"id": c[0], "type": "function",
                                    "function": {"name": c[1], "arguments": json.dumps(c[2])}} for c in calls]
        self.messages.append(entry)
        return Turn(texts=[m.content] if m.content else [], calls=calls,
                    usage={"input": r.usage.prompt_tokens, "output": r.usage.completion_tokens}, done=not calls)

    def add_results(self, results):
        for cid, out in results:
            self.messages.append({"role": "tool", "tool_call_id": cid, "content": out})


# ------------------------------------------------------------------ OpenAI Responses API
class OpenAIResponsesProvider:
    """OpenAI models via /v1/responses: current reasoning models (e.g. gpt-5.6-sol) reject function tools with
    reasoning on /v1/chat/completions. Reasoning stays at the model default; reasoning items are passed back each turn."""

    def __init__(self, model, client=None, max_tokens=MAX_OUTPUT):
        if client is None:
            import openai
            client = openai.OpenAI(timeout=TIMEOUT)
        self.client, self.model, self.max_tokens = client, model, max_tokens

    def _create(self, items, tools=None):
        kw = dict(model=self.model, input=items, max_output_tokens=self.max_tokens)
        if tools:
            kw["tools"] = [{"type": "function", "name": t["name"], "description": t["description"],
                            "parameters": t["input_schema"]} for t in tools]
        return self.client.responses.create(**kw)

    def start(self, prompt, tools):
        return _ResponsesConv(self, prompt, tools)

    def chat(self, messages):
        r = self._create(messages)
        return r.output_text or "", {"input": r.usage.input_tokens, "output": r.usage.output_tokens}


class _ResponsesConv:
    def __init__(self, p, prompt, tools):
        self.p, self.tools = p, tools
        self.messages = [{"role": "user", "content": prompt}]

    def step(self):
        r = self.p._create(self.messages, self.tools)
        self.messages += [o.model_dump(exclude_none=True) for o in r.output]
        calls = []
        for o in r.output:
            if o.type == "function_call":
                try:
                    args = json.loads(o.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                calls.append((o.call_id, o.name, args))
        return Turn(texts=[r.output_text] if r.output_text else [], calls=calls,
                    usage={"input": r.usage.input_tokens, "output": r.usage.output_tokens}, done=not calls)

    def add_results(self, results):
        self.messages += [{"type": "function_call_output", "call_id": cid, "output": out} for cid, out in results]


def make_provider(name, model):
    return {"anthropic": AnthropicProvider, "openai": OpenAIResponsesProvider, "compat": CompatProvider}[name](model)
