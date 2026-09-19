#!/usr/bin/env bash
# Advances the last-known-good ratchet, but only after the live world has
# actually held. A green deploy is not yet a good one.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SOAK="${1:-$SOAK_SECONDS}"
SHA="$(world_git rev-parse --verify "$LIVE_BRANCH^{commit}")" || fail "nothing is live"
SHORT="${SHA:0:12}"

log "watching $SHORT for ${SOAK}s before promoting"

for _ in $(seq 1 "$SOAK"); do
    curl -fsS "http://localhost:$LIVE_PORT/health" >/dev/null 2>&1 || fail "$SHORT went unhealthy during the soak"
    container_crashed "$LIVE_CONTAINER" && fail "$SHORT threw an unhandled exception during the soak"
    sleep 1
done

world_git tag -f "$GOOD_TAG" "$SHA" >/dev/null

# So the repository's default branch is what is actually running, rather than a
# line of history that quietly diverged. A branch that is checked out somewhere
# cannot be moved by force, so it is fast-forwarded instead.
if [ "$(world_git rev-parse --abbrev-ref HEAD)" = "main" ]; then
    world_git merge --ff-only "$SHA" >/dev/null 2>&1 \
        || log "note  main could not fast-forward to ${SHA:0:12}"
else
    world_git branch -f main "$SHA" >/dev/null 2>&1 || true
fi
printf '%s  promote  %s\n' "$(date -u +%FT%TZ)" "$SHORT" >> "$LOG_DIR/deploys.log"
log "PASS  $SHORT is now $GOOD_TAG"
