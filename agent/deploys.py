"""Asking the supervisor to put a change into the world.

The caretaker never touches a container, an image or a branch ref. It asks, and
the answer is whatever the health contract decides.
"""

import subprocess

import config

BIN = config.SUPERVISOR_DIR / "bin"


def _run(script, *args, timeout=900):
    result = subprocess.run(
        [str(BIN / script), *args],
        capture_output=True, text=True, timeout=timeout,
    )

    output = (result.stdout + result.stderr).strip()

    return {
        "ok": result.returncode == 0,
        "output": output[-4000:],
    }


def deploy():
    """Runs the health contract, and deploys only if it passes."""
    outcome = _run("deploy.sh", "proposed")
    outcome["deployed"] = outcome["ok"]

    if not outcome["ok"]:
        outcome["note"] = (
            "The change did not pass and the world was left as it was. "
            "The output says which check failed."
        )

    return outcome


def rollback(ref="last-known-good"):
    return _run("rollback.sh", ref)


def _seed_tag():
    """Where this run began. Anything before it belongs to a different world."""
    import json

    manifest = config.SUPERVISOR_DIR / "seed" / "manifest.json"

    try:
        return json.loads(manifest.read_text())["worldTag"]
    except (OSError, KeyError, json.JSONDecodeError):
        return None


def history(limit=20):
    log = config.SUPERVISOR_DIR / "state" / "logs" / "deploys.log"
    lines = log.read_text().splitlines()[-limit:] if log.exists() else []

    # Only this run's own history. What came before it was a different world,
    # tended by someone else, and is no more this caretaker's past than anyone
    # else's is.
    seed = _seed_tag()
    span = [f"{seed}..HEAD"] if seed else ["-15"]

    commits = subprocess.run(
        ["git", "-C", str(config.WORLD_REPO), "log", "--format=%h %an %s", *span],
        capture_output=True, text=True, check=False,
    ).stdout.splitlines()[:limit]

    def rev(ref):
        return subprocess.run(
            ["git", "-C", str(config.WORLD_REPO), "rev-parse", "--short", ref],
            capture_output=True, text=True, check=False,
        ).stdout.strip()

    return {
        "deploys": lines,
        "commits": commits,
        "live": rev("live"),
        "lastKnownGood": rev("last-known-good"),
        "proposed": rev("proposed"),
    }


def intervention():
    """Whether anything had to step in since the caretaker last looked."""
    path = config.SUPERVISOR_DIR / "state" / "intervention.json"
    return path.read_text() if path.exists() else ""


def notices(mark_seen=True):
    """
    Notes left about the machinery: something that stepped in, or something that
    was wrong in a way the caretaker could not have seen from inside the world.
    """
    import json

    path = config.SUPERVISOR_DIR / "state" / "notices.json"

    if not path.exists():
        return []

    try:
        entries = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []

    unseen = [entry for entry in entries if not entry.get("seen")]

    if mark_seen and unseen:
        for entry in entries:
            entry["seen"] = True
        path.write_text(json.dumps(entries, indent=2))

    return unseen
