"""Running a turn through the Claude CLI.

Uses the CLI rather than the API directly, so turns run on the account that is
already signed in. The caretaker's tools are given to it as an MCP server and
nothing else: no shell, no files, no network beyond what those tools reach.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import config

AGENT_DIR = Path(__file__).resolve().parent

# Everything the CLI would otherwise bring with it. The caretaker gets its own
# tools and nothing that would let it step around them.
DENIED = [
    "Bash", "Read", "Write", "Edit", "NotebookEdit", "Glob", "Grep",
    "WebFetch", "WebSearch", "Task", "Agent", "TodoWrite", "KillShell",
    "BashOutput", "SlashCommand", "Skill",
]


class TurnFailed(RuntimeError):
    pass


class NotSignedIn(TurnFailed):
    pass


CREDENTIAL_HELP = (
    "The CLI could not reach usable credentials. Either:\n"
    "  * run this from a terminal where `claude` is signed in and can read the\n"
    "    keychain, or\n"
    "  * run `claude setup-token` on your own machine and write the result to\n"
    "    state/claude-token (needed anywhere without a keychain, such as the\n"
    "    supervisor container).\n"
    "\n"
    "This will not come right on its own, so the caretaker stops rather than\n"
    "retrying against it."
)


# A turn must not inherit the environment of whatever started it: another Claude
# session's variables would point the CLI at the wrong endpoint or the wrong
# credentials.
KEEP = ("HOME", "PATH", "USER", "LANG", "LC_ALL", "TMPDIR", "SHELL")


def child_environment():
    environment = {name: os.environ[name] for name in KEEP if name in os.environ}
    environment["TERM"] = "dumb"

    # A token from `claude setup-token`, for running somewhere with no keychain.
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
        if os.environ.get(name):
            environment[name] = os.environ[name]

    return environment


def mcp_config():
    return {
        "mcpServers": {
            "caretaker": {
                "command": "python3",
                "args": [str(AGENT_DIR / "mcp_server.py")],
                "env": {
                    "CARETAKER_TOKEN": config.CARETAKER_TOKEN,
                    "CARETAKER_REACH": config.REACH,
                    "WORLD_URL": config.WORLD_URL,
                    "WORLD_REPO": str(config.WORLD_REPO),
                    "STATE_DIR": str(config.STATE_DIR.parent),
                    "PYTHONPATH": str(AGENT_DIR),
                },
            }
        }
    }


def check_credentials(timeout=120):
    """
    One trivial turn, with no tools, to find out now rather than on the first
    real wake. An expired token will never come good on its own, so the loop
    refuses to start rather than beating against it.
    """
    with tempfile.TemporaryDirectory() as scratch:
        try:
            result = subprocess.run(
                ["claude", "-p", "Reply with exactly: OK", "--output-format", "json"],
                capture_output=True, text=True, timeout=timeout,
                cwd=scratch, env=child_environment(), stdin=subprocess.DEVNULL,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as error:
            raise TurnFailed(f"could not run the claude CLI: {error}") from error

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise TurnFailed((result.stderr or result.stdout).strip()[-800:] or
                         f"the CLI exited with {result.returncode} and said nothing")

    if payload.get("is_error") or result.returncode != 0:
        detail = str(payload.get("result") or f"the CLI exited with {result.returncode}")

        if "logged in" in detail.lower() or "authenticate" in detail.lower():
            raise NotSignedIn(detail + "\n\n" + CREDENTIAL_HELP)

        raise TurnFailed(detail)

    return True


def run(system_prompt, opening, reach, model=None, timeout=1800):
    """Takes one turn. Returns the final text and what it cost."""
    config.REACH = reach

    with tempfile.TemporaryDirectory() as scratch:
        config_path = Path(scratch) / "mcp.json"
        config_path.write_text(json.dumps(mcp_config()))

        command = [
            "claude",
            "-p", opening,
            "--output-format", "json",
            "--system-prompt", system_prompt,
            "--mcp-config", str(config_path),
            "--strict-mcp-config",
            "--allowedTools", "mcp__caretaker",
            "--disallowedTools", *DENIED,
            "--permission-mode", "bypassPermissions",
            "--model", model or config.MODEL,
        ]

        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout,
                cwd=scratch,  # nothing of ours is reachable as a file
                env=child_environment(),
                stdin=subprocess.DEVNULL,  # the prompt is an argument, not piped
            )
        except subprocess.TimeoutExpired as error:
            raise TurnFailed(f"the turn ran past {timeout}s") from error

    # The CLI reports failures as JSON on stdout even when it exits non-zero.
    payload = None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        pass

    if payload is None:
        raise TurnFailed((result.stderr or result.stdout).strip()[-1500:] or
                         f"the CLI exited with {result.returncode} and said nothing")

    if payload.get("is_error") or result.returncode != 0:
        detail = str(payload.get("result") or payload.get("error") or
                     f"the CLI exited with {result.returncode}")

        if "logged in" in detail.lower() or "authenticate" in detail.lower():
            raise NotSignedIn(detail + "\n\n" + CREDENTIAL_HELP)

        raise TurnFailed(detail)

    usage = payload.get("usage") or {}

    return {
        "text": (payload.get("result") or "").strip(),
        "turns": payload.get("num_turns"),
        "cost": payload.get("total_cost_usd"),
        "duration_ms": payload.get("duration_ms"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "session_id": payload.get("session_id"),
    }
