"""What it can look at.

Read-only, and deliberately bare. Earlier runs had tools named `unanswered`,
`stuck`, `deaths` and `traffic`, which told it -- before it had read a single
event -- that those were the categories worth having, and that six commands was
roughly where being stuck began. That is an opinion encoded as an API, and it
survived every attempt to take the opinions out of the briefing.

What is left are the primitives. If stuckness matters, it can find that out.
"""

import json
import os
import time

import journal
import world_client

TOOLS = [
    {
        "name": "events",
        "description": "The event log, oldest first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {"type": "integer", "description": "Exclusive lower bound on sequence."},
                "limit": {"type": "integer", "description": "Maximum to return (default 200, max 2000)."},
                "type": {"type": "string", "description": "One event type."},
                "character": {"type": "string", "description": "One character's id."},
                "location": {"type": "integer", "description": "One place."},
            },
        },
    },
    {
        "name": "present",
        "description": "Who is in the world now.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "characters",
        "description": "Characters, newest first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "living": {"type": "boolean", "description": "Default true."},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "character",
        "description": "One character.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "character_events",
        "description": "One character's events, from birth.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "since": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "world",
        "description": "The world as it currently stands.",
        "input_schema": {
            "type": "object",
            "properties": {"full": {"type": "boolean", "description": "Default false."}},
        },
    },
    {
        "name": "location",
        "description": "One place as it currently stands.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    },
    {
        "name": "clock",
        "description": "Elapsed and remaining seconds in this turn.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "past_journal",
        "description": "Your earlier entries, oldest first.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Default 5."}},
        },
    },
]


HANDLERS = {
    "events": lambda **kw: world_client.events(**kw),
    "present": lambda **kw: world_client.present(),
    "characters": lambda **kw: world_client.characters(**kw),
    "character": lambda **kw: world_client.character(**kw),
    "character_events": lambda **kw: world_client.character_events(**kw),
    "world": lambda **kw: world_client.world(),
    "location": lambda **kw: world_client.location(**kw),
    "past_journal": lambda **kw: journal.entries(**kw),
    "clock": lambda **kw: _clock(),
}


def _clock():
    """What is left of this turn, from the deadline the harness set."""
    deadline = float(os.environ.get("CARETAKER_DEADLINE") or 0)
    started = float(os.environ.get("CARETAKER_STARTED") or 0)

    if not deadline:
        return {"note": "this turn has no limit set"}

    now = time.time()

    return {
        "elapsedSeconds": round(now - started) if started else None,
        "remainingSeconds": max(0, round(deadline - now)),
        "limitSeconds": round(deadline - started) if started else None,
    }


def run(name, arguments):
    """Dispatches one tool call. A failure is reported, never raised at the model."""
    handler = HANDLERS.get(name)

    if handler is None:
        return {"error": f"no such tool: {name}"}

    try:
        return handler(**(arguments or {}))
    except TypeError as error:
        return {"error": f"bad arguments for {name}: {error}"}
    except world_client.WorldError as error:
        return {"error": str(error)}


def render(result, cap=60000):
    text = json.dumps(result, indent=2, default=str)

    if len(text) > cap:
        text = text[:cap] + f"\n... truncated at {cap} characters; narrow the query to see more"

    return text + _time_left()


def _time_left():
    """
    What is left of the turn, on the end of every answer.

    A turn ends where the clock ends, and asking has to be remembered. One turn
    in run 004 spent 1780 of its 1800 seconds, designed the whole change, and
    wrote none of it: it asked the time at its fourth step and again at its
    fifteenth, by which point there was none. Time spent is not something it can
    feel, so it is said rather than offered.
    """
    deadline = float(os.environ.get("CARETAKER_DEADLINE") or 0)

    if not deadline:
        return ""

    remaining = max(0, round(deadline - time.time()))

    return f"\n\n[{remaining}s left in this turn]"
