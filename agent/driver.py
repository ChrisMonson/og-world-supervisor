"""Running a turn through the Claude CLI.

Uses the CLI rather than the API directly, so turns run on the account that is
already signed in. The caretaker's tools are given to it as an MCP server and
nothing else: no shell, no files, no network beyond what those tools reach.
"""

import json
import os
import subprocess
import tempfile
import time
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


TURN_DEADLINE = {"at": 0.0, "started": 0.0}

# Which kind of turn this is, passed to the tool server so that anything it
# commits can say so. For us, reading the history afterwards: a burst of commits
# from a four-minute turn looks exactly like one from a half-hour turn otherwise.
TURN = {"kind": ""}


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
                    "CARETAKER_DEADLINE": str(TURN_DEADLINE["at"]),
                    "CARETAKER_STARTED": str(TURN_DEADLINE["started"]),
                    "CARETAKER_TURN": TURN["kind"],
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


import render


def run(system_prompt, opening, reach, model=None, timeout=1800, transcript_path=None, kind=""):
    """
    Takes one turn.

    The whole exchange is streamed to disk as it happens: every tool call with its
    arguments, every result it saw, and everything it said between them. The
    model's own reasoning text is not exposed by the CLI, so what is kept is the
    record of what it chose to look at and what it concluded from it.
    """
    config.REACH = reach
    TURN["kind"] = kind
    TURN_DEADLINE["started"] = time.time()
    TURN_DEADLINE["at"] = TURN_DEADLINE["started"] + timeout

    with tempfile.TemporaryDirectory() as scratch:
        config_path = Path(scratch) / "mcp.json"
        config_path.write_text(json.dumps(mcp_config()))

        command = [
            "claude",
            "-p", opening,
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose",
            "--system-prompt", system_prompt,
            "--mcp-config", str(config_path),
            "--strict-mcp-config",
            "--allowedTools", "mcp__caretaker",
            "--disallowedTools", *DENIED,
            "--permission-mode", "bypassPermissions",
            "--model", model or config.MODEL,
            "--effort", config.EFFORT,
        ]

        events = []
        payload = None
        raw = None

        if transcript_path:
            Path(transcript_path).parent.mkdir(parents=True, exist_ok=True)
            raw = open(transcript_path, "w")

        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                cwd=scratch,  # nothing of ours is reachable as a file
                env=child_environment(),
                stdin=subprocess.DEVNULL,  # the prompt is an argument, not piped
            )

            deadline = time.time() + timeout

            for line in process.stdout:
                if raw:
                    raw.write(line)
                    raw.flush()  # so a turn in progress can be watched

                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # The deltas are only useful for reassembling; keep the whole
                # messages, which carry the tool calls and the text.
                if event.get("type") != "stream_event":
                    events.append(event)

                if event.get("type") == "result":
                    payload = event

                if time.time() > deadline:
                    process.kill()
                    raise TurnFailed(f"the turn ran past {timeout}s")

            stderr = process.stderr.read()
            process.wait(timeout=30)
        except subprocess.TimeoutExpired as error:
            raise TurnFailed(f"the turn ran past {timeout}s") from error
        finally:
            if raw:
                raw.close()

        result = subprocess.CompletedProcess(command, process.returncode, "", stderr)

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

    if transcript_path:
        readable = Path(transcript_path).with_suffix(".md")
        readable.write_text(render.header(transcript_path, events) + "\n" + render.render(events))

    # The last word on the account's standing, if the CLI said anything at all.
    limits = [event.get("rate_limit_info") for event in events
              if event.get("type") == "rate_limit_event"]

    return {
        "text": (payload.get("result") or "").strip(),
        "steps": len([event for event in events if event.get("type") == "assistant"]),
        "turns": payload.get("num_turns"),
        "cost": payload.get("total_cost_usd"),
        "duration_ms": payload.get("duration_ms"),
        "api_ms": payload.get("duration_api_ms"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_read": usage.get("cache_read_input_tokens"),
        "rate_limit": limits[-1] if limits else None,
        "session_id": payload.get("session_id"),
    }
