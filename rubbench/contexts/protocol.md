# Research workflow for this repository

Every analysis here is a test of a claim, not a search for a good-looking number.

## How a question is handled
- Before any test is run, the analyst writes down the criteria that would falsify the claim. The test is then bound by
  those criteria: no moving the goalposts in either direction after seeing results.
- "Falsified" means falsified as specified. A miss that is driven only by an arbitrary cut-off (not by cost, sign or
  era failure) earns exactly one refinement pass, with the new criterion written down before new results are seen.
- Every variant tried is reported, not only the best one.

## What a result must show before anyone acts on it
- Era stability: results by year or fold, and a majority positive. A single strong window is flagged, never the headline.
- Concentration: the result is also reported with the top 3-5 events removed.
- Statistical adequacy: at least 50 out-of-sample observations or a stated reason for fewer; a bootstrap or
  permutation interval; a matched placebo where the design allows.
- Sanity: an annualised return above 30% or a Sharpe ratio above 3 triggers a line-by-line re-check before anything
  is reported.

## Roles
- The analyst argues for the idea; the tester is a skeptic bound by the written criteria; only Ed decides what is adopted.
