# Done Alerts for Claude Code

You kick off a long task, switch to another window, and forget about it. Twenty minutes later you check back and Claude has been sitting there since minute three, waiting for you to approve something.

Done Alerts gives Claude a voice for those moments. When a turn finishes, you hear the project name and one line on how it went:

> "Billing service. Found the race condition, all forty tests pass now."

When Claude needs your approval, it says so: *"Billing service. I need your approval."*

- **Detailed mode** (default): Claude writes the line itself, with a mood tag for the voice actor, so a rough turn sounds different from a clean one
- **Standard mode**: fixed phrases only ("Finished coding.", "Planning's done, please review.")
- Quick back-and-forth stays quiet. Only turns longer than 20 seconds speak, and you can change that
- Several sessions finishing at once take turns instead of talking over each other

https://github.com/user-attachments/assets/e3a2c7be-fb1e-4951-990d-9a05dae9fefa

*Claude researches a question, finishes, and says so out loud with a one-line summary. Turn your sound on.*

## Pick a voice

| | Kokoro (default) | Fish Audio |
|---|---|---|
| Runs | on your computer, CPU only | in the cloud |
| Cost | free | a fraction of a cent per alert |
| Account | none | [fish.audio](https://fish.audio) API key |
| Mood | reads the line plainly | acts out the mood tag: relieved, frustrated, upbeat |
| Privacy | nothing leaves your machine | the one-line summary is sent to Fish |

Fish is the more human sounding of the two by a wide margin. Kokoro is the one you can install in thirty seconds and forget about. You can switch any time, and with Fish selected, Kokoro steps in whenever Fish can't be reached.

## Install

Paste this into Claude Code:

```
Install the done-alerts plugin from the alexleveled/claude-plugins marketplace, then run /done-alerts:alerts setup
```

Claude adds the marketplace, installs the plugin and walks you through setup. It asks before installing anything.

Or do it yourself:

```
/plugin marketplace add alexleveled/claude-plugins
/plugin install done-alerts@alexleveled
/done-alerts:alerts setup
```

Setup checks for [uv](https://docs.astral.sh/uv/) (the Python tool that runs the alerts) and installs it if you say yes. Then it asks which voice you want, downloads the Kokoro model (92 MB, one time) and plays a test alert.

### Adding a Fish Audio key

Get a key at [fish.audio](https://fish.audio) under API Keys. Then, in Claude Code running in a terminal, type `/plugin configure done-alerts@alexleveled` and paste the key into the field it shows. Then run `/reload-plugins` (or start a new session) so the alerts pick it up.

Using the VS Code extension? Its chat panel doesn't have `/plugin`. Open VS Code's terminal, run `claude`, do the step above there, `/exit`, then `/reload-plugins` back in the panel. The key is saved for your account, so every session gets it.

Claude Code keeps the key in your system's secure credential store and hands it only to the alert hooks. It never sits in a plain file, and you never have to paste it into the chat.

## Use

| You type | It does |
|---|---|
| `/done-alerts:alerts` | shows the current settings |
| `/done-alerts:alerts off` | mutes everything. `on` turns it back on |
| `/done-alerts:alerts standard` | fixed phrases only. `detailed` for Claude's own line |
| `/done-alerts:alerts engine fish` | switches to Fish. `engine kokoro` switches back |
| `/done-alerts:alerts voice bm_george` | picks a Kokoro voice (`voices` lists them) |
| `/done-alerts:alerts fish-voice <id> <name>` | picks any voice from the [Fish library](https://fish.audio/discovery) |
| `/done-alerts:alerts min 60` | only speak for turns longer than a minute |
| `/done-alerts:alerts name my-api-v2 "the API"` | how a project folder gets announced |
| `/done-alerts:alerts chime off` | no chime before the voice |
| `/done-alerts:alerts test` | plays a test alert when the reply finishes |

Natural language works too: "mute the alerts", "switch to the local voice".

## Settings

Everything lives in `~/.claude-voice/done-alerts/settings.json`. The commands above edit it for you. Changes apply on the next turn in every open session.

| Key | Default | |
|---|---|---|
| `engine` | `kokoro` | `kokoro` or `fish` |
| `mode` | `detailed` | `detailed`, `standard` or `off` |
| `min_turn_seconds` | `20` | turns shorter than this stay quiet. Approval prompts always speak |
| `chime` | `true` | a short chime before each alert |
| `kokoro_voice` / `kokoro_speed` | `bm_daniel` / `1.0` | |
| `fish_voice` / `fish_backup_voice` | Alok / Sarah | the backup is used if the main voice disappears from the Fish library |
| `fish_model` | `s2.1-pro` | `s2.1-pro-free` is free while Fish offers it |
| `kokoro_fallback` | `true` | with Fish selected, use Kokoro when Fish can't be reached |
| `project_names` | `{}` | folder name → spoken name |
| `skip_sessions` | `[]` | text from the first message of sessions that should never speak, like an always-on bot |

## How it works

Four hooks:

- **UserPromptSubmit**, detailed mode only: adds a short note to your prompt asking Claude to end working turns with a line like `🔊 [relieved] Fixed the flaky test, everything passes.` You'll see that line at the bottom of Claude's replies.
- **Stop**: reads the session transcript to find that line, works out what kind of turn it was (planning, coding, other) and how long it took, then hands off to a background process that synthesizes and plays it. Claude Code is never held up waiting for audio.
- **Notification**: permission prompts and questions.
- **SessionStart**: installs the packages and downloads the Kokoro model in the background, so the first alert is quick.

When Claude launches background agents and stops to wait for them, Done Alerts stays quiet until the work is actually done. Headless runs (`claude -p`, Agent SDK apps) are muted automatically. Set `CLAUDE_DONE_ALERTS_MUTE=1` to mute one session by hand.

Claude Code's transcript format isn't a public API. If an update changes it, the alerts fall back to the fixed phrases rather than going silent. Please [open an issue](https://github.com/alexleveled/claude-done-alerts/issues) if that happens.

The Kokoro model comes from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0) and gets checked against a pinned SHA-256 before use. The log is at `~/.claude-voice/done-alerts/alerts.log`.

## Platforms

Built and tested on Windows. macOS and Linux should work, and the tests run on all three in CI, but nobody has heard an alert on them yet. If you try it, an issue saying "works on my Mac" helps a lot. On Linux, audio needs PortAudio (`sudo apt install libportaudio2`); setup handles it.

## Also by me

**[Read Aloud](https://github.com/alexleveled/claude-read-aloud)**: hear Claude's last reply read out loud, from a slash command or a ▶ button in VS Code. It uses the same voice model, so it downloads once, and the two plugins take turns rather than talking over each other.

## Uninstall

```
/plugin uninstall done-alerts@alexleveled
```

Then delete `~/.claude-voice/` if you don't use Read Aloud.

## License

MIT. Kokoro is Apache 2.0. Fish Audio is a separate paid service with its own terms.
