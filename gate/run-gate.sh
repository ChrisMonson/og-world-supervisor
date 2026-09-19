#!/usr/bin/env bash
# The health contract. Nothing reaches the live world without passing this.
#
# Usage: run-gate.sh <worktree> <image-tag>
source "$(dirname "${BASH_SOURCE[0]}")/../bin/lib.sh"

WORKTREE="${1:?worktree path required}"
IMAGE="${2:?image tag required}"
GATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
    remove_container "$CANDIDATE_CONTAINER"
    docker volume rm "og-gate-data" "og-gate-identity" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# 1. Migrations may add, never remove ----------------------------------------
step "1/6  migrations are additive only"
python3 "$GATE_DIR/check-migrations.py" "$WORKTREE/migrations" || fail "migration check"

# 2. It builds ----------------------------------------------------------------
step "2/6  the image builds"
docker build -q -t "$IMAGE" "$WORKTREE" >/dev/null || fail "image build"

# 3. Its own tests pass -------------------------------------------------------
# Necessary but not sufficient: these live in the world repo and can be changed
# by whoever proposes the change. The checks that actually gate are ours.
step "3/6  the world's own tests pass"
docker run --rm \
    -v "$WORKTREE:/src" -v "og-nuget:/root/.nuget/packages" \
    -w /src mcr.microsoft.com/dotnet/sdk:10.0 \
    dotnet test --nologo -v q >"$LOG_DIR/gate-tests.log" 2>&1 \
    || { tail -30 "$LOG_DIR/gate-tests.log" >&2; fail "world tests"; }

# 4. It boots, on throwaway data ----------------------------------------------
# A world file with structural errors refuses to start, so this covers validation.
step "4/6  a candidate world boots on empty data"
docker volume rm og-gate-data og-gate-identity >/dev/null 2>&1 || true
remove_container "$CANDIDATE_CONTAINER"

docker run -d --name "$CANDIDATE_CONTAINER" \
    -p "$CANDIDATE_PORT:8080" \
    -v og-gate-data:/data -v og-gate-identity:/identity \
    -e OG_COMMIT=candidate \
    "$IMAGE" >/dev/null || fail "candidate would not start"

wait_healthy "$CANDIDATE_PORT" || {
    docker logs "$CANDIDATE_CONTAINER" 2>&1 | tail -30 >&2
    fail "candidate never became healthy"
}

# 5. It is actually playable ---------------------------------------------------
step "5/6  the world is playable"
python3 "$GATE_DIR/smoke.py" "ws://localhost:$CANDIDATE_PORT/ws" || fail "smoke test"

# 6. It stays up ----------------------------------------------------------------
step "6/6  ${SOAK_SECONDS}s soak with no unhandled exception"
sleep "$SOAK_SECONDS"

container_crashed "$CANDIDATE_CONTAINER" && {
    docker logs "$CANDIDATE_CONTAINER" 2>&1 | grep -A15 "Unhandled exception" | head -25 >&2
    fail "an unhandled exception during soak"
}

curl -fsS "http://localhost:$CANDIDATE_PORT/health" >/dev/null || fail "unhealthy after soak"

log "PASS  gate passed for $IMAGE"
