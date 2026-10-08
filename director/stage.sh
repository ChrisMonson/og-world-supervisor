#!/usr/bin/env bash
# Stands an archived world back up, isolated, so a director can play in it.
#
#   stage.sh <archived-run> <slot>      start it   (slot 0-9 picks the ports)
#   stage.sh stop <slot>                take it down
#
# The engine is built from the commit that was live when the run ended, not
# from the seed: genesis runs rewrote the engine, and a world file read by an
# engine it was not written for does not behave the way its players met it.
# The world files are the ones the run left on its volume. The data is fresh,
# so every director session starts from the world as authored rather than as
# its last visitors left it.
#
# Nothing here touches the live world, its identity, or any run's records.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../bin/lib.sh"

if [ "${1:-}" = "stop" ]; then
    SLOT="${2:?slot required}"
    docker rm -f "og-director-world-$SLOT" "og-director-identity-$SLOT" >/dev/null 2>&1 || true
    docker network rm "og-director-net-$SLOT" >/dev/null 2>&1 || true
    docker volume rm "og-director-data-$SLOT" "og-director-id-$SLOT" >/dev/null 2>&1 || true
    log "slot $SLOT stopped"
    exit 0
fi

RUN="${1:?archived run name required}"
SLOT="${2:?slot required}"
SRC="$ARCHIVE/$RUN"
[ -f "$SRC/world-repo.bundle" ] || fail "no bundle for $RUN"
[ -d "$SRC/world" ] || fail "no world files for $RUN"

WORLD_PORT=$((6080 + SLOT))
IDENTITY_PORT_T=$((6090 + SLOT))
WORK="$STATE_DIR/director/$RUN"
IMAGE="og-director:$(echo "$RUN" | tr -c 'a-z0-9.-\n' '-')"
NET="og-director-net-$SLOT"
WORLD_C="og-director-world-$SLOT"
ID_C="og-director-identity-$SLOT"
TOKEN="director-$SLOT"

step "restoring $RUN's live engine"
# Only what staging owns. Session logs and reports live beside these and must
# survive a restage -- the first version cleared the whole directory, and took
# every earlier session's record with it.
rm -rf "$WORK/repo" "$WORK/world" && mkdir -p "$WORK"
git clone -q "$SRC/world-repo.bundle" "$WORK/repo"
git -C "$WORK/repo" checkout -q origin/live
SHA="$(git -C "$WORK/repo" rev-parse --short=12 HEAD)"
cp -a "$SRC/world" "$WORK/world"

step "building $IMAGE from $SHA"
docker build -q -t "$IMAGE" "$WORK/repo" >/dev/null || fail "could not build $RUN's engine"

docker image inspect "$IDENTITY_IMAGE" >/dev/null 2>&1 \
    || docker build -q -t "$IDENTITY_IMAGE" "$SUPERVISOR_DIR/identity" >/dev/null

"$0" stop "$SLOT" >/dev/null
docker network create "$NET" >/dev/null

docker run -d --name "$ID_C" --network "$NET" \
    -p "127.0.0.1:$IDENTITY_PORT_T:8090" \
    -v "og-director-id-$SLOT:/identity" \
    -e IDENTITY_WORLD_KEY=director-world-key \
    -e IDENTITY_ADMIN_KEY=director-admin-key \
    --memory 256m \
    "$IDENTITY_IMAGE" >/dev/null || fail "identity would not start"

docker run -d --name "$WORLD_C" --network "$NET" \
    -p "127.0.0.1:$WORLD_PORT:8080" \
    -v "og-director-data-$SLOT:/data" \
    -v "$WORK/world:/world" \
    -e "Identity__Url=http://$ID_C:8090" \
    -e "Identity__PublicPort=$IDENTITY_PORT_T" \
    -e "Identity__Key=director-world-key" \
    -e "CARETAKER_TOKEN=$TOKEN" \
    -e "OG_COMMIT=$SHA" -e "OG_WORLD_SHA=$SHA" \
    --memory 1g --pids-limit 512 \
    "$IMAGE" >/dev/null || fail "world would not start"

wait_healthy "$WORLD_PORT" || { docker logs "$WORLD_C" 2>&1 | tail -20 >&2; fail "$RUN never became healthy"; }

cat > "$WORK/slot.json" <<JSON
{"run": "$RUN", "slot": $SLOT, "sha": "$SHA",
 "world": "http://127.0.0.1:$WORLD_PORT", "identity": "http://127.0.0.1:$IDENTITY_PORT_T",
 "token": "$TOKEN"}
JSON
log "PASS  $RUN ($SHA) on slot $SLOT: world :$WORLD_PORT, identity :$IDENTITY_PORT_T"
