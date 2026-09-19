# Open issues

## Resolved

### Identity was reachable from the world container

*Closed. The world no longer holds any of it.*

`IdentityStore` ran inside the world server and `/identity` was mounted into the
world's container, holding token to character and a full lineage table. Harmless
while the caretaker had only HTTP read tools; a direct handover of lineage once
it could run code there.

Identity is now its own service, in its own container, on its own volume, built
from the supervisor repo so the caretaker cannot edit it either.

A browser exchanges its token for a **ticket** directly with that service. Only
the ticket reaches the world. Redeeming it says which character belongs on this
connection and nothing more, it is single use, and it is different for every
connection — so nothing the world sees joins one life to the next.

Two keys: the world holds one that permits redeem, bind and release only.
Lineage needs a second, which lives in `state/identity-admin-key` and is never
passed into any world container. Verified: the world's key returns 401 on
`/lineage`, in either header.

This holds even at Phase 5, when the caretaker can run code in the world
process, because there is nothing there to find. Tokens never arrive.
