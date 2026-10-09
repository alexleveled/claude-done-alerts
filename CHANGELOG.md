# Changelog

## 0.1.3

- Setup and README: the Fish key has to be entered from Claude Code in a terminal (the VS Code panel has no `/plugin`), and it takes effect after `/reload-plugins`.

## 0.1.2

- The default Kokoro voice is now bm_daniel (calm, British, male) instead of af_heart. Anyone who picked a voice keeps it.

## 0.1.1

- Fixed: after a background agent finished, alerts stayed silent for up to three hours. Newer Claude Code versions record the agent's report as a queued command instead of a user message, so it wasn't being seen.
- Fixed: a tool's output that happened to contain the words "Async agent launched" counted as a running agent. Only real agent launches count now.

## 0.1.0

First public release.

- Spoken alerts when a turn finishes or Claude needs approval: the project name plus a line Claude writes (detailed) or a fixed phrase (standard)
- Kokoro (local, free) or Fish Audio (cloud, acts out a mood tag), with Kokoro as the fallback
- Fish API key stored through Claude Code's plugin options, in the system credential store
- Quiet for short turns and while background agents are still running; muted for headless runs
- Shares the voice model and playback lock with Read Aloud
- Guided setup with `/done-alerts:alerts setup`
- Windows, macOS and Linux (macOS and Linux audio not yet confirmed by a listener)
