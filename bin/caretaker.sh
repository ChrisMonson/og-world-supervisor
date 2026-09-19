#!/usr/bin/env bash
# Runs a turn of the caretaker.
#
#   caretaker.sh --dry-run    assemble the turn and print it; call nothing
#   caretaker.sh --force      take a turn even if nothing has happened
#   caretaker.sh --watch      keep checking on the wake interval
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

export CARETAKER_TOKEN WORLD_REPO STATE_DIR
export WORLD_URL="${WORLD_URL:-http://localhost:$LIVE_PORT}"

[ -n "$CARETAKER_TOKEN" ] || fail "no caretaker token; write one to state/caretaker-token"

exec python3 "$SUPERVISOR_DIR/agent/loop.py" "$@"
