# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "kokoro-onnx>=0.4.7",
#     "sounddevice>=0.4.6",
#     "filelock>=3.12",
# ]
# ///
"""Done Alerts: speaks when Claude Code finishes a turn or needs your approval.

    speak.py worker JOB                 speak one alert (started by hook.py)
    speak.py status                     current settings, one per line
    speak.py set KEY VALUE              change a setting (see `status` for the keys)
    speak.py name FOLDER SPOKEN NAME    how a project folder is announced
    speak.py voices                     Kokoro voices
    speak.py test                       the next time Claude stops, speak a test line
    speak.py say TEXT                   speak TEXT now with the current engine
    speak.py doctor                     JSON health report for setup
    speak.py download                   fetch the Kokoro voice model now
    speak.py session-start              SessionStart hook (background)

Run it through uv (`uv run --script speak.py ...`), which installs the packages listed above
on first use.
"""
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import wave
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fish  # noqa: E402
import home  # noqa: E402
import turn  # noqa: E402
import voice  # noqa: E402

WINDOWS = os.name == "nt"
TEST_LINE = ("[pleased]", "Done Alerts is working. This is how I'll sound when Claude finishes.")


# ---------------------------------------------------------------- audio

def chime(sr, approval=False):
    """A short two-note bell (three notes for approval), generated so there's no sound file
    to license."""
    import numpy as np

    notes = (1318.5, 987.8, 1318.5) if approval else (880.0, 1318.5)
    out = []
    for f in notes:
        t = np.arange(int(sr * 0.16)) / sr
        env = np.exp(-t * 18) * np.minimum(1, t * 400)
        out.append((np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * env * 0.18)
    out.append(np.zeros(int(sr * 0.12)))
    return np.concatenate(out).astype(np.float32)


def pcm_to_float(pcm, channels):
    import numpy as np

    a = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        a = a.reshape(-1, channels).mean(axis=1)
    return a


def _cache_path(s, voice_id, text):
    h = hashlib.sha1(f"{s['fish_model']}|{voice_id}|{text}".encode()).hexdigest()[:16]
    return home.CACHE / f"{h}.wav"


def _read_wav(path):
    with wave.open(str(path), "rb") as w:
        return w.readframes(w.getnframes()), w.getframerate(), w.getnchannels()


def _write_wav(path, pcm, sr, channels):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def fish_speech(mood, spoken, s, cache_ok):
    key = home.fish_key()
    if not key:
        home.log("engine is fish but no API key reached the hook; set it in /plugin -> done-alerts -> Configure options")
        return None
    text = f"{mood} {spoken}".strip()
    for v in [s.get("fish_voice"), s.get("fish_backup_voice")]:
        if not v or not v.get("id"):
            continue
        cached = _cache_path(s, v["id"], text)
        if cache_ok and cached.exists():
            pcm, sr, ch = _read_wav(cached)
            return pcm_to_float(pcm, ch), sr, "fish-cache"
        try:
            pcm, sr, ch = fish.tts(text, v["id"], key, s["fish_model"])
        except fish.AccountError as e:
            home.log(f"fish {v.get('name')}: {e}; check the key and credit at fish.audio")
            return None
        except urllib.error.HTTPError as e:  # e.g. the voice was removed: try the backup
            home.log(f"fish {v.get('name')} failed: HTTP {e.code}")
            continue
        except Exception as e:  # network down or timeout: the backup won't do better
            home.log(f"fish {v.get('name')} failed: {e!r}")
            return None
        if cache_ok:
            _write_wav(cached, pcm, sr, ch)
        return pcm_to_float(pcm, ch), sr, f"fish:{v.get('name')}"
    return None


def kokoro_speech(spoken, s):
    if voice.missing(s["model"]):
        home.log("Kokoro model not downloaded yet; run /done-alerts:alerts setup")
        return None
    k = voice.load_kokoro(s["model"])
    audio, sr = k.create(spoken, voice=s["kokoro_voice"], speed=float(s["kokoro_speed"]),
                         lang=voice.lang_for(s["kokoro_voice"]))
    return audio, sr, "kokoro"


def synthesize(mood, spoken, s, cache_ok):
    """Return (audio, sample_rate, engine) or None. Never raises."""
    if s["engine"] == "fish":
        try:
            got = fish_speech(mood, spoken, s, cache_ok)
        except Exception as e:
            home.log(f"fish crashed: {e!r}")
            got = None
        if got or not s.get("kokoro_fallback", True):
            return got
    try:
        return kokoro_speech(spoken, s)
    except Exception as e:
        home.log(f"kokoro failed: {e!r}")
        return None


def speak(mood, spoken, s, cache_ok, approval=False):
    import numpy as np

    got = synthesize(mood, spoken, s, cache_ok)
    if got is None:
        audio, sr, engine = chime(24000, approval), 24000, "chime only"
    else:
        audio, sr, engine = got
        if s.get("chime", True):
            audio = np.concatenate([chime(sr, approval), np.asarray(audio, dtype=np.float32)])
    voice.play(audio, sr)
    return engine


# ---------------------------------------------------------------- the alert

def worker(job_path):
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    Path(job_path).unlink(missing_ok=True)
    s = home.load_settings()
    project, kind = job.get("project") or "", job["kind"]

    mood, line, cat = "", None, "approval"
    if kind == "stop":
        time.sleep(1.0)  # let Claude Code finish writing the transcript
        testing = home.TEST_FLAG.exists()
        home.TEST_FLAG.unlink(missing_ok=True)
        text, tools, start, pending = turn.last_turn(turn.load(job.get("transcript_path")))
        text = text or job.get("last_assistant_message") or ""
        cat = turn.category(tools, job.get("permission_mode"))
        if testing:
            mood, line = TEST_LINE
        else:
            if pending:
                home.log(f"{project}: {pending} background agent(s) still running, staying quiet")
                return
            if start is not None:
                took = (datetime.now(timezone.utc) - start).total_seconds()
                if took < float(s.get("min_turn_seconds", 0)):
                    home.log(f"{project}: turn took {took:.0f}s, under min_turn_seconds, staying quiet")
                    return
            if s.get("mode") == "detailed":
                found = turn.voice_line(text)
                if found:
                    mood, line = found

    sentence = line or turn.PHRASES[cat]
    spoken = f"{project}. {sentence}" if project else sentence
    engine = speak(mood, spoken, s, cache_ok=line is None, approval=kind == "notify")
    home.log(f"{project}: [{kind}/{cat}] {engine} -> {mood} {spoken}".replace("  ", " "))


# ---------------------------------------------------------------- commands

def _bool(v):
    if v.lower() in ("on", "true", "yes", "1"):
        return True
    if v.lower() in ("off", "false", "no", "0"):
        return False
    raise ValueError("on or off")


SETTERS = {
    "engine": lambda v: v if v in ("kokoro", "fish") else (_ for _ in ()).throw(ValueError("kokoro or fish")),
    "mode": lambda v: v if v in ("detailed", "standard", "off") else (_ for _ in ()).throw(ValueError("detailed, standard or off")),
    "min_turn_seconds": int,
    "chime": _bool,
    "kokoro_voice": lambda v: v,
    "kokoro_speed": float,
    "model": lambda v: v if v in ("int8", "fp16", "full") else (_ for _ in ()).throw(ValueError("int8, fp16 or full")),
    "kokoro_fallback": _bool,
    "fish_model": lambda v: v,
}


def cmd_set(args):
    if not args:
        return __doc__
    key = {"min": "min_turn_seconds", "voice": "kokoro_voice", "speed": "kokoro_speed"}.get(args[0], args[0])
    if key in ("fish_voice", "fish_backup_voice"):
        if len(args) < 2:
            return f"Usage: set {key} <voice id from fish.audio> [name]"
        name = " ".join(args[2:]) or args[1][:8]
        home.save_settings(**{key: {"name": name, "id": args[1]}})
        return f"{key} set to {name} ({args[1]})."
    if key not in SETTERS or len(args) < 2:
        return f"Settings: {', '.join([*SETTERS, 'fish_voice', 'fish_backup_voice'])}."
    try:
        value = SETTERS[key](args[1])
    except ValueError as e:
        return f"{key}: {e}"
    home.save_settings(**{key: value})
    extra = ""
    if key == "engine" and value == "fish":
        extra = (" Fish needs an API key: /plugin -> Installed -> done-alerts -> Configure options."
                 " Without one, alerts use Kokoro.")
    return f"{key} set to {value}.{extra}"


def cmd_status():
    s = home.load_settings()
    lines = [f"engine:           {s['engine']}"
             + (" (Kokoro when Fish can't be reached)" if s['engine'] == "fish" and s['kokoro_fallback'] else ""),
             f"mode:             {s['mode']}",
             f"min turn:         {s['min_turn_seconds']}s",
             f"chime:            {'on' if s['chime'] else 'off'}",
             f"kokoro voice:     {s['kokoro_voice']} at {s['kokoro_speed']}x ({s['model']} model)",
             f"fish voice:       {s['fish_voice'].get('name')} (backup {(s.get('fish_backup_voice') or {}).get('name')}), model {s['fish_model']}"]
    names = s.get("project_names") or {}
    if names:
        lines.append("project names:    " + ", ".join(f"{k} -> {v}" for k, v in names.items()))
    return "\n".join(lines)


def cmd_doctor():
    s = home.load_settings()
    report = {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "home": str(home.HOME),
        "settings": {k: v for k, v in s.items() if k != "project_names"},
        "kokoro_model_missing": [p.name for p in voice.missing(s["model"])],
        # Claude Code passes the key to hooks, not to commands Claude runs, so this is
        # usually false here even when the key is set. The test alert is the real check.
        "fish_key_visible_here": bool(home.fish_key()),
        "uv": os.environ.get("DONE_ALERTS_UV") or shutil.which("uv"),
    }
    try:
        import sounddevice as sd
        report["audio_output"] = sd.query_devices(kind="output").get("name")
    except Exception as e:  # PortAudio missing on Linux, no output device, ...
        report["audio_output"] = None
        report["audio_error"] = str(e)
    try:
        report["recent_log"] = home.LOG.read_text(encoding="utf-8").splitlines()[-6:]
    except OSError:
        report["recent_log"] = []
    return json.dumps(report, indent=2, ensure_ascii=False)


def _record_python():
    """Save the path of the plain Python under this script's uv environment, for run.sh to
    start hook.py with directly. (The environment's own python is a launcher that starts a
    second process on Windows.)"""
    path = home.STATE / "python.path"
    base = Path(getattr(sys, "_base_executable", "") or sys.executable)
    if base.is_file():
        home.STATE.mkdir(parents=True, exist_ok=True)
        path.write_text(base.as_posix(), encoding="utf-8")
    else:
        path.unlink(missing_ok=True)


def cmd_session_start():
    """Runs in the background at session start. Getting here at all means uv has installed
    the packages, so the first alert won't wait for that. Also fetch the Kokoro model and
    clear out job files a crashed worker left behind."""
    s = home.load_settings()
    _record_python()
    cutoff = time.time() - 3600
    for p in home.JOBS.glob("job-*.json") if home.JOBS.exists() else []:
        if p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)
    if (s["engine"] == "kokoro" or s["kokoro_fallback"]) and voice.missing(s["model"]):
        try:
            voice.ensure_models(s["model"])
        except Exception as e:
            home.log(f"model prefetch failed: {e!r}")


