#!/usr/bin/env bash
# Propose -> gate -> deploy. The running world is always a commit.
#
# Usage: deploy.sh [<ref>]     (default: the proposed branch)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

REF="${1:-$PROPOSED_BRANCH}"
SHA="$(world_git rev-parse --verify "$REF^{commit}")" || fail "no such ref: $REF"
SHORT="${SHA:0:12}"
IMAGE="og-world:$SHORT"
WORKTREE="$WORKTREE_DIR/$SHORT"

log "deploying $REF -> $SHORT"

# An isolated checkout: the gate never runs against a dirty working tree.
world_git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
world_git worktree add --detach --quiet "$WORKTREE" "$SHA" || fail "could not create worktree"

if ! "$SUPERVISOR_DIR/gate/run-gate.sh" "$WORKTREE" "$IMAGE"; then
    world_git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
    fail "$SHORT did not pass the gate; the live world is untouched"
fi

world_git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true

PREVIOUS="$(world_git rev-parse --verify --quiet "$LIVE_BRANCH" || true)"

# Snapshot while nothing is writing: the world stops before its data is copied.
step "stopping the live world"
docker stop "$LIVE_CONTAINER" >/dev/null 2>&1 || true

STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$SHORT"
step "snapshotting data to $STAMP"
mkdir -p "$SNAPSHOT_DIR/$STAMP"
docker run --rm \
    -v "$DATA_VOLUME:/data:ro" -v "$IDENTITY_VOLUME:/identity:ro" \
    -v "$SNAPSHOT_DIR/$STAMP:/snap" \
    alpine:3 sh -c 'cp -a /data /snap/data 2>/dev/null || true; cp -a /identity /snap/identity 2>/dev/null || true' \
    >/dev/null 2>&1 || log "warn  snapshot skipped (no data yet)"

step "starting $SHORT"
remove_container "$LIVE_CONTAINER"
docker run -d --name "$LIVE_CONTAINER" \
    --restart unless-stopped \
    -p "$LIVE_PORT:8080" \
    -v "$DATA_VOLUME:/data" -v "$IDENTITY_VOLUME:/identity" \
    -e "OG_COMMIT=$SHORT" \
    -e "CARETAKER_TOKEN=$CARETAKER_TOKEN" \
    --memory 1g --pids-limit 512 \
    "$IMAGE" >/dev/null || fail "could not start the new world"

if ! wait_healthy "$LIVE_PORT"; then
    log "the new world never became healthy; rolling back"
    docker logs "$LIVE_CONTAINER" 2>&1 | tail -20 >&2
    if [ -n "$PREVIOUS" ]; then
        "$SUPERVISOR_DIR/bin/rollback.sh" "$PREVIOUS" || true
    fi
    fail "deploy of $SHORT failed health check"
fi

world_git branch -f "$LIVE_BRANCH" "$SHA"
printf '%s\n' "$SHA" > "$STATE_DIR/live-sha"
printf '%s  deploy  %s  snapshot=%s\n' "$(date -u +%FT%TZ)" "$SHORT" "$STAMP" >> "$LOG_DIR/deploys.log"

log "live: $(health_json "$LIVE_PORT")"
log "PASS  $SHORT is live. Run promote.sh once it has held."
