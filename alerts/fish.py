"""Fish Audio text to speech (https://fish.audio). Standard library only.

Fish's S2 models act out a mood tag at the start of the text, like "[pleased, relieved]",
which is what makes detailed alerts sound like a person reacting rather than a readout.
"""
import json
import struct
import urllib.error
import urllib.request

API = "https://api.fish.audio/v1/tts"


class AccountError(RuntimeError):
    """Bad key, no credit or rate limited: a backup voice won't help."""


def tts(text, voice_id, key, model, timeout=15):
    """Return (pcm16_bytes, sample_rate, channels)."""
    body = json.dumps({"text": text, "reference_id": voice_id, "format": "wav"}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "model": model,
        "User-Agent": "claude-done-alerts",
    })
    try:
        data = urllib.request.urlopen(req, timeout=timeout).read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 402, 403, 429):
            raise AccountError(f"Fish HTTP {e.code}") from e
        raise
    if len(data) < 1000:
        raise RuntimeError(f"Fish returned {len(data)} bytes")
    return parse_wav(data)


def parse_wav(data):
    """Return (pcm16_bytes, sample_rate, channels) from a 16-bit PCM WAV.

    Fish streams its WAV, so the RIFF and data sizes are 0xFFFFFFFF placeholders. Read the
    format chunk and take everything after the data header as audio."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise RuntimeError("not a WAV")
    sr = channels = bits = None
    i = 12
    while i + 8 <= len(data):
        cid = data[i:i + 4]
        size = struct.unpack("<I", data[i + 4:i + 8])[0]
        if cid == b"fmt ":
            fmt, channels, sr = struct.unpack("<HHI", data[i + 8:i + 16])
            bits = struct.unpack("<H", data[i + 22:i + 24])[0]
            if fmt not in (1, 0xFFFE) or bits != 16:
                raise RuntimeError(f"unsupported WAV format {fmt}/{bits}-bit")
        elif cid == b"data":
            if sr is None:
                raise RuntimeError("WAV data before format")
            body = data[i + 8:]
            if size != 0xFFFFFFFF and size <= len(body):
                body = body[:size]
            body = body[:len(body) - len(body) % (2 * channels)]
            return body, sr, channels
        i += 8 + size + (size % 2)
    raise RuntimeError("no data chunk")
