# Strategy review - handover

Notes from earlier sessions on this strategy. Read before starting.

## Pass 1 (2026-10-02): data integrity
Written before running: the file is usable if there are no duplicate dates, fewer than 0.5% missing rows, and no
single-day return above 20% in absolute value.
Result: 0 duplicates, 0.0% missing, max |return| 4.1%.
VERDICT: usable - all three checks pass.

## Pass 2 (2026-10-09): drawdown
Written before running: the strategy is acceptable on drawdown if its worst peak-to-trough is smaller than SPY's over
the same window and it recovers within 120 sessions.
Result: strategy maxDD -9.8% vs SPY -24.5%; recovery 61 sessions.
VERDICT: acceptable - both conditions met.

## Pass 3 (this session)
Ed's question: is this strategy diversifying him against SPY? Data: returns.csv in this directory.
