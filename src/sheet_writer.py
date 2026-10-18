"""
Step 5a: the writer fills the animation sheet (src/kits/sheets/*.json) for a
story, from its verified fact sheet (story_mode.gather + fact_sheet).

The kit owns the drawing, the timing and where things go on screen; the
writer supplies only words and numbers: the kit's parameters, the labels,
the design-vs-built contrast, the timeline, the "could it happen today"
lines, the AI clip's description, and the NARRATION of every shot. Every
figure anywhere in the sheet must appear in the source text, or the sheet
is sent back once with the problems, then refused.

    sheet = write_sheet(pool, topic, article, facts, "truss_bridge", call)
"""

import copy
import json
import re

# --------------------------------------------------------------------------
# What each kit needs from the writer. "params" are the kit block's own
# fields; "labels" are the 2D label slots; "labels_3d" are the 3D label slots
# (anchor, when, where are fixed by the kit; the writer writes the text).
# --------------------------------------------------------------------------

KITS = {
    "hanging_walkways": {
        "what": ("Decks or walkways hung from a roof on steel rods; one connection "
                 "carries more than it was designed to and lets go."),
        "params": {"levels": ["upper deck name", "lower deck name"],
                   "rod_lines": "number of rod lines along the deck (2-5)",
                   "failed_line": "index of the rod line that failed (0-based)"},
        "labels": ["roof", "rods", "beam", "nut", "upper_rod", "lower_rod"],
        "labels_3d": [("upper_deck", [2.0, 6.0], [140, 150], "cyan"),
                      ("lower_deck", [2.0, 6.0], [140, 420], "cyan"),
                      ("lower_rods_mid", [9.2, 12.4], [820, 300], "amber"),
                      ("upper_rod", [15.4, 19.4], [760, 150], "cyan"),
                      ("lower_rod", [15.4, 19.4], [760, 520], "cyan")],
        "multiplier": "how many times its design load the failed connection carried, ending in ×, e.g. 2×",
        "big_3d_anchor": "nut",
        "model_3d": {"walk_length": 36.0, "walk_width": 2.6, "level_z": [12.0, 5.0],
                     "roof_z": 19.5},
    },
    "truss_bridge": {
        "what": ("A steel truss bridge over one or more spans; one joint (a gusset "
                 "plate where beams meet) is weaker than the forces through it and "
                 "tears; the main span falls."),
        "params": {"deck": "top (deck truss) or bottom (through truss)",
                   "spans": "relative span lengths, e.g. [266, 456, 266]",
                   "panels": "number of truss panels end to end (16-32, even)",
                   "failed_node": "index of the failed top joint from the left end",
                   "failed_node_label": "the joint's name in the report, e.g. U10",
                   "load_near_node": "true if extra load sat over the joint that day"},
        "labels": ["deck", "truss", "piers", "river", "node", "plate", "load"],
        "labels_3d": [("deck", [2.0, 6.0], [140, 130], "cyan"),
                      ("truss", [2.6, 6.0], [700, 560], "cyan"),
                      ("load", [9.0, 12.4], [640, 120], "amber"),
                      ("diag", [10.0, 12.4], [760, 560], "amber"),
                      ("node", [15.4, 19.4], [780, 180], "cyan")],
        "multiplier": "the one ratio behind the tear: plate thickness (½) or added load (20%)",
        "big_3d_anchor": "node",
        "model_3d": {"span_m": [81, 139, 81], "deck_width_m": 34, "truss_depth_m": [9, 18],
                     "water_level_m": -32},
    },
}

# The shot list every mixed video follows (the 7 parts). Words: the narration
# budget for each shot, so the pacing holds (step 5b stretches the pictures
# to the voice).
SHOTS = [
    (1, "archive", "photo", 70), (1, "archive", "photos_disaster", 110),
    (2, "3d", "establish", 70), (2, "2d", "build", 130),
    (3, "3d", "load_path", 70), (3, "3d", "connection", 60), (3, "2d", "physics", 205),
    (4, "2d", "clock", 25), (4, "3d", "fall", 30), (4, "ai_video", "dramatization", 35),
    (4, "archive", "aftermath", 115),
    (5, "2d", "timeline", 145), (5, "archive", "investigation", 110),
    (6, "2d", "compare", 145),
    (7, "archive", "today_photos", 85), (7, "2d", "today", 95),
]
# ~1,260 words: 8-10 minutes in the am_echo voice with the pauses (owner, 2026-10-18)

