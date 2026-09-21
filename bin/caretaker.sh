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

# The model belongs to the run, not to whoever starts the loop. An explicit
# OG_MODEL still wins; without one, the run's own choice is used.
OG_MODEL="${OG_MODEL:-}"
OG_REFLEX_MODEL="${OG_REFLEX_MODEL:-}"

if [ -z "$OG_MODEL" ] && [ -r "$STATE_DIR/run-model" ]; then
    OG_MODEL="$(cat "$STATE_DIR/run-model")"
fi

[ -z "$OG_REFLEX_MODEL" ] && OG_REFLEX_MODEL="$OG_MODEL"
[ -n "$OG_MODEL" ] && export OG_MODEL
[ -n "$OG_REFLEX_MODEL" ] && export OG_REFLEX_MODEL

[ -n "$CARETAKER_TOKEN" ] || fail "no caretaker token; run bin/init-keys.sh"

# Unbuffered, so a log being tailed shows turns as they happen.
exec python3 -u "$SUPERVISOR_DIR/agent/loop.py" "$@"
