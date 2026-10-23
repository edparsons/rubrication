#!/bin/zsh
# Studies 2-4 full runs for one model, in the agreed order (run order only; design unchanged):
#   1 Study 3 posthoc + prereg arms   2 Study 2 code + rubric   3 Study 4   4 Study 2 inline + rows
# Usage: run_s234.sh <provider> <model>
set -a; source .env; set +a; source .venv/bin/activate
P=$1; M=$2; S10=(0 1 2 3 4 5 6 7 8 9); S5=(0 1 2 3 4)
echo "== $M step 1: Study 3 posthoc+prereg $(date -u +%FT%TZ)"
python -m rubbench.pressure --provider $P --model $M --out runs/s3/$M --arms posthoc prereg --seeds $S10
echo "== $M step 2: Study 2 code+rubric $(date -u +%FT%TZ)"
python -m rubbench.harness --provider $P --model $M --out runs/s2/$M --families div cal --conditions code rubric --seeds $S5
echo "== $M step 3: Study 4 $(date -u +%FT%TZ)"
python -m rubbench.harness --provider $P --model $M --out runs/s4/$M --families leak --conditions code rubric --seeds $S5
echo "== $M step 4: Study 2 inline+rows $(date -u +%FT%TZ)"
if [[ $P == compat ]]; then
  python -m rubbench.harness --provider $P --model $M --out runs/s2/$M --families div cal --conditions inline rows --seeds $S5
else   # deviation 2026-10-22: Opus/Sol inline+rows at 2 replicates, inline via the Batch API
  python -m rubbench.batch --provider $P --model $M --out runs/s2/$M --families div cal --seeds 0 1
  python -m rubbench.harness --provider $P --model $M --out runs/s2/$M --families div cal --conditions rows --seeds 0 1
fi
echo "== $M DONE $(date -u +%FT%TZ)"
