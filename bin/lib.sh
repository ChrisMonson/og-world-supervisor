# Shared settings and helpers for the supervisor.
set -euo pipefail

SUPERVISOR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORLD_REPO="${WORLD_REPO:-$(cd "$SUPERVISOR_DIR/../og-world" && pwd)}"

STATE_DIR="${STATE_DIR:-$SUPERVISOR_DIR/state}"
SNAPSHOT_DIR="${SNAPSHOT_DIR:-$STATE_DIR/snapshots}"
LOG_DIR="${LOG_DIR:-$STATE_DIR/logs}"
WORKTREE_DIR="${WORKTREE_DIR:-$STATE_DIR/worktrees}"

LIVE_CONTAINER="${LIVE_CONTAINER:-og-world}"
LIVE_PORT="${LIVE_PORT:-5080}"
DATA_VOLUME="${DATA_VOLUME:-og-data}"
IDENTITY_VOLUME="${IDENTITY_VOLUME:-og-identity}"

CANDIDATE_CONTAINER="og-world-candidate"
CANDIDATE_PORT="${CANDIDATE_PORT:-5099}"

LIVE_BRANCH="${LIVE_BRANCH:-live}"
PROPOSED_BRANCH="${PROPOSED_BRANCH:-proposed}"
GOOD_TAG="${GOOD_TAG:-last-known-good}"

SOAK_SECONDS="${SOAK_SECONDS:-20}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"

mkdir -p "$STATE_DIR" "$SNAPSHOT_DIR" "$LOG_DIR" "$WORKTREE_DIR"

log()  { printf '%s  %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
fail() { log "FAIL  $*"; exit 1; }
step() { log "----  $*"; }

world_git() { git -C "$WORLD_REPO" "$@"; }

# Waits for a container's /health to answer, or gives up.
wait_healthy() {
    local port="$1" timeout="${2:-$HEALTH_TIMEOUT}" waited=0
    while [ "$waited" -lt "$timeout" ]; do
        if curl -fsS "http://localhost:$port/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 1
}

health_json() { curl -fsS "http://localhost:$1/health" 2>/dev/null || echo '{}'; }

# An unhandled exception is a failure even if the process is somehow still up.
container_crashed() {
    docker logs "$1" 2>&1 | grep -qE "Unhandled exception|Application startup exception"
}

remove_container() { docker rm -f "$1" >/dev/null 2>&1 || true; }
