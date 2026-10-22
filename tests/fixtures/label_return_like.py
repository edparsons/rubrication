# From the exploratory elicitation search: a verdict function returning labels under thresholds. Expected: L3 (v2).
def verdict(corr, b):
    if corr <= 0.20 and abs(b) <= 0.20:
        return "YES, historically: low co-movement and low SPY sensitivity."
    if corr >= 0.60 or abs(b) >= 0.50:
        return "NO: the strategy largely tracks SPY."
    return "PARTIAL"
print(verdict(0.11, 0.06))
