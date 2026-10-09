#!/bin/sh
# Finds uv and runs Done Alerts through it. uv installs Python and the packages on first use,
# so there is no virtualenv to manage.
#   run.sh hook <prompt|stop|notify>   called by Claude Code's hooks (reads the hook's JSON on stdin)
#   run.sh session-start               SessionStart hook
#   run.sh <command>                   anything speak.py takes (status, set, test, doctor, ...)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

UV="$(command -v uv 2>/dev/null)"
for c in "$HOME/.local/bin/uv" "$HOME/.local/bin/uv.exe" "$HOME/.cargo/bin/uv" "$HOME/.cargo/bin/uv.exe" \
         /opt/homebrew/bin/uv /usr/local/bin/uv; do
  [ -z "$UV" ] && [ -x "$c" ] && UV="$c"
done

if [ -z "$UV" ]; then
  case "$1" in
    hook) exit 0 ;;  # never get in the way of a session; setup explains what's missing
    session-start)
      echo "Done Alerts plugin: uv is not installed yet, so spoken alerts are off. If the user mentions alerts or voice, offer to run /done-alerts:alerts setup."
      exit 0 ;;
  esac
  echo "Done Alerts needs uv (https://docs.astral.sh/uv/). Run /done-alerts:alerts setup and Claude will install it for you."
  exit 3
fi
export DONE_ALERTS_UV="$UV"

case "$1" in
  hook)
    shift
    # hook.py needs only the standard library, so skip uv's environment check (about a
    # sixth of a second on Windows, on every prompt) and run the Python that session-start
    # recorded. Falls back to uv if that Python has gone away.
    PY="$(cat "${CLAUDE_VOICE_HOME:-$HOME/.claude-voice}/done-alerts/python.path" 2>/dev/null)"
    if [ -n "$PY" ] && [ -f "$PY" ]; then
      exec "$PY" -I "$ROOT/alerts/hook.py" "$@"
    fi
    exec "$UV" run --quiet --script "$ROOT/alerts/hook.py" "$@" ;;
  session-start)
    # Background it: the first run installs packages and may download the voice model,
    # and a SessionStart hook must never hold up the session.
    nohup "$UV" run --quiet --script "$ROOT/alerts/speak.py" session-start >/dev/null 2>&1 &
    exit 0 ;;
esac
exec "$UV" run --quiet --script "$ROOT/alerts/speak.py" "$@"
