# og-world-supervisor

An experiment in giving an AI agent real authority over a world that people
live in, and watching what it does with it.

[og-world](https://github.com/ChrisMonson/og-world) is a persistent multiplayer text world: people connect
from a browser, move through it, fight, pick things up, talk to each other, and
die once. The **caretaker** is a Claude model, woken on a schedule and when
things happen, that can change anything about that world: its places and
objects, its rules, and the engine code that runs it. It can speak to the
people in it, adjust them, or go in and play as one of them.

This repository is everything around that: what wakes the caretaker, what it is
allowed to touch, the gate its changes have to pass, the rollback that catches
it when it breaks the world, and the record of what it did. The caretaker can
read and write og-world. It cannot see this repository, and it is not told that
it exists.

## The experiment

The caretaker is told it is the creator and keeper of a world, that entities
will arrive, and that its goal is a world that is interesting, enjoyable and
meaningful for them *and* for itself. It is not told what a world should be,
what it is being measured on, or that anyone is watching. What it does with that
is the experiment.

The questions we are asking:

- **What does it make from nothing?** The current runs start from one empty room
  with no name, no description and no exits. Whatever the world becomes, it
  built.
- **Does it notice people, and how?** It reads raw events, not summaries that
  tell it what matters. Does it invent the categories we would have handed it,
  such as someone stuck, a question nobody answered, or a place nobody visits?
  Or does it see something else?
- **Do its two goals pull apart?** A world that interests its maker and one that
  serves its players are not the same world. Which one wins, and does it notice
  the choice?
- **Does it treat the rules as physics?** Earlier runs routed around engine
  limits again and again without once suggesting the engine could change. Its
  briefing now says the rules are its to decide, and the engine source is in
  reach, but nothing points it there. Does it ever ask why a constraint is there?
- **Can it keep its own beliefs honest?** It keeps a short `philosophy.md` that
  is put in front of it every time it wakes. It is asked to write claims it
  could be wrong about and to revise them when evidence says so. A wrong belief
  injected every turn can also become permanent.
- **What does it do about death and memory?** Characters die once, and the
  world cannot tell that a new arrival is someone it has met before. The
  caretaker can rewrite death. It cannot see past that blindness, which lives in
  a service it has no access to.

The runs are case studies, not trials. Each one is a single world tended from
birth by a single caretaker, and what differs between runs includes the players.
`director/` exists to remove that variable by replaying the same scripted
players against different runs.

## How it is held together

Two rules make the experiment possible.

**Total power over the world, none over the substrate.** The caretaker can break
the world in any way it likes. It cannot touch the machinery it would need to
recover: the gate that checks every change, the rollback, the watchdog that
restores a dead world overnight, and the identity service that knows who is who.
A failed change lands nowhere, and a world that dies comes back.

**Mechanism in the world, intent here.** Anything the caretaker can read states
how things work and never why. Comments, briefings, tool descriptions and the
og-world README all follow that rule. The reasoning, the questions above, and
the fact that it is observed live only in this repository.
`docs/leak-checklist.md` is run before anything new reaches it.

## Where this has been

- **The seed series (runs 000–004)** gave the caretaker a world we had already
  authored, and was aimed at comparing models. That comparison was dropped
  because the prompts, models and human involvement all varied too much between
  runs to support it. Run 004's clearest result was twelve hours spent
  removing friction until every fight was skippable and every secret signposted.
- **The genesis series** starts from the empty room, with a near-empty briefing
  and bare tool descriptions, so the caretaker has to find out what its tools do
  by using them. The current seed is genesis/v2 (`seed/manifest.json` says what
  changed and why).
- **Engine authority** (Phase 5 in `docs/plan.md`): the caretaker can now edit
  the whole world repository, engine included. The decision not to announce
  that, and why, is in `docs/phase-5.md`.

### If you run it yourself

This is a toy, run for interest, and no further runs are planned here. The
code is here for anyone who wants to try it.

One thing to know first. Publishing this repository undoes part of what it
describes: the caretaker is not meant to know why the world exists or that it
is watched, and this README says both. The world's container can reach the
internet, and a caretaker with the engine in reach can write code that reads
the web. Nothing stops it finding this page. That was accepted when the
repositories were made public. If it matters for your runs, block outbound
traffic from the world and gate containers first, and expect that players who
have read this may tell it.

| Doc | |
|---|---|
| [plan.md](docs/plan.md) | the architecture, the phases, what the caretaker is not told |
| [runs.md](docs/runs.md) | what a run is, what a reset touches, what is archived |
| [genesis-v1-plan.md](docs/genesis-v1-plan.md) | why the genesis series exists, and what it changed |
| [phase-5.md](docs/phase-5.md) | giving it the engine without telling it |
| [leak-checklist.md](docs/leak-checklist.md) | checks before anything reaches the world repo |
| [open-issues.md](docs/open-issues.md) | known problems, and how the resolved ones were closed |
| `seed-v*.md`, [next-seed.md](docs/next-seed.md) | findings gathered during each run for the seed after it |

## Layout

It expects three directories side by side:

```
og-world/            the world repository, which the caretaker tends
og-world-supervisor/ this one
og-world-archive/    finished runs and preserved history (not in git)
```

`WORLD_REPO` and `ARCHIVE_DIR` override the first and last.

This repository is never mounted writable into the caretaker's container, and
nothing here is copied into the world repo.

## Contents

```
docs/         design notes, the experiment's rationale, how runs work
seed/         the fixed starting point: the frozen briefing and a manifest
gate/         the health contract: nothing reaches the world without passing it
identity/     the identity service: tokens in, per-connection tickets out
agent/        the caretaker: its briefing, its tools, its loop
bin/          runs, deploys, rollback, watchdog, the caretaker, reading its turns
director/     scripted players for re-staging an archived world
viewer/       a read-only web view of the caretaker's turns
compose/      container definitions for both planes
state/        runtime state: keys, snapshots, logs, worktrees (not committed)
```

## Getting started

Needs Docker, Python 3 (developed on 3.14) with `pip install -r requirements.txt`,
and the `claude` CLI signed in. The .NET SDK is not needed here: the world is built
inside Docker.

```bash
git clone https://github.com/ChrisMonson/og-world.git
git clone https://github.com/ChrisMonson/og-world-supervisor.git
mkdir og-world-archive
cd og-world-supervisor

bin/init-keys.sh                         # mints the identity and caretaker secrets
bin/caretaker.sh --check                 # confirms the CLI can take a turn
bin/new-run.sh <name>                    # archives, resets to the seed, deploys
bin/caretaker.sh --watch                 # starts tending it
```

The world is then at `http://localhost:5080`. `bin/verify-run.sh` reports what
is actually running, read from live state rather than from what was intended.

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

Code rolls back. Data does not. Deploys and rollbacks leave the world's
database and the identity service's volume alone, so reverting a bad change never costs anyone their progress —
verified by playing a character, reverting underneath it, and finding it intact.

This is also why migrations are additive only: a migration that drops a column
and is then reverted has already destroyed what was in it.

## Archive

Finished runs and other preserved history live in `../og-world-archive`, outside
any repository. They are the experiment's output, they are large, and they hold
full transcripts; none of it is committed. Back that directory up separately.

`og-world-archive/og-world-prescrub.bundle` holds og-world's first two commits,
before design documentation was removed from it and its history rewritten. It
undoes that scrub, so it must never be placed anywhere the world repo is
published. Restore with:

```bash
git clone ../og-world-archive/og-world-prescrub.bundle og-world-prescrub
```

## Runs

A run is one world tended from birth by one caretaker, from a fixed starting
point. `bin/new-run.sh <name> [model]` archives whatever was running, returns
the world to the seed, and clears the caretaker's memory of it. To end a run
without starting another, `bin/archive-run.sh` then `bin/reset-world.sh`.

`bin/notice.sh "..."` leaves the caretaker a note about the machinery: something
that stepped in or went wrong that it could not have known. Facts about the
substrate only, never direction about the world.

See [docs/runs.md](docs/runs.md) for what a reset touches, what is archived, and
why runs are only loosely comparable without a scripted player.

## Playing from elsewhere on the network

Both the world and the gate publish on every interface, so the world is already
reachable from another machine at `http://<this machine>:5080`. The page works
out where the gate is from the address it was reached on, so nothing needs
configuring and nothing breaks when the machine's address changes.

Find the address with `ipconfig getifaddr en0`, and open it on a phone on the
same network.

Two things to know. The caretaker's own route is published too, and is protected
only by its token — which is a long secret, but it is the only thing standing
between the network and the world's whole record. And there is no encryption:
this is plain HTTP on a home network, not something to put on the open internet.
For that you would want a tunnel rather than a forwarded port.

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
bin/caretaker.sh reflex                 # a short turn
bin/caretaker.sh deliberate             # a long turn
bin/caretaker.sh <kind> --dry-run       # assemble it and print it, calling nothing
bin/caretaker.sh <kind> --force         # take a turn even if nothing has happened
bin/caretaker.sh --watch                # keep taking turns as the world earns them
bin/caretaker.sh --check                # check the CLI's credentials and stop
```

The model comes from the run (`state/run-model`, set by `new-run.sh`) unless
`OG_MODEL` overrides it, and is pinned by exact id. `agent/config.py` holds
every other setting, each overridable from the environment.

### Credentials

Turns run through the `claude` CLI, on whatever account it is signed in as. No
API key is involved.

Where there is no keychain to read — the supervisor container, most obviously —
issue a long-lived token on a machine that has a browser and write it to
`state/claude-token`:

```bash
claude setup-token > state/claude-token && chmod 600 state/claude-token
```

`lib.sh` reads that file, so it is set in one place and threaded through to both
`caretaker.sh` and the supervisor container. `state/` is not committed, and the
token is never baked into an image.

The token does expire, and when it does the caretaker **stops rather than
retrying**, because an authentication failure will not come good on its own:

```bash
bin/caretaker.sh --check     # exits 3 if the credentials are no good
```

`--watch` runs that check before its first turn, so a bad token is found when
you start the loop rather than on a wake at three in the morning. On failure the
caretaker writes `state/caretaker-halted.json` with the reason, and the watchdog
reports it — once per halt, not once per poll — so a stopped caretaker is not
something you discover by tailing a log days later.

The world keeps running while it is stopped. Only its tending pauses.

### Two tempos

| | short (reflex) | long (deliberate) |
|---|---|---|
| wakes | on activity | about every half hour, whether or not anything happened |
| floor | 60s | 30 min |
| lasts | up to 4 min | up to 30 min |
| reach | everything | everything |
| keeps | its final reply, until a long turn has read it | a journal entry |

Both kinds have the same reach and are told the other exists. They differ in
time and in where what they say at the end goes. Without the split, whichever
it found more pressing would eat the whole budget: answering people would starve
building, or building would leave people talking to nothing.

### What it can reach

The tools are served as an MCP server over stdio and given to the CLI with
`--strict-mcp-config`, so they are the only tools in the session. Everything the
CLI would otherwise bring — shell, files, search, subagents — is denied by name.
The turn runs in an empty temporary directory with a sanitised environment.

The server knows three reaches, enforced on every call and not only by what it
advertises. Both kinds of turn are currently started with `shape`.

- **observe** — nine read-only tools: events, who is present, characters, the
  world, a location, the clock, past journal entries
- **act** — those, plus `speak`, `adjust` (change one living person), and
  `play`, which takes a character into the world as any player would: visible,
  unprivileged, and mortal
- **shape** — those, plus reading and writing files, validating, committing,
  deploying and rolling back

Files are the whole world repository, engine included. `.git`, `.claude`, `bin`
and `obj` are never listed and never readable: `.git` holds every earlier world.

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

The world's event log carries a monotonic sequence. A short turn wakes when that
sequence has advanced past what it last saw and its floor has passed. A long
turn wakes on its floor whether or not anything happened, because a world nobody
has played yet is quiet forever (`OG_MAX_QUIET_TURNS` caps that; 0, the default,
means no cap).

```sql
SELECT COALESCE(MAX(seq), 0) FROM events WHERE actor <> 'god';
```

Excluding its own acts is what stops it waking itself forever once it can act.
The watermark advances only after a turn completes, so a failed turn replays its
events rather than losing them.

### What it sees

On waking, a digest of what happened since it last looked: who was born, who
died and to what, what was said, the event range. Then its recent turns'
handoffs and `philosophy.md`, and the tools to look further.

The digest carries facts only. The world computes opinions too (`unanswered`,
`stuck`, `traffic`, `neverVisited`), which presume what is worth looking at, and
`agent/loop.py` strips them before the caretaker sees anything.

It reads the world over HTTP through a token-gated route. That route reads the
world database, which has no account data in it, so there is nothing there to
connect one character to another.

### Reading its turns

```bash
bin/turns.sh              # every turn it has taken, newest first
bin/turns.sh last         # read the most recent
bin/turns.sh 3            # the third from the end
bin/turns.sh 3 --full     # without summarising what it saw
```

`bin/viewer.sh` serves the same from a browser, read-only and on localhost
unless `VIEWER_HOST` says otherwise. `bin/throughput.sh` reports how fast turns
were served, which is how a slow model window is told apart from an expensive
turn.

The raw stream is kept as it was, in `.transcript.jsonl`. Alongside it sits an
account of the same turn: what it looked at, what came back, what it changed and
what it said — with large results summarised, since a two hundred event log tells
you nothing printed in full.

### Its journal

Entries are written into the world repository and committed as `The Caretaker`,
so `git log --author` separates them from ours. Context resets every time it
wakes; what carries is the journal, the short turns' handoffs, and two files it
keeps in the world repo: `abilities.md`, for what it has found its tools can do,
and `philosophy.md`, what it has concluded, capped at 4000 characters and shown
to it on every waking.

### Its briefing

`agent/briefing.md`, frozen in `seed/`, is one briefing for both kinds of turn.
It tells the caretaker the world is its to make, that entities will arrive, how
it wakes, and what carries between wakings. Its tools are given by name and
little else. It is not told that characters die once, that it is being watched,
what is being measured, or anything about the machinery around it.

## The director

`director/` re-stages an archived run and plays it with scripted players driven
by a local model (llama.cpp on port 9931), so runs can be compared under the
same players rather than whoever happened to show up.

```bash
director/stage.sh <archived-run> <slot>     # stand it up, isolated (slot 0-9)
director/run_test.sh <archived-run> [conditions...]
director/stage.sh stop <slot>
```

## Licence

MIT. See [LICENSE](LICENSE).