LIMITS = {"label": 48, "caption": 90, "title": 28, "big_label": 34, "sub": 44, "today": 90}


def _template(variant):
    k = KITS[variant]
    return {
        "kit": {"variant": variant, **{p: f"<{d}>" for p, d in k["params"].items()},
                "labels": {name: "<short label, under 48 characters>" for name in k["labels"]}},
        "labels_3d": {a: "<label for this part in the 3D view>" for a, *_ in k["labels_3d"]},
        "big_3d": {"text": "<the design_vs_built multiplier again, e.g. 2× or ½>",
                   "label": "<the multiplier label again>"},
        "hook": {"title": "<THE ... COLLAPSE: the episode's title, capitals, under 32 characters>",
                 "lines": ["<cold open: 3 to 5 lines, each under 90 characters, 60 words in all>"]},
        "disaster": {"place_date": "<CITY · DAY MONTH YEAR · TIME>", "place": "<where, one line>",
                     "caption": "<one line: what happened>"},
        "design_vs_built": {
            "designed": {"title": "<AS DESIGNED or WHAT IT NEEDED>", "detail": "", "load": ""},
            "built": {"title": "<AS BUILT>", "detail": "", "load": ""},
            "multiplier": "", "multiplier_label": "",
            "plate_built": "<only for gusset failures: thickness as built>",
            "plate_needed": "<only for gusset failures: thickness it needed>"},
        "numbers": [{"value": "<deaths>", "label": "PEOPLE KILLED"},
                    {"value": "", "label": "INJURED"}, {"value": "", "label": ""}],
        "clock": {"at": "<the moment of failure as H:MM, e.g. 7:05>",
                  "day": "<AM or PM · WEEKDAY DAY MONTH YEAR>",
                  "event": "<WHAT FAILS, in capitals>"},
        "timeline": [{"date": "", "title": "", "sub": "", "kind": "warning|event|failure"}],
        "today": {"title": "COULD IT HAPPEN TODAY?", "lines": ["", "", "<could it happen again now>"]},
        "ai_prompt": "<how the collapse looks, physically accurate, plain words, "
                     "ending with 'Static camera.'>",
        "photo_article": "<the Wikipedia article title of the event>",
        "shots": {clip: {"caption": "<on-screen line, under 90 characters>",
                         "narration": f"<about {words} words>"}
                  for _, _, clip, words in SHOTS},
    }


