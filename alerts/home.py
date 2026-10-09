"""Where Done Alerts keeps its files, and its settings.

Everything lives under ~/.claude-voice (override with CLAUDE_VOICE_HOME). The folder is
shared with the Read Aloud plugin: both use the same Kokoro model download and the same
playback lock, so an alert waits for the end of a sentence instead of talking over a read.

    ~/.claude-voice/
        models/              Kokoro model + voices (downloaded once, shared)
        play.lock            held while any audio plays
        done-alerts/
            settings.json    engine, mode, voices, threshold
            cache/           Fish audio for the fixed phrases, so they cost nothing twice
            alerts.log
"""
import json
import os
import time
from pathlib import Path

HOME = Path(os.environ.get("CLAUDE_VOICE_HOME") or Path.home() / ".claude-voice")
MODELS = HOME / "models"
PLAY_LOCK = HOME / "play.lock"
STATE = HOME / "done-alerts"
SETTINGS = STATE / "settings.json"
CACHE = STATE / "cache"
JOBS = STATE / "jobs"
TEST_FLAG = STATE / "test.pending"
LOG = STATE / "alerts.log"

DEFAULTS = {
    "engine": "kokoro",         # kokoro (local, free) | fish (Fish Audio, needs an API key)
    "mode": "detailed",         # detailed = a line Claude writes about the outcome
                                # standard = a fixed phrase like "Finished coding."
                                # off = silent
    "min_turn_seconds": 20,     # stay quiet for turns shorter than this
    "chime": True,              # a short chime before each alert
    "kokoro_voice": "bm_daniel",
    "kokoro_speed": 1.0,
    "model": "int8",            # Kokoro model size: int8 (92 MB) | fp16 (177 MB) | full (326 MB)
    "kokoro_fallback": True,    # with engine fish, use Kokoro when Fish can't be reached
    "fish_model": "s2.1-pro",
    "fish_voice": {"name": "Alok", "id": "b7204d4e40ef4a548c7c8547b7f73492"},
    "fish_backup_voice": {"name": "Sarah", "id": "933563129e564b19a115bedd57b7406a"},
    "project_names": {},        # folder name -> how to say it
    "skip_sessions": [],        # never speak for sessions whose first message contains any of these
}


def load_settings():
    s = dict(DEFAULTS)
    try:
        s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return s


def save_settings(**changes):
    s = load_settings()
    s.update(changes)
    STATE.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(s, indent=2), encoding="utf-8")
    return s


def fish_key():
    """The key the user entered in /plugin -> Configure options. Claude Code keeps it in the
    system credential store and hands it to the hooks as an environment variable."""
    for name in ("CLAUDE_PLUGIN_OPTION_FISH_API_KEY", "FISH_API_KEY"):
        v = (os.environ.get(name) or "").strip()
        if v:
            return v
    return None


def log(msg):
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > 512_000:
            LOG.write_text("", encoding="utf-8")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass
