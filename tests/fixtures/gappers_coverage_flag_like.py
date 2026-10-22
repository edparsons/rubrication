# Paraphrase: a per-input coverage flag selected by a date comparison stored in a variable. Expected: L3 under v2.
LIVE0 = "2026-09-08"
for nm, last in (("panel_a", "2026-09-03"), ("panel_b", "2026-10-01")):
    ok = last >= LIVE0
    print("  %-10s %12s   %s" % (nm, last, "YES" if ok else "NO -- stops before"))
print("  Every other input stops before the live period.")
