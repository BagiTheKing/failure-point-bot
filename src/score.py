"""
The episode's sound: the narration over a score (owner, 2026-10-18: "some
soundtracks should be good").

The cold open gets a thriller track up front and loud; every later part
gets a quiet bed, one track per part, crossfading at the part changes. The
music ducks under the voice (it follows the voice's own loudness), so words
are never fought for. Tracks come from music/ only (YouTube Audio Library
or Creative Commons with a credit sidecar, see music/README.md), and every
track used that needs a credit is returned for the description.

    credits = mix(voice_wav, plan, total, out_wav)
    plan: [(start, end, track filename, level)]
"""

import os
import subprocess

import numpy as np

from music_attribution import attribution_for

SR = 48000
MUSIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "music")
XFADE = 2.5

# one track per part of the 7-part structure, the cold open first
# owner's pick from the audition, 2026-10-18 (tools/fetch_music.py fetches it)
COLD_OPEN = os.getenv("INTRO_TRACK", "Impact Prelude - Kevin MacLeod.mp3")
PARTS = {1: "Lightless Dawn - Kevin MacLeod.mp3",          # the disaster: somber
         2: "Hidden Wonders - Kevin MacLeod.mp3",          # the structure: mysterious, like the intro's
         3: "Stay the Course - Kevin MacLeod.mp3",         # the physics: suspenseful, calm under the voice
         4: "Volatile Reaction - Kevin MacLeod.mp3",       # second by second: intense
         5: "Man Down - Kevin MacLeod.mp3",                # warnings and investigation: somber
         6: "Tyrant - Kevin MacLeod.mp3",                  # how it should have worked: steady
         7: "Leaving Home - Kevin MacLeod.mp3"}            # could it happen today: reflective
# all Kevin MacLeod (incompetech.com, CC BY 4.0), fetched with their credit
# by tools/fetch_music.py: the owner turned down the old horror-style beds
TRACKS = [COLD_OPEN] + sorted(set(PARTS.values()))
OPEN_LEVEL = 0.55            # the cold open's music, before ducking
BED_LEVEL = 0.10             # under the analysis
DUCK = 0.55                  # how far the music drops while the voice speaks
# a bed mastered hotter than this is turned down to it first: the tracks
# here range twentyfold (0.013 to 0.24 RMS), and two parts' beds came out
# "too loud for the ear" (owner, 2026-10-20, at a pause and at a part
# change). Quiet tracks are never raised, and the cold open's track is left
# as the owner chose it.
BED_RMS = 0.12


def _load(path, channels=2):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", str(channels),
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, channels).copy()


def _tamed(track):
    """The track turned down to BED_RMS if it is louder, measured on its
    sounding parts (a quiet intro or tail does not hide a loud body)."""
    level = np.sqrt((track ** 2).mean(axis=1))
    loud = level[level > 1e-3]
    rms = float(np.sqrt((loud ** 2).mean())) if len(loud) else 0.0
    return track * (BED_RMS / rms) if rms > BED_RMS else track


def _looped(track, n):
    if len(track) >= n:
        return track[:n]
    reps = int(np.ceil(n / len(track)))
    return np.concatenate([track] * reps)[:n]


def _ramp(n, a, b):
    return np.linspace(a, b, max(1, n), dtype=np.float32)


def _duck_gain(voice, depth=DUCK):
    """1 where the voice is silent, 1 - depth where it speaks: an envelope
    follower (fast attack, slow release) on the voice's level."""
    level = np.abs(voice).astype(np.float32)
    hop = SR // 100                                         # 10 ms frames
    n = len(level) // hop
    frames = level[: n * hop].reshape(n, hop).mean(axis=1)
    on = np.clip(frames / max(1e-4, np.percentile(frames, 90) * 0.25), 0, 1)
    env = np.zeros_like(on)
    # fast attack; a release slow enough (about a second) that the music
    # does not swell back up in the breath between two shots
    att, rel = 0.5, 0.012                                    # per 10 ms
    for i in range(1, len(on)):
        k = att if on[i] > env[i - 1] else rel
        env[i] = env[i - 1] + k * (on[i] - env[i - 1])
    gain = np.repeat(1 - depth * env, hop)
    return np.concatenate([gain, np.ones(len(level) - len(gain), np.float32)])


