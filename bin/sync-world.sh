#!/usr/bin/env bash
# Copies a revision's world files onto the volume the running world reads from.
#
#   sync-world.sh <sha>
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SHA="$(world_git rev-parse --verify "${1:?a revision is required}^{commit}")"
SHORT="${SHA:0:12}"
STAGE="$STATE_DIR/world-stage"

rm -rf "$STAGE" && mkdir -p "$STAGE"
world_git archive "$SHA" world | tar -x -C "$STAGE" || fail "could not take world files from $SHORT"

docker run --rm -v "$WORLD_VOLUME:/world" -v "$STAGE/world:/incoming:ro" alpine:3 \
    sh -c 'rm -rf /world/* && cp -a /incoming/. /world/ && chown -R 10001:10001 /world' \
    >/dev/null || fail "could not write the world files"

rm -rf "$STAGE"
