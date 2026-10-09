"""Reads the session transcript to decide what to say when Claude stops.

Claude Code's transcript format isn't a public API. Everything here degrades to "say the
fixed phrase" when it can't make sense of the file, so a format change makes the alerts
plainer, never wrong or silent.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# The line Claude appends in detailed mode:  🔊 [pleased, relieved] All three bugs fixed.
VOICE_LINE = re.compile(r"^\s*\U0001F50A\s*(\[[^\]]{1,60}\])?\s*(.+?)\s*$")
NOTIF_ID = re.compile(r"<tool-use-id>([^<]+)</tool-use-id>")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
AGENT_TOOLS = {"Agent", "Task"}
PENDING_MAX_AGE = 3 * 3600  # an agent that never reports back can't mute a session forever

PHRASES = {
    "planning": "Planning's done, please review.",
    "coding": "Finished coding.",
    "task": "Task finished.",
    "ready": "Ready for you.",
    "approval": "I need your approval.",
}

PROMPT_CONTEXT = (
    "Voice notifications are on. If this turn involves real work (any tool calls), end your "
    "final reply with one last line in exactly this form:\n"
    "\U0001F50A [mood tag] <one short spoken sentence, under 15 words, on how it went>\n"
    "The mood tag is a note to a voice actor (e.g. [pleased, relieved], [frustrated, tired], "
    "[calm, matter-of-fact], [optimistic]) and must match what actually happened. Say the "
    "outcome in plain spoken English: no file paths, code, or markdown. Do not say the project "
    "name; it is added automatically. Skip the line for pure chat replies with no tool calls."
)


def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def load(path):
    entries = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (OSError, TypeError):
        pass
    return entries


def prompt_text(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


def is_real_prompt(entry):
    """A message the person typed: not a tool result, not a meta entry, not a subagent's."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        blocks = [b for b in content if isinstance(b, dict)]
        return any(b.get("type") == "text" for b in blocks) and not any(
            b.get("type") == "tool_result" for b in blocks)
    return False


def last_turn(entries, now=None):
    """Return (last_assistant_text, tool_names, turn_start, pending_agents) for the latest turn.

    A turn spans from the person's last real message, not from the last <task-notification>.
    When Claude launches background agents it ends its turn early and is woken again as each
    one reports back; those wake-ups belong to the same piece of work. pending_agents counts
    background agents launched but not reported back yet. While any are out, Claude stopping
    doesn't mean the work is done.
    """
    start = 0
    for i in range(len(entries) - 1, -1, -1):
        if is_real_prompt(entries[i]) and not prompt_text(entries[i]).lstrip().startswith("<task-notification>"):
            start = i
            break
    turn_start = parse_ts(entries[start].get("timestamp")) if entries else None

    agent_calls = {b.get("id") for e in entries if e.get("type") == "assistant" and not e.get("isSidechain")
                   for b in (e.get("message") or {}).get("content") or []
                   if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in AGENT_TOOLS}
    launched, reported = {}, set()
    for e in entries:
        if e.get("isSidechain"):
            continue
        # Newer Claude Code versions deliver the <task-notification> as a queued command
        # (an attachment entry plus queue-operation entries), not as a user message.
        if e.get("type") == "attachment":
            reported.update(NOTIF_ID.findall(str((e.get("attachment") or {}).get("prompt") or "")))
            continue
        if e.get("type") == "queue-operation":
            reported.update(NOTIF_ID.findall(str(e.get("content") or "")))
            continue
        content = (e.get("message") or {}).get("content")
        if e.get("type") != "user":
            continue
        if isinstance(content, str):
            reported.update(NOTIF_ID.findall(content))
        for b in content if isinstance(content, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                reported.update(NOTIF_ID.findall(b.get("text", "")))
            elif (b.get("type") == "tool_result" and b.get("tool_use_id") in agent_calls
                  and "Async agent launched" in json.dumps(b.get("content"))):
                launched[b.get("tool_use_id")] = parse_ts(e.get("timestamp"))
    now = now or datetime.now(timezone.utc)
    pending = sum(1 for tid, ts in launched.items()
                  if tid not in reported and (ts is None or (now - ts).total_seconds() < PENDING_MAX_AGE))

    last_text, tools = "", set()
    for e in entries[start + 1:]:
        if e.get("type") != "assistant" or e.get("isSidechain"):
            continue
        for b in (e.get("message") or {}).get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").strip():
                last_text = b["text"]
            elif b.get("type") == "tool_use":
                tools.add(b.get("name", ""))
    return last_text, tools, turn_start, pending


def category(tools, permission_mode=None):
    if "ExitPlanMode" in tools:
        return "planning"
    if permission_mode == "plan":
        return "ready"  # still planning, e.g. asking a question; the plan isn't up yet
    if tools & EDIT_TOOLS:
        return "coding"
    return "task"


def voice_line(text):
    """The 🔊 line at the end of the reply, as (mood_tag, sentence), or None."""
    for line in reversed((text or "").strip().splitlines()):
        m = VOICE_LINE.match(line)
        if m:
            return (m.group(1) or "").strip(), m.group(2).strip()
        if line.strip() and not line.strip().startswith(("\U0001F50A", "```")):
            break  # only the last non-empty lines count
    return None


def project_name(cwd, names):
    base = Path(cwd).name if cwd else ""
    if base in (names or {}):
        return names[base]
    return re.sub(r"[-_.]+", " ", base).strip()


def is_skipped(transcript_path, skip):
    """True when the session's first lines contain one of the skip strings (an always-on bot,
    say). Reads only the start of the file."""
    if not skip or not transcript_path:
        return False
    try:
        with open(transcript_path, encoding="utf-8") as f:
            head = "".join(line for _, line in zip(range(15), f))
    except OSError:
        return False
    return any(s and s in head for s in skip)
