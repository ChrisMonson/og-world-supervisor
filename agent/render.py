#!/usr/bin/env python3
"""Turning a turn's raw stream into something a person can read.

The raw .jsonl is kept as it was. This renders the same thing as an account of
what the caretaker did: what it looked at, what it found there, what it changed,
and what it said — with the large results summarised rather than dumped, since a
two-hundred-event log tells you nothing when it is printed in full.

    render.py <transcript.jsonl>          print it
    render.py <transcript.jsonl> --full   don't summarise tool results
"""

import json
import sys
from pathlib import Path

TOOL_PREFIX = "mcp__caretaker__"

# Tools whose results are worth reading in full: they are short, and the detail
# is the point.
ALWAYS_FULL = {"validate", "commit", "deploy", "speak", "adjust", "rollback", "changes"}


def summarise(name, body):
    """A line or two saying what came back, instead of the whole of it."""
    text = body.strip()

    if not text:
        return "(nothing)"

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # A large result is cut off before it reaches the model, which leaves the
        # JSON unparseable. Say what it was rather than showing its first brace.
        if "truncated at" in text[-200:]:
            return f"{len(text)} characters, cut off before it was read in full"

        first = text.splitlines()[0]
        return first[:300] + (" …" if len(text) > 300 else "")

    if isinstance(data, dict) and "error" in data:
        return f"error: {data['error']}"

    # A deploy's answer is a whole gate run. The verdict is the part worth reading.
    if name == "deploy" and isinstance(data, dict):
        lines = [line.strip() for line in (data.get("output") or "").splitlines()]
        verdict = [line for line in lines
                   if "PASS" in line or "FAIL" in line or "smoke checks" in line or "live:" in line]
        head = "deployed" if data.get("deployed") else "REFUSED"
        return head + "\n" + "\n".join(verdict[-5:])

    if name in ("write_file", "commit") and isinstance(data, dict):
        return json.dumps(data)

    if name in ALWAYS_FULL:
        return json.dumps(data, indent=2)[:1200]

    if isinstance(data, dict) and "events" in data:
        events = data["events"]
        kinds = {}
        for event in events:
            kinds[event["type"]] = kinds.get(event["type"], 0) + 1
        span = f"{events[0]['seq']}–{events[-1]['seq']}" if events else "none"
        shape = ", ".join(f"{count} {kind}" for kind, count in
                          sorted(kinds.items(), key=lambda pair: -pair[1])[:6])
        note = f"  (of {data['total']} matching)" if data.get("truncated") else ""
        return f"{len(events)} events, seq {span}{note}\n{shape}" if events else "no events"

    if isinstance(data, list):
        if not data:
            return "empty"

        first = data[0]

        if isinstance(first, dict):
            for key in ("name", "text", "characterId", "id"):
                if key in first:
                    sample = [str(row.get(key, ""))[:48] for row in data[:6]]
                    more = f" … and {len(data) - 6} more" if len(data) > 6 else ""
                    return f"{len(data)}: " + "; ".join(sample) + more

            return f"{len(data)} rows"

        return f"{len(data)}: " + ", ".join(str(row)[:40] for row in data[:8])

    if isinstance(data, dict):
        if "locations" in data and isinstance(data["locations"], list):
            return (f"the whole world: {len(data['locations'])} places, "
                    f"{len(data.get('items', []))} kinds of thing")

        if "actions" in data:
            return f"{len(data['actions'])} action kinds, {len(data.get('notes', []))} notes"

        if "id" in data and "interactions" in data:
            return (f"location {data['id']} ({data.get('name')}): "
                    f"{len(data['interactions'])} interactions, "
                    f"monster={(data.get('monster') or {}).get('name')}")

        if "snapshot" in data:
            snap = data["snapshot"]
            return (f"{data.get('name')}: alive={data.get('alive')}, "
                    f"at {snap.get('locationId')}, "
                    f"{snap.get('hitPoints')}/{snap.get('maxHitPoints')} hp, "
                    f"carrying {snap.get('inventory')}")

        if "content" in data and "path" in data:
            return f"{data['path']}, {len(data['content'])} characters"

        keys = ", ".join(list(data)[:8])
        return f"{{{keys}}}"

    return str(data)[:300]


def render(events, full=False):
    out = []
    step = 0

    for event in events:
        kind = event.get("type")

        if kind == "assistant":
            for block in (event.get("message", {}).get("content") or []):
                block_type = block.get("type")

                if block_type == "thinking" and block.get("thinking", "").strip():
                    out += ["", "> *thinking*", "", block["thinking"].strip(), ""]

                elif block_type == "text" and block.get("text", "").strip():
                    out += ["", block["text"].strip(), ""]

                elif block_type == "tool_use":
                    step += 1
                    name = block.get("name", "").replace(TOOL_PREFIX, "")
                    arguments = block.get("input") or {}

                    if name == "write_file":
                        shown = f"path={arguments.get('path')}, {len(arguments.get('content',''))} characters"
                    else:
                        shown = json.dumps(arguments, default=str)
                        if len(shown) > 240:
                            shown = shown[:240] + " …"

                    out += [f"**{step}. {name}** · `{shown}`"]

        elif kind == "user":
            for block in (event.get("message", {}).get("content") or []):
                if block.get("type") != "tool_result":
                    continue

                body = block.get("content")

                if isinstance(body, list):
                    body = "".join(part.get("text", "") for part in body if isinstance(part, dict))

                body = str(body or "")
                shown = body[:4000] if full else summarise(_last_tool(events, block.get("tool_use_id")), body)

                indented = "\n".join("    " + line for line in shown.splitlines())
                out += [indented, ""]

        elif kind == "rate_limit_event":
            info = event.get("rate_limit_info") or {}
            if info.get("status") != "allowed":
                out += [f"> rate limit: {info.get('status')}", ""]

    return "\n".join(out).strip() + "\n"


def _last_tool(events, tool_use_id):
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in (event.get("message", {}).get("content") or []):
            if block.get("type") == "tool_use" and block.get("id") == tool_use_id:
                return block.get("name", "").replace(TOOL_PREFIX, "")
    return ""


def header(path, events):
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    name = Path(path).name.replace(".transcript.jsonl", "")
    when, _, kind = name.rpartition("-")

    bits = [f"# {kind} turn · {when}"]

    if result:
        seconds = round((result.get("duration_ms") or 0) / 1000, 1)
        bits.append(f"{result.get('num_turns')} steps · {seconds}s")

    return "\n".join(bits) + "\n"


def load(path):
    events = []

    for line in Path(path).read_text().splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") != "stream_event":
            events.append(event)

    return events


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    path = sys.argv[1]
    full = "--full" in sys.argv
    events = load(path)

    print(header(path, events))
    print(render(events, full=full))
    return 0


if __name__ == "__main__":
    sys.exit(main())
