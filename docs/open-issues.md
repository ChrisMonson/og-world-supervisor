# Open issues

## Identity is reachable from the world container — blocking Phase 5

**What.** `IdentityStore` runs inside the world server, and `/identity` is mounted
into the world's container. It holds `accounts` (token → the character currently
being played) and `character_history` (every character a token has had).

**Why it matters.** The two-container plan puts the caretaker in the same
container as the world. Today that is harmless: the caretaker has thirteen HTTP
tools and no way to read a file. At Phase 5 it gains the ability to run code in
that container, and at that point it can open `identity.db` and read lineage
directly. Even without `character_history`, a process that can watch `accounts`
over time sees one token move from one character to the next.

That would not just weaken the veil, it would hand over exactly the fact the
world is built not to say.

**Not currently exploitable.** Phase 3's caretaker has no file access, no shell,
and no write tools at all. This is a gap in the design, not a live one.

**Fix before Phase 5.** Identity moves out of the world process into its own
service, with its own volume, in its own container:

- the world calls it for resolve / bind / clear, holding a secret that permits
  only those three
- lineage reads require a second secret, held only by the supervisor
- the world container never mounts the identity volume

Ripples into the gate (a candidate would need both containers up) and into
`deploy.sh` and `rollback.sh`. Roughly a day's work, and cheapest done as the
first piece of Phase 4, before anything has write authority.

**Interim.** Until then, do not give the caretaker file access, a shell, or
arbitrary code execution in the world container. That is the line Phase 5
crosses, which is why this is listed as blocking it.
