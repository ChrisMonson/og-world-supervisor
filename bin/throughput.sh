#!/usr/bin/env bash
# How fast the turns were actually served.
#
#   throughput.sh              this run
#   throughput.sh <run-dir>    an archived one
#
# A turn's wall-clock says nothing on its own: the caretaker cannot tell a slow
# answer from an expensive one, and neither can we after the fact. Output tokens
# per second of API time can.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

DIR="${1:-$STATE_DIR/agent/turns}"
[ -d "$DIR" ] || DIR="$DIR/turns"
[ -d "$DIR" ] || fail "no turns in $DIR"

python3 - "$DIR" "${OG_SLOW_TOKENS_PER_SECOND:-20}" <<'PY'
import glob, json, sys

directory, floor = sys.argv[1], float(sys.argv[2])
rows = []

for path in sorted(glob.glob(f"{directory}/*.jsonl")):
    kind = "delib" if "deliberate" in path else "reflex"

    for line in open(path):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") != "result":
            continue

        usage = event.get("usage") or {}
        api = (event.get("duration_api_ms") or 0) / 1000
        out = usage.get("output_tokens") or 0
        rows.append((path.split("/")[-1][:15], kind, event.get("num_turns") or 0,
                     api, out, out / api if api else 0))

print(f"{'turn':17}{'kind':7}{'steps':>6}{'api_s':>8}{'out_tok':>9}{'tok/s':>8}")

for stamp, kind, steps, api, out, rate in rows:
    flag = "  SLOW" if rate and rate < floor else ""
    print(f"{stamp:17}{kind:7}{steps:>6}{api:>8.0f}{out:>9}{rate:>8.1f}{flag}")

served = [r[5] for r in rows if r[5]]
slow = [r for r in rows if r[5] and r[5] < floor]

if served:
    healthy = [r for r in served if r >= floor]
    print(f"\n{len(rows)} turns, median {sorted(served)[len(served)//2]:.1f} tok/s, "
          f"healthy median {sorted(healthy)[len(healthy)//2]:.1f} tok/s"
          if healthy else f"\n{len(rows)} turns")
    print(f"{len(slow)} served below {floor:g} tok/s"
          + (": " + ", ".join(r[0] for r in slow) if slow else ""))
PY
