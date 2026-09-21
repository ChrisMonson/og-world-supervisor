#!/usr/bin/env python3
"""The caretaker's hands, served over stdio.

A minimal MCP server so the tools can be given to the Claude CLI. No
dependencies: the protocol here is three methods and a notification.

Two sets of tools, and which set is available depends on how it was woken:

  observe   looking at the world; always available
  act       speech and small mercies, which take effect at once
  shape     editing the world's own files, which must pass the gate first
"""

import json
import os
import sys
import traceback

import body
import deploys
import journal
import tools as read_tools
import workspace
import world_client

PROTOCOL_VERSION = "2024-11-05"

ACT_TOOLS = [
    {
        "name": "speak",
        "description": (
            "Say something into the world. Target 'world', 'location' or "
            "'character'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "enum": ["world", "location", "character"]},
                "id": {"type": "string", "description": "Location number or character, when the target needs one."},
                "text": {"type": "string"},
            },
            "required": ["target", "text"],
        },
    },
    {
        "name": "adjust",
        "description": (
            "Change one living character directly. The reason is kept."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "characterId": {"type": "string", "description": "Character id or name."},
                "rationale": {"type": "string", "description": "Why. This is kept."},
                "hitPoints": {"type": "integer"},
                "give": {"type": "array", "items": {"type": "string"}, "description": "Item names that must already exist in the world."},
                "take": {"type": "array", "items": {"type": "string"}},
                "moveTo": {"type": "integer", "description": "A location to put them in."},
            },
            "required": ["characterId", "rationale"],
        },
    },
]

SHAPE_TOOLS = [
    {
        "name": "play",
        "description": (
            "Take a character and type into the world. Give a list of things to "
            "type; you get back what the world said."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "commands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "What to type, in order. Forty at most.",
                },
                "name": {
                    "type": "string",
                    "description": "Only used when you have no living character to return to.",
                },
                "pause": {
                    "type": "number",
                    "description": "Seconds to wait after each line for the world to answer. Default 0.6.",
                },
            },
            "required": ["commands"],
        },
    },
    {
        "name": "list_files",
        "description": "The files you can read and write.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_file",
        "description": (
            "Read a file from your working copy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write a file in your working copy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "replace_in_file",
        "description": (
            "Change part of a file. Fails without changing anything if what you "
            "are looking for is not there, or is there more times than count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "find": {"type": "string", "description": "Exact text to look for."},
                "put": {"type": "string", "description": "What to put in its place."},
                "count": {"type": "integer", "description": "How many it should match (default 1)."},
            },
            "required": ["path", "find", "put"],
        },
    },
    {
        "name": "validate",
        "description": (
            "Check a world file against the world's validator."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "changes",
        "description": "What you have changed and not committed.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "discard",
        "description": "Throw away uncommitted changes.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "commit",
        "description": (
            "Commit your working copy. The reason is kept."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "One line, what changed."},
                "rationale": {"type": "string", "description": "Why you did it."},
            },
            "required": ["message", "rationale"],
        },
    },
    {
        "name": "deploy",
        "description": (
            "Put your committed changes into the world. It is checked first; if "
            "the check fails nothing changes and you are told why."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "deploy_history",
        "description": "What has been deployed, and what is live.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "rollback",
        "description": "Return the world to an earlier commit. Nobody loses what they have.",
        "input_schema": {
            "type": "object",
            "properties": {"ref": {"type": "string", "description": "Defaults to the last known good commit."}},
        },
    },
]

HANDLERS = {
    **read_tools.HANDLERS,
    "speak": lambda **kw: world_client.speak(**kw),
    "adjust": lambda **kw: world_client.adjust(**kw),
    "list_files": lambda **kw: workspace.listing(),
    "read_file": lambda path: {"path": path, "content": workspace.read(path)},
    "write_file": lambda path, content: workspace.write(path, content),
    "replace_in_file": lambda path, find, put, count=1: workspace.replace(path, find, put, count),
    "validate": lambda path: world_client.validate(workspace.read(path)),
    "changes": lambda **kw: workspace.status(),
    "discard": lambda **kw: workspace.discard(),
    "commit": lambda **kw: workspace.commit(**kw),
    "deploy": lambda **kw: deploys.deploy(),
    "deploy_history": lambda **kw: deploys.history(**kw),
    "rollback": lambda **kw: deploys.rollback(**kw),
    "play": lambda **kw: body.play(**kw),
}


def available():
    """Which tools this run is allowed, by the reach it was started with."""
    reach = os.environ.get("CARETAKER_REACH", "observe")

    tools = list(read_tools.TOOLS)

    if reach in ("act", "shape"):
        tools += ACT_TOOLS

    if reach == "shape":
        tools += SHAPE_TOOLS

    return tools


def to_mcp(tool):
    return {
        "name": tool["name"],
        "description": tool["description"],
        "inputSchema": tool["input_schema"],
    }


def call(name, arguments):
    handler = HANDLERS.get(name)
    allowed = {tool["name"] for tool in available()}

    if name not in allowed:
        return {"error": f"{name} is not something you can do right now"}

    if handler is None:
        return {"error": f"no such tool: {name}"}

    try:
        return handler(**(arguments or {}))
    except TypeError as error:
        return {"error": f"bad arguments for {name}: {error}"}
    except (ValueError, world_client.WorldError) as error:
        return {"error": str(error)}
    except Exception as error:
        return {"error": f"{name} failed: {error}", "trace": traceback.format_exc()[-800:]}


def respond(message_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": message_id, "result": result}) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()

        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = message.get("method")
        message_id = message.get("id")

        if method == "initialize":
            respond(message_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "caretaker", "version": "1.0.0"},
            })
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            respond(message_id, {"tools": [to_mcp(tool) for tool in available()]})
        elif method == "tools/call":
            params = message.get("params") or {}
            outcome = call(params.get("name"), params.get("arguments"))
            respond(message_id, {
                "content": [{"type": "text", "text": read_tools.render(outcome)}],
                "isError": isinstance(outcome, dict) and "error" in outcome,
            })
        elif message_id is not None:
            respond(message_id, {})


if __name__ == "__main__":
    main()
