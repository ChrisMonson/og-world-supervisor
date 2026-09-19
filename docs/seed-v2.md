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

## Unresolved questions the caretaker has raised

- Does a living monster block movement? Nobody has ever tried to walk past one.
- What happens when an engine verb and an interaction both match? Established:
  the engine wins and the interaction never runs. Worth stating in the briefing
  or the actions reference rather than leaving to be discovered twice.
