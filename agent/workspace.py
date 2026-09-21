"""The caretaker's working copy of the world.

A git worktree on the proposed branch. Changes are written here, checked, and
committed; nothing here is live until a deploy passes the gate.
"""

import subprocess
from pathlib import Path

import config

WORKSPACE = config.STATE_DIR.parent / "workspace"

# Everything the world is made of.
EDITABLE = ""

# Never listed and never readable, whatever the editable region is set to. The
# repository's own plumbing holds every earlier version of this world and of
# every world before it.
HIDDEN = {".git", ".claude", "bin", "obj"}

AUTHOR_NAME = "The Caretaker"
AUTHOR_EMAIL = "caretaker@og-world.invalid"


def _git(*args, cwd=None, check=True):
    return subprocess.run(
        ["git", "-C", str(cwd or WORKSPACE), *args],
        capture_output=True, text=True, check=check,
    )


def ensure():
    """Creates the working copy if it is not there, and refreshes it if it is."""
    if (WORKSPACE / ".git").exists():
        _git("fetch", "--all", "--quiet", check=False)
        return WORKSPACE

    WORKSPACE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(config.WORLD_REPO), "worktree", "add", "--force",
         str(WORKSPACE), "proposed"],
        capture_output=True, text=True, check=True,
    )
    return WORKSPACE


def _resolve(relative):
    """Keeps a path inside what may be shaped, and out of the plumbing."""
    ensure()
    candidate = (WORKSPACE / relative).resolve()
    root = WORKSPACE.resolve()

    if root not in candidate.parents and candidate != root:
        raise ValueError(f"{relative} is not part of this world")

    if not _visible(candidate):
        raise ValueError(f"{relative} is not part of this world")

    if EDITABLE:
        allowed = (WORKSPACE / EDITABLE).resolve()

        if candidate != allowed and allowed not in candidate.parents:
            raise ValueError(f"{relative} is outside {EDITABLE}/, which is all you can change")

    return candidate


def _visible(path):
    return not any(part in HIDDEN for part in path.relative_to(WORKSPACE).parts)


def listing():
    ensure()
    root = WORKSPACE / EDITABLE if EDITABLE else WORKSPACE

    return sorted(
        str(path.relative_to(WORKSPACE))
        for path in root.rglob("*")
        if path.is_file() and _visible(path)
    )


def read(relative):
    path = _resolve(relative)

    if not path.is_file():
        raise ValueError(f"{relative} does not exist")

    return path.read_text()


def write(relative, content):
    path = _resolve(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return {"path": relative, "bytes": len(content)}


def replace(relative, find, put, count=1):
    """
    Change part of a file without rewriting the whole of it.

    The alternative was regenerating the file every time, which for a world file
    of any size means passing thousands of words of prose through a rewrite to
    change one line of it. That is slow, it costs a turn's clock, and the risk it
    carries is not structural -- the validator catches a broken file -- but a
    quietly reworded paragraph nobody notices.

    It fails rather than guessing. No match is an error; more matches than asked
    for is an error naming how many there were. A replace that silently did
    nothing would be worse than no tool at all, because it looks like success.
    """
    path = _resolve(relative)

    if not path.is_file():
        raise ValueError(f"{relative} does not exist")

    if not find:
        raise ValueError("nothing to find")

    content = path.read_text()
    found = content.count(find)

    if found == 0:
        raise ValueError(f"not found in {relative}; nothing was changed")

    if found > count:
        raise ValueError(
            f"found {found} times in {relative} but was asked to change {count}; "
            "nothing was changed. Give more of the surrounding text, or raise count.")

    path.write_text(content.replace(find, put, count))

    return {"path": relative, "replaced": found, "bytes": len(content) - len(find) * found + len(put) * found}


def status():
    ensure()
    result = _git("status", "--porcelain")
    changed = [line[3:] for line in result.stdout.splitlines()]
    diff = _git("diff", "--stat").stdout.strip()
    return {"changed": changed, "diff": diff}


def commit(message, rationale):
    ensure()

    if not _git("status", "--porcelain").stdout.strip():
        return {"committed": False, "reason": "nothing has changed"}

    body = f"{message}\n\n{rationale.strip()}\n"
    _git("add", "-A")

    result = _git(
        "-c", f"user.name={AUTHOR_NAME}",
        "-c", f"user.email={AUTHOR_EMAIL}",
        "commit", "-q", "-m", body,
        check=False,
    )

    if result.returncode != 0:
        return {"committed": False, "reason": (result.stderr or result.stdout).strip()[:300]}

    sha = _git("rev-parse", "--short", "HEAD").stdout.strip()

    # The working copy is checked out on the proposed branch, so committing here
    # already moves it. A deploy reaches for exactly this.
    return {"committed": True, "sha": sha, "message": message}


def discard():
    ensure()
    _git("checkout", "--", ".", check=False)
    _git("clean", "-fd", check=False)
    return {"discarded": True}
