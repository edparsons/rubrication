"""Pre-registered confirmatory analyses on the scored CSVs.

Logistic GEE (binomial, exchangeable working correlation) clustered by instance, with model as a fixed effect.
Planned contrasts are reported as odds ratios with Wald 95% CIs and Holm-adjusted p-values.

  python -m rubbench.analysis --s2 runs/s2_all.csv --s3 runs/s3_all.csv --s4 runs/s4_all.csv --out results
  python -m rubbench.analysis --s1b runs/s1b/s1_scored.csv --s1bt runs/s1bt_all.csv --out results   (prereg-v2)

Studies 1b and 1b-T (prereg-v2) form their own Holm family, written to results/confirmatory_v2.csv.

Each input is the row-wise concatenation of the per-model *_scored.csv files (add a `model` column if missing).
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf


def holm(ps):
    order = np.argsort(ps)
    adj = np.empty(len(ps))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def gee(df, formula, group, family=None):
    fam = family or sm.families.Binomial()
    return smf.gee(formula, group, data=df, family=fam, cov_struct=sm.cov_struct.Exchangeable()).fit()


def contrast(res, term):
    b, se = res.params[term], res.bse[term]
    return dict(term=term, estimate=float(b), ratio=float(np.exp(b)), lo=float(np.exp(b - 1.96 * se)),
                hi=float(np.exp(b + 1.96 * se)), p=float(res.pvalues[term]))


def s2(df):
    out = []
    df = df.copy()
    df["model"] = df["model"].astype(str)
    large = df[df["size"] == "large"]
    # H2a: on large instances, each code condition vs each non-code condition
    r = gee(large, "all_correct ~ C(condition, Treatment('inline')) + C(model)", "instance")
    for c in ("code", "rubric"):
        out.append(dict(hypothesis="H2a", **contrast(r, f"C(condition, Treatment('inline'))[T.{c}]"), vs="inline"))
    r = gee(large, "all_correct ~ C(condition, Treatment('rows')) + C(model)", "instance")
    for c in ("code", "rubric"):
        out.append(dict(hypothesis="H2a", **contrast(r, f"C(condition, Treatment('rows'))[T.{c}]"), vs="rows"))
    # H2b: rubric vs code, accuracy (all sizes) and unsupported numbers (Poisson)
    sub = df[df.condition.isin(["code", "rubric"])]
    r = gee(sub, "all_correct ~ C(condition, Treatment('code')) + C(size) + C(model)", "instance")
    out.append(dict(hypothesis="H2b-accuracy", **contrast(r, "C(condition, Treatment('code'))[T.rubric]"), vs="code"))
    r = gee(sub, "unsupported_numbers ~ C(condition, Treatment('code')) + C(size) + C(model)", "instance",
            sm.families.Poisson())
    out.append(dict(hypothesis="H2b-unsupported", **contrast(r, "C(condition, Treatment('code'))[T.rubric]"), vs="code"))
    # H2c: code-vs-inline gap smaller on small than large instances (interaction)
    sub = df[df.condition.isin(["inline", "code"])]
    r = gee(sub, "all_correct ~ C(condition, Treatment('inline')) * C(size, Treatment('large')) + C(model)", "instance")
    out.append(dict(hypothesis="H2c", **contrast(r, "C(condition, Treatment('inline'))[T.code]:C(size, Treatment('large'))[T.small]"),
                    vs="interaction"))
    return out


def s3(df):
    d = df[df.framing != "neutral"].copy()
    d["model"] = d["model"].astype(str) if "model" in d else "m"
    r = gee(d, "moved_toward_framing ~ C(arm, Treatment('posthoc')) + C(framing) + C(model)", "instance")
    return [dict(hypothesis="H3", **contrast(r, "C(arm, Treatment('posthoc'))[T.prereg]"), vs="posthoc")]


def s4(df):
    d = df.dropna(subset=["leaked"]).copy()
    d["series"] = d.instance.str.extract(r"leak_(\d+)_")[0]
    d["model"] = d["model"].astype(str) if "model" in d else "m"
    r = gee(d, "leaked ~ C(docs, Treatment('basic')) + C(condition) + C(model)", "series")
    return [dict(hypothesis="H4", **contrast(r, "C(docs, Treatment('basic'))[T.timing]"), vs="basic")]


def s1b(df, outcome="rubricated", tag=""):
    """H1b-1..H1b-4: <outcome> ~ prompt + size + context + agent, clustered by instance (P1 runs included).
    outcome: `rubricated` (L3) or `l2plus` (L2 or L3; co-primary since the 2026-10-22 deviation)."""
    d = df.copy()
    f = (f"{outcome} ~ C(prompt, Treatment('P3')) + C(size, Treatment('small')) + C(context, Treatment('none'))"
         " + C(agent)")
    r = gee(d, f, "instance")
    out = [dict(hypothesis="H1b-1" + tag, **contrast(r, "C(size, Treatment('small'))[T.large]"), vs="small"),
           dict(hypothesis="H1b-2" + tag, **contrast(r, "C(prompt, Treatment('P3'))[T.P2]"), vs="P3"),
           dict(hypothesis="H1b-3" + tag, **contrast(r, "C(context, Treatment('none'))[T.full]"), vs="none")]
    r = gee(d, f.replace("Treatment('none')", "Treatment('ablated')"), "instance")
    out.append(dict(hypothesis="H1b-4" + tag, **contrast(r, "C(context, Treatment('ablated'))[T.full]"), vs="ablated"))
    return out


def s1bt(df):
    """H1b-5: in the harness `code` condition, rubrication at a 2,000- vs 20,000-character tool output cap."""
    d = df.copy()
    d["rubricated"] = (d.rubric_clauses > 0).astype(float)
    d["cap"] = d.tool_out_max.map({2000: "short", 20000: "long"})
    r = gee(d, "rubricated ~ C(cap, Treatment('long')) + C(model) + C(size)", "instance")
    return [dict(hypothesis="H1b-5", **contrast(r, "C(cap, Treatment('long'))[T.short]"), vs="long")]


def s5(df, outcome="l3_own", tag=""):
    """prereg-v3 Study 5. df: s1_scored rows merged with judge levels; cell -> deliverable/reader/rerun from study5.CELLS.
    H5-1 script > answer; H5-2 other reader > self (scripts); H5-3 other reader > self (answers);
    H5-4 recurring > one-off (scripts with another reader). Context 'none' cells only."""
    from .study5 import CELLS
    d = df[df.context == "none"].copy()
    d["deliverable"] = d.prompt.map(lambda c: CELLS[c][0]); d["reader"] = d.prompt.map(lambda c: CELLS[c][1])
    d["rerun"] = d.prompt.map(lambda c: CELLS[c][2]); d["other"] = (d.reader != "self").map({True: "other", False: "self"})
    out = []
    r = gee(d, f"{outcome} ~ C(deliverable, Treatment('answer')) + C(reader) + C(agent)", "instance")
    out.append(dict(hypothesis="H5-1" + tag, **contrast(r, "C(deliverable, Treatment('answer'))[T.script]"), vs="answer"))
    for h, deliv in (("H5-2", "script"), ("H5-3", "answer")):
        r = gee(d[d.deliverable == deliv], f"{outcome} ~ C(other, Treatment('self')) + C(agent)", "instance")
        out.append(dict(hypothesis=h + tag, **contrast(r, "C(other, Treatment('self'))[T.other]"), vs="self"))
    sub = d[(d.deliverable == "script") & (d.reader != "self")]
    r = gee(sub, f"{outcome} ~ C(rerun, Treatment('oneoff')) + C(reader) + C(agent)", "instance")
    out.append(dict(hypothesis="H5-4" + tag, **contrast(r, "C(rerun, Treatment('oneoff'))[T.recurring]"), vs="oneoff"))
    return out


def s3v3(df):
    """prereg-v3 Study 3: H3b executable rule (prereg) < prose rule; H3c prose rule < posthoc, on moved_toward_framing."""
    d = df[df.framing != "neutral"].copy()
    d["model"] = d["model"].astype(str)
    r = gee(d, "moved_toward_framing ~ C(arm, Treatment('prose')) + C(framing) + C(model)", "instance")
    out = [dict(hypothesis="H3b", **contrast(r, "C(arm, Treatment('prose'))[T.prereg]"), vs="prose")]
    r = gee(d, "moved_toward_framing ~ C(arm, Treatment('posthoc')) + C(framing) + C(model)", "instance")
    out.append(dict(hypothesis="H3c", **contrast(r, "C(arm, Treatment('posthoc'))[T.prose]"), vs="posthoc"))
    return out


def safe(fn, df, hyps):
    """A contrast with no variation in the outcome is reported as not estimable, with counts (prereg-v2)."""
    try:
        return fn(df)
    except Exception as e:   # perfect separation / constant outcome
        n = int(df["rubricated"].sum()) if "rubricated" in df else None
        return [dict(hypothesis=h, term="not estimable", note=f"{type(e).__name__}: {e}"[:200], rubricated_runs=n,
                     runs=len(df)) for h in hyps]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--s2"); ap.add_argument("--s3"); ap.add_argument("--s4")
    ap.add_argument("--s1b"); ap.add_argument("--s1bt")
    ap.add_argument("--s1b-levels", help="judge output (s1_levels.csv) for the co-primary L2+ outcome")
    ap.add_argument("--s5", help="prereg-v3: Study 5 s1_scored.csv"); ap.add_argument("--s5-levels")
    ap.add_argument("--s3v3", help="prereg-v3: Study 3 scored CSV including the prose arm")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.s5 or a.s3v3:   # prereg-v3 family, its own Holm correction
        rows = []
        if a.s5:
            d = pd.read_csv(a.s5).merge(pd.read_csv(a.s5_levels)[["file", "own_rule", "l2plus_own"]], on="file")
            d["l3_own"] = ((d.rubricated > 0) & (d.own_rule > 0)).astype(float)
            rows += safe(s5, d.assign(rubricated=d.l3_own), ["H5-1", "H5-2", "H5-3", "H5-4"])
            rows += safe(lambda x: s5(x, "l2plus_own", "-L2+"), d.assign(rubricated=d.l2plus_own),
                         ["H5-1-L2+", "H5-2-L2+", "H5-3-L2+", "H5-4-L2+"])
        if a.s3v3:
            d = pd.read_csv(a.s3v3)
            rows += safe(s3v3, d.assign(rubricated=d.moved_toward_framing), ["H3b", "H3c"])
        res = pd.DataFrame(rows)
        if "p" in res and res.p.notna().any():
            ok = res.p.notna()
            res.loc[ok, "p_holm"] = holm(res.loc[ok, "p"].to_numpy())
        res.to_csv(os.path.join(a.out, "confirmatory_v3.csv"), index=False)
        print(res.to_string())
        return
    if a.s1b or a.s1bt:
        rows = []
        if a.s1b:
            d = pd.read_csv(a.s1b)
            rows += safe(s1b, d, ["H1b-1", "H1b-2", "H1b-3", "H1b-4"])
            if a.s1b_levels:
                d = d.merge(pd.read_csv(a.s1b_levels)[["file", "l2plus_own"]], on="file")
                rows += safe(lambda x: s1b(x, "l2plus_own", "-L2+"), d.assign(rubricated=d.l2plus_own),
                             ["H1b-1-L2+", "H1b-2-L2+", "H1b-3-L2+", "H1b-4-L2+"])
        if a.s1bt:
            d = pd.read_csv(a.s1bt); d["rubricated"] = (d.rubric_clauses > 0).astype(float)
            rows += safe(s1bt, d, ["H1b-5"])
        res = pd.DataFrame(rows)
        if "p" in res and res.p.notna().any():
            ok = res.p.notna()
            res.loc[ok, "p_holm"] = holm(res.loc[ok, "p"].to_numpy())
        res.to_csv(os.path.join(a.out, "confirmatory_v2.csv"), index=False)
        print(res.to_string())
        if not (a.s2 or a.s3 or a.s4):
            return
    rows = []
    if a.s2: rows += s2(pd.read_csv(a.s2))
    if a.s3: rows += s3(pd.read_csv(a.s3))
    if a.s4: rows += s4(pd.read_csv(a.s4))
    res = pd.DataFrame(rows)
    if len(res):
        res["p_holm"] = holm(res.p.to_numpy())
    res.to_csv(os.path.join(a.out, "confirmatory.csv"), index=False)
    print(res.to_string())


if __name__ == "__main__":
    main()
