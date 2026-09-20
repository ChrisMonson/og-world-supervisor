# Findings for a v2 seed

Collected during run 001. Each is something the caretaker could not fix or could
not see from its own tier.

## Verified defects

**The terminal lost its input on every deploy.** *(fixed in run 001, 1f8ad4d)*
The client disabled its input on socket close and only re-enabled it when asked
for a name or told of a death. A reconnect that resumed a living character sent
neither. Every deploy therefore locked out everyone already in the world: they
could read what was happening and not answer it. This corrupted the caretaker's
picture of its own players — it recorded Cavil as having gone quiet and possibly
left, when in fact he had been muted by our own client.

**`unanswered` has a hole in it.** A command the engine recognises but that does
nothing — `use key` on a non-consumable, `attack` in an empty room — emits a
`command` event and nothing else. No interaction, no `unparsed_command`. The
caretaker found this twice, in two different lives, both times by reading a
single character's events line by line rather than from any digest. It is
described to the caretaker as "the closest thing you have to being spoken to
directly", and it cannot see the cases where the engine thinks it succeeded.

**`if` / `ifNot` are named differently in the read view.** The world view reports
them as `requires` and `forbids`, so there is no way to learn what to write in a
world file. The caretaker has now routed around condition flags twice rather
than risk shipping something broken, and has never tested them.

**Possession is unobservable to interactions.** Conditions are set only by
interactions, and interactions never see an item being picked up, so no
interaction can be gated on carrying something. The caretaker worked out this
limitation itself and shipped a deliberate soft gate instead, but noted it as
unresolved. A door that cannot require its key is a real gap in what the world
can express.

**Nothing distinguishes the world as authored from the world as running.**
`read_file` returns the world file; `location` returns live state; the two differ
the moment anyone plays, and no tool says so. On its third turn the caretaker
read the file, saw `door-unlock` enabled there, and recorded as fact that its own
deploy had re-locked a door a player had opened — "nothing a character does to
the world's shape survives me touching the world's shape". It had not. The
overlay preserved the unlock correctly, and the live state still showed it.

Left uncorrected in run 001 deliberately. The fix is in the tools, not the
world: name the difference in both tool descriptions, and have the file reader
say plainly that it shows what was written rather than what is currently true.

This is the first belief the caretaker has recorded that cannot self-correct.
The others were contradicted by the world sooner or later; this one it has no
reason to re-check, because it thinks it already knows.

**Its main perception tool truncates.** A raw `events` result is cut off at
20,000 characters before it reaches the caretaker. On its third turn it asked for
200 events and read about two thirds of them. It is told the result was cut and
to narrow the query, so this is not silent — but the tool it reaches for first,
on a busy world, is the one that will hand it a partial picture. Worth either
raising the cap for that one tool or making the digest the obvious first move
and the raw feed the drill-down.

## Unresolved questions the caretaker has raised

- Does a living monster block movement? Nobody has ever tried to walk past one.
- What happens when an engine verb and an interaction both match? Established:
  the engine wins and the interaction never runs. Worth stating in the briefing
  or the actions reference rather than leaving to be discovered twice.
