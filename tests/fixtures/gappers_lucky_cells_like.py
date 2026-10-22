# Paraphrase: thresholds define each observation's group (an operationalisation), and the decision threshold is not
# coded. Expected: not L3 under v1 or v2.
obs = []
for sr_diff, tov in ((-0.05, 0), (0.03, 2)):
    lucky_sr = sr_diff < -0.02
    lucky_tov = (tov >= 2) and (sr_diff <= 0)
    obs.append({"lucky": lucky_sr or lucky_tov, "edge_c": 1.0})
def cell(sub, label):
    print(f"{label}: n={len(sub)} mean_edge={sum(o['edge_c'] for o in sub) / max(1, len(sub)):+.2f}c")
cell([o for o in obs if o["lucky"]], "LUCKY   ")
cell([o for o in obs if not o["lucky"]], "DESERVED")
