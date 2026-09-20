#!/usr/bin/env bash
# The caretaker's turns, as an account rather than a stream.
#
#   turns.sh              list them
#   turns.sh last         read the most recent
#   turns.sh <n>          read the nth from the end
#   turns.sh <n> --full   without summarising what it saw
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TURNS="$STATE_DIR/agent/turns"
[ -d "$TURNS" ] || fail "no turns yet"

FILES=()
while IFS= read -r line; do
    FILES+=("$line")
done < <(ls -1 "$TURNS"/*.transcript.jsonl 2>/dev/null | sort)

COUNT="${#FILES[@]}"
[ "$COUNT" -gt 0 ] || fail "no turns yet"

if [ $# -eq 0 ]; then
    echo "the caretaker has taken $COUNT turns:" >&2
    i=0
    while [ "$i" -lt "$COUNT" ]; do
        name="$(basename "${FILES[$i]}" .transcript.jsonl)"
        python3 - "$TURNS/$name.json" "$((COUNT - i))" "$name" <<'PY'
import json, sys
from pathlib import Path

path, index, name = sys.argv[1], sys.argv[2], sys.argv[3]
line = ""

if Path(path).exists():
    record = json.loads(Path(path).read_text())
    first = (record["text"].strip().splitlines() or [""])[0]
    line = f"{record['elapsed']:>6}s  {first[:92]}"

print(f"  {index:>2}  {name}  {line}")
PY
        i=$((i + 1))
    done
    exit 0
fi

case "$1" in
    last) PICK="${FILES[$((COUNT - 1))]}" ;;
    *[0-9]*) PICK="${FILES[$((COUNT - $1))]}" ;;
    *) fail "give a number, or 'last'" ;;
esac

shift || true
exec python3 "$SUPERVISOR_DIR/agent/render.py" "$PICK" "$@"
