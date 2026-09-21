"""The files that cross between one waking and the next.

It wakes with no memory. The journal holds what happened; these two hold what it
worked out. `abilities.md` is where it records what its tools actually do, which
matters because they are given to it by name and little else. `philosophy.md` is
what it has concluded, and it is put in front of it every time it wakes.

The cap on `philosophy.md` is the point rather than a limitation. Unbounded, it
would grow until it crowded out the digest and stopped being curated. Bounded,
keeping something means choosing to drop something else.
"""

import config
import workspace

PHILOSOPHY = "philosophy.md"
ABILITIES = "abilities.md"


def _read(name):
    try:
        path = workspace.ensure() / name
        return path.read_text() if path.exists() else ""
    except OSError:
        return ""


def philosophy():
    """What it concluded last time, as much of it as the cap allows."""
    text = _read(PHILOSOPHY)

    if len(text) <= config.PHILOSOPHY_LIMIT:
        return text, False

    return text[:config.PHILOSOPHY_LIMIT], True


def abilities_size():
    return len(_read(ABILITIES))
