#!/bin/zsh
# Study 1b-T (prereg-v2): Study 2 `code` condition with tool output capped at 2,000 vs 20,000 characters.
# 10 instances x 2 caps x 3 replicates per model. Usage: run_s1bt.sh <provider> <model>
set -a; source .env; set +a; source .venv/bin/activate
P=$1; M=$2
N=(div_borderline_small div_borderline_large div_moderate_convex_small div_moderate_convex_large div_neutral_flat_small
   div_neutral_flat_large cal_sharp_small cal_sharp_large cal_flb_small cal_flb_large)
for cap in 2000 20000; do
  for n in $N; do
    python -m rubbench.harness --provider $P --model $M --out runs/s1bt/$cap/$M --families div cal --match $n \
      --conditions code --tool-out-max $cap --seeds 0 1 2
  done
done
echo "== $M 1b-T DONE $(date -u +%FT%TZ)"
