"""HTTP client for the world's read-only surface.

Everything here observes. There is nothing in this module that changes anything
in the world, by construction.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

import config


class WorldError(RuntimeError):
    pass


def _post(path, payload, raw=False):
    body = payload.encode("utf-8") if raw else json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(f"{config.WORLD_URL}{path}", data=body, method="POST")
    request.add_header("X-Caretaker-Token", config.CARETAKER_TOKEN)
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:400]
        raise WorldError(f"{error.code} from {path}: {detail}") from error
    except urllib.error.URLError as error:
        raise WorldError(f"cannot reach the world at {config.WORLD_URL}: {error.reason}") from error


def _get(path, params=None):
    url = f"{config.WORLD_URL}{path}"

    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url = f"{url}?{urllib.parse.urlencode(clean)}"

    request = urllib.request.Request(url, method="GET")
    request.add_header("X-Caretaker-Token", config.CARETAKER_TOKEN)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")[:400]
        raise WorldError(f"{error.code} from {path}: {body}") from error
    except urllib.error.URLError as error:
        raise WorldError(f"cannot reach the world at {config.WORLD_URL}: {error.reason}") from error


def status():
    return _get("/caretaker/")


def digest(since=0):
    return _get("/caretaker/digest", {"since": since})


def events(since=0, limit=200, type=None, character=None, location=None):
    return _get("/caretaker/events", {
        "since": since, "limit": limit,
        "type": type, "character": character, "location": location,
    })


def characters(living=True, limit=100):
    return _get("/caretaker/characters", {"living": str(living).lower(), "limit": limit})


def character(id):
    return _get(f"/caretaker/characters/{urllib.parse.quote(id)}")


def character_events(id, since=0, limit=500):
    return _get(f"/caretaker/characters/{urllib.parse.quote(id)}/events",
                {"since": since, "limit": limit})


def present():
    return _get("/caretaker/present")


def world():
    return _get("/caretaker/world")


def actions():
    return _get("/caretaker/world/actions")


def location(id):
    return _get(f"/caretaker/world/locations/{int(id)}")


def unanswered(since=0, limit=100):
    return _get("/caretaker/signals/unanswered", {"since": since, "limit": limit})


def speech(since=0, mode=None, limit=100):
    return _get("/caretaker/signals/speech", {"since": since, "mode": mode, "limit": limit})


def deaths(since=0, limit=100):
    return _get("/caretaker/signals/deaths", {"since": since, "limit": limit})


def stuck(threshold=6):
    return _get("/caretaker/signals/stuck", {"threshold": threshold})


def traffic():
    return _get("/caretaker/signals/traffic")


# ---- acts, which take effect at once and change nothing on disk ----------------

def speak(target, text, id=None):
    return _post("/caretaker/act/speak", {"target": target, "id": id, "text": text})


def adjust(characterId, rationale, hitPoints=None, give=None, take=None, moveTo=None):
    return _post("/caretaker/act/adjust", {
        "characterId": characterId,
        "rationale": rationale,
        "hitPoints": hitPoints,
        "give": give,
        "take": take,
        "moveTo": moveTo,
    })


def validate(world_json):
    """Checks a proposed world file with the validator the world itself uses."""
    return _post("/caretaker/validate", world_json, raw=True)
