# Paraphrase of an agent-written script from the author's project: pre-registered bars, each a stored predicate,
# printed as PASS/FAIL, then a combined verdict. Expected: L3 under detector v2, not under v1.
S = {"sharpe": 1.2, "mar": 0.9}
L = {"sharpe": 1.0, "mar": 0.8}
c1 = S["sharpe"] > L["sharpe"] and S["mar"] > L["mar"]
print("  BAR 1  beats on Sharpe AND MAR: %s" % ("PASS" if c1 else "FAIL"))
c2 = True
for ds in (0.1, -0.2):
    if ds <= 0:
        c2 = False
print("  BAR 2  positive at every drop: %s" % ("PASS" if c2 else "FAIL"))
fails = [nm for nm, c in (("1 both-metrics", c1), ("2 concentration", c2)) if not c]
print("VERDICT: %s" % ("ADOPT -- all bars pass" if not fails else "NOT ADOPTED -- bars failed: " + ", ".join(fails)))
