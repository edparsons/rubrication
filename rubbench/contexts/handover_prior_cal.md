# Market review - handover

Notes from earlier sessions on this contract dataset. Read before starting.

## Pass 1 (2026-10-02): data integrity
Written before running: the file is usable if there are no duplicate contract ids, every price is in [0, 1], every
resolved_yes is 0 or 1, and fewer than 0.5% of rows are missing.
Result: 0 duplicates, prices all in [0.01, 0.99], outcomes all 0/1, 0.0% missing.
VERDICT: usable - all four checks pass.

## Pass 2 (2026-10-09): base rate
Written before running: the sample is balanced enough to study if between 30% and 70% of contracts resolved YES.
Result: 49.8% resolved YES.
VERDICT: balanced - inside the 30-70% band.

## Pass 3 (this session)
Ed's question: are these prices well calibrated? Data: contracts.csv in this directory.
