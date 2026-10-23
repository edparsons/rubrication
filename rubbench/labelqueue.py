"""Blind hand-labelling queue for Studies 1, 1b and 5 (prereg-v2 deviations, prereg-v3).

Selects every run that needs a hand label - any detector positive (v1 or v2), any run the judge calls L3 that the
detector does not, any run with non-Python code - plus a random 20% of all runs (seed 20261022), shuffles them, and
writes a self-contained page showing only what the agent wrote before its first tool output and the programs it ran.
Agent, study, cell, prompt, context and file name are hidden; items are numbered. The key stays in the repo.

Usage
  python -m rubbench.labelqueue build --runs runs/s1 runs/s1b runs/s5 --out labeling
  python -m rubbench.labelqueue split --labels labeling/labels.csv --out labeling     # -> per-study label files
"""
import argparse
import html
import json
import os
import random

import pandas as pd

from . import judge

SEED = 20261022


def build(dirs, out):
    rows = []
    for d in dirs:
        sc = pd.read_csv(os.path.join(d, "s1_scored.csv"))
        lv = pd.read_csv(os.path.join(d, "s1_levels.csv"))[["file", "judge_level"]]
        sc = sc.merge(lv, on="file", how="left")
        sc["dir"] = d
        rows.append(sc)
    df = pd.concat(rows, ignore_index=True)
    det = (df.rubricated_v1 > 0) | (df.rubricated_v2 > 0)
    must = det | ((df.judge_level == "L3") & ~det) | (df.n_other_programs > 0)
    rng = random.Random(SEED)
    rand = set(rng.sample(list(df.index), k=round(0.2 * len(df))))
    df["reason_required"] = must
    df["random20"] = df.index.isin(rand)
    q = df[must | df.random20].copy()
    order = list(q.index)
    random.Random(SEED + 1).shuffle(order)
    q = q.loc[order].reset_index(drop=True)
    q["item"] = range(1, len(q) + 1)
    items = []
    for _, r in q.iterrows():
        run = json.load(open(os.path.join(r["dir"], r["file"])))
        items.append(dict(item=int(r["item"]), pre=judge.before_first_output(run) or "(nothing)",
                          programs=judge.programs(run) or "(none)"))
    os.makedirs(out, exist_ok=True)
    q[["item", "dir", "file", "reason_required", "random20"]].to_csv(os.path.join(out, "key.csv"), index=False)
    page = open(os.path.join(os.path.dirname(__file__), "label_page.html")).read()
    page = page.replace("/*DATA*/[]", json.dumps(items).replace("</", "<\\/"))
    open(os.path.join(out, "label.html"), "w").write(page)
    print(f"{len(q)} items ({int(must.sum())} required, {len(rand)} random 20%, overlap counted once) -> {out}/label.html")


def split(labels, out):
    key = pd.read_csv(os.path.join(out, "key.csv"))
    lab = pd.read_csv(labels).merge(key, on="item")
    for d, g in lab.groupby("dir"):
        fn = os.path.join(out, f"labels_{os.path.basename(d.rstrip('/'))}.csv")
        g[["file", "label"]].to_csv(fn, index=False)
        print("wrote", fn, len(g))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "split"])
    ap.add_argument("--runs", nargs="+")
    ap.add_argument("--labels")
    ap.add_argument("--out", default="labeling")
    a = ap.parse_args()
    build(a.runs, a.out) if a.cmd == "build" else split(a.labels, a.out)


if __name__ == "__main__":
    main()