def main():
    if WINDOWS:
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    try:
        if cmd == "worker":
            worker(args[1])
        elif cmd == "status":
            print(cmd_status())
        elif cmd == "set":
            print(cmd_set(args[1:]))
        elif cmd == "name" and len(args) > 2:
            names = dict(home.load_settings().get("project_names") or {})
            names[args[1]] = " ".join(args[2:])
            home.save_settings(project_names=names)
            print(f"{args[1]} will be announced as \"{names[args[1]]}\".")
        elif cmd == "voices":
            current = home.load_settings()["kokoro_voice"]
            for v, d in voice.ENGLISH_VOICES.items():
                print(f"{'*' if v == current else ' '} {v:<12} {d}")
            print("\nKokoro voices: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md"
                  "\nFish voices: https://fish.audio/discovery (copy the ID from the voice's page)")
        elif cmd == "test":
            home.STATE.mkdir(parents=True, exist_ok=True)
            home.TEST_FLAG.write_text(str(time.time()), encoding="utf-8")
            s = home.load_settings()
            if s["mode"] == "off":
                print("Alerts are off. Turn them on first (set mode detailed).")
            else:
                print("Test queued: you'll hear it as soon as this reply finishes.")
        elif cmd == "say":
            s = home.load_settings()
            print(f"played via {speak('', ' '.join(args[1:]) or 'Hello.', s, cache_ok=False)}")
        elif cmd == "doctor":
            print(cmd_doctor())
        elif cmd == "download":
            voice.ensure_models(home.load_settings()["model"])
            print("Kokoro voice model ready.")
        elif cmd == "session-start":
            cmd_session_start()
        else:
            print(__doc__)
    except Exception as e:
        home.log(f"{cmd} failed: {e!r}")
        if cmd in ("worker", "session-start"):
            return
        print(f"Done Alerts error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
