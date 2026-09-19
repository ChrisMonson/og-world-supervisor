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


def read_watermark():
    if not config.WATERMARK_FILE.exists():
        return {"seq": 0, "at": 0}

    try:
        return json.loads(config.WATERMARK_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"seq": 0, "at": 0}


def write_watermark(seq):
    config.WATERMARK_FILE.write_text(json.dumps({"seq": seq, "at": time.time()}))


def should_wake(force=False):
    """Returns (wake, reason, watermark)."""
    mark = read_watermark()

    try:
        status = world_client.status()
    except world_client.WorldError as error:
        return False, f"the world is unreachable: {error}", mark

    # Its own acts do not count: waking on them would be a loop with no exit.
    latest = status.get("latestOtherSeq", status["latestSeq"])

    if force:
        return True, f"forced (latest {latest}, last seen {mark['seq']})", mark

    if latest <= mark["seq"]:
        return False, f"nothing has happened since {mark['seq']}", mark

    waited = time.time() - mark["at"]

    if waited < config.MIN_WAKE_INTERVAL:
        remaining = int(config.MIN_WAKE_INTERVAL - waited)
        return False, f"{latest - mark['seq']} new events, but {remaining}s of the floor remain", mark

    return True, f"{latest - mark['seq']} new events since {mark['seq']}", mark
