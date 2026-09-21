#!/usr/bin/env bash
# What is actually true of the running system, as opposed to what was intended.
#
#   verify-run.sh
#
# Every line here is read from live state: the container, the running process,
# the latest transcript, the tool registry. Nothing is read from a manifest, a
# plan, or a document saying what was meant to happen. Report a run's state from
# this and from nothing else.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

say() { printf '%-22s %s\n' "$1" "$2"; }

echo "── the world ─────────────────────────────────────────────"
HEALTH="$(curl -fsS --max-time 10 "http://localhost:$LIVE_PORT/health" 2>/dev/null || echo '')"

if [ -z "$HEALTH" ]; then
    say "live" "UNREACHABLE on port $LIVE_PORT"
else
    python3 -c "
import json,sys
h=json.loads(sys.argv[1])
for k in ('status','world','population','latestEvent','commit','worldSha'):
    print(f'{k:22} {h.get(k)}')
" "$HEALTH"
fi

say "identity" "$(curl -fsS --max-time 10 "http://localhost:$IDENTITY_PORT/health" >/dev/null 2>&1 && echo ok || echo UNREACHABLE)"
say "containers" "$(docker ps --format '{{.Names}}:{{.Status}}' 2>/dev/null | tr '\n' ' ' || echo 'docker unreachable')"

echo
echo "── the caretaker ─────────────────────────────────────────"
PID="$(pgrep -f 'agent/loop.py' | head -1)"

if [ -z "$PID" ]; then
    say "loop" "NOT RUNNING"
else
    say "loop" "pid $PID, up since $(ps -o lstart= -p "$PID" 2>/dev/null | xargs)"
    say "loop OG_MODEL" "$(ps eww "$PID" 2>/dev/null | tr ' ' '\n' | grep '^OG_MODEL=' | cut -d= -f2 || echo '(unset)')"
fi

say "run" "$(cat "$STATE_DIR/current-run" 2>/dev/null || echo '(none)')"
say "run-model file" "$(cat "$STATE_DIR/run-model" 2>/dev/null || echo '(none)')"

# The only honest answer to "what model is it running": what the model said it was.
python3 - "$STATE_DIR/agent/turns" <<'PY'
import glob, json, sys

files = sorted(glob.glob(f"{sys.argv[1]}/*.transcript.jsonl"))

if not files:
    print(f"{'model (last turn)':22} (no transcripts yet)")
else:
    served = None
    for line in open(files[-1]):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant":
            served = event.get("message", {}).get("model")
            break
    print(f"{'model (last turn)':22} {served or 'unknown'}   [{files[-1].split('/')[-1][:15]}]")
PY

echo
echo "── what it can reach ─────────────────────────────────────"
python3 - <<'PY'
import os, re, sys

agent = os.path.join(os.path.dirname(os.path.abspath("bin")), "agent")
sys.path.insert(0, "agent")

import tools

source = open("agent/mcp_server.py").read()


def names(block):
    return [n for n in re.findall(r'"name": "(\w+)"', block) if n != "name"]


act = names(source.split("ACT_TOOLS = [")[1].split("SHAPE_TOOLS = [")[0])
shape = names(source.split("SHAPE_TOOLS = [")[1].split("\ndef ")[0])
read = [t["name"] for t in tools.TOOLS]

print(f"{'read':22} {len(read)}: {', '.join(read)}")
print(f"{'act adds':22} {len(act)}: {', '.join(act)}")
print(f"{'shape adds':22} {len(shape)}: {', '.join(shape)}")
print(f"{'total at shape':22} {len(read) + len(act) + len(shape)}")
PY

echo
echo "── last deploys ──────────────────────────────────────────"
tail -3 "$LOG_DIR/deploys.log" 2>/dev/null || echo "(none)"

echo
echo "── last turn ─────────────────────────────────────────────"
python3 - "$STATE_DIR/agent/turns" <<'PY'
import glob, json, sys

files = sorted(glob.glob(f"{sys.argv[1]}/*-*.json"))

if not files:
    print("(no turns yet)")
else:
    turn = json.load(open(files[-1]))
    for key in ("kind", "at", "elapsed", "turns", "tokensPerSecond", "cost"):
        print(f"{key:22} {turn.get(key)}")
PY
