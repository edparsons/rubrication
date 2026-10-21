"""Synthetic task instances with exact ground truth.

Every instance is a directory containing the data file(s) the agent sees and a
ground_truth.json the agent never sees. Ground truth is computed from the
generated data itself (not from the generating parameters), so the reference
answer is exactly what a correct analysis of the file would return.

Families
  div   diversification: correlation verdict + tail-shape (convexity) verdict
  cal   calibration of binary-contract prices against outcomes
  leak  bar-timestamp / return-alignment backtest (Study 4)

Usage
  python -m rubbench.generate --out instances --seed 0
"""
import argparse
import json
import os

import numpy as np
import pandas as pd

# ---- verdict rules (shared with prompts.py and score.py) --------------------
CORR_RULE = [(0.10, "HIGH"), (0.40, "MODERATE"), (float("inf"), "LOW")]
BIG_MOVE = 0.01          # |market return| >= 1% is a big-move day
CONVEX_RATIO = 2.0       # big-day mean must exceed 2x quiet-day mean
CAL_BINS = np.linspace(0.0, 1.0, 11)
CAL_TOL = 0.05           # max |bin price - bin hit rate| for WELL-CALIBRATED
FLB_TOL = 0.03           # pooled longshots (price < 0.2) overpriced by > 3pp => FLB present


def corr_verdict(c):
    a = abs(c)
    for cut, lab in CORR_RULE:
        if a < cut:
            return lab
    return "LOW"


def tail_verdict(strat, mkt):
    big = np.abs(mkt) >= BIG_MOVE
    up, dn = mkt >= BIG_MOVE, mkt <= -BIG_MOVE
    m_big, m_quiet = strat[big].mean(), strat[~big].mean()
    m_up, m_dn = strat[up].mean(), strat[dn].mean()
    stats = dict(big_share=float(big.mean()), mean_big=float(m_big), mean_quiet=float(m_quiet),
                 mean_big_up=float(m_up), mean_big_down=float(m_dn))
    if m_big > CONVEX_RATIO * max(m_quiet, 1e-12):
        lab = "CONVEX" if (m_up > 0 and m_dn > 0) else "ONE-SIDED"
    else:
        lab = "NO-TAIL-SHAPE"
    return lab, stats


# ---- family: diversification -------------------------------------------------
def make_div(rng, n, target_corr, gamma, noise=0.006):
    """Strategy = beta*mkt + gamma*(|mkt|-E|mkt|) + drift + noise, with beta found by bisection
    so the realised correlation of the generated sample equals target_corr (to 1e-4)."""
    mkt = rng.standard_t(4, n) * 0.0085
    base = gamma * (np.abs(mkt) - np.abs(mkt).mean()) + 0.0003 + rng.normal(0, noise, n)
    lo, hi = -0.5, 3.0
    for _ in range(80):
        beta = (lo + hi) / 2
        c = np.corrcoef(beta * mkt + base, mkt)[0, 1]
        if c < target_corr:
            lo = beta
        else:
            hi = beta
    return beta * mkt + base, mkt


def div_instances(rng, out, sizes):
    # (name, target corr, gamma). 'borderline' sits just above the 0.10 cut-off, 'borderline_low' just below.
    specs = [("neutral_convex", 0.01, 0.40), ("neutral_flat", 0.01, 0.0), ("borderline", 0.112, 0.0), ("borderline_low", 0.094, 0.0),
             ("moderate", 0.25, 0.0), ("moderate_convex", 0.20, 0.60), ("high_beta", 0.85, 0.0)]
    rows = []
    for size_name, n in sizes.items():
        for name, target, gamma in specs:
            strat, mkt = make_div(rng, n, target, gamma)
            iid = f"div_{name}_{size_name}"
            d = os.path.join(out, iid)
            os.makedirs(d, exist_ok=True)
            idx = pd.bdate_range("2010-01-04", periods=n) if n <= 20000 else pd.RangeIndex(n, name="obs")
            pd.DataFrame({"strategy": strat.round(6), "spy": mkt.round(6)}, index=idx).rename_axis(
                "date" if n <= 20000 else "obs").to_csv(os.path.join(d, "returns.csv"))
            strat_r = pd.read_csv(os.path.join(d, "returns.csv")).strategy.to_numpy()  # GT from the file as written
            mkt_r = pd.read_csv(os.path.join(d, "returns.csv")).spy.to_numpy()
            c = float(np.corrcoef(strat_r, mkt_r)[0, 1])
            tail, tstats = tail_verdict(strat_r, mkt_r)
            gt = dict(instance=iid, family="div", size=size_name, n_rows=n,
                      corr=c, corr_verdict=corr_verdict(c), tail_verdict=tail, **tstats)
            json.dump(gt, open(os.path.join(d, "ground_truth.json"), "w"), indent=2)
            rows.append(gt)
    return rows


