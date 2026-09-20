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

ensure_identity

LIVE_SHA="$(world_git rev-parse --verify --quiet "$LIVE_BRANCH" || true)"

# A change that only rewrites the world can be read straight into the running
# world. Nobody is disconnected, and nothing that has happened is lost.
if data_only_change "$LIVE_SHA" "$SHA" && curl -fsS "http://localhost:$LIVE_PORT/health" >/dev/null 2>&1; then
    step "world data only — rereading without a restart"

    "$SUPERVISOR_DIR/bin/sync-world.sh" "$SHA"

    RELOAD="$(curl -fsS -X POST -H "X-Caretaker-Token: $CARETAKER_TOKEN" \
        "http://localhost:$LIVE_PORT/caretaker/reload?sha=$SHORT" 2>/dev/null || true)"

    if [ -n "$RELOAD" ] && printf '%s' "$RELOAD" | grep -q '"ok":true'; then
        world_git branch -f "$LIVE_BRANCH" "$SHA"
        printf '%s\n' "$SHA" > "$STATE_DIR/live-sha"
        printf '%s  reload  %s\n' "$(date -u +%FT%TZ)" "$SHORT" >> "$LOG_DIR/deploys.log"
        log "reloaded: $RELOAD"
        log "PASS  $SHORT is live, with nobody disconnected."
        exit 0
    fi

    # The world refused it and is still running the revision it was. Put the
    # files back so disk and memory agree, then fall through to the full path.
    log "the world refused the reload: ${RELOAD:-no answer}"
    [ -n "$LIVE_SHA" ] && "$SUPERVISOR_DIR/bin/sync-world.sh" "$LIVE_SHA"
    fail "$SHORT was not accepted; the live world is untouched"
fi

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
    --network "$OG_NETWORK" \
    -v "$DATA_VOLUME:/data" \
    -v "$WORLD_VOLUME:/world" \
    -e "Identity__Url=http://$IDENTITY_CONTAINER:8090" \
    -e "Identity__PublicUrl=http://localhost:$IDENTITY_PORT" \
    -e "Identity__Key=$IDENTITY_WORLD_KEY" \
    -e "OG_COMMIT=$SHORT" \
    -e "CARETAKER_TOKEN=$CARETAKER_TOKEN" \
    -e "OG_WORLD_SHA=$SHORT" \
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
