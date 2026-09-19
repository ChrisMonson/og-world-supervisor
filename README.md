# og-world-supervisor

The supervisor plane for [og-world](../og-world): everything the caretaker agent
must not be able to read or change.

This repository is private to the humans running the experiment. It is never
mounted writable into the agent's container, and the design notes here are never
copied into the world repo.

## Contents

```
docs/         design notes, the experiment's rationale, open questions
gate/         health contract and validation the agent cannot edit
archive/      preserved history, including og-world before its scrub
```

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
