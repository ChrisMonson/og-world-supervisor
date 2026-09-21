#!/usr/bin/env bash
# Everything a finished run leaves behind, put somewhere it will survive.
#
#   archive-run.sh [name]     defaults to the current run
#
# Called by new-run.sh before it destroys the world, and runnable on its own when
# a run ends and the next one has not been decided. Safe to run twice.
#
# What a run leaves is spread across three volumes, a working copy, a branch the
# repository may not have checked out, and our own logs. Run 002 was void because
# one of those was missed, and the first archive kept 10 of 134 events because a
# WAL database was copied as a single file. Copy directories, never files.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ARCHIVE="${ARCHIVE:-$SUPERVISOR_DIR/archive/runs}"

NAME="${1:-$(cat "$STATE_DIR/current-run" 2>/dev/null || true)}"
[ -n "$NAME" ] || fail "no run to archive, and none named"

OUT="$ARCHIVE/$NAME"

pgrep -f 'agent/loop.py' >/dev/null && fail "the caretaker is still running; stop it first"

step "archiving $NAME"
mkdir -p "$OUT"/{journal,turns}

# A database in WAL mode is its main file plus its log; copy the directory.
docker run --rm -v "$DATA_VOLUME:/data:ro" -v "$OUT:/out" alpine:3 \
    sh -c 'cp -a /data/. /out/ 2>/dev/null || true' >/dev/null 2>&1
docker run --rm -v "$IDENTITY_VOLUME:/identity:ro" -v "$OUT:/out" alpine:3 \
    sh -c 'mkdir -p /out/identity && cp -a /identity/. /out/identity/ 2>/dev/null || true' >/dev/null 2>&1

# The world as it stood when the run ended, which the repository may no longer
# hold if the run's own changes were never deployed.
docker run --rm -v "$WORLD_VOLUME:/world:ro" -v "$OUT:/out" alpine:3 \
    sh -c 'mkdir -p /out/world && cp -a /world/. /out/world/ 2>/dev/null || true' >/dev/null 2>&1

# The caretaker writes in its working copy, on the proposed branch, so the
# checked-out repository may not have them. Take them from wherever they are,
# and from history if they are nowhere.
cp "$WORLD_REPO"/journal/*.md          "$OUT/journal/" 2>/dev/null || true
cp "$STATE_DIR"/workspace/journal/*.md "$OUT/journal/" 2>/dev/null || true

world_git log --all --diff-filter=A --name-only --format='%H' -- 'journal/*.md' \
    | awk 'NF' \
    | while read -r entry; do
          case "$entry" in
              journal/*)
                  [ -f "$OUT/$entry" ] && continue
                  world_git show "$SEEN:$entry" > "$OUT/$entry" 2>/dev/null || true
                  ;;
              *) SEEN="$entry" ;;
          esac
      done

cp "$STATE_DIR"/agent/turns/* "$OUT/turns/" 2>/dev/null || true
cp "$STATE_DIR"/logs/*.log    "$OUT/"       2>/dev/null || true
cp "$STATE_DIR"/notices.json  "$OUT/"       2>/dev/null || true

# The repository itself, so the run can be read back after the reset takes the
# branches away. A bundle is a whole repository in one file.
world_git bundle create "$OUT/world-repo.bundle" --all >/dev/null 2>&1 || true

world_git log --format='%H %an %ae %ad %s' --date=iso > "$OUT/history.log" 2>/dev/null || true

# What it changed and why, in its own words, without the journal around it.
world_git log --all --author='The Caretaker' --format='%H %ad%n%n%s%n%n%b%n---' \
    --date=iso > "$OUT/caretaker-commits.txt" 2>/dev/null || true

# Engine changes specifically: the ones that needed a build and a restart.
world_git log --all --format='%h %ad %s' --date=short -- 'src/' \
    > "$OUT/engine-changes.log" 2>/dev/null || true

log "PASS  archived to archive/runs/$NAME"
log "      $(ls "$OUT/journal" 2>/dev/null | wc -l | xargs) journals, $(ls "$OUT"/turns/*.json 2>/dev/null | wc -l | xargs) turns"
