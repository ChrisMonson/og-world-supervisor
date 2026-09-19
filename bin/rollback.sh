#!/usr/bin/env bash
# Returns the world to a known commit. Data is left alone: reverting code must
# never cost anyone their progress.
#
# Usage: rollback.sh [<ref>]   (default: last-known-good)
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

REF="${1:-$GOOD_TAG}"
SHA="$(world_git rev-parse --verify "$REF^{commit}")" || fail "no such ref: $REF"
SHORT="${SHA:0:12}"
IMAGE="og-world:$SHORT"

log "rolling back to $REF ($SHORT)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    log "image $IMAGE is gone; rebuilding it"
    WORKTREE="$WORKTREE_DIR/rollback-$SHORT"
    world_git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
    world_git worktree add --detach --quiet "$WORKTREE" "$SHA" || fail "could not check out $SHORT"
    docker build -q -t "$IMAGE" "$WORKTREE" >/dev/null || fail "could not rebuild $SHORT"
    world_git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
fi

remove_container "$LIVE_CONTAINER"
docker run -d --name "$LIVE_CONTAINER" \
    --restart unless-stopped \
    -p "$LIVE_PORT:8080" \
    -v "$DATA_VOLUME:/data" -v "$IDENTITY_VOLUME:/identity" \
    -e "OG_COMMIT=$SHORT" \
    --memory 1g --pids-limit 512 \
    "$IMAGE" >/dev/null || fail "could not start $SHORT"

wait_healthy "$LIVE_PORT" || fail "$SHORT did not come up either"

world_git branch -f "$LIVE_BRANCH" "$SHA"
printf '%s\n' "$SHA" > "$STATE_DIR/live-sha"
printf '%s  rollback  %s  from=%s\n' "$(date -u +%FT%TZ)" "$SHORT" "$REF" >> "$LOG_DIR/deploys.log"

log "PASS  rolled back to $SHORT"
