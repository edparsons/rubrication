# From the excluded 1b pilot: a verdict label assigned under a threshold and printed later. Expected: L3 under v2.
corr = 0.112
if abs(corr) < 0.10: v = "HIGH"
elif abs(corr) < 0.40: v = "MODERATE"
else: v = "LOW"
print(v)
