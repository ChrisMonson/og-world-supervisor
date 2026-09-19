# Implementation plan

## Premise

A persistent multiplayer text world, tended by an AI agent with real authority
over it. The agent can edit world data and, eventually, the engine. It perceives
the world through an event log and acts through a gated deploy cycle. The
experiment is what it does with that.

## Architecture

Three services, and a rule about which may know what:

- **identity** — exchanges a visitor's token for a per-connection ticket. Its own
  container, its own volume, built from this repo. The world never sees a token.
- **world** — gameplay, and eventually the caretaker's own code. Assumed broken
  at any moment.
- **supervisor** — git, the gate, deploy, rollback, the deadman switch, the
  caretaker's scheduling. What survives the world breaking.

Two planes, which never share a process:

- **World plane** — the engine and the agent loops. Fully agent-writable.
- **Supervisor plane** — git, the build, the health gate, deploy, rollback, the
  deadman switch, and the agent's scheduling. Read-only to the agent.

The agent's power over the world is total; its power over the substrate is zero.
It must never be able to break the machinery it would need to repair itself.

## Three tiers of change

| Tier | Example | Path | Latency |
|---|---|---|---|
| Ephemeral | answering a prayer, ambient text | runtime, live | immediate |
| Data | new location, item, puzzle | commit → validate → hot reload | seconds |
| Code | new verb, engine change | commit → build → health gate → swap | ~a minute |

## Phases

- **0 — Core** *(done)*. Session-scoped engine, data-driven items and monsters,
  event log, validator, console runner.
- **1 — Server** *(done)*. ASP.NET Core + WebSocket, SQLite persistence, web
  terminal client. Single-threaded world mutation.
- **2 — Supervisor** *(done)*. Containers, git-driven deploy, health contract,
  deadman switch, additive-only migration gate. Proven with human commits first.
- **3 — Agent, read-only** *(done)*. Query interface, digests, journal, wake
  predicate. It observes and writes notes; no write tools. Establishes a
  baseline of what it notices before it can change anything.
- **4 — Agent, world authority**. Tier 1 and 2 tools, the two loops.
- **5 — Engine authority**. Action-provider plugin seam, then the full engine.

## Health contract

Read-only to the agent. Mounted `:ro` so "it can't edit its own gate" is enforced
by the filesystem, not by instruction.

1. Solution builds
2. Every world file loads and passes the validator
3. Harness: boot, two bots connect, move, fight, take an item, disconnect,
   reconnect, state intact
4. 60-second soak, no unhandled exception
5. `/health` reports the running commit SHA

## The wake predicate

```sql
SELECT MAX(seq) FROM events WHERE actor != 'god';
```

Wake if that exceeds `lastSeenSeq` and the interval floor has elapsed. Advance
the watermark only after a successful turn, so a crashed turn replays rather than
drops. Excluding the god's own events is what stops a self-sustaining loop.

## What the caretaker is not told

The agent perceives the world completely and the substrate not at all.

- Characters are mortal and singular. There is no account field on a character or
  on any event, and no table in the world database links a character to whoever
  played it. That mapping lives in the connection layer, supervisor-side.
- Inference is fair game and is not defended against. Reused names, habits, timing
  and routes will all leak continuity, and a player who wants to be recognised
  across lives can simply say so. What the world will not do is tell it.
- This includes prose. Engine comments, the agent's briefing, and anything else it
  can read must state mechanisms without explaining the intent behind them.
- These design notes live here and never in the world repo. The agent gets read
  access to that repo, and this document explains the experiment it is inside of.
- Its briefing tells it that it tends a world and that characters die once. It
  does not mention that it is being watched, what is being measured, or that the
  same hands return under new names.

## Standing constraints

- **World state and player state roll back independently.** Player saves are not
  in git. Reverting a bad engine change must not cost anyone their progress.
- **Migrations are additive-only.** `ADD` and `CREATE` are allowed; `DROP`,
  renames and type narrowing are rejected by the gate. Code rolls back; data
  does not.
- **Everything shown to a player is escaped.** Both player speech and the
  agent's own output are untrusted input to a browser.
- **Every piece of mutable state declares a scope.** World or character. Getting
  this wrong produces a world that looks shared but isn't.
- **Death is final.** A character dies once and drops what it carried where it
  fell. Playing on means a new character, sharing nothing with the last — no
  inventory, no flags, no quest progress, no id.