def prompt(topic, facts_text, variant):
    k = KITS[variant]
    return (
        f"Story: {topic}\n\nVERIFIED FACT SHEET (the only facts you may use):\n{facts_text}\n\n"
        f"This episode is animated with the kit \"{variant}\": {k['what']}\n"
        "The kit draws the structure and the failure; you write the WORDS: its "
        "parameters, labels, the contrast between what was designed and what was "
        "built, the warnings, today's lesson, and the narration of every shot.\n\n"
        "Rules:\n"
        "- Every figure (number, date, time, quantity) must come from the fact "
        "sheet, written the same way. No figure you cannot point to.\n"
        "- The narration explains HOW and WHY it failed, plainly, one step at a "
        "time, in the order of the shots. Short sentences. No hype words.\n"
        "- physics: the forces, the weak point, why it gave way. timeline: the "
        "warnings people missed. compare: what should have been done. today: "
        "could it happen again, and what changed.\n"
        "- The dramatization shot's narration is what the people there lived, in "
        "plain words; its ai_prompt describes the collapse as it physically "
        "happened.\n"
        "- Labels under 48 characters, captions under 90.\n"
        "- hook is the cold open, the first 30 seconds over fast footage and tense "
        "music, there to make the viewer stay: open on the moment (date, time, "
        "place), one hard image of what happened, the toll, and close on the "
        "hidden cause stated as a fact. Present tense, plain words, no questions "
        "to the viewer, no hype.\n"
        "- design_vs_built.multiplier is THE one figure that explains the failure "
        f"(for this kit: {k['multiplier']}), short enough to fill the screen; "
        "multiplier_label under 34 characters.\n"
        "- design_vs_built contrasts what sound engineering called for with what "
        "stood there. If the mistake was in the design itself, say so: titles "
        "WHAT IT NEEDED / WHAT IT HAD, and never call the faulty design adequate. "
        "plate_needed is a figure from the fact sheet, or empty if it gives none.\n"
        "- Every timeline date is said in the timeline shot's narration, in the "
        "same words (the picture shows each event as its date is spoken).\n"
        "- timeline: 3 to 6 moments in THIS structure's own story (design "
        "changes, earlier damage, inspections, warnings, decisions), not other "
        "disasters; titles under 28 characters, subs under 44.\n"
        "- design_vs_built.designed states what sound engineering required (the "
        "code load, the right thickness, the original detail), never the flawed "
        "figure; built states what was actually there.\n"
        "- Write every shot's narration to its full length: the episode runs 8 "
        "to 10 minutes and each picture holds for as long as its words.\n"
        "- today.lines (each under 90 characters) say what changed since and "
        "whether it could happen again. Do not repeat the cause there.\n"
        "- Kit parameters the facts do not give: use the kit's usual values "
        "(hanging walkways: 3 rod lines, the middle one failed; truss bridge: "
        "28 panels).\n"
        "- The archive shots (photo, photos_disaster, aftermath, investigation, "
        "today_photos) are narrated over real photographs: say what they show.\n\n"
        "Output ONLY JSON in exactly this shape (replace every <...>):\n"
        + json.dumps(_template(variant), ensure_ascii=False, indent=1))


def _figures(text):
    return re.findall(r"\d[\d,.]*", text or "")


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _spans(v):
    """Span lengths as numbers, whether the writer gave [266, 456] or
    ["266 ft", "456"] or "266, 456, 266"; [] when there are none."""
    items = v if isinstance(v, list) else re.findall(r"\d+(?:\.\d+)?", str(v or ""))
    out = []
    for x in items:
        m = re.search(r"\d+(?:\.\d+)?", str(x))
        if m:
            out.append(float(m.group()) if "." in m.group() else int(m.group()))
    return out


def hook_problems(hook, source_text):
    """Problems with a cold open {"title", "lines"}, [] when usable."""
    problems = []
    lines = hook.get("lines") if isinstance(hook, dict) else None
    if not isinstance(lines, list) or not 3 <= len(lines) <= 5:
        return ["hook.lines needs 3 to 5 lines"]
    if sum(len(str(x).split()) for x in lines) > 70:
        problems.append("hook.lines run over 70 words")
    if any(len(str(x)) > 90 for x in lines):
        problems.append("a hook line is over 90 characters")
    if not hook.get("title") or len(hook["title"]) > 32:
        problems.append("hook.title must be under 32 characters")
    src = re.sub(r"[\s,]", "", source_text or "")
    missing = sorted({f for t in lines for f in _figures(str(t))
                      if f.rstrip(".,").replace(",", "") not in src and len(f.rstrip(".,")) > 1})
    if missing:
        problems.append("hook figures not in the facts: " + ", ".join(missing))
    return problems


