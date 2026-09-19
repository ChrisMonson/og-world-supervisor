#!/usr/bin/env bash
# Leaves a note for the caretaker about the machinery around it: something that
# stepped in, something that was wrong, something it could not have known.
#
# Facts about the substrate only. Not a way to tell it what to do with the world.
#
#   notice.sh "what happened"
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

TEXT="${1:?a notice is required}"
FILE="$STATE_DIR/notices.json"

python3 - "$FILE" "$TEXT" <<'PY'
import json, sys
from datetime import datetime, timezone

path, text = sys.argv[1], sys.argv[2]

try:
    with open(path) as handle:
        notices = json.load(handle)
except (FileNotFoundError, json.JSONDecodeError):
    notices = []

notices.append({
    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "text": text,
    "seen": False,
})

with open(path, "w") as handle:
    json.dump(notices[-20:], handle, indent=2)

print(f"noted ({len(notices)} total)")
PY
