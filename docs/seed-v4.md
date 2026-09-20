# Findings for a v4 seed

Collected during run 003. Not yet applied: run 003 is still going, and changing
the seed under a running caretaker is what made run 002 void.

## Already applied to agent/, pending a seed cut

**The caretaker was told about a budget that does not exist.** Its briefing
promised a budget of tokens, which stopped being true when turns moved to the
CLI. What actually ends a turn is a wall clock, and it knew nothing about that.
Both briefings now state the real limit, the opening message names it, and a
`clock` tool answers elapsed and remaining. `seed/` still holds the old text, so
`new-run.sh` will refuse to start until v4 is cut.

## To apply

**The terminal turns off capitalisation and spellcheck.** `index.html` sets
`autocapitalize="none" spellcheck="false"` for a terminal feel, which makes
prayers and speech arrive as lowercase runs of words — and those are the lines
people write most carefully. Turn both on.

Leave `autocorrect="off"`. The engine matches item and creature names, and a
phone confidently replacing a fantasy word with a real one is not something the
caretaker's near-miss matching can rescue: it corrects typos, not confident
substitutions.

**A turn can hang without the timeout firing.** The deadline is only checked when
a line arrives on the CLI's stdout, so a process that produces no output at all
blocks forever in the read loop. Needs a watchdog that kills on the deadline
regardless of output.

**`speak` and `adjust` say nothing when their target has left.** Both silently
succeed against a character who is no longer in the world. The caretaker healed a
departed player into the void, then routed another player to meet her, and only
found out by calling `present` afterwards. It wrote itself a rule about checking
first; the tools should simply say so.

**Deliberation can now fire on a quiet world.** *(applied)* Both loops shared a
wake predicate that needed a player event, so the caretaker could never take a
building turn on an empty world however long its list of things to build.

The gate existed for the quick turns, which run up to 1440 times a day and would
otherwise spend most of that waking for nothing. The long turns are capped at 48
a day by their floor, and a world with nobody in it is still a world worth
tending. They now wake on the floor alone; the quick turns still need something
to have happened.

**Interactions that stop answering.** A `once` interaction goes mute after it
fires, so a player who repeats themselves is talking to nothing. Hit twice in one
run: the camp's cold-ashes line masking the firepit, and the cairn's trade after
it completed. Both were patched by voice. Worth a way for a spent interaction to
leave something behind that still answers.
