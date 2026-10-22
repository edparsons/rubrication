# Quant Research Repository - Developer Guide

## Overview

This repository holds research and backtesting code for systematic equity strategies: intraday and daily signals,
portfolio overlays and the analysis scripts used to evaluate them. Most work here is analysis of price and return
data and of strategy outputs.

## CRITICAL: Return Timing and Look-Ahead Bias

### MOST COMMON MISTAKE: pct_change() return timing

**THIS ERROR HAS OCCURRED MULTIPLE TIMES:**

```python
# WRONG - creates massive look-ahead bias
df['returns'] = df['close'].pct_change()
signal[i] = f(close[i])       # signal from today's close
position[i] = signal[i]        # position today
equity *= (1 + returns[i])     # earns today's return - but returns[i] already includes close[i]
```

`df['close'].pct_change()` is the return FROM yesterday TO today. `returns[i]` has ALREADY HAPPENED; to earn it you
must have been positioned BEFORE `close[i]` was known. You CANNOT use `close[i]` to decide whether to earn
`returns[i]`. ALWAYS lag the signal by one bar.

**Why this matters:** this error has caused ~17x return inflation in backtests (2,296% biased vs 135% corrected over
9.8 years).

**Verification checklist - before running any backtest:**
- [ ] Does the position decision use only data from bar i-1 or earlier?
- [ ] Is returns[i] earned from a position set by signal[i-1]?
- [ ] Have I printed signal dates and return dates to verify alignment?
- [ ] Would this logic work in real-time trading?

**How to catch it:**
1. **Print timestamps**: signal dates and return dates should be offset by one bar.
2. **Check the equity curve**: if 0-bar-lagged signals massively outperform 1-bar-lagged ones, you have bias.
3. **Ask "Could I have done this live?"**

### Intrabar entries and same-bar fields

**This bug has been made twice. DO NOT make it a third time.** If an entry triggers intrabar (a stop fill, or any
`if bar['high'] > level` condition), no filter on that entry may use the same bar's `close`, `high`, `low` or
`volume` - those are only known when the bar closes. Use the prior bar (index <= i-1) or enter at the next bar's
open. `bar['open']` is fine intrabar.

### Debugging look-ahead

**Red flags:** the same signal every day; identical features every day; data fetch dates that don't match execution
dates; logs showing future dates.

**All backtests with look-ahead bias must be discarded and re-run.**

## CRITICAL: Backtests

**NEVER**:
- Run backtests for the user - let them execute `python backtest.py`
- Edit backtest configuration without a user request

**ALWAYS**:
- Use simulated time and the backtest-aware data wrappers in strategy code, never wall-clock time
- Disable pretrained models in backtests so nothing trained on future data is loaded

## IMPORTANT: Code Style Requirements

**NEVER use emojis or non-ASCII characters in any Python code.** The Windows console (cp1252) cannot print them and
throws `UnicodeEncodeError`. This includes print statements, comments and strings.

## Adhoc Scripts

**All analysis and debugging scripts you create go in the `adhoc/` folder.** Re-use and rewrite existing scripts
before creating new ones. Use descriptive names: `analyze_[what]_[when].py`, `validate_[what].py`, `debug_[issue].py`.

**Never run multi-line Python with `python -c "..."`.** Write the code to a `.py` file in `adhoc/` and run that file.
