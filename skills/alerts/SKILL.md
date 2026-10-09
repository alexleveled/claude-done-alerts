---
name: alerts
description: Control Done Alerts, the spoken notifications when Claude finishes a turn or needs approval. Use when the user types /done-alerts:alerts, or says "mute the alerts", "turn the voice off", "switch to Fish", "use the local voice", "test the alert", "set up done alerts". Arguments - setup, status, test, detailed, standard, off, on, engine <kokoro|fish>, voice <name>, speed <n>, min <seconds>, chime <on|off>, name <folder> <spoken name>, fish-voice <id> [name], voices.
argument-hint: "[setup | status | test | detailed | standard | off | engine kokoro|fish | voice <name> | min <s> | name <folder> <spoken>]"
---

# Done Alerts

Every command goes through one launcher. Write it out exactly, with the quotes:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/run.sh" <command>
```

| User asked for | Command |
|---|---|
| nothing, or `status` | `status` |
| `detailed` / `standard` / `off` | `set mode <that>` |
| `on` | `set mode detailed` |
| `engine kokoro` / `engine fish` | `set engine <that>` |
| `voice <name>` / `speed <n>` | `set voice <name>` / `set speed <n>` (Kokoro) |
| `fish-voice <id> [name]` | `set fish_voice <id> [name]` |
| `min <seconds>` | `set min <seconds>` |
| `chime on\|off` | `set chime <on\|off>` |
| `name <folder> <spoken name>` | `name <folder> <spoken name>` |
| `voices` | `voices` |
| `test` | `test` |
| `setup` | follow **Setup** below |

Reply with the command's output in a line or two. Settings apply on the next turn in every open session, with no restart.

`test` doesn't play anything itself. It queues a test line that the Stop hook speaks as soon as your reply ends, so it checks the real path from end to end. Keep the reply after `test` to one short line.

If the output says uv is missing, go to **Setup**.

## Modes

- `detailed` (default): the project name, then one line about how the turn went, which you write. While it's on, a hook asks you to end working turns with a line like `🔊 [pleased] Login bug fixed, all tests pass.` With Fish, the bracketed mood is acted out. Kokoro reads the sentence plainly.
- `standard`: the project name and a fixed phrase ("Finished coding.", "Task finished.", "Planning's done, please review."). You write nothing extra.
- `off`: silent.

Turns shorter than `min_turn_seconds` (default 20) stay quiet, so quick back-and-forth doesn't chatter. Permission prompts always speak: "I need your approval."

## Setup

Walk the user through this one step at a time. Ask before installing anything.

1. Run `doctor`.
   - **uv missing** (the launcher says so): uv is the Python tool that installs and runs the alerts. Explain that, ask, then install it:
     - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
     - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

     Run `doctor` again. The first run takes up to a minute while uv installs Python and the packages.
   - **`audio_output` is null:** on Linux, ask, then install PortAudio (`sudo apt install libportaudio2`, or `sudo dnf install portaudio`). Elsewhere, ask the user to check their speakers.
2. **Pick the voice.** Ask which they want:
   - **Kokoro** (default): free, runs on their computer, nothing leaves the machine. Needs a one-time 92 MB download. Doesn't act out moods.
   - **Fish Audio**: a more expressive cloud voice that acts out the mood of each line. Needs a Fish Audio account and API key, and costs a fraction of a cent per alert (the fixed phrases are cached, so they're only paid for once).
3. **Kokoro:** if `kokoro_model_missing` isn't empty, run `download` (also needed for Fish users, as the fallback when Fish can't be reached, unless they'd rather skip it with `set kokoro_fallback off`). Offer `voices` and `set voice <name>` if they want a different voice than bm_daniel (calm, British, male).
4. **Fish:** run `set engine fish`. Then the user adds their key, which Claude Code stores in the system's secure credential store, not in a file:
   - Get a key at https://fish.audio → API Keys.
   - Type `/plugin configure done-alerts@alexleveled` and paste the key (or `/plugin` → Installed → done-alerts → Configure options).
   - Never ask the user to paste the key into the chat.

   The default voice is Alok (calm, British, male), with Sarah as backup. To use another voice from https://fish.audio/discovery: `set fish_voice <id> <name>`.
5. Run `test`, end the reply there, and ask in that same reply whether they heard it. If they didn't, run `doctor` on the next turn and read `recent_log`: it says which engine played, or why it didn't. `fish_key_visible_here: false` is normal, since only the hooks receive the key. If a hook never ran at all (no new log line), the plugin may need `/reload-plugins` or a new session.

Finish with a short summary: what they'll hear, `/done-alerts:alerts off` to mute, `standard` for fixed phrases only.

## Notes

- Muted automatically for headless runs (`claude -p`, Agent SDK apps). Set `CLAUDE_DONE_ALERTS_MUTE=1` in the environment to mute one session, or add a string from a session's first message to `skip_sessions` in `~/.claude-voice/done-alerts/settings.json` to mute an always-on bot.
- Two sessions finishing together take turns instead of talking over each other. The lock is shared with the Read Aloud plugin.
- Settings, the model and the log (`alerts.log`) live in `~/.claude-voice/`.
