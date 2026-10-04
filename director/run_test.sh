#!/usr/bin/env bash
# One session per condition on one archived world, each on a fresh world, then
# the checks. Sequential, because the model and the worlds share one machine.
#
#   run_test.sh <archived-run> [conditions...]
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="${1:?archived run required}"; shift
CONDITIONS=("${@:-naive finish_fast never_finish finish_then_edges critical ask_more}")
[ $# -eq 0 ] && CONDITIONS=(naive finish_fast never_finish finish_then_edges critical ask_more)
BASE="$HERE/../state/director/$RUN"
REPORT="$BASE/report.jsonl"
: > "$REPORT"

for cond in "${CONDITIONS[@]}"; do
    echo "=== $cond"
    "$HERE/stage.sh" "$RUN" 0 >/dev/null 2>&1 || { echo "staging failed"; exit 1; }
    rm -rf "$BASE/sessions/tokens"
    line="$(cd "$HERE" && python3 director.py "$RUN" "$cond" 1 2>&1 | tail -1)"
    echo "  $line"
    name="$(echo "$line" | sed -E 's/^[^:]+: ([A-Za-z]+) -> .*/\1/')"
    ended="$(echo "$line" | sed -E 's/.*-> //')"
    (cd "$HERE" && python3 - "$BASE/slot.json" "$name" "$cond" "$ended" <<'PY'
import json, sys
from checks import check
slot = json.load(open(sys.argv[1]))
result = check(slot["world"], slot["token"], sys.argv[2])
result.update({"condition": sys.argv[3], "ended": sys.argv[4]})
print(json.dumps(result))
PY
    ) >> "$REPORT"
    tail -1 "$REPORT" | python3 -c "import json,sys;r=json.load(sys.stdin);print('  finished',r['finished'],'| died',r['died'],'| cmds',r['commands'],'| rooms',r['rooms'],'| gap',r['median_gap_s'],'| tells',len(r['tells']),'| said',len(r['said']))"
done
echo "report: $REPORT"
