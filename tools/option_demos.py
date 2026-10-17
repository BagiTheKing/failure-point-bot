"""
Animation options, side by side, on one story (the Hyatt Regency walkways).

Step 3 of the redesign: before choosing how the pipeline makes its
mechanism animations, each candidate is tried for real on the same beat
(the building, the connection, the doubled load, the failure).

    python tools/option_demos.py scratch out/   # free writers write the whole animation
    python tools/option_demos.py blocks out/    # free writers describe a scene; our renderer draws it
    python tools/option_demos.py aivideo out/   # a generated still, animated by Wan 2.2 (HF Space)

Every result is kept as it comes out, failures included: the point is to see
what each option does unattended.
"""

import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

FACTS = """Hyatt Regency walkway collapse, Kansas City, 17 July 1981, 7:05 pm.
- A hotel atrium had two suspended walkways stacked one above the other: the
  4th-floor walkway directly above the 2nd-floor walkway. (A third walkway, on
  the 3rd floor, was off to the side and did not fall.)
- Both hung from the atrium roof on steel hanger rods, three rod lines along
  the length. Each walkway rested on cross beams ("box beams": two steel
  channels welded toe to toe) that the rods passed through, held by a nut
  under the beam.
- AS DESIGNED: one continuous rod from the roof through the 4th-floor beam
  down to the 2nd-floor beam. Each nut carried one walkway.
- AS BUILT (a change approved in 1979): two rods. The upper rod went from the
  roof to the 4th-floor beam. A separate lower rod hung from the 4th-floor
  beam down to the 2nd-floor beam. So the nut under the 4th-floor beam
  carried BOTH walkways: twice the load it was meant to.
- On the night, the nut and rod pulled through the bottom of the 4th-floor
  box beam at the middle rod. The 4th-floor walkway fell onto the 2nd-floor
  walkway and both fell to the lobby floor, crowded for a tea dance.
- 114 people killed, 216 injured.
"""

BEAT = """the building drawn as a side elevation (roof, rods, the two walkways
stacked, people), then the camera zooms into the middle 4th-floor connection,
arrows show the 4th-floor walkway's weight and the 2nd-floor walkway pulling
on the lower rod, both arriving on one nut ("2x load"), the steel turns red,
the nut pulls through, and the 4th-floor walkway falls onto the 2nd and both
fall."""

STYLE = """Blueprint style: dark navy background (9,22,41) with a faint grid,
white lines (226,236,255), the failing part in red (255,75,58), forces as amber
arrows (255,176,32), labels in cyan (70,210,255) with leader lines."""


# ---------------------------------------------------------------------------
# The writers
# ---------------------------------------------------------------------------

def writers(limit=4):
    """One model per provider, in the pipeline's own order."""
    from llm_provider import get_pool
    pool = get_pool()
    print("writers configured:", pool.describe())
    picked, seen = [], set()
    for m in pool.models:
        p = pool.provider_for(m)
        if p in seen:
            continue
        seen.add(p)
        picked.append((pool, m, p))
    return picked[:limit]


def ask(pool, model, system, user, max_tokens=8000):
    from longform_llm import _reply_text
    client = pool.client_for(model)
    r = client.chat.completions.create(
        model=pool.api_name(model),
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.4, max_tokens=max_tokens)
    return _reply_text(r) or ""


def code_block(text):
    m = re.findall(r"```(?:python|py|json)?\s*\n(.*?)```", text, re.S)
    return max(m, key=len) if m else text


# ---------------------------------------------------------------------------
# Option: the writer writes the whole animation program
# ---------------------------------------------------------------------------

REPAIRS = 2     # times a writer may fix its own crash

SCRATCH_PROMPT = f"""Write ONE complete Python 3 program that renders an
animated engineering explainer clip and saves it as an MP4.

The clip, about 14 seconds, 1280x720, 30 fps, no sound: {BEAT}

{STYLE}

Facts (stay accurate to them):
{FACTS}

Rules for the program:
- Use only Pillow (PIL), numpy and the ffmpeg command line (installed).
  Fonts: use ImageFont.truetype("fonts/Inter-Bold.otf", size) (the file
  exists); fall back to ImageFont.load_default() if it fails.
- The output path is sys.argv[1].
- It must run unattended in under 4 minutes and exit 0.
Reply with the program only, in one ```python block."""


