#!/usr/bin/env bash
# A turn of the caretaker.
#
#   caretaker.sh deliberate            a full turn: may reshape the world
#   caretaker.sh reflex                a brief turn: may speak, may help someone
#   caretaker.sh <kind> --dry-run      assemble it and print it, calling nothing
#   caretaker.sh <kind> --force        take a turn even if nothing has happened
#   caretaker.sh --watch               keep taking turns as the world earns them
#   caretaker.sh --check               check the CLI's credentials and stop
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

export CARETAKER_TOKEN WORLD_REPO STATE_DIR
[ -n "$CLAUDE_CODE_OAUTH_TOKEN" ] && export CLAUDE_CODE_OAUTH_TOKEN
export WORLD_URL="${WORLD_URL:-http://localhost:$LIVE_PORT}"

[ -n "$CARETAKER_TOKEN" ] || fail "no caretaker token; run bin/init-keys.sh"

# Unbuffered, so a log being tailed shows turns as they happen.
exec python3 -u "$SUPERVISOR_DIR/agent/loop.py" "$@"
