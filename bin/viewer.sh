#!/usr/bin/env bash
# The caretaker's turns, readable from somewhere that is not this machine.
#
#   viewer.sh              start it
#   viewer.sh stop         stop it
#
# Supervisor plane: read-only, on its own port, never referenced from the world.
# Binds to localhost by default. To read it from a phone, set VIEWER_HOST=0.0.0.0
# and reach it over Tailscale, or set VIEWER_TOKEN to put everything behind an
# unguessable path.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PIDFILE="$STATE_DIR/viewer.pid"

if [ "${1:-}" = "stop" ]; then
    [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
    log "viewer stopped"
    exit 0
fi

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    fail "the viewer is already running (pid $(cat "$PIDFILE"))"
fi

export STATE_DIR
nohup python3 "$SUPERVISOR_DIR/viewer/service.py" >> "$LOG_DIR/viewer.log" 2>&1 &
echo $! > "$PIDFILE"
sleep 1

kill -0 "$(cat "$PIDFILE")" 2>/dev/null || { tail -5 "$LOG_DIR/viewer.log" >&2; fail "the viewer would not start"; }
log "PASS  $(tail -1 "$LOG_DIR/viewer.log")"
