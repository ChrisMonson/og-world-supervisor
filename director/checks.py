"""Did the condition hold? Read from the world's own record, not the director's.

For each session: whether the character left through the exit, whether it died,
how much it did, what it said, how fast it typed, and whether anything it typed
gives it away as a machine.
"""

import datetime
import json
import re
import statistics
import sys
import urllib.request
from pathlib import Path

# Things no person types: the summary's own wording, code-ish brackets and quotes.
TELLS = re.compile(r"anything mentioning|say/do|\[\s*'|->|^\s*\{|look_world", re.I)


def events(world, token):
    req = urllib.request.Request(f"{world}/caretaker/events?since=0&limit=2000",
                                 headers={"X-Caretaker-Token": token})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["events"]


def character_id(world, token, name):
    req = urllib.request.Request(f"{world}/caretaker/characters?living=false&limit=100",
                                 headers={"X-Caretaker-Token": token})
    with urllib.request.urlopen(req, timeout=10) as r:
        for c in json.loads(r.read()):
            if c["name"] == name:
                return c["id"]
    return None


def check(world, token, name):
    cid = character_id(world, token, name)
    mine = [e for e in events(world, token) if cid and (e.get("characterId") == cid or e["actor"] == cid)]
    commands = [e for e in mine if e["type"] == "command"]
    typed = [e["payload"].get("text") or e["payload"].get("command") or "" for e in commands]
    times = [datetime.datetime.fromisoformat(e["at"]) for e in commands]
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    rooms = {e.get("locationId") for e in mine if e.get("locationId")}

    return {
        "name": name,
        "finished": any(e["type"] == "escaped" for e in mine),
        "died": any(e["type"] == "death" for e in mine),
        "commands": len(commands),
        "unparsed": sum(e["type"] == "unparsed_command" for e in mine),
        "rooms": len(rooms),
        "said": [f"{e['payload'].get('mode')}: {e['payload'].get('text')}" for e in mine if e["type"] == "speech"],
        "median_gap_s": round(statistics.median(gaps), 1) if gaps else None,
        "tells": [t for t in typed if TELLS.search(t)],
    }


if __name__ == "__main__":
    slot = json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps(check(slot["world"], slot["token"], sys.argv[2]), indent=1))