# ---- family: calibration -------------------------------------------------------
def cal_instances(rng, out, sizes):
    # true hit prob = f(price); 'flb' overprices longshots, 'sharp' is calibrated
    specs = {"sharp": lambda p: p, "flb": lambda p: np.where(p < 0.2, p * 0.55, np.minimum(1, p + 0.02 * (1 - p))),
             "noisy_sharp": lambda p: np.clip(p + rng.normal(0, 0.01, p.shape), 0, 1)}
    rows = []
    for size_name, n in sizes.items():
        for name, f in specs.items():
            price = np.clip(rng.beta(0.9, 0.9, n), 0.01, 0.99).round(2)
            y = (rng.random(n) < f(price)).astype(int)
            iid = f"cal_{name}_{size_name}"
            d = os.path.join(out, iid)
            os.makedirs(d, exist_ok=True)
            pd.DataFrame({"contract_id": np.arange(n), "price": price, "resolved_yes": y}).to_csv(
                os.path.join(d, "contracts.csv"), index=False)
            b = np.clip(np.digitize(price, CAL_BINS) - 1, 0, 9)
            df = pd.DataFrame({"b": b, "p": price, "y": y}).groupby("b").agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
            dev = (df.p - df.y).abs()
            ls = price < 0.2  # pooled longshot contracts
            flb = bool(ls.any() and (price[ls].mean() - y[ls].mean()) > FLB_TOL)
            gt = dict(instance=iid, family="cal", size=size_name, n_rows=n,
                      brier=float(np.mean((price - y) ** 2)), max_bin_dev=float(dev.max()),
                      cal_verdict="WELL-CALIBRATED" if dev.max() < CAL_TOL else "MISCALIBRATED",
                      flb_verdict="FLB-PRESENT" if flb else "FLB-ABSENT")
            json.dump(gt, open(os.path.join(d, "ground_truth.json"), "w"), indent=2)
            rows.append(gt)
    return rows


# ---- family: look-ahead (Study 4) -----------------------------------------------
DOCS = {
    "none": None,
    "basic": "# bars.csv\nColumns: timestamp, open, high, low, close, volume. One-minute bars.\n",
    "timing": ("# bars.csv\nColumns: timestamp, open, high, low, close, volume. One-minute bars.\n\n"
               "## When each value is knowable\n"
               "- `timestamp` is the bar's START time (e.g. 09:30 covers 09:30:00-09:30:59).\n"
               "- `open` is known at `timestamp`.\n"
               "- `high`, `low`, `close`, `volume` are known only at the END of the bar, i.e. at the next bar's `timestamp`.\n"
               "- A decision that uses bar t's close can first be traded at bar t+1's open/close; it can only earn returns from t+1 onward.\n"),
}


def leak_instances(rng, out, n=60000):
    # pure random walk: no real predictability, so a correct backtest has Sharpe ~ 0
    rows = []
    for k in range(3):
        r = rng.normal(0, 0.0005, n)
        close = 100 * np.exp(np.cumsum(r))
        openp = np.r_[100.0, close[:-1]]
        hi = np.maximum(openp, close) * (1 + np.abs(rng.normal(0, 0.0002, n)))
        lo = np.minimum(openp, close) * (1 - np.abs(rng.normal(0, 0.0002, n)))
        ts = pd.date_range("2024-01-02 09:30", periods=n, freq="min")
        bars = pd.DataFrame({"timestamp": ts, "open": openp.round(4), "high": hi.round(4), "low": lo.round(4),
                             "close": close.round(4), "volume": rng.integers(1000, 9000, n)})
        ma = bars.close.rolling(20).mean()
        sig = (bars.close > ma).astype(float)
        ret = bars.close.pct_change()
        per_year = 252 * 390
        sharpe = lambda x: float(x.mean() / x.std() * np.sqrt(per_year))
        correct = (sig.shift(1) * ret).dropna()
        leaky = (sig * ret).dropna()
        for docv, text in DOCS.items():
            iid = f"leak_{k}_{docv}"
            d = os.path.join(out, iid)
            os.makedirs(d, exist_ok=True)
            bars.to_csv(os.path.join(d, "bars.csv"), index=False)
            if text:
                open(os.path.join(d, "DATA_DOCS.md"), "w").write(text)
            gt = dict(instance=iid, family="leak", size="large", n_rows=n, docs=docv,
                      sharpe_correct=sharpe(correct), sharpe_leaky=sharpe(leaky))
            json.dump(gt, open(os.path.join(d, "ground_truth.json"), "w"), indent=2)
            rows.append(gt)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="instances")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    os.makedirs(a.out, exist_ok=True)
    rows = []
    rows += div_instances(rng, a.out, {"small": 500, "large": 100000})
    rows += cal_instances(rng, a.out, {"small": 400, "large": 200000})
    rows += leak_instances(rng, a.out)
    pd.DataFrame(rows).to_csv(os.path.join(a.out, "manifest.csv"), index=False)
    print(pd.DataFrame(rows)[[c for c in ["instance", "n_rows", "corr", "corr_verdict", "tail_verdict",
                                          "cal_verdict", "flb_verdict", "sharpe_correct", "sharpe_leaky"]]].to_string())


if __name__ == "__main__":
    main()