def mix(voice_wav, plan, total, out_wav):
    """Narration plus score, written as a 48 kHz stereo WAV; returns the
    credit lines the description needs for the tracks used."""
    import soundfile as sf
    n = int(round(total * SR))
    voice = _load(voice_wav, 1)[:, 0]
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    music = np.zeros((n, 2), np.float32)
    credits, cache = [], {}
    for entry in plan:
        start, end, name, level = entry[:4]
        fade_in = entry[4] if len(entry) > 4 else XFADE
        path = os.path.join(MUSIC_DIR, name)
        if not os.path.exists(path):
            print(f"  music missing, silent instead: {name}")
            continue
        if (name, level) not in cache:
            raw = _load(path)
            cache[(name, level)] = _tamed(raw) if level < OPEN_LEVEL else raw
        a = max(0, int((start - min(XFADE, fade_in) / 2) * SR))
        b = min(n, int((end + XFADE / 2) * SR))
        if b <= a:
            continue
        seg = _looped(cache[(name, level)], b - a) * level
        f, fi = int(XFADE * SR), max(1, int(fade_in * SR))
        env = np.ones(b - a, np.float32)
        env[:fi] = _ramp(min(fi, b - a), 0, 1)[: len(env[:fi])]
        env[-f:] = np.minimum(env[-f:], _ramp(min(f, b - a), 1, 0)[-len(env[-f:]):])
        music[a:b] += seg * env[:, None]
        credit = attribution_for(path)
        if credit and credit not in credits:
            credits.append(credit)
    gain = _duck_gain(voice)[:n]
    out = music * gain[:, None] + voice[:, None]
    tail = int(min(3.0, total / 4) * SR)                     # the last seconds fade out
    out[-tail:] *= _ramp(tail, 1, 0)[:, None]
    sf.write(out_wav, np.clip(out, -1, 1), SR)
    return credits


def even_loudness(in_wav, out_wav, target=-16.0, peak=-1.5):
    """The whole mix brought to `target` LUFS with ONE gain (ffmpeg
    loudnorm, measured first, then applied linearly). The single-pass
    loudnorm the episodes used rides its gain through the video: it turns
    up during every pause, so the first words after one, and the cold
    open's first hit, came out in a loud burst (owner, 2026-10-20: "too
    loud for the ear" at 0:01, 3:53, 5:53, each right after a pause)."""
    import json
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", in_wav, "-af",
                            f"loudnorm=I={target}:TP={peak}:LRA=20:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
    m = json.loads(probe[probe.rindex("{"):probe.rindex("}") + 1])
    af = (f"loudnorm=I={target}:TP={peak}:LRA=20:linear=true:measured_I={m['input_i']}:"
          f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", in_wav, "-af", af, "-ar", str(SR), out_wav],
                   check=True)
    return out_wav


def shutter(seed=0):
    """A camera shutter, synthesized (no sound library, nothing to license):
    the blade's sharp click, the mirror's thud 40 ms later, a short metallic
    ring. Stereo float32 at SR."""
    rnd = np.random.default_rng(seed)
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)

    def click(at, length, bright, gain):
        a, m = int(at * SR), int(length * SR)
        noise = rnd.standard_normal(m).astype(np.float32)
        if bright:
            noise = np.diff(noise, prepend=0)                  # crisp, high
        env = np.exp(-np.arange(m) / (m / 5)).astype(np.float32)
        out[a:a + m] += gain * noise * env

    click(0.000, 0.012, True, 0.9)                             # the blades
    click(0.040, 0.030, False, 0.6)                            # the mirror slaps back
    thud = np.sin(2 * np.pi * 140 * t) * np.exp(-t / 0.018) * (t >= 0.040)
    ring = np.sin(2 * np.pi * 3100 * t) * np.exp(-(t - 0.004).clip(0) / 0.03) * 0.08
    out += (0.35 * thud + ring).astype(np.float32)
    out /= max(1e-6, np.abs(out).max())
    pan = 0.15 * rnd.uniform(-1, 1)
    return np.stack([out * (1 - pan), out * (1 + pan)], axis=1) * 0.8


