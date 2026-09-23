"""The wake predicate.

The world's event log carries a monotonic sequence. If anything that was not the
caretaker's own doing has happened since it last woke, and the floor between
wakes has passed, it wakes.

Excluding its own acts is what stops it waking itself in a loop. Its acts are
not only the ones it signs as god: a character it is walking around in is its
own doing too, and so the lives behind its own hands are excluded the same way.
The world's own clock -- a creature coming back to a room hours after it was
killed -- is nobody's doing at all, and is not news.

What is excluded here changes only whether a turn is taken. A turn that is taken
is handed the whole digest, this included: it decides what to wake for, never
what it gets to see.
"""

import json
import time
import urllib.error
import urllib.request

import body
import config
import world_client

# The world's own clock turning over is nobody's doing, so it is not a reason to
# wake. This used to be a list of event types, and the list broke the first time
# the caretaker invented one: it wrote monsters that wander on a timer, and each
# step woke it, in a world nobody was in.
#
# So it is a rule instead. An engine event that happens *to* someone -- a monster
# swinging at a character -- carries that character's id, and matters. One that
# carries nobody is ambient, whatever it is called.
def _ambient(event):
    return event["actor"] == "engine" and not event.get("characterId")

PAGE = 500


def _file(reflex):
    return config.REFLEX_WATERMARK_FILE if reflex else config.WATERMARK_FILE


def read_watermark(reflex=False):
    path = _file(reflex)

    if not path.exists():
        return {"seq": 0, "at": 0}

    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"seq": 0, "at": 0}


def write_watermark(seq, reflex=False, quiet_turns=0):
    _file(reflex).write_text(json.dumps({
        "seq": seq,
        "at": time.time(),
        "quietTurns": quiet_turns,
    }))


def _own_characters():
    """
    Every character the caretaker's own hands have held. Identity keeps this;
    the world is never told it, and neither is the caretaker.
    """
    token_file = config.STATE_DIR / "body-token"
    key_file = config.SUPERVISOR_DIR / "state" / "identity-admin-key"

    if not token_file.exists() or not key_file.exists():
        return set()

    try:
        url = f"{body._identity_url()}/lineage/{token_file.read_text().strip()}"
        request = urllib.request.Request(url, method="GET")
        request.add_header("X-Identity-Admin", key_file.read_text().strip())

        with urllib.request.urlopen(request, timeout=10) as response:
            rows = json.loads(response.read())["characters"]

        return {row["character_id"] for row in rows}
    except (urllib.error.URLError, OSError, KeyError, ValueError):
        # Better to wake for its own footsteps than to sleep through a stranger.
        return set()


def _news_since(seq):
    """
    (latest, count) over the events that someone other than the caretaker
    caused. Returns the sequence unmoved when nothing there is news.
    """
    mine = _own_characters()
    latest, count, cursor = seq, 0, seq

    while True:
        rows = world_client.events(since=cursor, limit=PAGE)["events"]

        if not rows:
            break

        for event in rows:
            if event["actor"] == "god" or _ambient(event):
                continue

            if event["actor"] in mine or event.get("characterId") in mine:
                continue

            latest, count = max(latest, event["seq"]), count + 1

        cursor = rows[-1]["seq"]

        if len(rows) < PAGE:
            break

    return latest, count


def should_wake(reflex=False, force=False):
    """Returns (wake, reason, watermark). The two tempos keep separate marks."""
    mark = read_watermark(reflex)
    floor = config.MIN_REFLEX_INTERVAL if reflex else config.MIN_WAKE_INTERVAL

    try:
        status = world_client.status()
    except world_client.WorldError as error:
        return False, f"the world is unreachable: {error}", mark

    # Its own acts do not count: waking on them would be a loop with no exit.
    try:
        latest, news = _news_since(mark["seq"])
    except world_client.WorldError:
        latest = status.get("latestOtherSeq", status["latestSeq"])
        news = max(0, latest - mark["seq"])

    if force:
        return True, f"forced (latest {latest}, last seen {mark['seq']})", mark

    waited = time.time() - mark["at"]

    # The quick turns wake only for something that happened, because they run
    # often enough that waking for nothing would be most of what they did. The
    # long turns are rare, and a world with nobody in it is still a world worth
    # tending: an empty digest is a turn spent building rather than answering.
    if latest <= mark["seq"]:
        if reflex:
            return False, f"nothing has happened since {mark['seq']}", mark

        taken = mark.get("quietTurns", 0)

        if config.MAX_QUIET_TURNS and taken >= config.MAX_QUIET_TURNS:
            return False, (f"nothing has happened since {mark['seq']}, and "
                           f"{taken} turns have already been spent on the quiet world"), mark

        if waited < config.MIN_QUIET_WAKE_INTERVAL:
            remaining = int(config.MIN_QUIET_WAKE_INTERVAL - waited)
            return False, f"nothing has happened, and {remaining}s of the quiet floor remain", mark

        count = (f"{taken + 1} of {config.MAX_QUIET_TURNS}" if config.MAX_QUIET_TURNS
                 else f"{taken + 1} in a row, no cap")
        return True, (f"nothing has happened since {mark['seq']}; "
                      f"a turn with the world to itself ({count})"), mark

    if waited < floor:
        remaining = int(floor - waited)
        return False, f"{news} new events, but {remaining}s of the floor remain", mark

    return True, f"{news} new events since {mark['seq']}", mark
