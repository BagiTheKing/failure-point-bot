"""
Failure Point's five recurring episode types.

Every episode is the same promise: a real machine, structure or plant failed,
here is the exact thing that broke, and here is what it cost. The formats split
that promise by WHAT failed, because the viewer recognises the object before
they read a word, and three COLLAPSE episodes in a row should read as a set.

    THE COLLAPSE   a building, bridge, roof or walkway came down
    THE BREACH     a dam, reservoir, tank or levee let go
    THE BLAST      a plant, mine, refinery or reactor exploded or burned
    THE SINKING    a ship, submarine or offshore rig was lost
    THE MACHINE    an aircraft, rocket, train or piece of software failed

WHY THESE (October 2026)
------------------------
The small channels breaking out in this niche (vidIQ outliers, last six months,
under 20k subscribers) all lead with the object and a hard number: "26 Tons of
Concrete With Glue", "A 920-Ton Rotor Tore Free", "A $275 Million Hotel
Implodes". The object is the antagonist; the people are engineers who were
overruled or who did not have the one measurement that mattered.

A format is worth having only if a viewer can see it, so each one carries an
accent colour and a name on the thumbnail. The accent must stay legible on a
dark, desaturated frame.

Adding one: add an entry here, point topics at it in src/topics.py, and nothing
else needs to change.
"""

# The part of every brief that is the same for all five: the mechanism is the
# product. A viewer who cannot repeat what failed has watched nothing.
_MECHANISM = (
    "The viewer must finish able to say, in their own words, exactly WHAT "
    "failed and WHY: name the component, the load, the material, the unit, the "
    "number. Explain every technical term in plain words the first time it "
    "appears. Name the warning signs that were there before the failure and "
    "who saw them. The people are rarely villains; be fair to the decision at "
    "the moment it was made, with what was known then. Never invent a quote, "
    "a figure or a motive. Never dwell on gore; the number of dead is stated "
    "plainly, once, with respect. Never end on a moral.")

# Accent colours are RGB, and each is the one word the eye lands on in the
# thumbnail plus the rule above the headline.
FORMATS = {
    "collapse": {
        "name": "THE COLLAPSE",
        "accent": (255, 92, 60),        # signal red: failure, alarm
        "promise": "it was built to stand, and it came down",
        "brief": (
            "This is a COLLAPSE story: a building, bridge, roof, walkway or "
            "crane that was supposed to carry its load and did not. Follow "
            "the load path: where the weight went, the one connection or "
            "member that could not take it, and the change or shortcut that "
            "put it there. " + _MECHANISM),
        "tags": ["structural failure", "building collapse", "bridge collapse",
                 "engineering disasters", "structural engineering"],
        "hashtags": ["#engineering", "#collapse", "#disaster"],
    },
    "breach": {
        "name": "THE BREACH",
        "accent": (56, 152, 255),       # water blue
        "promise": "it was built to hold, and it let go",
        "brief": (
            "This is a BREACH story: a dam, reservoir, storage tank, levee or "
            "tailings pile that was holding something back. Show what it was "
            "holding, how much, how fast it came out once it failed, and how "
            "far it travelled. The mechanism is usually water or pressure "
            "finding the one weakness: seepage, overtopping, a cracked seam, "
            "the ground beneath it. " + _MECHANISM),
        "tags": ["dam failure", "dam collapse", "flood disaster",
                 "engineering disasters", "civil engineering"],
        "hashtags": ["#engineering", "#dam", "#disaster"],
    },
    "blast": {
        "name": "THE BLAST",
        "accent": (255, 150, 0),        # fire orange
        "promise": "it was built to contain, and it went up",
        "brief": (
            "This is a BLAST story: a plant, refinery, mine, warehouse, "
            "pipeline or reactor that exploded or burned. Name the substance, "
            "the quantity, and the chain of small failures (a valve, a "
            "procedure, an alarm switched off, a shift handover) that let it "
            "reach an ignition source. Explain the chemistry or physics in "
            "one or two plain sentences. " + _MECHANISM),
        "tags": ["industrial disaster", "industrial accident", "explosion",
                 "engineering disasters", "chemical plant explosion"],
        "hashtags": ["#engineering", "#industrial", "#disaster"],
    },
    "sinking": {
        "name": "THE SINKING",
        "accent": (0, 200, 170),        # deep-sea teal
        "promise": "it was built to float, and it went down",
        "brief": (
            "This is a SINKING story: a ship, ferry, submarine or offshore "
            "platform lost to its own design, loading or maintenance. Explain "
            "stability, watertightness or structural fatigue in plain words, "
            "name the one opening, weld, weight or door that mattered, and "
            "how long the people on board had once it started. " + _MECHANISM),
        "tags": ["shipwreck", "maritime disaster", "ship sinking",
                 "engineering disasters", "naval engineering"],
        "hashtags": ["#engineering", "#shipwreck", "#disaster"],
    },
    "machine": {
        "name": "THE MACHINE",
        "accent": (255, 216, 0),        # amber
        "promise": "it was built to work, and one part did not",
        "brief": (
            "This is a MACHINE story: an aircraft, rocket, spacecraft, train, "
            "medical device or piece of software that failed in operation. "
            "Trace the failure to the single part, line of code, unit "
            "conversion or maintenance step, and show the seconds or minutes "
            "between the first sign and the end. " + _MECHANISM),
        "tags": ["engineering failure", "air crash investigation",
                 "how it failed", "engineering disasters", "aviation disaster"],
        "hashtags": ["#engineering", "#disaster", "#howitfailed"],
    },
}

DEFAULT_FORMAT = "collapse"


def get(key: str) -> dict:
    """The format's config, falling back to COLLAPSE rather than raising. A topic
    that slipped through untagged must still produce a video."""
    return FORMATS.get(key or "", FORMATS[DEFAULT_FORMAT])


def name_of(key: str) -> str:
    return get(key)["name"]


def accent_of(key: str) -> tuple:
    return get(key)["accent"]


def brief_of(key: str) -> str:
    return get(key)["brief"]


def tags_of(key: str) -> list:
    return list(get(key)["tags"])


def hashtags_of(key: str) -> list:
    """The three that render above the title. YouTube counts the first three
    hashtags found anywhere in the description, so they are worth choosing
    rather than letting the writer scatter its own through the text."""
    return list(get(key)["hashtags"])


# A live run reached the very last step of the pipeline — script, narration,
# images, video, thumbnail, description all already built — and had YouTube's
# upload API reject the whole thing with "invalidTags" and no indication of
# which tag was the problem. The list-wide 500-character budget below already
# existed; what was missing is YouTube's OTHER two tag rules: no single tag
# over 100 characters, and neither '<' nor '>' anywhere in one. Both are easy
# for a free-form LLM tag (script.get("tags")) to violate by accident — the
# channel's own fixed tags above are hand-written and already clean.
_TAG_MAX_LEN = 100
_TAG_LIST_BUDGET = 500


def sanitize_tags(tags: list) -> list:
    """The final YouTube-safe tag list: stripped, deduped in order, and
    validated against YouTube's actual tag rules before anything is spent
    building a video around them."""
    seen, cleaned = set(), []
    for t in tags:
        if not isinstance(t, str):
            continue
        t = t.strip()
        if not t or t in seen or len(t) > _TAG_MAX_LEN or "<" in t or ">" in t:
            continue
        seen.add(t)
        cleaned.append(t)

    trimmed, budget = [], _TAG_LIST_BUDGET
    for t in cleaned:
        cost = len(t) + 1
        if cost > budget:
            break
        trimmed.append(t)
        budget -= cost
    return trimmed
