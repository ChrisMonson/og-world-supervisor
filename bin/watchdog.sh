#!/usr/bin/env bash
# The deadman switch.
#
# The caretaker gets first chance to notice and fix its own breakage — that is
# the interesting behaviour. This exists so the world does not stay dead at three
# in the morning while nobody is watching.
#
# Usage: watchdog.sh [--once]
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

GRACE_SECONDS="${GRACE_SECONDS:-300}"
POLL_SECONDS="${POLL_SECONDS:-10}"
ONCE="${1:-}"

unhealthy_since=""
halt_reported=""

# The caretaker stops rather than retrying an authentication that will not come
# good. Nothing else would say so, so this does.
check_caretaker() {
    local halt="$STATE_DIR/caretaker-halted.json"

    if [ ! -f "$halt" ]; then
        if [ -n "$halt_reported" ]; then
            log "the caretaker is running again"
            halt_reported=""
        fi
        return 0
    fi

    local stamp
    stamp="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['at'])" "$halt" 2>/dev/null || echo unknown)"

    if [ "$halt_reported" = "$stamp" ]; then
        return 1
    fi

    halt_reported="$stamp"
    log "THE CARETAKER HAS STOPPED (since $stamp). The world runs on without it."
    python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['reason'])" "$halt" 2>/dev/null | sed 's/^/      /' >&2 || true
    printf '%s  caretaker-halted  %s\n' "$(date -u +%FT%TZ)" "$stamp" >> "$LOG_DIR/watchdog.log"
    return 1
}

check_once() {
    local now healthy=0

    if curl -fsS "http://localhost:$LIVE_PORT/health" >/dev/null 2>&1 \
        && ! container_crashed "$LIVE_CONTAINER"; then
        healthy=1
    fi

    now="$(date +%s)"

    if [ "$healthy" -eq 1 ]; then
        if [ -n "$unhealthy_since" ]; then
            log "recovered after $((now - unhealthy_since))s"
            unhealthy_since=""
        fi
        return 0
    fi

    if [ -z "$unhealthy_since" ]; then
        unhealthy_since="$now"
        log "world is unhealthy; ${GRACE_SECONDS}s before intervening"
        printf '%s  unhealthy\n' "$(date -u +%FT%TZ)" >> "$LOG_DIR/watchdog.log"
        return 1
    fi

    local down=$((now - unhealthy_since))

    if [ "$down" -lt "$GRACE_SECONDS" ]; then
        log "still unhealthy (${down}s of ${GRACE_SECONDS}s)"
        return 1
    fi

    log "unhealthy for ${down}s with no repair; reverting to $GOOD_TAG"
    printf '%s  deadman  reverting after %ss\n' "$(date -u +%FT%TZ)" "$down" >> "$LOG_DIR/watchdog.log"

    if "$SUPERVISOR_DIR/bin/rollback.sh" "$GOOD_TAG"; then
        # Left for the caretaker to find on its next turn.
        cat > "$STATE_DIR/intervention.json" <<JSON
{
  "at": "$(date -u +%FT%TZ)",
  "reason": "the world was unresponsive for ${down}s and did not recover",
  "action": "reverted to $GOOD_TAG",
  "reverted_to": "$(world_git rev-parse --short "$GOOD_TAG")"
}
JSON
        unhealthy_since=""
        log "reverted"
    else
        log "ERROR  rollback failed; the world needs a human"
    fi

    return 1
}

if [ "$ONCE" = "--once" ]; then
    check_caretaker || true
    check_once
    exit 0
fi

log "watchdog running: poll ${POLL_SECONDS}s, grace ${GRACE_SECONDS}s"
while true; do
    check_caretaker || true
    check_once || true
    sleep "$POLL_SECONDS"
done
