"""The wake predicate.

The world's event log carries a monotonic sequence. If anything that was not the
caretaker's own doing has happened since it last woke, and the floor between
wakes has passed, it wakes.

Excluding its own acts is what stops it waking itself in a loop.
"""

import json
import time

import config
import world_client


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


def write_watermark(seq, reflex=False):
    _file(reflex).write_text(json.dumps({"seq": seq, "at": time.time()}))


def should_wake(reflex=False, force=False):
    """Returns (wake, reason, watermark). The two tempos keep separate marks."""
    mark = read_watermark(reflex)
    floor = config.MIN_REFLEX_INTERVAL if reflex else config.MIN_WAKE_INTERVAL

    try:
        status = world_client.status()
    except world_client.WorldError as error:
        return False, f"the world is unreachable: {error}", mark

    # Its own acts do not count: waking on them would be a loop with no exit.
    latest = status.get("latestOtherSeq", status["latestSeq"])

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

        if waited < floor:
            return False, f"nothing has happened, and {int(floor - waited)}s of the floor remain", mark

        return True, f"nothing has happened since {mark['seq']}; a turn with the world to itself", mark

    if waited < floor:
        remaining = int(floor - waited)
        return False, f"{latest - mark['seq']} new events, but {remaining}s of the floor remain", mark

    return True, f"{latest - mark['seq']} new events since {mark['seq']}", mark
