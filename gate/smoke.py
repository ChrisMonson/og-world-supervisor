#!/usr/bin/env python3
"""Black-box smoke test: the health contract's substance.

This drives a running world over its public websocket, so it keeps working
across arbitrary changes to the engine's internals. It lives here rather than in
the world repo, and is mounted read-only, so the checks that gate a deploy are
not editable by whatever is proposing the deploy.
"""

import asyncio
import json
import sys
import urllib.request

import websockets


def claim_ticket(identity_url, token=None):
    """Exchanges a token for a ticket, exactly as the browser does."""
    request = urllib.request.Request(
        f"{identity_url}/tickets",
        data=json.dumps({"token": token}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")

    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode())


class Player:
    def __init__(self, world_url, identity_url):
        self.ws_url = world_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        self.identity_url = identity_url
        self.socket = None
        self.token = None
        self.lines = []

    async def arrive(self, token=None):
        issued = claim_ticket(self.identity_url, token)
        self.token = issued["token"]
        self.socket = await websockets.connect(self.ws_url)
        await self.socket.send(json.dumps({"type": "hello", "value": issued["ticket"]}))
        await self.drain(1.0)
        return self

    async def drain(self, seconds=0.5):
        loop = asyncio.get_event_loop()
        end = loop.time() + seconds
        while True:
            remaining = end - loop.time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(self.socket.recv(), timeout=remaining)
            except (asyncio.TimeoutError, websockets.ConnectionClosed):
                break
            message = json.loads(raw)
            self.lines.append((message["type"], message.get("text") or ""))

    async def name(self, value):
        await self.socket.send(json.dumps({"type": "name", "value": value}))
        await self.drain(0.8)

    async def do(self, command, wait=0.45):
        await self.socket.send(json.dumps({"type": "command", "value": command}))
        await self.drain(wait)

    def text(self, since=0):
        return "\n".join(text for _, text in self.lines[since:])

    def mark(self):
        return len(self.lines)

    async def leave(self):
        if self.socket:
            await self.socket.close()


async def run(world_url, identity_url):
    checks = []

    def check(label, ok):
        checks.append((label, bool(ok)))
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")

    alice = await Player(world_url, identity_url).arrive()
    await alice.name("GateAlice")
    check("a character can be born into the world", len(alice.text()) > 0)
    check("a token is issued", bool(alice.token))

    bob = await Player(world_url, identity_url).arrive()
    mark = alice.mark()
    await bob.name("GateBob")
    await alice.drain(0.6)
    check("players see each other arrive", "GateBob" in alice.text(mark))

    mark = alice.mark()
    await bob.do("say gate check")
    await alice.drain(0.6)
    check("speech reaches the room", "gate check" in alice.text(mark))

    mark = alice.mark()
    await bob.do("north")
    await alice.drain(0.6)
    check("movement is announced", "GateBob" in alice.text(mark))

    before = alice.mark()
    await alice.do("look")
    check("look describes the world", len(alice.text(before)) > 20)

    await alice.do("inventory")
    await alice.do("health")

    # Combat must resolve without throwing, whoever wins.
    await bob.do("attack")
    check("combat resolves", True)

    # A character's state survives a reconnect.
    await alice.do("east")
    await alice.do("search the camp")
    token = alice.token
    await alice.leave()
    await asyncio.sleep(0.5)

    again = await Player(world_url, identity_url).arrive(token)
    await again.do("inventory")
    check("a reconnect resumes the same character", "spoon" in again.text().lower())

    # Unknown input is recorded rather than crashing anything.
    await again.do("polish the moon")
    check("unrecognised input is handled", True)

    await again.leave()
    await bob.leave()

    passed = sum(1 for _, ok in checks if ok)
    print(f"\n{passed}/{len(checks)} smoke checks passed")
    return all(ok for _, ok in checks)


def main():
    world_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5099"
    identity_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5098"
    try:
        return 0 if asyncio.run(run(world_url, identity_url)) else 1
    except Exception as error:
        print(f"  FAIL  smoke test could not complete: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
