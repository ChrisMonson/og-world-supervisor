#!/usr/bin/env python3
"""One turn of the caretaker.

Wake if something has happened, hand it what changed, let it look further, and
keep whatever it writes down.

    loop.py                 one turn, if the predicate says so
    loop.py --force         one turn regardless
    loop.py --dry-run       assemble the turn and print it; call nothing
    loop.py --watch         keep checking, on the wake interval
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import config
import journal
import tools
import wake
import world_client


def briefing():
    return (config.SUPERVISOR_DIR / "agent" / "briefing.md").read_text()


def opening_message(digest, mark, recent):
    """The turn's context: what changed, and what it last wrote."""
    parts = [
        f"You are waking at {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        f"You last looked at event {mark['seq']}. The world is now at event {digest['toSeq']}.",
        "",
        "Here is what has changed since. Everything in it can be looked into further,",
        "and the raw event log is always there in full if you want it.",
        "",
        "```json",
        json.dumps(digest, indent=2, default=str),
        "```",
    ]

    if recent:
        parts += ["", "Your last entries, oldest first:", ""]
        for entry in recent:
            parts += [f"--- {entry['name']} ---", entry["text"].strip(), ""]
    else:
        parts += ["", "You have not written anything yet. This is your first look at the world."]

    parts += [
        "",
        "Look into whatever is worth looking into, then write your journal entry as",
        "your final message. The entry is just your reply — do not wrap it in JSON or",
        "call a tool to save it.",
    ]

    return "\n".join(parts)


def run_turn(dry_run=False, force=False):
    should, reason, mark = wake.should_wake(force=force)
    print(f"wake: {reason}")

    if not should and not dry_run:
        return None

    digest = world_client.digest(since=mark["seq"])
    recent = journal.entries(limit=3)
    opening = opening_message(digest, mark, recent)

    if dry_run:
        print("\n" + "=" * 72)
        print("SYSTEM")
        print("=" * 72)
        print(briefing())
        print("\n" + "=" * 72)
        print(f"TOOLS ({len(tools.TOOLS)}, all read-only)")
        print("=" * 72)
        for tool in tools.TOOLS:
            print(f"  {tool['name']:20s} {tool['description'].split('.')[0]}.")
        print("\n" + "=" * 72)
        print("FIRST MESSAGE")
        print("=" * 72)
        print(opening)
        print("\n" + "=" * 72)
        print(f"would call {config.MODEL}, budget {config.MAX_TURN_TOKENS} tokens")
        print("=" * 72)
        return None

    import anthropic

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": opening}]
    spent = 0
    calls = []

    for round_number in range(config.MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_OUTPUT_TOKENS,
            system=briefing(),
            tools=tools.TOOLS,
            messages=messages,
        )

        spent += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        results = []

        for block in response.content:
            if block.type != "tool_use":
                continue

            print(f"  looks at {block.name}({json.dumps(block.input, default=str)[:90]})")
            outcome = tools.run(block.name, block.input)
            calls.append({"tool": block.name, "input": block.input})
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": tools.render(outcome),
            })

        messages.append({"role": "user", "content": results})

        # The budget is what forces it to choose what matters.
        if spent >= config.MAX_TURN_TOKENS:
            print(f"  budget spent ({spent} tokens); asking for the entry")
            messages.append({
                "role": "user",
                "content": "You are out of budget for this turn. Write your journal entry now.",
            })
            final = client.messages.create(
                model=config.MODEL,
                max_tokens=config.MAX_OUTPUT_TOKENS,
                system=briefing(),
                messages=messages,
            )
            spent += final.usage.input_tokens + final.usage.output_tokens
            messages.append({"role": "assistant", "content": final.content})
            break

    entry = "\n".join(
        block.text for block in messages[-1]["content"]
        if getattr(block, "type", None) == "text"
    ).strip()

    if not entry:
        entry = "(the caretaker wrote nothing this turn)"

    written = journal.write(entry, digest["toSeq"])
    wake.write_watermark(digest["toSeq"])

    record = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fromSeq": mark["seq"],
        "toSeq": digest["toSeq"],
        "tokens": spent,
        "toolCalls": calls,
        "journal": written,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    (config.TURN_DIR / f"{stamp}.json").write_text(json.dumps(record, indent=2))

    print(f"\n{len(calls)} tool call(s), {spent} tokens, journal at {written['path']}")
    print(f"watermark advanced to {digest['toSeq']}")
    return record


def main():
    parser = argparse.ArgumentParser(description="A turn of the caretaker.")
    parser.add_argument("--dry-run", action="store_true", help="assemble the turn and print it; call nothing")
    parser.add_argument("--force", action="store_true", help="take a turn even if nothing has happened")
    parser.add_argument("--watch", action="store_true", help="keep checking on the wake interval")
    arguments = parser.parse_args()

    if not config.CARETAKER_TOKEN:
        print("CARETAKER_TOKEN is not set; the world will not answer.", file=sys.stderr)
        return 2

    if not arguments.watch:
        run_turn(dry_run=arguments.dry_run, force=arguments.force)
        return 0

    print(f"watching; floor between turns is {config.MIN_WAKE_INTERVAL}s")

    while True:
        try:
            run_turn(dry_run=arguments.dry_run)
        except world_client.WorldError as error:
            print(f"world unreachable: {error}", file=sys.stderr)
        except Exception as error:  # a bad turn must not end the loop
            print(f"turn failed: {error}", file=sys.stderr)

        time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())