def scratch(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    report = []
    for pool, model, provider in writers():
        tag = re.sub(r"[^a-z0-9]+", "-", provider.lower())
        src = os.path.join(out_dir, f"scratch_{tag}.py")
        mp4 = os.path.join(out_dir, f"scratch_{tag}.mp4")
        row = {"provider": provider, "model": model}
        t = time.time()
        try:
            code = code_block(ask(pool, model, "You write correct, complete Python programs.",
                                  SCRATCH_PROMPT))
        except Exception as e:
            row["result"] = f"writer failed: {type(e).__name__}: {str(e)[:200]}"
            report.append(row)
            print(row)
            continue
        row["attempts"] = []
        for attempt in range(1 + REPAIRS):
            open(src, "w").write(code)
            row["lines"] = code.count("\n") + 1
            try:
                p = subprocess.run([sys.executable, src, mp4], capture_output=True, text=True,
                                   timeout=300)
                ok = p.returncode == 0 and os.path.exists(mp4) and os.path.getsize(mp4) > 10000
                err = "" if ok else (p.stderr or p.stdout)[-1500:]
            except subprocess.TimeoutExpired:
                ok, err = False, "timed out after 300 s"
            row["attempts"].append("rendered" if ok else err[-300:])
            if ok or attempt == REPAIRS:
                break
            # the pipeline would retry: hand the writer its own error
            try:
                code = code_block(ask(pool, model, "You write correct, complete Python programs.",
                                      SCRATCH_PROMPT + "\n\nYour previous program:\n```python\n"
                                      + code + "\n```\nfailed with:\n" + err
                                      + "\nReply with the whole corrected program."))
            except Exception as e:
                row["attempts"].append(f"writer failed: {type(e).__name__}")
                break
        row["result"] = "rendered" if ok else "crashed every time"
        row["seconds"] = round(time.time() - t)
        report.append(row)
        print(json.dumps(row, indent=1))
    json.dump(report, open(os.path.join(out_dir, "scratch_report.json"), "w"), indent=1)


# ---------------------------------------------------------------------------
# Option: the writer describes the scene with fixed building blocks, and our
# own renderer (the A-F look) draws it
# ---------------------------------------------------------------------------

BLOCKS_PROMPT = f"""You lay out an animated engineering diagram. You do NOT
write code: you describe the scene in JSON, using only the building blocks
below, and a renderer draws it in a fixed blueprint style.

The scene to describe, about 14 seconds: {BEAT}

Facts (stay accurate to them):
{FACTS}

Coordinates: world units, x 0-1280 left to right, y 0-720 top to bottom,
as seen at zoom 1. The camera can zoom in on any point later.

Parts (each has a unique "id"):
- {{"id","type":"line","x0","y0","x1","y1","width"}}  roof, walls, floor, rods
- {{"id","type":"box","x0","y0","x1","y1"}}            beams, decks
- {{"id","type":"nut","x","y"}}                        a small solid block (a nut or bolt head)
- {{"id","type":"people","x0","x1","y","n"}}           n standing figures with feet on y

Steps (each has "t" = start time in seconds):
- {{"t","do":"draw","ids":[...],"dur"}}                 the parts draw themselves in
- {{"t","do":"label","target":id,"text","color":"cyan|red|amber","dur"}}  label with a leader line, shown for dur seconds
- {{"t","do":"camera","x","y","zoom","dur"}}            move the camera so (x,y) is centred at this zoom
- {{"t","do":"force","x0","y0","x1","y1","text"}}       an amber arrow from (x0,y0) to (x1,y1), with a short text
- {{"t","do":"stress","ids":[...],"dur"}}               these parts glow and turn red over dur seconds
- {{"t","do":"fail","ids":[...],"dy","dur"}}            these parts fall dy units over dur seconds
- {{"t","do":"caption","text","dur"}}                   a subtitle at the bottom for dur seconds
- {{"t","do":"big","text","color","dur"}}               a large statement on screen, like "2x LOAD"

Reply with ONE JSON object {{"duration": seconds, "parts": [...], "steps": [...]}}
in a ```json block, nothing else."""


def blocks(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    report = []
    for pool, model, provider in writers():
        tag = re.sub(r"[^a-z0-9]+", "-", provider.lower())
        spec_path = os.path.join(out_dir, f"blocks_{tag}.json")
        mp4 = os.path.join(out_dir, f"blocks_{tag}.mp4")
        row = {"provider": provider, "model": model}
        try:
            raw = code_block(ask(pool, model, "You reply with valid JSON only.", BLOCKS_PROMPT))
            spec = json.loads(raw)
            json.dump(spec, open(spec_path, "w"), indent=1)
            row["parts"], row["steps"] = len(spec.get("parts", [])), len(spec.get("steps", []))
            render_spec(spec, mp4)
            row["result"] = "rendered"
        except Exception as e:
            row["result"] = f"failed: {type(e).__name__}: {str(e)[:300]}"
        report.append(row)
        print(json.dumps(row, indent=1))
    json.dump(report, open(os.path.join(out_dir, "blocks_report.json"), "w"), indent=1)


COLORS = None


def render_spec(spec, mp4):
    """Draws a blocks scene with the A-F primitives (tools/style_samples.py)."""
    import shutil
    import style_samples as S
    from PIL import ImageDraw
    colors = {"cyan": S.CYAN, "red": S.RED, "amber": S.AMBER, "white": S.LINE,
              "green": S.GREEN}
    parts = {p["id"]: p for p in spec.get("parts", []) if "id" in p}
    steps = sorted(spec.get("steps", []), key=lambda s: float(s.get("t", 0)))
    T = min(30.0, float(spec.get("duration") or 14))
    frames = mp4 + "_frames"
    os.makedirs(frames, exist_ok=True)

    def num(d, k, default=0.0):
        try:
            return float(d.get(k, default))
        except (TypeError, ValueError):
            return default

    def camera(t):
        cx, cy, z = S.W / 2, S.H / 2, 1.0
        for s in steps:
            if s.get("do") != "camera" or num(s, "t") > t:
                continue
            k = S.ease(S.prog(t, num(s, "t"), num(s, "t") + max(0.01, num(s, "dur", 1))))
            cx, cy, z = (S.lerp(cx, num(s, "x", cx), k), S.lerp(cy, num(s, "y", cy), k),
                         S.lerp(z, max(0.2, num(s, "zoom", z)), k))
        return cx, cy, z

    def state(pid, t):
        drawn, drop, red = 0.0, 0.0, 0.0
        listed = False
        for s in steps:
            if pid not in (s.get("ids") or []):
                continue
            a, d = num(s, "t"), max(0.01, num(s, "dur", 1))
            k = S.prog(t, a, a + d)
            if s.get("do") == "draw":
                listed = True
                drawn = max(drawn, k)
            elif s.get("do") == "stress":
                red = max(red, k)
            elif s.get("do") == "fail":
                drop += num(s, "dy", 200) * k * k
        return (drawn if listed else 1.0), drop, red

    def anchor(pid):
        p = parts.get(pid) or {}
        if p.get("type") in ("nut",):
            return num(p, "x"), num(p, "y")
        if p.get("type") == "people":
            return (num(p, "x0") + num(p, "x1")) / 2, num(p, "y") - 10
        return (num(p, "x0") + num(p, "x1")) / 2, (num(p, "y0") + num(p, "y1")) / 2

    n = int(T * S.FPS)
    for i in range(n):
        t = i / S.FPS
        f = S.Frame(*camera(t))
        f.grid(1)
        for pid, p in parts.items():
            drawn, drop, red = state(pid, t)
            if drawn <= 0:
                continue
            col = S.mix(S.LINE, S.RED, red)
            typ = p.get("type")
            if typ == "line":
                f.poly([(num(p, "x0"), num(p, "y0") + drop), (num(p, "x1"), num(p, "y1") + drop)],
                       col, max(1, min(6, num(p, "width", 2))), drawn)
            elif typ == "box":
                f.rect(num(p, "x0"), num(p, "y0") + drop, num(p, "x1"), num(p, "y1") + drop,
                       col, (18, 38, 66), 2, drawn)
            elif typ == "nut" and drawn >= 1:
                x, y = num(p, "x"), num(p, "y") + drop
                a, b = f.P(x - 5, y - 2), f.P(x + 5, y + 2)
                f.d.rectangle([a, b], fill=col)
            elif typ == "people":
                S.draw_people(f, num(p, "y") + drop, num(p, "x0"), num(p, "x1"), drawn,
                              n=int(num(p, "n", 12)))
        big_y = 120
        for s in steps:
            a, d = num(s, "t"), max(0.01, num(s, "dur", 2))
            if t < a:
                continue
            do = s.get("do")
            if do == "label" and t < a + d:
                al = S.prog(t, a, a + 0.4) * (1 - S.prog(t, a + d - 0.3, a + d))
                ax, ay = anchor(s.get("target"))
                ay += state(s.get("target"), t)[1]
                sx, sy = f.P(ax, ay)
                tx = sx / S.SS + (140 if sx / S.SS < S.W / 2 else -140)
                ty = max(60, min(S.H - 120, sy / S.SS - 70))
                f.label(str(s.get("text", ""))[:60], ax, ay, tx, ty, al,
                        colors.get(s.get("color"), S.CYAN))
            elif do == "force":
                k = S.prog(t, a, a + 0.8)
                f.arrow(num(s, "x0"), num(s, "y0"), num(s, "x1"), num(s, "y1"), S.AMBER, 5, 14,
                        k, world=False)
                sx, sy = f.P(num(s, "x0"), num(s, "y0"))
                f.text(str(s.get("text", ""))[:40], sx / S.SS + 12, sy / S.SS, 18, S.AMBER,
                       "Inter-Bold.otf", screen=True, alpha=k)
            elif do == "caption" and t < a + d:
                f.caption(str(s.get("text", ""))[:90],
                          S.prog(t, a, a + 0.4) * (1 - S.prog(t, a + d - 0.3, a + d)))
            elif do == "big" and t < a + d:
                f.text(str(s.get("text", ""))[:24], S.W - 60, big_y, 54,
                       colors.get(s.get("color"), S.RED), "InterDisplay-Black.otf",
                       screen=True, alpha=S.prog(t, a, a + 0.4), anchor="rs")
                big_y += 70
        f.done().save(os.path.join(frames, f"{i:05d}.png"))
    S._encode(frames, mp4)
    shutil.rmtree(frames)


# ---------------------------------------------------------------------------
# Option: AI video. A generated still of the atrium, animated by Wan 2.2 on
# the free ZeroGPU quota (the same Space the pipeline's hook shot uses).
# ---------------------------------------------------------------------------

def aivideo(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    still = os.path.join(out_dir, "aivideo_still.jpg")
    from visual_engine import cloudflare_generate
    img = cloudflare_generate(
        "wide shot of a 1980s hotel atrium lobby, two suspended steel and glass "
        "walkways stacked one above the other hanging from the glass roof on thin "
        "steel rods, crowd of people dancing on the lobby floor and standing on the "
        "walkways, photorealistic, 1981", 1280, 720)
    if img:
        open(still, "wb").write(img)
    else:
        # Workers AI out for the day: start from the Blender render of the atrium
        print("Workers AI unavailable: starting from the 3D render of the atrium")
        import shutil
        shutil.copy(os.path.join(HERE, "demo_assets", "atrium_3d.jpg"), still)
    print("still:", still)
    if not os.getenv("HF_TOKEN"):
        print("HF_TOKEN not set in this repository: the AI video step cannot run")
        return
    import animate_engine
    t = time.time()
    try:
        ok = animate_engine.animate(
            still,
            "The upper walkway suddenly breaks loose from its steel rods and falls onto "
            "the lower walkway, and both crash down to the lobby floor, dust rises, "
            "people run. Static camera.",
            os.path.join(out_dir, "aivideo_collapse.mp4"), 6.0)
        print("AI video:", "OK" if ok else "FAILED", f"in {time.time() - t:.0f}s")
    except Exception as e:
        print(f"AI video failed: {type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    {"scratch": scratch, "blocks": blocks, "aivideo": aivideo}[sys.argv[1]](sys.argv[2])
