import json
from pathlib import Path
import struct
from datetime import datetime, timedelta, timezone

import fish
import turn

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def ts(seconds_ago):
    return (NOW - timedelta(seconds=seconds_ago)).isoformat().replace("+00:00", "Z")


def user(text, ago=100):
    return {"type": "user", "timestamp": ts(ago), "message": {"role": "user", "content": text}}


def asst(*blocks, ago=10):
    return {"type": "assistant", "timestamp": ts(ago), "message": {"role": "assistant", "content": list(blocks)}}


def text(t):
    return {"type": "text", "text": t}


def tool(name, tid="t1"):
    return {"type": "tool_use", "id": tid, "name": name, "input": {}}


def tool_result(content="ok", tid="t1", ago=50):
    return {"type": "user", "timestamp": ts(ago), "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "content": content}]}}


def test_last_text_tools_and_start():
    entries = [user("old", 500), asst(text("old reply"), ago=490),
               user("fix the bug", 100), asst(text("Looking."), tool("Edit")), tool_result(),
               asst(text("Fixed.\n\U0001F50A [pleased] Bug fixed."))]
    last, tools, start, pending = turn.last_turn(entries, now=NOW)
    assert last.startswith("Fixed.")
    assert tools == {"Edit"}
    assert (NOW - start).total_seconds() == 100
    assert pending == 0


def test_task_notification_is_not_a_new_turn():
    entries = [user("do it", 300), asst(tool("Agent")),
               tool_result("Async agent launched successfully", ago=290),
               user("<task-notification><tool-use-id>t1</tool-use-id></task-notification>", 20),
               asst(text("All done."))]
    last, tools, start, pending = turn.last_turn(entries, now=NOW)
    assert (NOW - start).total_seconds() == 300
    assert last == "All done."
    assert pending == 0


def test_pending_agent_counts_until_reported():
    entries = [user("do it", 300), asst(tool("Agent")),
               tool_result("Async agent launched successfully", ago=290), asst(text("Started."))]
    assert turn.last_turn(entries, now=NOW)[3] == 1


def test_old_pending_agent_expires():
    entries = [user("do it", 5 * 3600), asst(tool("Agent")),
               tool_result("Async agent launched successfully", ago=4 * 3600), asst(text("Started."))]
    assert turn.last_turn(entries, now=NOW)[3] == 0


def test_sidechain_and_meta_ignored():
    entries = [user("real", 100),
               {**user("meta", 50), "isMeta": True},
               {**user("sub", 40), "isSidechain": True},
               {**asst(text("subagent text")), "isSidechain": True},
               asst(text("main text"))]
    last, _, start, _ = turn.last_turn(entries, now=NOW)
    assert last == "main text"
    assert (NOW - start).total_seconds() == 100


def test_empty_transcript():
    assert turn.last_turn([], now=NOW) == ("", set(), None, 0)


def test_load_missing_and_bad_lines(tmp_path):
    assert turn.load(None) == []
    assert turn.load(tmp_path / "nope.jsonl") == []
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(user("hi")) + "\nnot json\n", encoding="utf-8")
    assert len(turn.load(p)) == 1


def test_category():
    assert turn.category({"ExitPlanMode", "Edit"}) == "planning"
    assert turn.category({"Read"}, "plan") == "ready"
    assert turn.category({"Write"}) == "coding"
    assert turn.category({"Bash"}) == "task"


def test_voice_line():
    assert turn.voice_line("Done.\n\n\U0001F50A [pleased, relieved] All three fixed.") == (
        "[pleased, relieved]", "All three fixed.")
    assert turn.voice_line("Done.\n\U0001F50A No mood here.  \n") == ("", "No mood here.")
    assert turn.voice_line("\U0001F50A [x] early line\nThen more text.") is None
    assert turn.voice_line("") is None
    assert turn.voice_line(None) is None


def test_project_name():
    assert turn.project_name("/home/me/my-cool_app", {}) == "my cool app"
    assert turn.project_name(str(Path("work") / "Skills-Repo"), {"Skills-Repo": "Skills"}) == "Skills"
    assert turn.project_name("", {}) == ""


def test_is_skipped(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(user("Session supervisor boot: hello")) + "\n", encoding="utf-8")
    assert turn.is_skipped(str(p), ["supervisor boot"])
    assert not turn.is_skipped(str(p), ["something else"])
    assert not turn.is_skipped(str(p), [])
    assert not turn.is_skipped(None, ["x"])


def wav(samples, sr=44100, channels=1, streamed=True):
    body = struct.pack(f"<{len(samples)}h", *samples)
    fmt = struct.pack("<HHIIHH", 1, channels, sr, sr * 2 * channels, 2 * channels, 16)
    riff = 0xFFFFFFFF if streamed else 4 + 8 + len(fmt) + 8 + len(body)
    size = 0xFFFFFFFF if streamed else len(body)
    return (b"RIFF" + struct.pack("<I", riff) + b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
            + b"data" + struct.pack("<I", size) + body)


def test_parse_streamed_wav():
    pcm, sr, ch = fish.parse_wav(wav([1, 2, 3, 4], 44100))
    assert (sr, ch) == (44100, 1)
    assert struct.unpack("<4h", pcm) == (1, 2, 3, 4)


def test_parse_wav_trims_odd_tail_and_honours_size():
    pcm, _, _ = fish.parse_wav(wav([1, 2, 3]) + b"\x07")
    assert len(pcm) == 6
    pcm, _, ch = fish.parse_wav(wav([1, 2, 3, 4], channels=2, streamed=False) + b"junkjunk")
    assert ch == 2 and len(pcm) == 8


def test_parse_wav_rejects_garbage():
    import pytest
    with pytest.raises(RuntimeError):
        fish.parse_wav(b"ID3" + b"\0" * 100)
