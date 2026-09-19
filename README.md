# og-world-supervisor

The supervisor plane for [og-world](../og-world): everything the caretaker agent
must not be able to read or change.

This repository is private to the humans running the experiment. It is never
mounted writable into the agent's container, and the design notes here are never
copied into the world repo.

## Contents

```
docs/         design notes, the experiment's rationale, open questions
gate/         the health contract: nothing reaches the world without passing it
agent/        the caretaker: its briefing, its tools, its loop
bin/          deploy, promote, rollback, watchdog, caretaker
compose/      container definitions for both planes
archive/      preserved history, including og-world before its scrub
state/        runtime state: snapshots, logs, worktrees, watermark (not committed)
```

## The deploy cycle

```bash
bin/deploy.sh [ref]      # gate it, then make it live (default: proposed)
bin/promote.sh [seconds] # advance last-known-good, once it has held
bin/rollback.sh [ref]    # return to a known commit (default: last-known-good)
bin/watchdog.sh          # the deadman switch
```

The running world is always identifiable as a commit. `/health` reports it.

`deploy.sh` checks out the candidate into an isolated worktree, runs the gate
against it, and only then stops the world, snapshots its data, and starts the new
image. A failed gate leaves the live world untouched.

`last-known-good` is a ratchet: it advances only after a deploy has actually
held, so a green deploy is not yet a good one.

## The health contract

`gate/run-gate.sh`, in order:

1. Migrations are additive only
2. The image builds
3. The world's own tests pass
4. A candidate boots on empty data and answers `/health`
5. `gate/smoke.py` plays it over a websocket
6. It survives a soak with no unhandled exception

Step 3 is necessary but not sufficient: those tests live in the world repo and
can be changed by whoever proposes the change. Step 5 is the one that actually
gates, which is why it lives here and is mounted read-only. It drives the world
through its public websocket, so it keeps working across any internal rewrite.

This was verified by deleting the world's own test files and breaking movement in
the same commit: step 3 passed, step 5 caught it, and the live world never moved.

## The deadman switch

`watchdog.sh` polls `/health`. When the world is unresponsive past the grace
period and has not recovered, it reverts to `last-known-good` and leaves
`state/intervention.json` explaining what it did.

The grace period is deliberate: noticing and repairing its own breakage is the
caretaker's job and the more interesting outcome. The watchdog is there so the
world does not stay dead overnight while nobody is watching.

## What rolls back, and what does not

Code rolls back. Data does not. Deploys and rollbacks leave `/data` and
`/identity` alone, so reverting a bad change never costs anyone their progress —
verified by playing a character, reverting underneath it, and finding it intact.

This is also why migrations are additive only: a migration that drops a column
and is then reverted has already destroyed what was in it.

## Why the split

The agent gets read and write access to the world repo, and eventually to the
engine source inside it. Anything explaining *why* the world is built the way it
is — the gate, the rollback machinery, what the agent is not told, the fact that
it is being observed at all — belongs here instead.

Standing habit: **mechanism in the world repo, intent in this one.**

## Archive

`archive/og-world-prescrub.bundle` holds og-world's first two commits, before
design documentation was removed from it and its history rewritten. Restore with:

```bash
git clone archive/og-world-prescrub.bundle og-world-prescrub
```

## The caretaker

Read-only for now. It can look at the world and write in its journal; it has no
way to change anything.

```bash
bin/caretaker.sh --dry-run   # assemble a turn and print it, calling nothing
bin/caretaker.sh --force     # take a turn now
bin/caretaker.sh --watch     # keep checking on the wake interval
```

Needs `ANTHROPIC_API_KEY` for a real turn, and a token in
`state/caretaker-token` that deploys pass through to the world.

### Waking

The world's event log carries a monotonic sequence. It wakes when that sequence
has advanced past what it last saw and the floor between turns has passed:

```sql
SELECT COALESCE(MAX(seq), 0) FROM events WHERE actor <> 'god';
```

Excluding its own acts is what stops it waking itself forever once it can act.
The watermark advances only after a turn completes, so a failed turn replays its
events rather than losing them.

### What it sees

A digest of everything since it last looked — who was born, who died and to
what, what was said, what went unanswered, who is stuck, where people go, which
places nobody has walked into — and thirteen read-only tools to look further.

The digest is a starting view, never a filter. Every list reports the total it
was drawn from, and the raw event feed stays available unfiltered, so a summary
is never a wall.

It reads the world over HTTP through a token-gated route. That route reads the
world database, which has no account data in it, so there is nothing there to
connect one character to another.

### Its journal

Entries are written into the world repository and committed as `The Caretaker`,
so `git log --author` separates them from ours. The journal is the only thing
that carries between turns: context resets every time it wakes.

### Its briefing

`agent/briefing.md` tells it that it tends a world, how the world works, that
characters die once and for good, and that it can currently only observe. It
does not tell it that it is being watched, what is being measured, or anything
about the machinery around it.
