# Runs

A run is one world, tended from birth by one caretaker, from a fixed starting
point. Runs are meant to be comparable: same world, same briefings, so that what
differs between them is the mind doing the tending.

## The seed

`seed/manifest.json` names everything that defines a starting point:

- the world repository at tag `seed/v1`
- the two briefings, frozen in `seed/`
- the default model

`bin/new-run.sh` refuses to start if `agent/briefing.md` or
`agent/briefing-reflex.md` differ from the frozen copies. A run taken from an
edited briefing cannot be compared with one taken from the original, and the
check exists so that is a deliberate act rather than something that happens by
drift.

**To change the seed**, edit the briefings or the world, tag `seed/v2`, copy the
briefings into `seed/`, and update the manifest. Do not quietly edit in place.

## Starting a run

```bash
bin/new-run.sh 002-sonnet sonnet
OG_MODEL=sonnet bin/caretaker.sh --watch
```

That archives whatever was running, puts the world back to the seed, clears
everything the caretaker had accumulated, and deploys. What is left is a world
nobody has played and a caretaker with no memory of having tended one.

## What a reset touches

| | |
|---|---|
| `og-data` volume | every event, character and the world's mutable overlay |
| `og-identity-data` volume | accounts, tickets, lineage — everyone becomes a stranger |
| `state/agent/` | both watermarks, turn records, transcripts |
| `state/notices.json`, `intervention.json` | machinery notes |
| `state/workspace` | the caretaker's working copy, removed so branches can move |
| `main`, `proposed`, `live`, `last-known-good` | all returned to the seed commit |
| `og-world:<sha>` images | pruned to the seed's |

Engine code, the gate, the identity service and the keys are untouched.

## What is archived, and why it matters

Before anything is destroyed, `archive/runs/<name>/` receives:

- `world.db` — **the whole directory**, not just the file. SQLite in WAL mode
  keeps recent writes in `world.db-wal`, and copying the file alone silently
  loses them. The first attempt at this archived 10 events out of 134.
- `identity/` — the lineage, which is the only record of which characters shared
  a player
- `journal/` — everything the caretaker wrote
- `turns/` — per-turn records and full transcripts
- `deploys.log`, `watchdog.log`, `notices.json`, `history.log`

The archive is the output of the experiment. A reset that does not archive first
destroys the thing the run was for.

## What a run does not inherit

A reset returns the world and clears the caretaker's memory, but the repository
keeps its history, and the caretaker's own commits are in it — authored under its
own name, with its reasons in the message.

A fresh caretaker asking what had been deployed would have been handed those:
not merely facts about a world it never saw, but the knowledge that someone
tended this place before it. That is a much larger thing to learn by accident.

So the history it is shown is scoped to its own run, from the seed tag forward.
A caretaker waking into a new world sees nothing, because nothing has happened in
it yet.

The repository's plumbing — `.git` above all — is never listed and never
readable, whatever the editable region is set to. This matters most at Phase 5,
when that region widens to the whole repository: `.git` holds every earlier
version of this world and of every world before it, and a file listing would
otherwise hand it over.

## Comparing runs

The uncontrolled variable is the players. Two runs where different people did
different things are not really comparable — you are measuring the players as
much as the caretaker.

For a controlled comparison, drive each run with a **scripted player**: a fixed
trace of arrivals, commands, prayers and deaths, replayed identically. The
harness in `gate/smoke.py` already drives characters over the websocket and is
most of the way to this. A trace that took people two days replays in minutes,
so several models can be run against the same world in an afternoon.

Without that, treat runs as case studies rather than as trials.

## Run 000

The pilot, taken before any of this existed. Kept for the record and not
comparable with anything: the world had been played by hand, the briefing has
since changed, and a fault in the world's history was corrected mid-run.
