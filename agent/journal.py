"""The caretaker's journal.

Entries live in the world repository and are committed as they are written, so
the record of what it was thinking sits in the same history as the world itself.
Nothing else it produces survives a turn.
"""

import subprocess
from datetime import datetime, timezone

import config
import workspace

AUTHOR_NAME = "The Caretaker"
AUTHOR_EMAIL = "caretaker@og-world.invalid"


def _root():
    """
    Entries are written in the working copy, on the same branch as the changes
    they explain, so a deploy carries the reasoning with the change.
    """
    return workspace.ensure()


def _git(*args, check=True):
    return subprocess.run(
        ["git", "-C", str(_root()), *args],
        capture_output=True, text=True, check=check,
    )


def _directory():
    return _root() / "journal"


def entries(limit=5):
    """The most recent entries, newest last, as the caretaker left them."""
    directory = _directory()

    if not directory.is_dir():
        return []

    files = sorted(directory.glob("*.md"))[-limit:]
    return [{"name": path.name, "text": path.read_text()} for path in files]


def write(text, seq):
    """Records an entry and commits it."""
    directory = _directory()
    directory.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    path = directory / f"{stamp}.md"

    header = f"# {stamp}\n\nWorld observed through event {seq}.\n\n"
    path.write_text(header + text.strip() + "\n")

    _git("add", str(path))

    committed = _git(
        "-c", f"user.name={AUTHOR_NAME}",
        "-c", f"user.email={AUTHOR_EMAIL}",
        "commit", "-q", "-m", f"Journal: {stamp}",
        check=False,
    )

    return {
        "path": str(path.relative_to(_root())),
        "committed": committed.returncode == 0,
        "detail": (committed.stderr or committed.stdout).strip()[:200],
    }
