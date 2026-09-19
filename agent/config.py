"""Settings for the caretaker loop, all overridable from the environment."""

import os
from pathlib import Path

SUPERVISOR_DIR = Path(__file__).resolve().parent.parent
WORLD_REPO = Path(os.environ.get("WORLD_REPO", SUPERVISOR_DIR.parent / "og-world")).resolve()

STATE_DIR = Path(os.environ.get("STATE_DIR", SUPERVISOR_DIR / "state")) / "agent"
TURN_DIR = STATE_DIR / "turns"
WATERMARK_FILE = STATE_DIR / "watermark"

WORLD_URL = os.environ.get("WORLD_URL", "http://localhost:5080")
CARETAKER_TOKEN = os.environ.get("CARETAKER_TOKEN", "")

MODEL = os.environ.get("OG_MODEL", "claude-opus-5")
MAX_TURN_TOKENS = int(os.environ.get("OG_MAX_TURN_TOKENS", "60000"))
MAX_OUTPUT_TOKENS = int(os.environ.get("OG_MAX_OUTPUT_TOKENS", "8000"))
MAX_TOOL_ROUNDS = int(os.environ.get("OG_MAX_TOOL_ROUNDS", "20"))

# The floor between wakes, so one person typing steadily cannot wake it constantly.
MIN_WAKE_INTERVAL = int(os.environ.get("OG_MIN_WAKE_INTERVAL", "300"))

# The caretaker's own acts are excluded from the wake predicate: without this it
# would wake itself forever.
GOD_ACTOR = "god"

JOURNAL_DIR = WORLD_REPO / "journal"

for directory in (STATE_DIR, TURN_DIR):
    directory.mkdir(parents=True, exist_ok=True)
