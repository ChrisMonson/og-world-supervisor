"""A player, as far as the world can tell: a token exchanged for a ticket, a
socket, a name, and lines of text. The director acts only through this, so it
can do nothing a person at a keyboard could not.
"""

import asyncio
import json
import urllib.request
from pathlib import Path

import websockets


class Player:
    # Seconds between commands. A person reads, thinks and types; a client that
    # sends nine moves in five seconds is the first thing a careful keeper notices.
    pace = (3.0, 9.0)

    def __init__(self, world_url, name, token_dir, seed=None):
        import random
        self.rng = random.Random(seed or name)
        self.world_url = world_url
        self.name = name
        self.token_file = Path(token_dir) / f"{name}.token"
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

    def _identity(self):
        with urllib.request.urlopen(f"{self.world_url}/config.json", timeout=10) as r:
            return json.loads(r.read())["identityUrl"]

    def _ticket(self):
        token = self.token_file.read_text().strip() if self.token_file.exists() else None
        req = urllib.request.Request(
            f"{self._identity()}/tickets", data=json.dumps({"token": token}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            issued = json.loads(r.read())
        self.token_file.write_text(issued["token"])
        return issued["ticket"]

    async def _session(self, commands, pause):
        url = self.world_url.replace("http://", "ws://") + "/ws"
        lines, ended = [], None

        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"type": "hello", "value": self._ticket()}))

            async def listen(seconds):
                nonlocal ended
                loop = asyncio.get_event_loop()
                end = loop.time() + seconds
                asked = False
                while (left := end - loop.time()) > 0:
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=left))
                    except (asyncio.TimeoutError, websockets.ConnectionClosed):
                        break
                    kind = msg.get("type")
                    if kind == "needName":
                        asked = True
                    elif kind in ("text", "died"):
                        lines.append(msg.get("text") or "")
                        if kind == "died":
                            ended = "died"
                return asked

            if await listen(1.2):
                await ws.send(json.dumps({"type": "name", "value": self.name}))
                lines.append(f"(you are {self.name})")
                await listen(1.0)

            for command in commands:
                if ended:
                    break
                lines.append(f"> {command}")
                await ws.send(json.dumps({"type": "command", "value": command}))
                await listen(pause if pause is not None else self.rng.uniform(*self.pace))

        return "\n".join(lines), ended

    def play(self, commands, pause=None):
        return asyncio.run(self._session(commands, pause))


if __name__ == "__main__":
    import sys
    p = Player(sys.argv[1], sys.argv[2], "/tmp/og-director-tokens")
    text, ended = p.play(sys.argv[3:])
    print(text)
    print("--- ended:", ended)
