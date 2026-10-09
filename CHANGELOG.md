# Changelog

## 0.1.0

First public release.

- Spoken alerts when a turn finishes or Claude needs approval: the project name plus a line Claude writes (detailed) or a fixed phrase (standard)
- Kokoro (local, free) or Fish Audio (cloud, acts out a mood tag), with Kokoro as the fallback
- Fish API key stored through Claude Code's plugin options, in the system credential store
- Quiet for short turns and while background agents are still running; muted for headless runs
- Shares the voice model and playback lock with Read Aloud
- Guided setup with `/done-alerts:alerts setup`
- Windows, macOS and Linux (macOS and Linux audio not yet confirmed by a listener)
