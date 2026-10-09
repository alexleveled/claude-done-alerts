# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Claude Code hook entry points. Standard library only, so it starts fast on every prompt.

    hook.py prompt   UserPromptSubmit: in detailed mode, asks Claude for a spoken summary line
    hook.py stop     Stop: Claude finished a turn
    hook.py notify   Notification: a permission prompt or question is waiting

The hook only reads its input and decides whether to speak. The speaking happens in a
detached worker (speak.py worker <job>), so Claude Code is never held up.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import home  # noqa: E402
import turn  # noqa: E402

WINDOWS = os.name == "nt"


def muted(s, payload):
    if s.get("mode") == "off":
        return True
    if os.environ.get("CLAUDE_DONE_ALERTS_MUTE"):
        return True
    # Headless runs (claude -p, Agent SDK apps) have nobody listening.
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"):
        return True
    return turn.is_skipped(payload.get("transcript_path"), s.get("skip_sessions"))


def spawn_worker(job):
    """Run speak.py through uv, detached, so it outlives this hook."""
    home.JOBS.mkdir(parents=True, exist_ok=True)
    job_path = home.JOBS / f"job-{os.getpid()}-{int(time.time() * 1000)}.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    uv = os.environ.get("DONE_ALERTS_UV") or "uv"
    cmd = [uv, "run", "--quiet", "--script", str(HERE / "speak.py"), "worker", str(job_path)]
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
              close_fds=True, cwd=str(HERE))
    if not WINDOWS:
        subprocess.Popen(cmd, start_new_session=True, **kw)
        return
    # A hidden console (CREATE_NO_WINDOW) for uv and the Python it starts to inherit. With
    # no console at all (DETACHED_PROCESS), Windows gives that Python a visible one.
    flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(cmd, creationflags=flags | 0x01000000, **kw)  # + CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        subprocess.Popen(cmd, creationflags=flags, **kw)


def main():
    if WINDOWS:
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        s = home.load_settings()
        if muted(s, payload):
            return
        project = turn.project_name(payload.get("cwd") or os.getcwd(), s.get("project_names"))
        if cmd == "prompt":
            if s.get("mode") == "detailed":
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": turn.PROMPT_CONTEXT,
                }}))
        elif cmd == "stop":
            spawn_worker({
                "kind": "stop",
                "project": project,
                "transcript_path": payload.get("transcript_path"),
                "permission_mode": payload.get("permission_mode"),
                "last_assistant_message": payload.get("last_assistant_message"),
            })
        elif cmd == "notify":
            spawn_worker({"kind": "notify", "project": project})
    except Exception as e:
        home.log(f"hook {cmd} error: {e!r}")


if __name__ == "__main__":
    main()
