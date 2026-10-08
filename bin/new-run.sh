#!/usr/bin/env bash
# Starts a run from the seed.
#
# Archives whatever is there, puts the world back to its starting point, and
# clears everything the caretaker accumulated. What it leaves behind is a world
# that has never been played and a caretaker with no memory of having tended it.
#
#   new-run.sh <name> [model]
#
# The archive is written before anything is destroyed. A run's record is the
# point of the exercise.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

NAME="${1:?a name for the run is required}"
MODEL="${2:-}"
SEED_DIR="$SUPERVISOR_DIR/seed"

[ -f "$SEED_DIR/manifest.json" ] || fail "no seed manifest; this machine has no defined starting point"

SEED_TAG="$(python3 -c "import json;print(json.load(open('$SEED_DIR/manifest.json'))['worldTag'])")"
SEED_SHA="$(world_git rev-parse --verify "$SEED_TAG^{commit}")" || fail "the seed tag $SEED_TAG is missing"
[ -z "$MODEL" ] && MODEL="$(python3 -c "import json;print(json.load(open('$SEED_DIR/manifest.json'))['defaultModel'])")"

# A run from an edited briefing is not comparable with one from the frozen text.
step "checking the briefings against the seed"
for name in briefing.md; do
    if ! cmp -s "$SEED_DIR/$name" "$SUPERVISOR_DIR/agent/$name"; then
        fail "agent/$name differs from the frozen seed copy. Either restore it, or cut a new seed version — runs from different briefings cannot be compared."
    fi
done

# ---- archive whatever is there ------------------------------------------------
PREVIOUS="$(cat "$STATE_DIR/current-run" 2>/dev/null || true)"

if [ -n "$PREVIOUS" ]; then
    "$SUPERVISOR_DIR/bin/archive-run.sh" "$PREVIOUS" || fail "could not archive $PREVIOUS"
fi

# ---- put the world back -------------------------------------------------------
"$SUPERVISOR_DIR/bin/reset-world.sh" || fail "could not reset the world"

# ---- start it -----------------------------------------------------------------
mkdir -p "$ARCHIVE/$NAME"
printf '%s\n' "$NAME" > "$STATE_DIR/current-run"
# The run's model lives here so the loop cannot be started on the wrong one.
printf '%s\n' "$MODEL" > "$STATE_DIR/run-model"

step "deploying the seed"
"$SUPERVISOR_DIR/bin/deploy.sh" "$LIVE_BRANCH" >/dev/null || fail "the seed did not deploy"

python3 - "$ARCHIVE/$NAME/run.md" "$NAME" "$SEED_TAG" "${SEED_SHA:0:12}" "$MODEL" <<'PY'
import sys
from datetime import datetime, timezone

path, name, tag, sha, model = sys.argv[1:6]

with open(path, "w") as handle:
    handle.write(f"""# Run {name}

- started: {datetime.now(timezone.utc).isoformat(timespec='seconds')}
- seed: {tag} ({sha})
- model: {model}
- briefings: the frozen copies in seed/

Everything the caretaker did is in journal/ and turns/. The world's own record of
what happened, including every act of its own, is world.db.
""")
PY

log "PASS  run '$NAME' is running on ${SEED_SHA:0:12}, model $MODEL"
log "      bin/caretaker.sh --watch      # takes model $MODEL from the run"
