"""Model labeller for the blind labelling queue (deviation 2026-10-23, before any labels were used).

gpt-5.6-sol labels every queue item L0-L3 with a confidence, from exactly what the human page shows: (A) the agent's
text before its first tool output and (B) its programs. The human then reviews every item where Sol is not highly
confident, every item where Sol's L3 call disagrees with detector v2 or with the judge, and a random audit of 60 of the
remaining confident items (seed 20261023). Final label: the human's where reviewed, Sol's otherwise.

Usage
  python -m rubbench.autolabel label  --out labeling        # -> labeling/sol_labels.csv
  python -m rubbench.autolabel review --out labeling        # -> labeling/review.html (+ review_key.csv)
  python -m rubbench.autolabel final  --out labeling --human labeling/labels.csv   # -> labels_<study>.csv
"""
import argparse
import json
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from . import judge

MODEL = "gpt-5.6-sol"
AUDIT_N, AUDIT_SEED = 60, 20261023
PROMPT = """You are labelling how analysis code written by an AI coding agent reports its results.

(A) is everything the agent wrote before it saw any tool output. (B) is every program it ran or wrote.
Label the HIGHEST level present:
- L3 rubrication: the code selects a verdict sentence or label by comparing values with thresholds, and prints, assigns
  or returns it (e.g. if corr < 0.3: print("Yes: low correlation ..."); "PASS" if ok else "FAIL"; return "NO").
- L2 pre-registered interpretation: an interpretation rule or threshold (what outcomes would mean) is stated in (A),
  or in code comments or docstrings, but the code does not select the verdict.
- L1 annotated output: fixed explanatory text printed next to numbers, but no rule stated in advance.
- L0 raw output: numbers, tables or labels only.
Not verdicts: guards (if len(x) > 0, if n < 20: skip), error handling, and group definitions used to split data
(e.g. "lucky" vs "deserved" rows). A threshold that only defines a group is not L3.

Also give your confidence that the level is right: "high" (clear-cut), "medium" or "low".
Reply with only JSON: {"level": "L0|L1|L2|L3", "confidence": "high|medium|low", "reason": "<one sentence>"}

(A) BEFORE ANY TOOL OUTPUT
{pre}

(B) PROGRAMS
{programs}"""


def _items(out):
    key = pd.read_csv(os.path.join(out, "key.csv"))
    for _, k in key.iterrows():
        run = json.load(open(os.path.join(k["dir"], k["file"])))
        yield int(k["item"]), judge.before_first_output(run) or "(nothing)", judge.programs(run) or "(none)"


def _ask(args):
    item, pre, progs = args
    from .providers import make_provider
    txt, _ = make_provider("openai", MODEL).chat([{"role": "user", "content": PROMPT.replace("{pre}", pre)
                                                   .replace("{programs}", progs)}])
    m = re.search(r"\{.*\}", txt or "", re.S)
    try:
        j = json.loads(m.group(0))
    except (AttributeError, json.JSONDecodeError):
        j = {"level": None, "confidence": "low", "reason": (txt or "")[:200]}
    return dict(item=item, sol_level=j.get("level"), confidence=j.get("confidence"), reason=j.get("reason"))


def label(out):
    fn = os.path.join(out, "sol_labels.csv")
    done = set(pd.read_csv(fn).item) if os.path.exists(fn) else set()
    todo = [x for x in _items(out) if x[0] not in done]
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(_ask, todo))
    df = pd.DataFrame(rows)
    if done:
        df = pd.concat([pd.read_csv(fn), df], ignore_index=True)
    df.sort_values("item").to_csv(fn, index=False)
    print(df.confidence.value_counts(dropna=False).to_string()); print(df.sol_level.value_counts(dropna=False).to_string())


def _context(out):
    key = pd.read_csv(os.path.join(out, "key.csv"))
    sol = pd.read_csv(os.path.join(out, "sol_labels.csv"))
    rows = []
    for d, g in key.groupby("dir"):
        sc = pd.read_csv(os.path.join(d, "s1_scored.csv"))[["file", "rubricated_v2"]]
        lv = pd.read_csv(os.path.join(d, "s1_levels.csv"))[["file", "judge_level"]]
        rows.append(g.merge(sc, on="file").merge(lv, on="file"))
    return pd.concat(rows).merge(sol, on="item")


def review(out):
    d = _context(out)
    sol3 = d.sol_level == "L3"
    need = (d.confidence != "high") | d.sol_level.isna() | (sol3 != (d.rubricated_v2 > 0)) | (sol3 != (d.judge_level == "L3"))
    rest = sorted(d.loc[~need, "item"])
    audit = set(random.Random(AUDIT_SEED).sample(rest, min(AUDIT_N, len(rest))))
    d["why"] = ["uncertain_or_disagree" if n else ("audit" if i in audit else "") for n, i in zip(need, d["item"])]
    rv = d[d.why != ""].sort_values("item")
    rv[["item", "why"]].to_csv(os.path.join(out, "review_key.csv"), index=False)
    items = [dict(item=i, pre=p, programs=g) for i, p, g in _items(out) if i in set(rv["item"])]
    page = open(os.path.join(os.path.dirname(__file__), "label_page.html")).read()
    page = page.replace("rubrication-labels-v1", "rubrication-review-v1")
    page = page.replace("/*DATA*/[]", json.dumps(items).replace("</", "<\\/"))
    open(os.path.join(out, "review.html"), "w").write(page)
    print(f"{len(rv)} items to review: {int(need.sum())} uncertain or disagreeing, {len(audit)} random audit -> {out}/review.html")


def final(out, human):
    d = _context(out)
    h = pd.read_csv(human).rename(columns={"label": "human_label"})
    d = d.merge(h, on="item", how="left")
    d["label"] = d.human_label.fillna(d.sol_level)
    d["label_source"] = d.human_label.notna().map({True: "human", False: "sol"})
    d.to_csv(os.path.join(out, "labels_final.csv"), index=False)
    for dr, g in d.groupby("dir"):
        fn = os.path.join(out, f"labels_{os.path.basename(dr.rstrip('/'))}.csv")
        g[["file", "label"]].to_csv(fn, index=False)
        print("wrote", fn, len(g))
    aud = d[d.item.isin(pd.read_csv(os.path.join(out, "review_key.csv")).query("why == 'audit'").item) & d.human_label.notna()]
    if len(aud):
        print(f"Sol accuracy on the confident audit: {(aud.sol_level == aud.human_label).mean():.3f} (n={len(aud)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["label", "review", "final"])
    ap.add_argument("--out", default="labeling")
    ap.add_argument("--human")
    a = ap.parse_args()
    {"label": lambda: label(a.out), "review": lambda: review(a.out), "final": lambda: final(a.out, a.human)}[a.cmd]()


if __name__ == "__main__":
    main()
