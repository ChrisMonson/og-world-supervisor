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

import carried
import config
import deploys
import driver
import journal
import wake
import world_client

AGENT_DIR = config.SUPERVISOR_DIR / "agent"


def halt(reason):
    """
    Leaves a note saying why the caretaker stopped, where something other than a
    log tail will find it.
    """
    config.HALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.HALT_FILE.write_text(json.dumps({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason": reason,
    }, indent=2))


def clear_halt():
    config.HALT_FILE.unlink(missing_ok=True)


def briefing(kind):
    name = "briefing.md" if kind == "deliberate" else "briefing-reflex.md"
    return (AGENT_DIR / name).read_text()


def opening(kind, digest, mark, recent):
    limit = config.REFLEX_TIMEOUT if kind == "reflex" else config.DELIBERATION_TIMEOUT

    parts = [
        f"You are waking at {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        f"This turn is cut off after {limit} seconds. Ask `clock` for what is left.",
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
            "What has been done to the world so far:",
            "",
            "```json",
            json.dumps(standing, indent=2, default=str),
            "```",
        ]

        for notice in deploys.notices():
            parts += [
                "",
                f"Noted by the machinery around the world, at {notice['at']}:",
                "",
                notice["text"].strip(),
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

    concluded, clipped = carried.philosophy()

    if concluded.strip():
        parts += ["", "From philosophy.md, which you wrote:", "", concluded.strip()]

        if clipped:
            parts += ["", "(That is the cap. The rest of the file was cut off here.)"]

    size = carried.abilities_size()
    parts += ["", f"abilities.md holds {size} characters." if size
              else "abilities.md is empty."]

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
        print(f"reach=shape  model={config.REFLEX_MODEL if reflex else config.MODEL}")
        print("=" * 72)
        return None

    started = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    transcript = config.TURN_DIR / f"{stamp}-{kind}.transcript.jsonl"

    try:
        outcome = driver.run(
            transcript_path=str(transcript),
            system_prompt=system,
            opening=first,
            # The same reach on both kinds of turn: a short turn is short, not
            # smaller. What it may do is bounded by the clock and nothing else.
            reach="shape",
            model=config.REFLEX_MODEL if reflex else config.MODEL,
            timeout=config.REFLEX_TIMEOUT if reflex else config.DELIBERATION_TIMEOUT,
        )
    except driver.NotSignedIn as error:
        halt(str(error))
        print(f"[{kind}] {error}", file=sys.stderr)
        raise SystemExit(3)
    except driver.TurnFailed as error:
        # A failed turn leaves the watermark alone, so its events come round again.
        print(f"[{kind}] turn failed: {error}", file=sys.stderr)
        return None

    api_seconds = (outcome.get("api_ms") or 0) / 1000
    output = outcome.get("output_tokens") or 0
    rate = round(output / api_seconds, 1) if api_seconds else None

    record = {
        "kind": kind,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fromSeq": mark["seq"],
        "toSeq": digest["toSeq"],
        "elapsed": round(time.time() - started, 1),
        "turns": outcome["turns"],
        "cost": outcome["cost"],
        "model": config.REFLEX_MODEL if reflex else config.MODEL,
        "effort": config.EFFORT,
        "apiSeconds": round(api_seconds, 1),
        "outputTokens": output,
        "tokensPerSecond": rate,
        "rateLimit": outcome.get("rate_limit"),
        "text": outcome["text"],
        "transcript": transcript.name,
    }

    if not reflex:
        record["journal"] = journal.write(outcome["text"] or "(nothing written)", digest["toSeq"])

    # A turn taken on an empty world counts toward the run of quiet turns;
    # anything a player does resets it.
    quiet = 0 if reflex or digest["toSeq"] > mark["seq"] else mark.get("quietTurns", 0) + 1
    wake.write_watermark(digest["toSeq"], reflex=reflex, quiet_turns=quiet)

    (config.TURN_DIR / f"{stamp}-{kind}.json").write_text(json.dumps(record, indent=2))

    clear_halt()

    print(f"[{kind}] {outcome['turns']} steps, {record['elapsed']}s, "
          f"{rate if rate is not None else '?'} tok/s, transcript at {transcript.name}")

    # Said plainly, because a turn that ran at a crawl is not a turn that went
    # badly, and next morning the two are indistinguishable without this line.
    if rate is not None and rate < config.SLOW_TOKENS_PER_SECOND:
        share = api_seconds / record["elapsed"] if record["elapsed"] else 0
        standing = (outcome.get("rate_limit") or {}).get("status", "unreported")
        print(f"[{kind}] SLOW  served at {rate} tok/s against a floor of "
              f"{config.SLOW_TOKENS_PER_SECOND}; {api_seconds:.0f}s of the turn's "
              f"{record['elapsed']}s was spent waiting on the API ({share:.0%}), "
              f"account standing {standing}. Nothing the caretaker did explains this.",
              file=sys.stderr)
    print(f"[{kind}] {outcome['text'][:400]}")

    return record


def main():
    parser = argparse.ArgumentParser(description="A turn of the caretaker.")
    parser.add_argument("kind", nargs="?", default="deliberate", choices=["reflex", "deliberate"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="check the CLI's credentials and exit")
    arguments = parser.parse_args()

    if arguments.check:
        try:
            driver.check_credentials()
            clear_halt()
            print("credentials are good")
            return 0
        except driver.TurnFailed as error:
            if isinstance(error, driver.NotSignedIn):
                halt(str(error))
            print(error, file=sys.stderr)
            return 3

    if not config.CARETAKER_TOKEN:
        print("CARETAKER_TOKEN is not set; the world will not answer.", file=sys.stderr)
        return 2

    if not arguments.watch:
        take_turn(arguments.kind, dry_run=arguments.dry_run, force=arguments.force)
        return 0

    # Find out about credentials now, not on the first wake in the small hours.
    if not arguments.dry_run:
        try:
            driver.check_credentials()
            clear_halt()
            print("credentials are good")
        except driver.NotSignedIn as error:
            halt(str(error))
            print(error, file=sys.stderr)
            return 3
        except driver.TurnFailed as error:
            print(f"could not check credentials: {error}", file=sys.stderr)
            return 3

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
