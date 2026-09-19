"""The caretaker's journal.

Entries live in the world repository and are committed as they are written, so
the record of what it was thinking sits in the same history as the world itself.
Nothing else it produces survives a turn.
"""

import subprocess
from datetime import datetime, timezone

import config

AUTHOR_NAME = "The Caretaker"
AUTHOR_EMAIL = "caretaker@og-world.invalid"


def _git(*args, check=True):
    return subprocess.run(
        ["git", "-C", str(config.WORLD_REPO), *args],
        capture_output=True, text=True, check=check,
    )


def entries(limit=5):
    """The most recent entries, newest last, as the caretaker left them."""
    if not config.JOURNAL_DIR.is_dir():
        return []

    files = sorted(config.JOURNAL_DIR.glob("*.md"))[-limit:]
    return [{"name": path.name, "text": path.read_text()} for path in files]


def write(text, seq):
    """Records an entry and commits it."""
    config.JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    path = config.JOURNAL_DIR / f"{stamp}.md"

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
        "path": str(path.relative_to(config.WORLD_REPO)),
        "committed": committed.returncode == 0,
        "detail": (committed.stderr or committed.stdout).strip()[:200],
    }
