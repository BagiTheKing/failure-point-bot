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
    "fuselage": {
        "what": ("A pressurised airliner fuselage: thin aluminium skin joined along its "
                 "length by overlapping lap joints, bonded and riveted; the bond lets go, "
                 "fatigue cracks grow at the rivets of one row and join, and a section "
                 "of the cabin tears away in flight."),
        "params": {"aircraft": "the aircraft type, e.g. Boeing 737-200",
                   "joint_label": "the failed joint's name in the report, e.g. S-10L",
                   "cycles": "how many flights (pressurisation cycles) the airframe had flown, a figure from the facts",
                   "section": "what tore away, short, e.g. 18 feet of cabin roof"},
        "labels": ["fuselage", "cabin", "skin", "joint", "rivets", "bond", "tear_strap"],
        "labels_3d": [("cabin", [2.0, 6.0], [140, 140], "cyan"),
                      ("wing", [2.6, 6.0], [760, 600], "cyan"),
                      ("skin", [9.0, 12.4], [820, 150], "amber"),
                      ("joint", [15.4, 19.4], [760, 150], "cyan")],
        "multiplier": "the flights the airframe had flown, e.g. 89,680 (multiplier_label: FLIGHTS ON ONE AIRFRAME)",
        "big_3d_anchor": "joint",
        "title_hint": "THE ... FLIGHT 243 or THE ... DISASTER",
        "model_3d": {"section_x": [-8.6, -3.1], "seam_x": -6.0},
    },
    "orbiter": {
        "what": ("A winged spacecraft returning from orbit: the leading edge of each wing is "
                 "a row of heat-shield panels (reinforced carbon-carbon); debris struck one "
                 "panel at launch and holed it; on re-entry superheated air got in through "
                 "the hole, melted the aluminium structure behind it, and the wing, then the "
                 "whole vehicle, broke apart."),
        "params": {"vehicle": "the vehicle's name, e.g. Space Shuttle Columbia",
                   "panel": "the number of the heat-shield panel that was breached, a figure from the facts",
                   "days": "how many days the mission flew with the damage, a figure from the facts",
                   "heat": "how hot the air entering the breach was, as the facts write it"},
        "labels": ["vehicle", "wing", "leading_edge", "panel", "shield", "spar", "foam", "hole",
                   "heat", "breach", "melt"],
        "labels_3d": [("wing", [2.0, 6.0], [140, 140], "cyan"),
                      ("nose", [2.6, 6.0], [760, 600], "cyan"),
                      ("edge", [9.0, 12.4], [820, 150], "amber"),
                      ("panel", [15.4, 19.4], [760, 150], "cyan")],
        "multiplier": ("the one figure behind the failure, e.g. the impact the panels were required "
                       "to withstand (multiplier_label: what it measures)"),
        "big_3d_anchor": "panel",
        "title_hint": "THE ... DISASTER",
        # what the other kits' habits would get wrong here (owner, 2026-10-23: no
        # over-dramatization, nothing the sources do not say)
        "rules": [
            "dramatization: nobody knows what the crew lived and the sources do not say; narrate "
            "only what Mission Control saw and heard, in order, from the facts (the failing sensors, "
            "the last call). Never describe the crew's thoughts, feelings or last moments.",
            "aftermath: there was no rescue; it is the search for the debris and what was recovered.",
            "hook: it was not a freak accident: foam had come off the tank on earlier flights and "
            "came to be treated as normal. Say that, not 'one piece of foam'.",
            "design_vs_built: nothing was built wrong; titles WHAT IT NEEDED / WHAT IT HAD (the "
            "requirement the panels were held to, against the strike they took).",
            "Blame no single person: the decisions (declining to image the wing, calling the strike "
            "a turnaround issue) are stated as dated facts, as the report states them.",
            "Keep the sources' qualifiers: 'about', 'approximately', 'probably exceeding'. The "
            "16-by-17-inch hole is from the later impact test, not a measurement of Columbia.",
            "The breakup was no explosion: aerodynamic forces overcame the damaged wing.",
        ],
        "model_3d": {},
    },
    "earth_dam": {
        "what": ("A zoned earthfill dam across a canyon of jointed rock: its core of fine soil "
                 "carried down into deep key trenches cut in the abutments, a grout curtain below. "
                 "Water under full head finds open rock joints at a trench, gets into the trench "
                 "fill and carries it away (internal erosion, piping); a leak appears on the "
                 "downstream face, grows into a hole, and the dam above it collapses."),
        "params": {"dam": "the dam's name, e.g. Teton Dam",
                   "height": "the dam's height as the facts give it, e.g. 305 ft"},
        "labels": ["dam", "rock", "reservoir", "trench", "node", "core", "curtain", "upstream", "downstream",
                   "seep", "crack", "pipe", "leak"],
        "labels_3d": [("dam", [2.0, 6.0], [140, 140], "cyan"),
                      ("reservoir", [2.6, 6.0], [760, 140], "cyan"),
                      ("abutment", [9.0, 12.4], [820, 150], "amber"),
                      ("hole", [15.4, 19.4], [760, 150], "cyan")],
        "multiplier": "the one figure behind the failure, e.g. the dam's height or the hours from first leak to breach",
        "big_3d_anchor": "hole",
        "title_hint": "THE ... DAM FAILURE",
        "model_3d": {},
        # what the other kits' habits would get wrong here
        "rules": [
            "The investigation names two possible ways the leak began (water through unsealed joints under "
            "the grout cap, or cracking of the trench fill); say both, and that the panel could not tell "
            "which, because the failed section was washed away.",
            "Count the dead as the sources do: say who counted what if they differ.",
            "The panel found construction followed the design; the design is what failed. Name the design "
            "decisions as the panel does; blame no single person.",
            "dramatization: what witnesses saw that morning, in the panel's words and times (leaks, the "
            "whirlpool, the bulldozers sent to fill the hole); nothing nobody recorded.",
            "Keep the sources' qualifiers: 'about', 'approximately'.",
        ],
    },
    "eyebar_chain": {
        "what": ("A suspension bridge hung from chains of steel eyebars, two bars to a link, pinned "
                 "together at the joints; hangers drop from the chain joints to a stiffening truss "
                 "and deck; the towers stand on rocker bearings. A crack grows unseen where one "
                 "eyebar's eye bears on its pin; the eye breaks, its sister bar slides off the pin, "
                 "the chain parts and the whole bridge collapses."),
        "params": {"bridge": "the bridge's name, e.g. the Silver Bridge"},
        "labels": ["west", "east", "chain", "tower", "truss", "node", "pin", "eyebar", "water", "crack",
                   "hidden", "break", "slip"],
        "labels_3d": [("bridge", [2.0, 6.0], [140, 140], "cyan"),
                      ("tower", [2.6, 6.0], [760, 140], "amber"),
                      ("chain", [9.0, 12.4], [820, 150], "cyan"),
                      ("joint", [15.4, 19.4], [760, 150], "red")],
        "multiplier": "the one figure behind the failure, e.g. the crack's size or the bars per link",
        "big_3d_anchor": "joint",
        "title_hint": "THE ... BRIDGE COLLAPSE",
        "model_3d": {},
        "rules": [
            "The NTSB found the flaw could not be seen or found by any inspection method then known "
            "without taking the joint apart: never say inspectors missed it or should have caught it.",
            "In 1927 stress corrosion and corrosion fatigue were not known to occur in this class of "
            "steel in rural exposure: say so; the design was normal practice for its time.",
            "The design weakness is the NTSB's own: only two eyebars per link, so one broken bar made "
            "the chain's failure inevitable; with three or more there was 'the possibility' one break "
            "would not have led to disaster. Keep 'possibility'; claim no certainty.",
            "Name no person as to blame. Keep the report's qualifiers: 'about', 'approximately'.",
            "dramatization: the collapse in the report's terms (about 1 minute, beginning in the Ohio "
            "side span and moving east); no invented last words or scenes in vehicles.",
        ],
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

LIMITS = {"label": 48, "caption": 90, "title": 28, "big_label": 34, "sub": 44, "today": 90,
          "thumb_top": 18, "thumb_sub": 22}


def _template(variant):
    k = KITS[variant]
    return {
        "kit": {"variant": variant, **{p: f"<{d}>" for p, d in k["params"].items()},
                "labels": {name: "<short label, under 48 characters>" for name in k["labels"]}},
        "labels_3d": {a: "<label for this part in the 3D view>" for a, *_ in k["labels_3d"]},
        "big_3d": {"text": "<the design_vs_built multiplier again, e.g. 2× or ½>",
                   "label": "<the multiplier label again>"},
        "hook": {"title": f"<{k.get('title_hint', 'THE ... COLLAPSE')}: the episode's title, capitals, "
                          "under 32 characters>",
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
        "clock": {"at": "<the moment of failure as H:MM, e.g. 7:05, or H:MM:SS when the facts give the second>",
                  "day": "<AM or PM · WEEKDAY DAY MONTH YEAR>",
                  "event": "<WHAT FAILS, in capitals>"},
        "timeline": [{"date": "", "title": "", "sub": "", "kind": "warning|event|failure"}],
        "today": {"title": "COULD IT HAPPEN TODAY?", "lines": ["", "", "<could it happen again now>"]},
        "thumbnail": {"top": "<2 to 3 words, capitals: the failure as one image, e.g. ROOF TORN OFF>",
                      "sub": "<2 to 4 words, capitals, with the key figure, e.g. AT 24,000 FEET>"},
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
        "- The narration is read aloud by a synthetic voice: write clock times as a "
        "narrator says them (\"just after seven in the evening\", never \"7:05 p.m.\").\n"
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
        "same words (the picture shows each event as its date is spoken), and "
        "carries its year (\"MAY 1978\", \"1979\"): a warning nobody dated belongs "
        "in the narration, not on the timeline.\n"
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
        "- thumbnail.top under 18 characters and thumbnail.sub under 22: the words "
        "on the episode's picture, true to the facts.\n"
        "- The archive shots (photo, photos_disaster, aftermath, investigation, "
        "today_photos) are narrated over real photographs: say what they show.\n"
        + "".join(f"- {r}\n" for r in k.get("rules", [])) + "\n"
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


def _shots(v):
    """The writer's shots as {clip: {"caption", "narration"}}, whatever shape
    it gave them in: a list of shots with their clip names, a shot as a list
    of sentences or a bare string."""
    if isinstance(v, list):
        v = {x.get("clip"): x for x in v if isinstance(x, dict) and x.get("clip")}
    out = {}
    for clip, sh in (v or {}).items() if isinstance(v, dict) else []:
        if isinstance(sh, list):
            dicts = [x for x in sh if isinstance(x, dict)]
            sh = dicts[0] if dicts else {"narration": " ".join(str(x) for x in sh)}
        elif isinstance(sh, str):
            sh = {"narration": sh}
        elif not isinstance(sh, dict):
            sh = {}
        out[clip] = {**sh, "caption": str(sh.get("caption", "") or ""),
                     "narration": str(sh.get("narration", "") or "")}
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
    if variant == "fuselage":
        if not re.search(r"\d", str(k.get("cycles", ""))):
            problems.append("kit.cycles needs the number of flights the airframe had flown")
    if variant == "orbiter":
        if not re.fullmatch(r"\d{1,2}", str(k.get("panel", "")).strip()):
            problems.append("kit.panel needs the breached panel's number")
        if not re.search(r"\d", str(k.get("days", ""))):
            problems.append("kit.days needs how many days the mission flew")
    if variant == "hanging_walkways":
        try:
            n, i = int(k.get("rod_lines", 0)), int(k.get("failed_line", -1))
            if not 2 <= n <= 6 or not 0 <= i < n:
                problems.append("kit.rod_lines / kit.failed_line out of range")
        except (TypeError, ValueError):
            problems.append("kit.rod_lines / kit.failed_line are not numbers")
        if len(k.get("levels") or []) != 2:
            problems.append("kit.levels needs exactly two names")
    reply["shots"] = shots = _shots(reply.get("shots"))
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
    th = reply.get("thumbnail") or {}
    shorts += [("thumbnail.top", th.get("top", ""), "thumb_top"), ("thumbnail.sub", th.get("sub", ""), "thumb_sub")]
    shorts += [(f"today.lines[{i}]", line, "today")
               for i, line in enumerate((reply.get("today") or {}).get("lines") or [])]
    for where, text, limit in shorts:
        if len(text or "") > LIMITS[limit]:
            problems.append(f"{where} is over {LIMITS[limit]} characters "
                            f"({len(text)}: {text!r}; write it shorter)")
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
    if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", at.strip()):
        problems.append("clock.at must be the moment as H:MM, e.g. 7:05 (or H:MM:SS)")
    missing = sorted({f for t in _strings(claims)
                      for f in _figures(t) if f.rstrip(".,").replace(",", "") not in src
                      and len(f.rstrip(".,")) > 1})
    if missing:
        problems.append("figures not in the fact sheet: " + ", ".join(missing[:8]))
    problems += hook_problems(reply.get("hook") or {}, source_text)
    tl_text = ((reply.get("shots") or {}).get("timeline") or {}).get("narration", "")
    undated = [e.get("date", "") for e in reply.get("timeline") or []
               if not re.search(r"\b(?:1[89]|20)\d\d\b", str(e.get("date", "")))]
    if undated:
        problems.append("timeline dates without a year (give the year, or move the event "
                        "into the narration): " + ", ".join(undated))
    unsaid = [e.get("date", "") for e in reply.get("timeline") or []
              if e.get("date", "") not in undated and not any(y in tl_text for y in re.findall(r"\b(?:1[89]|20)\d\d\b", str(e.get("date", ""))))]
    if unsaid:
        problems.append("timeline dates never said in the timeline narration: " + ", ".join(unsaid))
    if not (reply.get("timeline") and 3 <= len(reply["timeline"]) <= 6):
        problems.append("timeline needs 3 to 6 entries")
    return problems


def clock_of(c):
    """The kit's clock from the writer's moment: counts the last 10 seconds
    (to the second when the moment has one: 9:00:18 counts from 9:00:08)."""
    parts = [int(x) for x in (c.get("at") or "0:00").strip().split(":")[:3]]
    h, m, sec = (parts + [0])[:3]
    t = (h * 60 + m) * 60 + sec - 10
    bh, bm, bs = t // 3600, t // 60 % 60, t % 60
    return {"from_seconds": bs, "label_before": f"{(bh % 12) or 12}:{bm:02d}" + ":{s:02d}",
            "label_next": f"{h}:{m:02d}" + ":{s:02d}",       # once the count crosses into the moment's minute
            "label_at": f"{h}:{m:02d}:{sec:02d}", "day": c.get("day", ""), "event": c.get("event", "")}


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
    elif variant == "hanging_walkways":
        kit["rod_lines"], kit["failed_line"] = int(kit["rod_lines"]), int(kit["failed_line"])
    elif variant == "earth_dam":
        kit["family"] = "water"
    elif variant == "eyebar_chain":
        pass
    elif variant == "orbiter":
        kit["family"] = "spaceflight"
        kit["panel"] = int(str(kit["panel"]).strip())
    else:
        kit["family"] = "aircraft"
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
        "thumbnail": {k_: str(v).upper() for k_, v in (r.get("thumbnail") or {}).items() if v},
        "shots": shots,
    }


ROLES = {"photo": "the structure (or aircraft) before the disaster, over a photograph of it",
         "photos_disaster": "the disaster as it happened, over photographs",
         "establish": "the structure as a whole, over the 3D model",
         "build": "how it was designed and built, step by step",
         "load_path": "how the load travels through it",
         "connection": "the one part that failed, close up",
         "physics": "the forces on that part, and why it gave way",
         "clock": "the moment of failure, in one sentence",
         "fall": "the failure itself, physically",
         "dramatization": "what the people there lived, in plain words",
         "aftermath": "the rescue and the toll",
         "timeline": "the warnings people missed, each with its date",
         "investigation": "what the investigation found",
         "compare": "what should have been done, against what was done",
         "today_photos": "the place or the fleet afterwards, over photographs",
         "today": "what changed since, and whether it could happen again"}


def expand_short(pool, call, data, facts_text, topic, rules=()):
    """Writes again, one by one, the shots whose narration came back short
    (the free writers often cut a long sheet short); a small reply per shot
    fits where the whole sheet did not. Returns how many grew."""
    shots = _shots(data.get("shots"))
    grown = 0
    for _, _, clip, words in SHOTS:
        sh = shots.get(clip) or {"caption": "", "narration": ""}
        have = sh["narration"]
        if len(have.split()) >= words * 0.6:
            continue
        reply = call(pool, "You write documentary narration from a verified fact sheet. Never add a fact. "
                     "Output only JSON.",
                     f"Story: {topic}\n\nVERIFIED FACT SHEET (the only facts you may use):\n{facts_text}\n\n"
                     f"Shot \"{clip}\": {ROLES.get(clip, '')}.\n"
                     + "".join(f"Rule: {r}\n" for r in rules) + f"Its narration now ({len(have.split())} words): "
                     f"{have or '(none)'}\n\nWrite this shot's narration at about {words} words: plain, short "
                     "sentences, every figure exactly as the fact sheet writes it, clock times as a narrator says "
                     "them. Output {\"narration\": \"...\"}", max_tokens=1500, expect={"narration": str})
        new = str((reply or {}).get("narration", "")) if isinstance(reply, dict) else ""
        if len(new.split()) > len(have.split()):
            shots[clip] = {**sh, "narration": new}
            grown += 1
    data["shots"] = shots
    return grown


def write_sheet(pool, topic, article, facts, variant, call, attempts=4):
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
        if isinstance(data, dict) and any("is too short" in p for p in problems):
            grown = expand_short(pool, call, data, facts_text, topic, KITS[variant].get("rules", ()))
            if grown:
                print(f"   ✍️  {grown} short shot(s) written again at length")
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
