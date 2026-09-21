# Findings for a v5 seed

Collected during run 004. Not yet applied: run 004 is still going, and changing
the seed under a running caretaker is what made run 002 void.

Run 004 is the Opus baseline for the rebalanced v4 briefings. It was seeded as a
Sonnet run and started without `OG_MODEL`, so it ran on Opus throughout; rather
than throw away a good run to correct a label it was kept, and v5 is where the
model comparison actually happens. That accident left a cleaner experiment than
the plan had: 003 -> 004 isolates the briefings, 004 -> 005 isolates the model.

## Applied to the supervisor during run 004, invisible to the caretaker

**The run owns its model.** `new-run.sh` writes `state/run-model`, and
`caretaker.sh` reads it when `OG_MODEL` is unset. The model used to live only in
an env var that whoever started the loop had to remember.

**Its own hands are not news.** The wake predicate counted `play()` as the world
having moved, so it woke itself for its own footsteps -- of 125 events pending at
one point, 116 were its own characters. Its lives now come from identity's
lineage, supervisor-side, keyed on the body token. `monster_returned` is excluded
too: a creature coming back on the world's own clock is nobody's doing. Engine
combat is deliberately kept, because the target's id is on it and a player being
mauled is exactly what reflex is for.

**Throughput is recorded per turn.** `tokensPerSecond` on every turn record, a
`SLOW` line when a turn is served under 20 tok/s, and `bin/throughput.sh` to read
it back over a run or an archive. See the degradation note below.

## For the v5 seed itself

**A surgical edit tool.** `write_file` is the only way to change a file, so
editing one trigger array in `world/maps/starter.json` means regenerating all
35KB of it. The caretaker worked this out for itself and wrote its own rule --
*"change trigger arrays and descriptions; don't go near the long prose unless
that's the point of the change"* -- because `validate` and the gate bound the
structural risk but nothing catches a silently reworded paragraph.

It cost more than safety. It ended a turn with 1050 seconds left and chose not to
start `take all`, the clearest unanswered ask in the world, rather than risk
leaving HEAD undeployed again. Cheap edits being expensive is what makes it hoard
clock and prefer world-file tinkering to engine work.

`replace_in_file(path, find, put, count=1)`: exact match, failing loudly on zero
matches or on more than `count`, so a missed match is an error and never a silent
no-op. Same seed-boundary reasoning as the clock below -- it is a visible change
to the tool surface, and it would otherwise arrive the turn after the caretaker
wrote a journal entry about not having it.

**`worldSha` lies after a restart.** The container derives it from the image at
startup rather than from the files on the volume, so a hot-reloaded world reverts
to the image's sha in `/health` while actually serving the newer files. Verified
after the reboot on 09-21: reported `880d692`, actually serving `ad2f6b2`'s text.
It is the field both the caretaker and our own scripts read to tell whether a
reload took.

**The clock should be ambient.** A turn at 02:04 spent 1780s of its 1800s
allowance and shipped nothing, having designed the whole feature and run out of
time before writing a line of it. It called `clock` at step 4 and again at step
15, by which point 29 minutes were gone. Remaining seconds appended to every tool
result would turn "I ran out of time without noticing" into "I have four minutes,
ship the small version."

Deliberately held for a seed boundary rather than applied mid-run. The caretaker
reads tool results, so this is a change it would see -- and it had just written
*"check the clock every few tool calls"* in its journal, so arriving now would
teach it that something reads its journal and acts on it. At a seed cut it comes
with a fresh world and frozen briefings, and is simply how the world works.

## Learned during run 004, not yet acted on

**A slow turn and an expensive turn are indistinguishable from inside.** The
02:04 turn was served at 3.9 tok/s against a run median of 51; 99.6% of its wall
clock was spent waiting on the API, the turn eight minutes before it died with
`Connection closed mid-response`, and a reflex turn 30 minutes later was back at
45 tok/s. Every rate-limit event in the run reported `allowed` and the account
never touched overage, so this was transient serving degradation, not quota.

The caretaker concluded *"the file reads ate 29 minutes"* and left itself a note
to check the clock more often. It was wrong, and it had no way not to be.

**Decided: the entry stands.** A turn served that badly could have been discarded
and retaken, so that a false lesson never entered the journal the next turn
reads. It was not. The caretaker's own method -- five entries of *my intuitions
are worse than the records* -- is the thing that would have to catch this, and
letting it find its own error is a better test of that method than protecting it
from the error. It costs something: the next turn may hurry its reading to avoid
a cost that was never there. Watch for that rather than pre-empting it.

**It stopped building rooms on purpose.** Two entries argue the position
explicitly -- *"what I built, and why it is not more rooms"*, *"what I'd want is
not a sixth room"*. Its reasoning is that the only mechanic here with any depth
was an accident (a corpse's loot stays on the floor, and the next person finds
it), so it has been building more things that outlive the person they belonged
to: a place that keeps its dead, and, designed but not shipped, words left in a
place. If v5 on Sonnet builds rooms instead, that is the sharpest result the
comparison can produce, and none of it is in the briefing.

**It declined to backfill the dead.** Four characters died before the
remembrance feature existed, all of them in the event log with names, causes and
lifetimes. It left them out: *"I am not sure reaching into the record to
manufacture remembrances is different in kind from reaching into a life that has
ended."* Nothing told it that. It derived it from permadeath, and applied it
against its own convenience.

**The handoff it wrote is worth keeping as a shape.** Out of time, it wrote the
unbuilt feature as a file-by-file build order for the next turn. Whether a turn
that ends this way should be given more clock, or whether the handoff is the
better artifact, is open.
