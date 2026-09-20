"""Walking in the world.

The caretaker can take a character and play, exactly as anyone else does: a
token, a ticket, a name, and whatever the engine makes of what it types. It is
visible to whoever else is there, its actions are real, and it dies once.

Nothing here is privileged. If it picks something up, the floor is emptier. If
it kills the troll, the key is on the ground for whoever comes next. If it dies,
what it carried is lying where it fell and the character is finished.
"""

import asyncio
import json
import urllib.request
from pathlib import Path

import config

TOKEN_FILE = config.STATE_DIR / "body-token"
NAME_FILE = config.STATE_DIR / "body-name"

IDENTITY_URL = config.SUPERVISOR_DIR.joinpath("state", "identity-url")


def _identity_url():
    """Where a visitor is let in. The world itself says, as it tells a browser."""
    with urllib.request.urlopen(f"{config.WORLD_URL}/config.json", timeout=10) as response:
        return json.loads(response.read())["identityUrl"]


def _ticket():
    """A token of its own, kept between visits, exchanged for a ticket."""
    token = TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else None

    request = urllib.request.Request(
        f"{_identity_url()}/tickets",
        data=json.dumps({"token": token}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")

    with urllib.request.urlopen(request, timeout=10) as response:
        issued = json.loads(response.read())

    TOKEN_FILE.write_text(issued["token"])
    return issued["ticket"]


async def _walk(ticket, name, commands, pause):
    import websockets

    url = config.WORLD_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
    transcript = []
    named = False

    async with websockets.connect(url) as socket:
        await socket.send(json.dumps({"type": "hello", "value": ticket}))

        async def listen(seconds):
            loop = asyncio.get_event_loop()
            end = loop.time() + seconds

            while True:
                remaining = end - loop.time()

                if remaining <= 0:
                    return

                try:
                    raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
                except (asyncio.TimeoutError, Exception):
                    return

                message = json.loads(raw)

                if message.get("type") == "needName":
                    nonlocal named
                    named = True
                elif message.get("type") in ("text", "died"):
                    transcript.append(message.get("text") or "")

        await listen(1.2)

        # A new character only when the last one is finished.
        if named:
            await socket.send(json.dumps({"type": "name", "value": name}))
            transcript.append(f"— you are {name}, newly born —")
            await listen(1.0)

        for command in commands:
            transcript.append(f"> {command}")
            await socket.send(json.dumps({"type": "command", "value": command}))
            await listen(pause)

    return transcript


def play(commands, name=None, pause=0.6):
    """
    Takes a turn in the world as a character. Returns what the world said back.

    Keeps the same character between visits until it dies. A name is only used
    when there is no living character to return to.
    """
    if not isinstance(commands, list) or not commands:
        return {"error": "give a list of things to type"}

    if len(commands) > 40:
        return {"error": "forty at a time is the most; the world moves while you are in it"}

    chosen = (name or (NAME_FILE.read_text().strip() if NAME_FILE.exists() else "") or "").strip()

    if not chosen:
        return {"error": "the first time you go in, you have to be called something"}

    NAME_FILE.write_text(chosen)

    try:
        transcript = asyncio.run(_walk(_ticket(), chosen, commands, pause))
    except Exception as error:
        return {"error": f"could not go in: {error}"}

    return {
        "playedAs": chosen,
        "transcript": transcript,
        "note": ("What you did there is in the world's record like anyone else's, "
                 "and anyone present saw it."),
    }
