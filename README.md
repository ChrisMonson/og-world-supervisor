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
identity/     the identity service: tokens in, per-connection tickets out
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

## Identity

A visitor's browser holds a token. It exchanges that token for a **ticket**
directly with the identity service, and presents only the ticket to the world.
Redeeming a ticket tells the world which character belongs on this connection —
single use, different every connection, meaningless afterwards.

The world therefore holds nothing that joins one character to the next, which
stays true even once the caretaker can run code inside it.

```
browser  --token-->  identity          (POST /tickets)
browser  --ticket->  world             (websocket hello)
world    --ticket->  identity          (redeem / bind / release, world key)
supervisor --------> identity          (lineage, admin key)
```

`bin/init-keys.sh` mints all three secrets. The admin key stays in `state/` and
is never passed into a world container.

## The caretaker

```bash
bin/caretaker.sh reflex                 # a brief turn: may speak, may help someone
bin/caretaker.sh deliberate             # a full turn: may reshape the world
bin/caretaker.sh <kind> --dry-run       # assemble it and print it, calling nothing
bin/caretaker.sh --watch                # keep taking turns as the world earns them
```

Turns run through the `claude` CLI, on whatever account it is signed in as.
There is no API key involved. Where there is no keychain to read — the supervisor
container, most obviously — run `claude setup-token` once and put the result in
`CLAUDE_CODE_OAUTH_TOKEN`.

### Two tempos

| | reflex | deliberate |
|---|---|---|
| wakes | often, on activity | rarely |
| floor | 60s | 30 min |
| reach | look, speak, change a person | all of that, plus the world's files |
| keeps | nothing | a journal entry |

Without the split, whichever it found more pressing would eat the whole budget:
answering people would starve building, or building would leave people talking
to nothing.

Its reflex briefing says plainly that silence is the default and that speaking is
the exception it chooses to make. A world where a voice comes out of the air
every few minutes is a worse world than one where it almost never does.

### What it can reach

The tools are served as an MCP server over stdio and given to the CLI with
`--strict-mcp-config`, so they are the only tools in the session. Everything the
CLI would otherwise bring — shell, files, search, subagents — is denied by name.
The turn runs in an empty temporary directory with a sanitised environment.

Three reaches, and a turn is started with exactly one:

- **observe** — thirteen read-only tools
- **act** — those, plus speech and changing one living person
- **shape** — those, plus the world's data files, commit, deploy and rollback

The reach is enforced by the server, not only by which tools it advertises: a
call to something outside the current reach is refused. File paths are confined
to the world's data directory, so this tier cannot touch the engine.

### How a change reaches the world

The caretaker edits a git worktree on the `proposed` branch, checks its work
against the same validator the world uses, and commits with its reasons. Asking
to deploy runs the full health contract. A change that fails it lands nowhere
and the caretaker is told which check said no.

Acts are different: speech and adjustments take effect immediately, touch no
files, and are recorded in the world's own event log under their own actor — so
they sit in the same history as everything a player does, and never wake the
caretaker back up.

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
