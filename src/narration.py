"""
Step 5b: the voice sets the pace.

Every shot's narration is recorded on its own in the channel voice (Kokoro,
am_echo), so we know exactly how long each sentence takes. Each shot then
gets a slot on screen: a breath before the voice, the voice, and a pause
after it so the picture can sink in (owner, 2026-10-17: leave people time
to process each step). The kits stretch their holds and the 3D camera
slows down to fill their slots (kits.blueprint.Beats.fitted, kits.timemap);
the voice track is laid along the finished reel, each shot's take starting
with its own shot.

    voiced = record(sheet, "out/voice")            # {clip: {"wav", "seconds"}}
    slots = slots_of(sheet, voiced)                # {clip: seconds on screen}
    track([(start_seconds, wav), ...], total_seconds, "out/voice.wav")
"""

import os

PAD_IN = 0.4         # silence before a shot's voice
PAD_OUT = 0.9        # and after it, before the next shot begins
MIN_SLOT = 3.0       # no shot flashes by, even with a one-line narration
SR = 24000           # Kokoro's sample rate


def _trim(samples, sr, floor=0.01):
    """Cuts the silence Kokoro leaves at both ends of a take."""
    import numpy as np
    loud = np.flatnonzero(np.abs(samples) > floor)
    if not len(loud):
        return samples
    a = max(0, loud[0] - int(0.03 * sr))
    b = min(len(samples), loud[-1] + int(0.08 * sr))
    return samples[a:b]


def record(sheet, out_dir, voice=None):
    """Records every shot's narration; returns {clip: {"wav", "seconds"}}."""
    import soundfile as sf
    from audio_engine import KOKORO_VOICE, _kokoro_instance_get, _kokoro_lang
    voice = voice or KOKORO_VOICE
    os.makedirs(out_dir, exist_ok=True)
    tts = _kokoro_instance_get()
    out = {}
    for sh in sheet["shots"]:
        text = (sh.get("narration") or "").strip()
        if not text:
            continue
        samples, sr = tts.create(text, voice=voice, speed=1.0, lang=_kokoro_lang(voice))
        samples = _trim(samples, sr)
        path = os.path.join(out_dir, f"{sh['clip']}.wav")
        sf.write(path, samples, sr)
        out[sh["clip"]] = {"wav": path, "seconds": round(len(samples) / sr, 3)}
        print(f"  {sh['clip']:<15} {out[sh['clip']]['seconds']:6.1f} s  ({len(text.split())} words)")
    return out


def slots_of(sheet, voiced):
    """Seconds each shot holds the screen: breath, voice, pause."""
    return {sh["clip"]: max(MIN_SLOT, PAD_IN + voiced.get(sh["clip"], {}).get("seconds", 0) + PAD_OUT)
            for sh in sheet["shots"]}


def track(placed, total, out_wav):
    """placed: [(start seconds, wav)]. Lays every take PAD_IN after its
    shot's start on one silent track of `total` seconds."""
    import numpy as np
    import soundfile as sf
    out = np.zeros(int(round(total * SR)) + 1, dtype=np.float32)
    ends = []
    for start, wav in sorted(placed):
        data, sr = sf.read(wav, dtype="float32")
        if sr != SR:
            raise ValueError(f"{wav}: {sr} Hz, expected {SR}")
        a = int(round((start + PAD_IN) * SR))
        b = min(len(out), a + len(data))
        out[a:b] += data[:b - a]
        ends.append((start + PAD_IN, start + PAD_IN + len(data) / SR, os.path.basename(wav)))
    for (a0, a1, n0), (b0, _, n1) in zip(ends, ends[1:]):
        if a1 > b0 + 0.05:
            print(f"  ⚠️ {n0} runs {a1 - b0:.1f} s into {n1}")
    sf.write(out_wav, np.clip(out, -1, 1), SR)
    return out_wav
