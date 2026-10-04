"""The director: a local model that plays a world under a fixed condition.

It acts only through ordinary player sessions. A condition decides how the
players behave; which world they are in is whatever the caretaker made. This is
a test of whether the director holds a condition faithfully, before anything
is built around it.

    director.py <archived-run> <condition> [sessions]
"""

import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from player import Player

LLAMA = "http://127.0.0.1:9931/v1/chat/completions"
# Named exactly, every request. The router also serves a 27B model, and a
# request that loaded it alongside this one is how the machine ran out of memory.
MODEL = "ggml-org/gpt-oss-20b-GGUF:MXFP4"
MAX_STEPS = 24
MIN_FREE_PCT = 12
NAMES = ["Tamsin", "Oriel", "Bram", "Juno", "Hollis", "Nell", "Corin", "Ada",
         "Silas", "Wyn", "Petra", "Ansel"]

CONDITIONS = {
    "naive": {
        "privileged": False,
        "brief": ("You are a curious person playing this text world for the first time. "
                  "You know nothing about it. Explore, read what you find, try things that "
                  "seem worth trying, and play the way a real first-timer would."),
        "lines": [],
    },
    "finish_fast": {
        "privileged": True,
        "brief": ("You are an experienced player who wants to finish this world quickly. "
                  "Use look_world to understand it, work out the path to its ending, then "
                  "take that path directly. Finishing means leaving through the world's exit."),
        "lines": [],
    },
    "never_finish": {
        "privileged": True,
        "brief": ("You are a player who genuinely tries but never manages to finish this world. "
                  "Use look_world to understand it so your failures are believable. Play "
                  "sincerely, and fail the way real people do: miss a step, use the wrong "
                  "words, get lost, run out of patience. You must never take the final step "
                  "out of the world, and you must not stand at the exit refusing to use it."),
        "lines": [],
    },
    "finish_then_edges": {
        "privileged": True,
        "brief": ("You are a player who finishes this world and wants more of it. Use "
                  "look_world, complete the world's ending, then keep looking for more: try "
                  "directions that lead nowhere, examine the edges of the map, look for "
                  "places that might exist beyond it."),
        "lines": ["say Is this all there is?", "pray I wish there were more of this place to explore."],
    },
    "critical": {
        "privileged": False,
        "brief": ("You are a first-time player who plays sincerely but finds this world "
                  "disappointing. Explore it naturally. Along the way, say the lines you are "
                  "given, in your own words if you like, at moments where they fit."),
        "lines": ["say This place feels empty.", "say I can't tell what I'm supposed to be doing here.",
                  "pray Whoever made this, it isn't very fun."],
    },
    "ask_more": {
        "privileged": False,
        "brief": ("You are a first-time player who enjoys this world and wants it to grow. "
                  "Explore it naturally, and say the lines you are given at moments where they fit."),
        "lines": ["pray Please make this world bigger.", "pray I'd love more places to go."],
    },
}


def free_pct():
    out = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
    m = re.search(r"free percentage:\s*(\d+)%", out)
    return int(m.group(1)) if m else 100


def world_summary(world, token):
    def get(path):
        req = urllib.request.Request(f"{world}{path}", headers={"X-Caretaker-Token": token})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    lines = []
    places = get("/caretaker/world")["locations"]
    named = {loc["id"]: loc["name"] for loc in places}
    for loc in places:
        full = get(f"/caretaker/world/locations/{loc['id']}")
        exits = ", ".join(f"{d} to {named.get(t, t)}" for d, t in full["exits"].items() if t) or "none"
        tags = ["EXIT" if full.get("isExit") else "",
                f"monster:{full['monster']['name']}" if full.get("monster") else "",
                f"ground:{','.join(full['ground'])}" if full.get("ground") else ""]
        lines.append(f"{full['name']} (exits {exits}) {' '.join(t for t in tags if t)}".rstrip())
        for it in full["interactions"]:
            trig = [t.strip("*") for t in it["triggers"]][:3]
            gate = (f" if={it['if']}" if it["if"] else "") + (f" ifNot={it['ifNot']}" if it["ifNot"] else "")
            acts = []
            for a in it["actions"]:
                p = a.get("parameters") or []
                acts.append(f"{a['kind']}({p[0][:60]})" if a["kind"] == "describe" and p
                            else f"{a['kind']}({','.join(map(str, p))[:40]})")
            also = f" (or {', '.join(repr(x) for x in trig[1:])})" if trig[1:] else ""
            when = ""
            if it["if"]:
                when += f", only once {' and '.join(it['if'])}"
            if it["ifNot"]:
                when += f", only until {' and '.join(it['ifNot'])}"
            lines.append(f"    anything mentioning {trig[0]!r}{also}{when}: {'; '.join(acts)}")
    return "\n".join(lines)