def check(reply, variant, source_text):
    """Problems with the writer's reply, [] when it can be used."""
    problems = []
    if not isinstance(reply, dict):
        return ["the reply is not a JSON object"]
    src = re.sub(r"[\s,]", "", source_text or "")
    k = reply.get("kit") or {}
    for p in KITS[variant]["params"]:
        if p not in k or (isinstance(k[p], str) and k[p].startswith("<")):
            problems.append(f"kit.{p} is missing")
    if variant == "truss_bridge":
        try:
            n, i = int(k.get("panels", 0)), int(k.get("failed_node", -1))
            if not 8 <= n <= 40 or not 0 < i < n:
                problems.append("kit.panels / kit.failed_node out of range")
            if not _spans(k.get("spans")):
                problems.append("kit.spans needs the span lengths as numbers")
        except (TypeError, ValueError):
            problems.append("kit.panels / kit.failed_node are not numbers")
    if variant == "hanging_walkways":
        try:
            n, i = int(k.get("rod_lines", 0)), int(k.get("failed_line", -1))
            if not 2 <= n <= 6 or not 0 <= i < n:
                problems.append("kit.rod_lines / kit.failed_line out of range")
        except (TypeError, ValueError):
            problems.append("kit.rod_lines / kit.failed_line are not numbers")
        if len(k.get("levels") or []) != 2:
            problems.append("kit.levels needs exactly two names")
    shots = reply.get("shots") or {}
    for _, _, clip, words in SHOTS:
        sh = shots.get(clip) or {}
        nar = sh.get("narration", "")
        if len(nar.split()) < words * 0.6:
            problems.append(f"shots.{clip}.narration is too short ({len(nar.split())} words, about {words} wanted)")
        if len(sh.get("caption", "")) > LIMITS["caption"]:
            problems.append(f"shots.{clip}.caption is over {LIMITS['caption']} characters")
    dvb = reply.get("design_vs_built") or {}
    if variant == "hanging_walkways" and not str(dvb.get("multiplier", "")).strip().endswith("×"):
        problems.append("design_vs_built.multiplier must be a load factor like 2× for this kit")
    shorts = [("design_vs_built.multiplier_label", dvb.get("multiplier_label", ""), "big_label"),
              ("big_3d.label", (reply.get("big_3d") or {}).get("label", ""), "big_label")]
    for i, e in enumerate(reply.get("timeline") or []):
        shorts += [(f"timeline[{i}].title", e.get("title", ""), "title"),
                   (f"timeline[{i}].sub", e.get("sub", ""), "sub")]
    shorts += [(f"today.lines[{i}]", line, "today")
               for i, line in enumerate((reply.get("today") or {}).get("lines") or [])]
    for where, text, limit in shorts:
        if len(text or "") > LIMITS[limit]:
            problems.append(f"{where} is over {LIMITS[limit]} characters")
    for name, text in (k.get("labels") or {}).items():
        if len(text) > LIMITS["label"]:
            problems.append(f"kit.labels.{name} is over {LIMITS['label']} characters")
    for text in _strings(reply):
        if text.startswith("<") and text.endswith(">"):
            problems.append(f"a placeholder was left: {text[:50]!r}")
            break
    # span lengths are drawing proportions, not claims: not checked against the source
    claims = {**reply, "kit": {**k, "spans": []}}
    at = (reply.get("clock") or {}).get("at", "")
    if not re.fullmatch(r"\d{1,2}:\d{2}", at.strip()):
        problems.append("clock.at must be the moment as H:MM, e.g. 7:05")
    missing = sorted({f for t in _strings(claims)
                      for f in _figures(t) if f.rstrip(".,").replace(",", "") not in src
                      and len(f.rstrip(".,")) > 1})
    if missing:
        problems.append("figures not in the fact sheet: " + ", ".join(missing[:8]))
    problems += hook_problems(reply.get("hook") or {}, source_text)
    tl_text = ((reply.get("shots") or {}).get("timeline") or {}).get("narration", "")
    unsaid = [e.get("date", "") for e in reply.get("timeline") or []
              if not any(y in tl_text for y in re.findall(r"\b(?:1[89]|20)\d\d\b", str(e.get("date", ""))))]
    if unsaid:
        problems.append("timeline dates never said in the timeline narration: " + ", ".join(unsaid))
    if not (reply.get("timeline") and 3 <= len(reply["timeline"]) <= 6):
        problems.append("timeline needs 3 to 6 entries")
    return problems


def clock_of(c):
    """The kit's clock from the writer's moment: counts the last 10 seconds."""
    h, m = (c.get("at") or "0:00").strip().split(":")[:2]
    h, m = int(h), int(m)
    before = f"{h}:{m - 1:02d}" if m else f"{(h - 1) or 12}:59"
    return {"from_seconds": 50, "label_before": before + ":{s:02d}",
            "label_at": f"{h}:{m:02d}:00", "day": c.get("day", ""), "event": c.get("event", "")}


