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

# Identity runs apart from the world, on its own volume, in its own container.
# The world never mounts it and never holds a token.
IDENTITY_CONTAINER="${IDENTITY_CONTAINER:-og-identity}"
IDENTITY_IMAGE="${IDENTITY_IMAGE:-og-identity:current}"
IDENTITY_VOLUME="${IDENTITY_VOLUME:-og-identity-data}"
IDENTITY_PORT="${IDENTITY_PORT:-5090}"
OG_NETWORK="${OG_NETWORK:-og-net}"

# The world gets the key for redeem/bind/release. Lineage needs the other one,
# which lives here and is never passed into any world container.
IDENTITY_WORLD_KEY="${IDENTITY_WORLD_KEY:-$(cat "$SUPERVISOR_DIR/state/identity-world-key" 2>/dev/null || true)}"
IDENTITY_ADMIN_KEY="${IDENTITY_ADMIN_KEY:-$(cat "$SUPERVISOR_DIR/state/identity-admin-key" 2>/dev/null || true)}"

CANDIDATE_CONTAINER="og-world-candidate"
CANDIDATE_PORT="${CANDIDATE_PORT:-5099}"
GATE_IDENTITY_PORT="${GATE_IDENTITY_PORT:-5098}"

LIVE_BRANCH="${LIVE_BRANCH:-live}"
PROPOSED_BRANCH="${PROPOSED_BRANCH:-proposed}"
GOOD_TAG="${GOOD_TAG:-last-known-good}"

# Read-only access to the world's observation surface. Without it the whole
# /caretaker route stays closed.
CARETAKER_TOKEN="${CARETAKER_TOKEN:-$(cat "$SUPERVISOR_DIR/state/caretaker-token" 2>/dev/null || true)}"

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

ensure_network() {
    docker network inspect "$OG_NETWORK" >/dev/null 2>&1 || docker network create "$OG_NETWORK" >/dev/null
}

# Identity outlives any single world. It is not part of a world deploy, and a
# rollback of the world does not touch it.
ensure_identity() {
    ensure_network

    if [ -z "$IDENTITY_WORLD_KEY" ] || [ -z "$IDENTITY_ADMIN_KEY" ]; then
        fail "identity keys missing; run bin/init-keys.sh"
    fi

    if docker ps --format '{{.Names}}' | grep -qx "$IDENTITY_CONTAINER"; then
        return 0
    fi

    docker image inspect "$IDENTITY_IMAGE" >/dev/null 2>&1 \
        || docker build -q -t "$IDENTITY_IMAGE" "$SUPERVISOR_DIR/identity" >/dev/null \
        || fail "could not build identity"

    remove_container "$IDENTITY_CONTAINER"
    docker run -d --name "$IDENTITY_CONTAINER" \
        --restart unless-stopped \
        --network "$OG_NETWORK" \
        -p "$IDENTITY_PORT:8090" \
        -v "$IDENTITY_VOLUME:/identity" \
        -e "IDENTITY_WORLD_KEY=$IDENTITY_WORLD_KEY" \
        -e "IDENTITY_ADMIN_KEY=$IDENTITY_ADMIN_KEY" \
        --memory 256m --pids-limit 128 \
        "$IDENTITY_IMAGE" >/dev/null || fail "could not start identity"

    local waited=0
    while [ "$waited" -lt 30 ]; do
        curl -fsS "http://localhost:$IDENTITY_PORT/health" >/dev/null 2>&1 && return 0
        sleep 1
        waited=$((waited + 1))
    done

    fail "identity never became healthy"
}
