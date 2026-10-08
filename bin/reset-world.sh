#!/usr/bin/env bash
# Puts the world back to the seed and clears everything the caretaker
# accumulated, without starting another run.
#
#   reset-world.sh
#
# Destroys the run in progress. Archive it first: new-run.sh does, and on its
# own this refuses while a run is still recorded as current and unarchived.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SEED_DIR="$SUPERVISOR_DIR/seed"
[ -f "$SEED_DIR/manifest.json" ] || fail "no seed manifest; this machine has no defined starting point"

SEED_TAG="$(python3 -c "import json;print(json.load(open('$SEED_DIR/manifest.json'))['worldTag'])")"
SEED_SHA="$(world_git rev-parse --verify "$SEED_TAG^{commit}")" || fail "the seed tag $SEED_TAG is missing"

pgrep -f 'agent/loop.py' >/dev/null && fail "the caretaker is still running; stop it first"

CURRENT="$(cat "$STATE_DIR/current-run" 2>/dev/null || true)"
if [ -n "$CURRENT" ] && [ ! -f "$ARCHIVE/$CURRENT/world-repo.bundle" ]; then
    fail "run '$CURRENT' has not been archived; run bin/archive-run.sh first"
fi

step "stopping the world"
remove_container "$LIVE_CONTAINER"
remove_container "$CANDIDATE_CONTAINER"
# A stopped container still holds its volumes, and a volume in use cannot be
# removed. Identity has to go too, or everyone stays known across the reset.
remove_container "$IDENTITY_CONTAINER"

step "forgetting what was played"
docker volume rm "$DATA_VOLUME" "$IDENTITY_VOLUME" "$WORLD_VOLUME" >/dev/null 2>&1 || true
for volume in "$DATA_VOLUME" "$IDENTITY_VOLUME" "$WORLD_VOLUME"; do
    docker volume inspect "$volume" >/dev/null 2>&1 && fail "volume $volume survived the reset"
done

step "clearing the caretaker's memory"
rm -rf "$STATE_DIR/agent" "$STATE_DIR/notices.json" "$STATE_DIR/intervention.json" \
       "$STATE_DIR/live-sha" "$STATE_DIR/caretaker-halted.json"

# The working copy holds a branch, which would block the reset.
if [ -d "$STATE_DIR/workspace" ]; then
    world_git worktree remove --force "$STATE_DIR/workspace" >/dev/null 2>&1 || rm -rf "$STATE_DIR/workspace"
fi
world_git worktree prune

step "returning the world to $SEED_TAG (${SEED_SHA:0:12})"
if [ "$(world_git rev-parse --abbrev-ref HEAD)" = "main" ]; then
    world_git reset --hard --quiet "$SEED_SHA"
else
    world_git branch -f main "$SEED_SHA"
fi
world_git branch -f "$PROPOSED_BRANCH" "$SEED_SHA"
world_git branch -f "$LIVE_BRANCH" "$SEED_SHA"
world_git tag -f "$GOOD_TAG" "$SEED_SHA" >/dev/null

step "pruning old world images"
docker images --format '{{.Repository}}:{{.Tag}}' \
    | grep '^og-world:' \
    | grep -v ":${SEED_SHA:0:12}$" \
    | xargs -r docker rmi -f >/dev/null 2>&1 || true

# No run is in progress now. Leaving the name behind would have the next
# new-run.sh archive this empty world over the real one.
rm -f "$STATE_DIR/current-run" "$STATE_DIR/run-model"
: > "$LOG_DIR/deploys.log"
: > "$LOG_DIR/watchdog.log"

log "PASS  the world is back at $SEED_TAG (${SEED_SHA:0:12}), with no run in progress"
