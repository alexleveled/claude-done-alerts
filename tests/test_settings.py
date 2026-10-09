import importlib

import pytest


@pytest.fixture
def speak(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_VOICE_HOME", str(tmp_path))
    import home
    importlib.reload(home)
    import speak as sp
    importlib.reload(sp)
    return sp


def test_defaults(speak):
    import home
    s = home.load_settings()
    assert s["engine"] == "kokoro" and s["mode"] == "detailed" and s["min_turn_seconds"] == 20


def test_set_values(speak):
    import home
    assert "set to fish" in speak.cmd_set(["engine", "fish"])
    assert "kokoro or fish" in speak.cmd_set(["engine", "elevenlabs"])
    speak.cmd_set(["min", "45"])
    speak.cmd_set(["chime", "off"])
    speak.cmd_set(["voice", "bm_daniel"])
    speak.cmd_set(["fish_voice", "abc123", "My", "Voice"])
    s = home.load_settings()
    assert s["engine"] == "fish" and s["min_turn_seconds"] == 45 and s["chime"] is False
    assert s["kokoro_voice"] == "bm_daniel"
    assert s["fish_voice"] == {"name": "My Voice", "id": "abc123"}
    assert "detailed, standard or off" in speak.cmd_set(["mode", "loud"])
    assert "Settings:" in speak.cmd_set(["nonsense", "1"])


def test_fish_key_env(speak, monkeypatch):
    import home
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_FISH_API_KEY", raising=False)
    monkeypatch.delenv("FISH_API_KEY", raising=False)
    assert home.fish_key() is None
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_FISH_API_KEY", "  k1 ")
    assert home.fish_key() == "k1"


def test_status_runs(speak):
    assert "engine:" in speak.cmd_status()