def assemble(reply, variant, facts_source="", source_name="source"):
    """The writer's reply, laid out as a kit sheet (kits/sheets/*.json)."""
    k = KITS[variant]
    r = copy.deepcopy(reply)
    kit = {"family": "structure", **r["kit"], "variant": variant}
    if variant == "truss_bridge":
        kit["spans"] = _spans(kit.get("spans"))
        kit["panels"] = int(kit["panels"]) // 2 * 2
        kit["failed_node"] = int(kit["failed_node"])
        kit["load_near_node"] = str(kit.get("load_near_node")).lower() in ("true", "1", "yes")
        kit["river"] = True
    else:
        kit["rod_lines"], kit["failed_line"] = int(kit["rod_lines"]), int(kit["failed_line"])
    m3 = dict(k["model_3d"])
    texts = r.get("labels_3d") or {}
    m3["labels_3d"] = [{"anchor": a, "text": texts.get(a, ""), "color": c, "t": t, "at": at}
                       for a, t, at, c in k["labels_3d"] if texts.get(a)]
    big = r.get("big_3d") or {}
    m3["big_3d"] = {"anchor": k["big_3d_anchor"], "text": big.get("text", ""),
                    "label": big.get("label", ""), "t": [16.8, 19.4]}
    m3["ai_prompt"] = r.get("ai_prompt", "")
    shots = []
    for part, tool, clip, _ in SHOTS:
        sh = (r.get("shots") or {}).get(clip, {})
        shots.append({"part": part, "tool": tool, "clip": clip,
                      "caption": sh.get("caption", ""), "narration": sh.get("narration", "")})
    tag = source_name
    for t in r.get("timeline", []):
        t["source"] = tag
    return {
        "story": r.get("story", ""),
        "sources": {tag: facts_source},
        "kit": kit,
        "model_3d": m3,
        "disaster": {**r.get("disaster", {}), "photo_article": r.get("photo_article", "")},
        "hook": {"title": str((r.get("hook") or {}).get("title", "")).upper(),
                 "lines": list((r.get("hook") or {}).get("lines") or []),
                 "sub": str(r.get("disaster", {}).get("place_date", "")).split("·")[0].strip()
                 + (" · " + str(r.get("disaster", {}).get("place_date", "")).split("·")[1].strip()
                    if "·" in str(r.get("disaster", {}).get("place_date", "")) else "")},
        "design_vs_built": {**r.get("design_vs_built", {}), "source": tag},
        "numbers": [{**n, "source": tag} for n in r.get("numbers", []) if n.get("value")],
        "clock": clock_of(r.get("clock", {})),
        "timeline": r.get("timeline", []),
        "today": {**r.get("today", {}), "source": tag},
        "shots": shots,
    }


def write_sheet(pool, topic, article, facts, variant, call, attempts=2):
    """The animation sheet for this story and kit, or None."""
    from story_mode import sheet_text
    facts_text = sheet_text(facts)
    source = article.get("text", "") + "\n" + facts_text
    feedback = ""
    for attempt in range(attempts):
        data = call(pool, "You write documentary narration and on-screen text from a "
                    "verified fact sheet. Never add a fact. Output only JSON.",
                    prompt(topic, facts_text, variant) + feedback, max_tokens=8000,
                    expect={"shots": dict, "kit": dict})
        problems = check(data, variant, source)
        if not problems:
            sheet = assemble(data, variant, facts.get("source", article.get("url", "")))
            sheet["story"] = topic
            print(f"🧾 Animation sheet written ({variant}), attempt {attempt + 1}.")
            return sheet
        print(f"   ↩️  Sheet attempt {attempt + 1}: " + "; ".join(problems[:6]))
        feedback = ("\n\nYOUR LAST REPLY HAD THESE PROBLEMS, fix every one:\n- "
                    + "\n- ".join(problems))
    print("⚠️ No usable animation sheet: the episode cannot be animated.")
    return None
