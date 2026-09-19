"""The caretaker's tools.

Read-only. Every one of these looks at something; none of them change anything.
The raw event feed is always reachable unfiltered, so a summary is never a wall.
"""

import json

import journal
import world_client

TOOLS = [
    {
        "name": "events",
        "description": (
            "The raw event log, oldest first. Every command, movement, fight, death, "
            "item and word spoken, exactly as recorded. Filter by type, character or "
            "location, or pass nothing and read it all. The response says how many "
            "events matched, so you can tell when you are seeing only part."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {"type": "integer", "description": "Exclusive lower bound on sequence. 0 for the beginning."},
                "limit": {"type": "integer", "description": "Maximum to return (default 200, max 2000)."},
                "type": {"type": "string", "description": "One event type, e.g. death, speech, unparsed_command."},
                "character": {"type": "string", "description": "Restrict to one character's id."},
                "location": {"type": "integer", "description": "Restrict to one place."},
            },
        },
    },
    {
        "name": "unanswered",
        "description": (
            "What people typed that the world had no answer for, grouped by what they "
            "said and ordered by how often. The closest thing you have to being asked "
            "for something directly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {"type": "integer"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "speech",
        "description": (
            "What has been said. Mode is one of say (to the room), yell (to everyone), "
            "whisper (to one person) or pray (to nobody the world knows of)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {"type": "integer"},
                "mode": {"type": "string", "enum": ["say", "yell", "whisper", "pray"]},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "deaths",
        "description": "Who died, where, to what, and how long they had lived.",
        "input_schema": {
            "type": "object",
            "properties": {"since": {"type": "integer"}, "limit": {"type": "integer"}},
        },
    },
    {
        "name": "stuck",
        "description": (
            "Living characters who have typed several commands in one place without "
            "moving or achieving anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"threshold": {"type": "integer", "description": "Commands before counting as stuck (default 6)."}},
        },
    },
    {
        "name": "traffic",
        "description": (
            "Where people go: events, distinct visitors, deaths and unanswered "
            "commands per place, plus the places nobody has ever walked into."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "present",
        "description": "Who is in the world right now, where they are standing, and their health.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "characters",
        "description": "Characters, newest first. Living only by default; pass living=false for the dead as well.",
        "input_schema": {
            "type": "object",
            "properties": {"living": {"type": "boolean"}, "limit": {"type": "integer"}},
        },
    },
    {
        "name": "character",
        "description": "One character in full: name, when it was born, whether it still lives, and its current state.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "character_events",
        "description": "Everything one character has done, from birth. A single life rather than a population.",
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
        "description": "The whole world as it currently stands: every place, its exits, and the items that exist.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "location",
        "description": (
            "One place in detail: description, exits, what creature stands there, what "
            "lies on the ground, and every interaction it will respond to."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    },
    {
        "name": "actions",
        "description": (
            "Everything an interaction can be made to do, and how triggers, "
            "conditions and scope work. Read this before writing an interaction: "
            "the world is capable of more than the interactions currently in it "
            "happen to use."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "past_journal",
        "description": "Your own earlier entries, oldest first. What you were thinking when you last looked.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "How many recent entries (default 5)."}},
        },
    },
]

HANDLERS = {
    "events": lambda **kw: world_client.events(**kw),
    "unanswered": lambda **kw: world_client.unanswered(**kw),
    "speech": lambda **kw: world_client.speech(**kw),
    "deaths": lambda **kw: world_client.deaths(**kw),
    "stuck": lambda **kw: world_client.stuck(**kw),
    "traffic": lambda **kw: world_client.traffic(),
    "present": lambda **kw: world_client.present(),
    "characters": lambda **kw: world_client.characters(**kw),
    "character": lambda **kw: world_client.character(**kw),
    "character_events": lambda **kw: world_client.character_events(**kw),
    "world": lambda **kw: world_client.world(),
    "location": lambda **kw: world_client.location(**kw),
    "actions": lambda **kw: world_client.actions(),
    "past_journal": lambda **kw: journal.entries(**kw),
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


def render(result, cap=20000):
    text = json.dumps(result, indent=2, default=str)

    if len(text) <= cap:
        return text

    return text[:cap] + f"\n... truncated at {cap} characters; narrow the query to see more"