def add_sfx(mix_wav, sfx, out_wav):
    """Lays sound effects [(seconds, samples (n, 2))] over a mixed track."""
    import soundfile as sf
    data, sr = sf.read(mix_wav, dtype="float32", always_2d=True)
    for at, s in sfx:
        a = int(at * sr)
        b = min(len(data), a + len(s))
        if a < b:
            data[a:b] += s[: b - a]
    sf.write(out_wav, np.clip(data, -1, 1), sr)
    return out_wav


# ---------------------------------------------------------------------------
# Sound effects for the cold open, synthesized (owner, 2026-10-18: "effects,
# that is important"). All stereo float32 at SR, peak about 0.8.
# ---------------------------------------------------------------------------

def _norm(x, peak=0.8):
    return (x / max(1e-6, np.abs(x).max()) * peak).astype(np.float32)


def _st(x, width=0.0):
    return np.stack([x * (1 - width), x * (1 + width)], axis=1).astype(np.float32)


def _lowpass(x, k):
    """A cheap moving-average low-pass of k samples."""
    if k <= 1:
        return x
    c = np.cumsum(np.concatenate([np.zeros(k), x]))
    return ((c[k:] - c[:-k]) / k).astype(np.float32)


def boom(seed=1, length=2.2):
    """A deep cinematic impact: a sub-bass drop with a noise crack on top."""
    rnd = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    f = 38 + 60 * np.exp(-t / 0.08)                           # pitch falls into the sub
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.7)
    crack = _lowpass(rnd.standard_normal(n).astype(np.float32), 6) * np.exp(-t / 0.05)
    tail = _lowpass(rnd.standard_normal(n).astype(np.float32), 60) * np.exp(-t / 0.9) * 0.6
    return _st(_norm(sub + 0.5 * crack + tail))


def whoosh(seed=2, length=0.55):
    """Air rushing past: noise swept up then down in brightness and level."""
    rnd = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / n
    env = np.sin(np.pi * t) ** 2
    noise = rnd.standard_normal(n).astype(np.float32)
    dark = _lowpass(noise, 40)
    bright = noise - _lowpass(noise, 8)
    mix = dark * (1 - env) + bright * env
    pan = np.linspace(-0.5, 0.5, n)
    x = _norm(mix * env, 0.6)
    return np.stack([x * (1 - pan), x * (1 + pan)], axis=1).astype(np.float32)


def riser(length=2.4, seed=3):
    """Tension climbing into a hit: noise and a rising tone, growing."""
    rnd = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    grow = (t / length) ** 2
    f = 180 * (1 + 4 * (t / length) ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25
    hiss = rnd.standard_normal(n).astype(np.float32)
    hiss = hiss - _lowpass(hiss, int(30 - 26 * (0.5)))
    return _st(_norm((tone + 0.5 * hiss) * grow, 0.55), 0.1)


def rumble(length=4.0, seed=4):
    """Heavy steel and concrete going: a low rumble with metal groans."""
    rnd = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n) / SR
    low = _lowpass(rnd.standard_normal(n).astype(np.float32), 120)
    env = np.minimum(1, t / 0.3) * np.exp(-np.maximum(0, t - length * 0.6) / 0.6)
    groan = np.zeros(n, np.float32)
    for k in range(3):                                         # creaks, falling in pitch
        at = rnd.uniform(0.1, length * 0.7)
        m = (t >= at) & (t < at + 0.7)
        f = 260 - 140 * (t - at) / 0.7
        groan += np.where(m, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * (t - at) / 0.7), 0)
    return _st(_norm(low * env * 3 + 0.25 * groan * env, 0.8), 0.05)
