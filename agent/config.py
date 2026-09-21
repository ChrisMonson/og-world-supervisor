"""Settings for the caretaker loop, all overridable from the environment."""

import os
from pathlib import Path

SUPERVISOR_DIR = Path(__file__).resolve().parent.parent
WORLD_REPO = Path(os.environ.get("WORLD_REPO", SUPERVISOR_DIR.parent / "og-world")).resolve()

STATE_DIR = Path(os.environ.get("STATE_DIR", SUPERVISOR_DIR / "state")) / "agent"
TURN_DIR = STATE_DIR / "turns"
WATERMARK_FILE = STATE_DIR / "watermark"
HALT_FILE = Path(os.environ.get("STATE_DIR", SUPERVISOR_DIR / "state")) / "caretaker-halted.json"
REFLEX_WATERMARK_FILE = STATE_DIR / "reflex-watermark"

WORLD_URL = os.environ.get("WORLD_URL", "http://localhost:5080")
CARETAKER_TOKEN = os.environ.get("CARETAKER_TOKEN", "")

MODEL = os.environ.get("OG_MODEL", "opus")
# How far the caretaker can reach on a given turn: observe, act, or shape.
REACH = os.environ.get("CARETAKER_REACH", "observe")

REFLEX_MODEL = os.environ.get("OG_REFLEX_MODEL", "opus")
REFLEX_TIMEOUT = int(os.environ.get("OG_REFLEX_TIMEOUT", "240"))
DELIBERATION_TIMEOUT = int(os.environ.get("OG_DELIBERATION_TIMEOUT", "1800"))

# Below this, the turn was not slow because of what it was doing. A healthy turn
# runs at 40-90 output tokens a second; a degraded window has run at 4. The
# caretaker cannot tell the difference from inside -- a slow answer and an
# expensive one look the same to it -- so the machinery has to notice instead.
SLOW_TOKENS_PER_SECOND = float(os.environ.get("OG_SLOW_TOKENS_PER_SECOND", "20"))

# How much of what it concluded is carried into the next waking. The cap is the
# point: keeping something has to mean dropping something else, or the file stops
# being curated and becomes a log.
PHILOSOPHY_LIMIT = int(os.environ.get("OG_PHILOSOPHY_LIMIT", "4000"))

# Floors between wakes, so one person typing steadily cannot wake it constantly.
MIN_WAKE_INTERVAL = int(os.environ.get("OG_MIN_WAKE_INTERVAL", "1800"))
MIN_REFLEX_INTERVAL = int(os.environ.get("OG_MIN_REFLEX_INTERVAL", "60"))

# A long turn on a world nobody is in. A world that has never been played is
# that state permanently, and capping it there would have the run build for three
# turns and then sleep forever, so 0 means no cap.
MIN_QUIET_WAKE_INTERVAL = int(os.environ.get("OG_MIN_QUIET_WAKE_INTERVAL", "1800"))
MAX_QUIET_TURNS = int(os.environ.get("OG_MAX_QUIET_TURNS", "0"))

# The caretaker's own acts are excluded from the wake predicate: without this it
# would wake itself forever.
GOD_ACTOR = "god"

JOURNAL_DIR = WORLD_REPO / "journal"

for directory in (STATE_DIR, TURN_DIR):
    directory.mkdir(parents=True, exist_ok=True)
