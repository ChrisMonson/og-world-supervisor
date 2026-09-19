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


def history(limit=20):
    log = config.SUPERVISOR_DIR / "state" / "logs" / "deploys.log"
    lines = log.read_text().splitlines()[-limit:] if log.exists() else []

    commits = subprocess.run(
        ["git", "-C", str(config.WORLD_REPO), "log", "--format=%h %an %s", "-15"],
        capture_output=True, text=True, check=False,
    ).stdout.splitlines()

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
