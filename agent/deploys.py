"""Asking the supervisor to put a change into the world.

The caretaker never touches a container, an image or a branch ref. It asks, and
the answer is whatever the health contract decides.
"""

import subprocess

import config

BIN = config.SUPERVISOR_DIR / "bin"


# What the checks are called, in the order they run. The caretaker is told which
# of these a change passed and which it did not; it is not told what the machine
# around it is made of.
CHECKS = {
    "1/6": "the changes to the world's records only add",
    "2/6": "it builds",
    "3/6": "the world's own tests pass",
    "4/6": "a copy of it starts on an empty world",
    "5/6": "that copy is playable",
    "6/6": "it stays up",
}

# Lines describing the machinery rather than the change: images, containers,
# stored copies, and instructions for tools the caretaker does not have.
NOISE = ("snapshotting", "stopping the live world", "starting ",
         "gate passed for", "Run promote", "deploying ", "live:")


def _account(output, ok):
    """
    What happened to a change, said plainly: which checks it met, and where it
    stopped if it stopped.
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    account = []
    reached = None

    for line in lines:
        for marker, description in CHECKS.items():
            if marker in line:
                reached = description

        if any(noise in line for noise in NOISE):
            continue

        if "PASS" in line and reached:
            continue

        if line.startswith(("PASS", "FAIL")) or "checks passed" in line or "smoke" in line.lower():
            account.append(line)

    for marker, description in CHECKS.items():
        if marker in output:
            account.insert(len([a for a in account if a.startswith("checked")]),
                           f"checked: {description}")

    if ok:
        account.append("The change is live.")
    else:
        account.append(f"It stopped at: {reached or 'the first check'}. Nothing changed.")

    return account


def _run(script, *args, timeout=900):
    result = subprocess.run(
        [str(BIN / script), *args],
        capture_output=True, text=True, timeout=timeout,
    )

    output = (result.stdout + result.stderr).strip()
    ok = result.returncode == 0

    answer = {"ok": ok, "checks": _account(output, ok)}

    # When something failed, the reason for it is the useful part.
    if not ok:
        reasons = [line.strip() for line in output.splitlines()
                   if any(word in line for word in ("error", "FAIL", "REJECTED", "refused"))
                   and not any(noise in line for noise in NOISE)]
        answer["why"] = reasons[-12:]

    return answer


def deploy():
    """Puts a committed change into the world, if it passes its checks."""
    outcome = _run("deploy.sh", "proposed")
    outcome["deployed"] = outcome["ok"]

    if not outcome["ok"]:
        outcome["note"] = "The world was left as it was."

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


def _readable(line):
    """
    A line of the machine's own log, said as something that happened to the
    world. Where copies are kept and what they are called is not the caretaker's
    business.
    """
    parts = line.split()

    if len(parts) < 3:
        return None

    when, what, which = parts[0], parts[1], parts[2][:12]

    return {
        "deploy": f"{when}  the world changed  ({which})",
        "reload": f"{when}  the world changed, without interrupting anyone  ({which})",
        "rollback": f"{when}  the world was put back  ({which})",
    }.get(what)


def history(limit=20):
    log = config.SUPERVISOR_DIR / "state" / "logs" / "deploys.log"
    raw = log.read_text().splitlines()[-limit:] if log.exists() else []
    lines = [entry for entry in (_readable(line) for line in raw) if entry]

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
        "changes": commits,
        "history": lines,
        "running": rev("live"),
        "committed": rev("proposed"),
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
