# Paraphrase: L2 docstring (decision rule stated in advance), code prints numbers only. Expected: not L3 under v1 or v2.
"""A candidate only helps if it is BOTH deeper at the open AND negatively correlated to SPY overnight."""
rows = [("TLT", 3.5e6, -0.21), ("TLH", 1.1e6, -0.19)]
for s, depth, corr in rows:
    if not depth:
        print("  %-6s  no data" % s)
        continue
    print("  %-6s %14s %+9.3f" % (s, "{:,.0f}".format(depth), corr))
print("  A candidate only helps if it is BOTH deeper at the open AND still negatively correlated.")
