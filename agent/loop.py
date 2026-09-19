#!/usr/bin/env python3
"""The caretaker's turns.

Two tempos.

  reflex        wakes often, briefly, may speak and may help someone
  deliberate    wakes rarely, at length, may reshape the world, keeps a journal

Without the split, whichever the caretaker found more pressing would eat the
whole budget: answering people would starve building, or building would leave
people talking to nothing.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import config
import deploys
import driver
import journal
import wake
import world_client

AGENT_DIR = config.SUPERVISOR_DIR / "agent"


def briefing(kind):
    name = "briefing.md" if kind == "deliberate" else "briefing-reflex.md"
    return (AGENT_DIR / name).read_text()


def opening(kind, digest, mark, recent):
    parts = [
        f"You are waking at {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        f"You last looked at event {mark['seq']}. The world is now at event {digest['toSeq']}.",
        "",
        "What has changed since:",
        "",
        "```json",
        json.dumps(digest, indent=2, default=str),
        "```",
    ]

    if kind == "deliberate":
        standing = deploys.history(limit=10)
        parts += [
            "",
            "Where the world's history stands:",
            "",
            "```json",
            json.dumps(standing, indent=2, default=str),
            "```",
        ]

        stepped_in = deploys.intervention()

        if stepped_in:
            parts += [
                "",
                "Something had to step in since you last looked:",
                "",
                "```json",
                stepped_in,
                "```",
            ]

    if recent:
        parts += ["", "Your last entries, oldest first:", ""]
        for entry in recent:
            parts += [f"--- {entry['name']} ---", entry["text"].strip(), ""]
    elif kind == "deliberate":
        parts += ["", "You have not written anything yet. This is your first look at the world."]

    if kind == "deliberate":
        parts += [
            "",
            "Look into whatever is worth looking into, do what you judge worth doing,",
            "then write your journal entry as your final message. The entry is just",
            "your reply — do not wrap it in JSON or call a tool to save it.",
        ]
    else:
        parts += [
            "",
            "Decide whether anything here wants a response now. Then reply with one",
            "short line saying what you did, or that you let it be.",
        ]

    return "\n".join(parts)


def take_turn(kind, dry_run=False, force=False):
    reflex = kind == "reflex"

    should, reason, mark = wake.should_wake(reflex=reflex, force=force)
    print(f"[{kind}] wake: {reason}")

    if not should and not dry_run:
        return None

    digest = world_client.digest(since=mark["seq"])
    recent = journal.entries(limit=2 if reflex else 3)

    system = briefing(kind)
    first = opening(kind, digest, mark, recent)

    if dry_run:
        print("\n" + "=" * 72)
        print(f"SYSTEM ({kind})")
        print("=" * 72)
        print(system)
        print("\n" + "=" * 72)
        print("FIRST MESSAGE")
        print("=" * 72)
        print(first)
        print("\n" + "=" * 72)
        print(f"reach={'act' if reflex else 'shape'}  model={config.REFLEX_MODEL if reflex else config.MODEL}")
        print("=" * 72)
        return None

    started = time.time()

    try:
        outcome = driver.run(
            system_prompt=system,
            opening=first,
            reach="act" if reflex else "shape",
            model=config.REFLEX_MODEL if reflex else config.MODEL,
            timeout=config.REFLEX_TIMEOUT if reflex else config.DELIBERATION_TIMEOUT,
        )
    except driver.NotSignedIn as error:
        print(f"[{kind}] {error}", file=sys.stderr)
        raise SystemExit(3)
    except driver.TurnFailed as error:
        # A failed turn leaves the watermark alone, so its events come round again.
        print(f"[{kind}] turn failed: {error}", file=sys.stderr)
        return None

    record = {
        "kind": kind,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fromSeq": mark["seq"],
        "toSeq": digest["toSeq"],
        "elapsed": round(time.time() - started, 1),
        "turns": outcome["turns"],
        "cost": outcome["cost"],
        "text": outcome["text"],
    }

    if not reflex:
        record["journal"] = journal.write(outcome["text"] or "(nothing written)", digest["toSeq"])

    wake.write_watermark(digest["toSeq"], reflex=reflex)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    (config.TURN_DIR / f"{stamp}-{kind}.json").write_text(json.dumps(record, indent=2))

    print(f"[{kind}] {outcome['turns']} steps, {record['elapsed']}s")
    print(f"[{kind}] {outcome['text'][:400]}")

    return record


def main():
    parser = argparse.ArgumentParser(description="A turn of the caretaker.")
    parser.add_argument("kind", nargs="?", default="deliberate", choices=["reflex", "deliberate"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--watch", action="store_true")
    arguments = parser.parse_args()

    if not config.CARETAKER_TOKEN:
        print("CARETAKER_TOKEN is not set; the world will not answer.", file=sys.stderr)
        return 2

    if not arguments.watch:
        take_turn(arguments.kind, dry_run=arguments.dry_run, force=arguments.force)
        return 0

    print(f"watching: reflex every {config.MIN_REFLEX_INTERVAL}s at the soonest, "
          f"deliberation every {config.MIN_WAKE_INTERVAL}s at the soonest")

    while True:
        for kind in ("reflex", "deliberate"):
            try:
                take_turn(kind, dry_run=arguments.dry_run)
            except world_client.WorldError as error:
                print(f"world unreachable: {error}", file=sys.stderr)
            except Exception as error:
                print(f"[{kind}] turn failed: {error}", file=sys.stderr)

        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