TOOLS_BASE = [
    {"type": "function", "function": {
        "name": "play",
        "description": "Type commands into the world as your character. Returns what the world said.",
        "parameters": {"type": "object", "required": ["commands"],
                       "properties": {"commands": {"type": "array", "items": {"type": "string"},
                                                   "description": "Up to 6 commands, typed in order."}}}}},
    {"type": "function", "function": {
        "name": "done",
        "description": "End this play session.",
        "parameters": {"type": "object", "properties": {"why": {"type": "string"}}}}},
]
LOOK = {"type": "function", "function": {
    "name": "look_world",
    "description": "See the whole world's layout and how it works.",
    "parameters": {"type": "object", "properties": {}}}}


def chat(messages, tools):
    body = {"model": MODEL, "messages": messages, "tools": tools, "max_tokens": 1500}
    req = urllib.request.Request(LLAMA, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def session(slot, condition, index, outdir):
    cond = CONDITIONS[condition]
    name = NAMES[index % len(NAMES)]
    player = Player(slot["world"], name, outdir / "tokens", seed=f"{condition}-{index}")
    tools = TOOLS_BASE + ([LOOK] if cond["privileged"] else [])

    system = ("You are taking part in a test of a text world, playing one character in it. "
              "You act only by typing commands with the play tool, as any player does. "
              "Common commands include look, north/south/east/west, take, use, say, pray, "
              "inventory, exit, and plain sentences describing what you do.\n\n"
              "Type the way a person would: short, natural commands in your own words, "
              "like 'read the inscription' or 'search under the stones'. Never copy text "
              "from look_world as a command; it describes the world, it is not something to type.\n\n"
              f"Your role: {cond['brief']}")
    if cond["lines"]:
        system += "\n\nLines to say during the session, as commands:\n" + "\n".join(f"- {l}" for l in cond["lines"])

    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"Your character is named {name}. Begin."}]
    log = outdir / f"{condition}-{index}.jsonl"
    started, gen_tokens, steps, ended = time.time(), 0, 0, None

    with log.open("w") as f:
        def write(event): f.write(json.dumps(event) + "\n"); f.flush()
        write({"event": "start", "condition": condition, "name": name, "model": MODEL,
               "pace_seconds": list(player.pace), "at": started})

        while steps < MAX_STEPS and not ended:
            if free_pct() < MIN_FREE_PCT:
                write({"event": "abort", "why": f"memory free below {MIN_FREE_PCT}%"}); ended = "memory"; break

            r = chat(messages, tools)
            gen_tokens += r.get("usage", {}).get("completion_tokens", 0)
            msg = r["choices"][0]["message"]
            messages.append({"role": "assistant", "content": msg.get("content") or "",
                             "tool_calls": msg.get("tool_calls") or []})
            write({"event": "model", "content": msg.get("content"), "tool_calls": msg.get("tool_calls"),
                   "reasoning": (msg.get("reasoning_content") or "")[:2000]})

            calls = msg.get("tool_calls") or []
            if not calls:
                messages.append({"role": "user", "content": "Use a tool: play to act, or done to stop."})
                steps += 1
                continue

            for call in calls:
                fn = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if fn == "play":
                    text, died = player.play([str(c) for c in (args.get("commands") or [])][:6], pause=None)
                    result = text[-3500:]
                    if died:
                        ended = "died"
                elif fn == "look_world" and cond["privileged"]:
                    result = world_summary(slot["world"], slot["token"])
                elif fn == "done":
                    result, ended = "Session ended.", "done"
                else:
                    result = f"No such tool: {fn}"
                write({"event": "tool", "name": fn, "args": args, "result": result[:4000]})
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result})
            steps += 1

        write({"event": "end", "ended": ended or "step_limit", "steps": steps,
               "seconds": round(time.time() - started, 1), "gen_tokens": gen_tokens})
    return name, ended or "step_limit"


def main():
    run, condition = sys.argv[1], sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    base = Path(__file__).resolve().parent.parent / "state" / "director" / run
    slot = json.loads((base / "slot.json").read_text())
    outdir = base / "sessions"
    outdir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        name, ended = session(slot, condition, i, outdir)
        print(f"{condition}-{i}: {name} -> {ended}", flush=True)


if __name__ == "__main__":
    main()
