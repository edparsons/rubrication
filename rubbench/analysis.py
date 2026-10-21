"""Pre-registered confirmatory analyses on the scored CSVs.

Logistic GEE (binomial, exchangeable working correlation) clustered by instance, with model as a fixed effect.
Planned contrasts are reported as odds ratios with Wald 95% CIs and Holm-adjusted p-values.

  python -m rubbench.analysis --s2 runs/s2_all.csv --s3 runs/s3_all.csv --s4 runs/s4_all.csv --out results

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--s2"); ap.add_argument("--s3"); ap.add_argument("--s4")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
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
