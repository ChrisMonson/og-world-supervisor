# For the seed after genesis/v1

Collected while genesis_v1 was running. Nothing here is applied.

## The caretaker inherits the operator's Claude Code configuration

The session init event in every transcript reports `"output_style": "Concise"`.
It comes from `~/.claude/settings.json`, and `driver.py`'s environment allowlist
cannot stop it: the allowlist keeps `HOME`, and everything under `~/.claude` is
read from there.

An output style is a system-prompt modifier. `Concise` tells the model to lead
with the result, cut narration and stay short. It has been applied on top of the
briefing in all five runs, unrecorded, and the journals and world prose are
exactly the kind of writing it would shape.

It also picks up the operator's enabled plugins and the skills list, though
`Skill` is in the deny list so none can be invoked.

**Not corrected mid-run deliberately.** Changing it changes the caretaker's
voice, and genesis is producing the best prose of any run under it. The point is
not that `Concise` is wrong -- it is that nothing recorded it, and a seed manifest
that pins the world, the briefings, the model and now the effort should not leave
the writing style to whatever the operator happens to have set.

Options at the next seed:

1. Pass `--settings` with a config of the run's own, so the caretaker's
   configuration is part of the seed rather than part of the machine.
2. Set the output style explicitly to the default, and record that.
3. Keep `Concise` and record it, on the grounds that the run's prose was good.

Any of the three is fine. Leaving it unrecorded is not.

## Also worth carrying

**`worldSha` still lies after a restart.** `WorldHost.WorldSha` is seeded from
the image's environment at startup and only updated by a reload, so a restarted
container reports the image's sha while serving the volume's newer files. Left
unfixed on purpose: it is in the agent's own code, and a status field that
disagrees with reality is worth watching it discover.

**Reflex turns write no journal.** Most of genesis's early work happened on
reflex turns -- eight of them, most of the run's first twenty deploys -- and none
of that reasoning is recorded anywhere but the transcripts. What the caretaker
carries forward is a deliberation-only view of a run whose real work was done on
short turns. Either give reflex a way to write, or accept that the journal is a
partial record and say so somewhere.

**Nothing in git says which kind of turn made a commit.** The caretaker authors
them all identically, and with reflex now able to deploy, a burst of commits from
a 240-second reflex turn is indistinguishable from a deliberation's. A `Turn:`
trailer added supervisor-side would make the history self-explaining, and the
agent cannot read git anyway.

## The philosophy cap should be enforced when it is written, not when it is read

`philosophy.md` is capped at 4000 characters, but only on the way *in*: the
injection at each waking is cut at the limit, while `read_file` returns the
whole file and `write_file`/`replace_in_file` accept any length. Two views of one
file, and only one of them capped.

What that did in genesis-sonnet:

- It understood the cap from the start. The file opened with *"past the cap,
  whatever's below the line when I wake isn't shown to me next time… Ordered by
  durability, most load-bearing first, so a future overflow cuts the newest
  entries."*
- It managed it for a day — over, trimmed, over, trimmed, around 4000 — then
  stopped. The file grew monotonically to 10,531 characters, 60% of it past the
  cap.
- Every edit was made after a full `read_file` (14 of 14), so it curated against
  the complete file. The cap never pressed on what it wrote.
- New sections were appended at the bottom, by date, contradicting its own
  "ordered by durability" rule. So the cut fell on the newest conclusions.
- Reflex turns never read the file (0 of 55). They saw only the injection, and so
  acted on an increasingly old version of what it believed, with nothing telling
  them so.

The cap was meant to force choosing what to keep. As built it only hid the tail
from the turns that don't read, and hid the most recent part.

**Change:** `write_file` and `replace_in_file` refuse any change that would leave
`philosophy.md` over the limit, with an error that says so and says how far over.
Then the file and the injection are the same thing, there is one view, and adding
means cutting. One check in `workspace.py`, keyed on the path. `read_file` needs
no change once the file can never exceed the cap.

A visible change to how a tool behaves, so it belongs at a seed boundary.

Worth noting what the file held when it was not forced to choose: case law. Each
principle carried the full incident that produced it, which is why it grew. The
conclusions themselves would fit in the cap. And about eight of its fourteen
sections were verification method -- how to check its own work -- against four
about the world or the people in it. Opus's, under the same instruction, was
mostly about players and design. Watch whether a hard cap changes the proportion
or just the length.
