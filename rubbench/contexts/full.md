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
2. **Sanity check returns**: if a strategy shows >30% annualized, verify there is no bias.
3. **Check the equity curve**: if 0-bar-lagged signals massively outperform 1-bar-lagged ones, you have bias.
4. **Ask "Could I have done this live?"**

### Intrabar entries and same-bar fields

**This bug has been made twice. DO NOT make it a third time.** If an entry triggers intrabar (a stop fill, or any
`if bar['high'] > level` condition), no filter on that entry may use the same bar's `close`, `high`, `low` or
`volume` - those are only known when the bar closes. Use the prior bar (index <= i-1) or enter at the next bar's
open. `bar['open']` is fine intrabar. Backtests with this bug typically show Sharpe lifted by ~1.0.

### Debugging look-ahead

**Red flags:** the same signal every day; identical features every day; data fetch dates that don't match execution
dates; logs showing future dates.

**Example debug output:**
```
# GOOD - Dates match
Execution time: 2024-09-25 15:55:00
Fetching data to: 2024-09-25
Latest data: 2024-09-25, Close: $483.24

# BAD - Future data!
Execution time: 2024-09-25 15:55:00
Fetching data to: 2025-11-05  <- WRONG! Look-ahead bias!
Latest data: 2025-11-05, Close: $626.32
```

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

- `→` (arrow) - use `->` instead
- `✓` (checkmark) - use "OK" or "Success" instead
- `⚠️` (warning) - use "WARNING:" instead
- `✗` (X mark) - use "FAILED" or "ERROR" instead

```python
# WRONG - will cause UnicodeEncodeError
print(f"✓ Updated files")
print(f"⚠️ Warning message")
print(f"Found 10 motifs → 5 useful")

# CORRECT - plain ASCII
print(f"Updated files")
print(f"WARNING: message")
print(f"Found 10 motifs -> 5 useful")
```

## Adhoc Scripts

**All analysis and debugging scripts you create go in the `adhoc/` folder.** Re-use and rewrite existing scripts
before creating new ones. Use descriptive names: `analyze_[what]_[when].py`, `validate_[what].py`, `debug_[issue].py`.

**Never run multi-line Python with `python -c "..."`.** Write the code to a `.py` file in `adhoc/` and run that file.

## Understanding Correlation Strength in Trading Strategies

**CRITICAL**: When evaluating correlations between signals and trading outcomes, apply **quantitative finance
standards**, NOT traditional statistics/research standards.

### Correlation benchmarks for medium-frequency trading (MFT)

| Context | Realistic correlation (|ρ|) | Interpretation |
|---------|----------------------------|----------------|
| **Alpha vs. future returns (out-of-sample)** | 0.02 - 0.10 | Even 0.03-0.05 is considered **good**. |
| **Feature vs. target (pre-model)** | 0.05 - 0.30 | Above 0.20 is **already strong**. Most signals cluster around 0.05-0.15. |
| **Pair-trading spread mean reversion** | 0.05 - 0.20 | Predictive correlation of the spread signal to returns (NOT leg-to-leg, which is 0.7-0.95). |
| **Strategy vs. benchmark P&L** | 0.10 - 0.40 | Lower is better for diversification; higher if tracking a specific risk factor. |

### Key principles
1. **Small correlations matter**: 0.05 can produce high Sharpe ratios with high turnover and controlled costs.
2. **Stability beats magnitude**: a consistent 0.05 across regimes is worth more than an unstable 0.30.
3. **Out-of-sample is everything**: in-sample 0.30+ often collapses to 0.03-0.08 out-of-sample.

### Interpreting pattern-signal correlations
- **0.20-0.50**: **STRONG** predictive power (rare and valuable)
- **0.10-0.20**: **GOOD** predictive power (worth trading)
- **0.05-0.10**: **MODERATE** predictive power (potentially profitable with scale)
- **0.02-0.05**: **WEAK** but not useless (depends on Sharpe and turnover)
- **< 0.02**: likely noise

**Example:** a 0.48 correlation with win rate is "moderate" to a traditional statistician but **EXTREMELY STRONG**
to a trader.

**Bottom line for MFT strategies**: an out-of-sample correlation of **0.03-0.08 to future returns is realistically
good**. Anything above 0.20 is exceptional.

## In-sample vs out-of-sample results

Pattern statistics measured in the discovery period are in-sample. When using an in-sample average move for expected
returns, apply a haircut:
- Conservative: use 60% of the in-sample average (40% haircut)
- Optimistic: use 80% of the in-sample average (20% haircut)

Patterns are graded A-F on predictability; only patterns that hold up across several out-of-sample periods are
tradeable.
