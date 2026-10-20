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


_ONES = ["twelve", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve"]
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty"}
_TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
          "seventeen", "eighteen", "nineteen"]


def _minutes(m):
    if m < 10:
        return f"oh {_ONES[m]}"
    if m < 20:
        return _TEENS[m - 10]
    return _TENS[m // 10] + (f"-{_ONES[m % 10]}" if m % 10 else "")


def _clock(h, m, half):
    """A clock time the way a narrator says it: "five past six in the
    evening", "half past nine at night", "midnight"."""
    h24 = (h % 12) + (12 if half == "p" else 0) if half else h
    if half and h24 in (0, 12) and m == 0:
        return "midnight" if h24 == 0 else "noon"
    part = ("in the morning" if h24 < 12 else "in the afternoon" if h24 < 18
            else "in the evening" if h24 < 21 else "at night") if half else ""
    hh = h % 12
    if not half:                         # no a.m./p.m.: "nine thirty", "six o'clock"
        return f"{_ONES[hh]} o'clock" if m == 0 else f"{_ONES[hh]} {_minutes(m)}"
    if m == 0:
        said = _ONES[hh]
    elif m == 15:
        said = f"quarter past {_ONES[hh]}"
    elif m == 30:
        said = f"half past {_ONES[hh]}"
    elif m == 45:
        said = f"quarter to {_ONES[(hh + 1) % 12]}"
    elif m in (5, 10, 20, 25):
        said = f"{_minutes(m) if m > 9 else 'five'} past {_ONES[hh]}"
    else:
        said = f"{_ONES[hh]} {_minutes(m)}"
    return f"{said} {part}".strip()


def spoken(text):
    """The narration as the voice should read it (owner, 2026-10-20: clock
    times came out very robotic): "6:05 p.m." becomes "five past six in the
    evening", "5 a.m." "five in the morning". Everything else is unchanged,
    and the word timings are taken on this same text."""
    import re

    def at(mo):
        h, m = int(mo.group(1)), int(mo.group(2) or 0)
        half = (mo.group(3) or "").lower()[:1] or None
        if not half and 12 < h < 24:         # 24-hour: 18:05 is five past six in the evening
            h, half = h - 12, "p"
        if h > 23 or m > 59 or (half and not 1 <= h <= 12):
            return mo.group(0)
        rest = mo.string[mo.end():]
        # "p.m." closing a sentence: its dot is the full stop too
        tail = "." if mo.group(4) and (not rest.strip() or re.match(r"\s+[A-Z]", rest)) else ""
        return _clock(h, m, half) + tail
    text = re.sub(r"\b(\d{1,2}):(\d{2})(?:\s*([ap])\.?\s?m\b(\.)?)?", at, text, flags=re.I)
    text = re.sub(r"\b(\d{1,2})()\s*([ap])\.?\s?m\b(\.)?", at, text, flags=re.I)
    return text


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
        text = spoken((sh.get("narration") or "").strip())
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


def words_of(text, wav):
    """When each word of a take is spoken: [{"word", "start", "end"}] in
    seconds from the take's start, anchored on the take's real pauses
    (audio_engine._align_kokoro), so on-screen events can land on the word
    that names them."""
    import soundfile as sf
    from audio_engine import _align_kokoro, _estimate_word_timings
    text = spoken(text)
    samples, sr = sf.read(wav, dtype="float32")
    try:
        words = _align_kokoro(text, samples, sr, "en-us")
        if words and len(words) == len(text.split()):
            return words
    except Exception as e:
        print(f"  word alignment failed ({type(e).__name__}): estimating")
    return _estimate_word_timings(text, len(samples) / float(sr))


def find_word(words, *needles):
    """Start of the first word matching any needle (case and punctuation
    ignored; a needle may be several words), or None."""
    import re
    norm = [re.sub(r"[^\w]", "", w["word"].lower()) for w in words]
    for needle in needles:
        parts = [re.sub(r"[^\w]", "", p.lower()) for p in str(needle).split()]
        parts = [p for p in parts if p]
        if not parts:
            continue
        for i in range(len(norm) - len(parts) + 1):
            if norm[i:i + len(parts)] == parts:
                return words[i]["start"]
    return None
