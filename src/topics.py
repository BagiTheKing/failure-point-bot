"""
Curated topic pool for The Point of Failure: engineering and industrial disasters.

Why this exists: letting the LLM pick its own topic every day produces the same
five famous disasters over and over, which makes the channel feel mass-produced.
A curated pool plus a date-based rotation guarantees months of unique, verifiably
real stories before any repeat.

Every entry is one failure with a mechanism a viewer can repeat afterwards: the
object, the part that broke, the warning that was missed, and the cost. Each
entry is (topic sentence, reach, anniversary as "MM-DD" or None). The
anniversary feeds the trend lane's "this week in disasters" fallback
(anniversary_topics below); it only chooses WHICH story runs, it is never
printed in a title, so a date that is a day off costs nothing.

The pools are grouped by episode format (src/formats.py): each group is a
different object the viewer recognises on sight. Adding a topic means putting
it in the group whose object it is about.
"""

import datetime
import os

# The channel launched single-niche: no experiment lane. Kept as a knob so a
# second lane can be tested later without code changes.
EXPERIMENT_EVERY = int(os.getenv("EXPERIMENT_EVERY", "0"))

# ---------------------------------------------------------------------------
# REACH: how much of an audience a subject can find before the script does any
# work.
#
#   WIDE       Recognised on sight, or shocking without any prior knowledge,
#              and not already done a thousand times.
#   NARROW     Real, well documented, and few people are searching for it. The
#              hook has to do all the work.
#   SATURATED  Famous, and covered by many better-funded channels (Chernobyl,
#              Titanic, Tacoma Narrows). Recognition does not help when the
#              feed already has fifty versions.
#
# Every rating below is editorial judgement at launch. Re-rate a topic only
# from an upload at least MIN_RATING_AGE_DAYS old: a day-old video has barely
# any views by definition, and rating on it would mark everything the channel
# just published as a flop.
MIN_RATING_AGE_DAYS = 7

WIDE = "wide"
NARROW = "narrow"
SATURATED = "saturated"

# Tiers this pipeline may publish, best first. SATURATED is never selected
# automatically — set REACH_FLOOR=all to override.
REACH_ORDER = [WIDE, NARROW, SATURATED]
REACH_FLOOR = os.getenv("REACH_FLOOR", WIDE)

# THE COLLAPSE — buildings, bridges, roofs, walkways, cranes.
_COLLAPSE = [
    ("The Hyatt Regency walkway collapse (1981), where a single change to how two walkways hung doubled the load on one connection and killed 114 people", WIDE, "07-17"),
    ("The Sampoong Department Store collapse (1995), the Seoul store whose owners removed columns and added a rooftop restaurant until 502 people died", WIDE, "06-29"),
    ("The Silver Bridge collapse (1967), where one cracked eyebar dropped a rush-hour bridge into the Ohio River and killed 46", WIDE, "12-15"),
    ("The Quebec Bridge collapse (1907), the longest cantilever span in the world, which fell the same afternoon its consulting engineer telegraphed to add no more load", WIDE, "08-29"),
    ("The Tay Bridge disaster (1879), the Scottish railway bridge that blew down in a winter gale with a train on it, after its designer made no proper allowance for wind", WIDE, "12-28"),
    ("The Ronan Point collapse (1968), where a gas explosion in one kitchen brought down an entire corner of a 22-storey London tower block", WIDE, "05-16"),
    ("The Hartford Civic Center roof collapse (1978), the space-frame roof that sagged for years and fell under snow hours after 5,000 fans went home", WIDE, "01-18"),
    ("The Kemper Arena roof collapse (1979), brought down by a storm and the fatigue in the bolts that hung it", NARROW, "06-04"),
    ("The I-35W Mississippi River bridge collapse (2007), traced to gusset plates designed half as thick as they needed to be forty years earlier", WIDE, "08-01"),
    ("The Seongsu Bridge collapse (1994), where a 48-metre span of a Seoul bridge dropped into the Han River during the morning commute", NARROW, "10-21"),
    ("The West Gate Bridge collapse (1970), where engineers in Melbourne removed bolts to flatten a buckle in a span that then fell and killed 35 workers", WIDE, "10-15"),
    ("The Dee Bridge disaster (1847), the cast-iron railway girder that snapped under a train and ended the use of cast iron for bridges", NARROW, "05-24"),
    ("The Ashtabula River railroad bridge disaster (1876), the iron truss that failed under a snowbound express and killed 92", NARROW, "12-29"),
    ("The Mianus River Bridge collapse (1983), where one rusted pin let a span of Interstate 95 drop into the river at night", NARROW, "06-28"),
    ("The Hotel New World collapse in Singapore (1986), where the building's own weight had been miscalculated from the day it was designed", NARROW, "03-15"),
    ("The L'Ambiance Plaza collapse (1987), the Connecticut apartment building that fell while its concrete floors were being jacked into place", NARROW, "04-23"),
    ("The Knickerbocker Theatre roof collapse (1922), where heavy snow brought a Washington cinema roof down on its audience and killed 98", NARROW, "01-28"),
    ("The Pemberton Mill collapse (1860), the Massachusetts textile mill built with brittle cast-iron columns that fell on 600 workers", NARROW, "01-10"),
    ("The Tacoma Narrows Bridge (1940), the span designed for wind loads that twisted itself apart in a 40 mph breeze", SATURATED, "11-07"),
    ("The Citicorp Center crisis (1978), when a student's question revealed a New York skyscraper could blow over in a storm and engineers secretly welded it at night", WIDE, None),
]

# THE BREACH — dams, reservoirs, tanks, levees, tailings.
_BREACH = [
    ("The Johnstown Flood (1889), the dam a private club lowered and modified until it failed and killed 2,209 people downstream", WIDE, "05-31"),
    ("The St. Francis Dam failure (1928), the Los Angeles dam its builder inspected and declared safe hours before it collapsed and killed over 400", WIDE, "03-12"),
    ("The Vajont Dam disaster (1963), where a perfect dam held and the mountain beside it slid into the reservoir and sent a wave over the top", WIDE, "10-09"),
    ("The Banqiao Dam failure (1975), designed against a once-in-a-thousand-year storm that arrived within a decade and killed tens of thousands", WIDE, "08-08"),
    ("The Malpasset Dam failure (1959), the thin French arch dam that burst when the rock beneath one side gave way", NARROW, "12-02"),
    ("The Teton Dam failure (1976), the brand-new Idaho dam that leaked, eroded and collapsed on its first filling while cameras rolled", WIDE, "06-05"),
    ("The Boston Molasses Flood (1919), the storage tank that leaked so visibly it was painted brown to hide it, until it burst", SATURATED, "01-15"),
    ("The London Beer Flood (1814), when a single failed iron hoop released a wave of porter through a London parish", NARROW, "10-17"),
    ("The Aberfan disaster (1966), where a colliery spoil tip built over a spring slid onto a Welsh village school", WIDE, "10-21"),
    ("The Buffalo Creek flood (1972), where three coal-waste dams in West Virginia failed four days after a federal inspector called them satisfactory", NARROW, "02-26"),
    ("The Baldwin Hills Reservoir failure (1963), the Los Angeles reservoir that cracked open on live television above a neighbourhood", NARROW, "12-14"),
    ("The Val di Stava dam collapse (1985), where two mine tailings dams in the Italian Alps gave way and buried a village in mud", NARROW, "07-19"),
    ("The Gleno Dam disaster (1923), the Italian dam that failed weeks after filling, built with cheaper materials than designed", NARROW, "12-01"),
    ("The Machchhu dam failure (1979), when a dam in Gujarat was overtopped and destroyed the town of Morbi", NARROW, "08-11"),
    ("The Kelly Barnes Dam failure (1977), the earthen dam above a Georgia college that had been raised again and again until it gave way", NARROW, "11-06"),
    ("The New Orleans floodwall failures during Hurricane Katrina (2005), where the 17th Street Canal floodwall gave way below its design load because of the weak soil beneath it", WIDE, "08-29"),
]

# THE BLAST — plants, refineries, mines, warehouses, reactors, factory fires.
_BLAST = [
    ("The Halifax Explosion (1917), when a munitions ship collided in the harbour and detonated with the force of the largest man-made blast before the atomic bomb", WIDE, "12-06"),
    ("The Texas City disaster (1947), started by a cargo fire on a ship full of ammonium nitrate that crowds gathered on the docks to watch", WIDE, "04-16"),
    ("The Bhopal gas disaster (1984), where a pesticide plant's safety systems were switched off or broken when water reached a tank of methyl isocyanate", WIDE, "12-03"),
    ("The Piper Alpha disaster (1988), the North Sea platform destroyed after a pump whose safety valve had been removed for maintenance was switched back on", WIDE, "07-06"),
    ("The Flixborough disaster (1974), where a temporary pipe bypass at a chemical plant ruptured and the vapour cloud levelled the site", WIDE, "06-01"),
    ("The Seveso disaster (1976), the Italian chemical plant that released a dioxin cloud over the towns around it", NARROW, "07-10"),
    ("The Oppau explosion (1921), where workers loosened a hardened fertiliser pile with dynamite, as they had done thousands of times before", WIDE, "09-21"),
    ("The Courrieres mine disaster (1906), Europe's worst mining disaster, where a coal dust explosion killed 1,099 miners", NARROW, "03-10"),
    ("The Senghenydd colliery disaster (1913), the Welsh mine explosion that killed 439, the worst mining disaster in British history", NARROW, "10-14"),
    ("The Benxihu Colliery disaster (1942), the deadliest coal mine disaster in history, where ventilation was shut off to starve a fire", NARROW, "04-26"),
    ("The Monongah mining disaster (1907), the worst mine disaster in American history, two explosions that killed at least 362", NARROW, "12-06"),
    ("The Farmington Mine disaster (1968), the West Virginia explosion that led to America's federal mine safety law", NARROW, "11-20"),
    ("The Upper Big Branch Mine disaster (2010), where clogged water sprayers and coal dust turned a methane spark into an explosion that killed 29", NARROW, "04-05"),
    ("The Triangle Shirtwaist Factory fire (1911), where locked doors and a collapsing fire escape killed 146 garment workers in eighteen minutes", WIDE, "03-25"),
    ("The New London School explosion (1937), where a Texas school saved money by tapping raw unodourised natural gas, and a spark levelled the building", WIDE, "03-18"),
    ("The Grover Shoe Factory boiler explosion (1905), which blew a Massachusetts factory apart and led to the first boiler safety code", NARROW, "03-20"),
    ("The PEPCON explosion (1988), when a fire at a Nevada rocket-fuel plant set off thousands of tonnes of ammonium perchlorate", NARROW, "05-04"),
    ("The San Juanico disaster (1984), the chain of gas tank explosions at a Mexico City LPG terminal that killed hundreds", NARROW, "11-19"),
    ("The Guadalajara explosions (1992), when fuel leaking into the sewers blew up eight kilometres of city streets", WIDE, "04-22"),
    ("The Ufa train disaster (1989), when a leaking pipeline filled a valley with gas just as two passenger trains passed each other", WIDE, "06-04"),
    ("The Buncefield fire (2005), where a fuel tank gauge stuck and a safety switch never tripped, overfilling the tank until it exploded", NARROW, "12-11"),
    ("The Texas City refinery explosion (2005), where a tower was overfilled during startup and vented fuel next to occupied trailers", NARROW, "03-23"),
    ("The SL-1 reactor accident (1961), the only fatal reactor accident in the United States, caused by pulling one control rod too far", WIDE, "01-03"),
    ("The Windscale fire (1957), where Britain's plutonium reactor caught fire and workers fought it from the top with hoses", NARROW, "10-10"),
    ("The Kyshtym disaster (1957), the secret Soviet nuclear waste tank explosion hidden for decades", NARROW, "09-29"),
    ("The Port Chicago disaster (1944), where ammunition being loaded onto a ship detonated and killed 320 men", NARROW, "07-17"),
    ("The Sayano-Shushenskaya power station accident (2009), where a 920-tonne turbine tore free of its bolts inside Russia's largest hydroelectric plant", WIDE, "08-17"),
    ("The Chernobyl safety test (1986), the experiment that disabled the protections it was meant to verify", SATURATED, "04-26"),
    ("The Deepwater Horizon blowout (2010), where a failed cement job and a misread pressure test let a well blow out under a drilling rig", SATURATED, "04-20"),
]

# THE SINKING — ships, ferries, submarines, offshore rigs.
_SINKING = [
    ("The sinking of the Vasa (1628), Sweden's mightiest warship, built too tall and too narrow, which sank twenty minutes into its maiden voyage", WIDE, "08-10"),
    ("The Sultana explosion (1865), the worst maritime disaster in American history, caused by a boiler patched overnight on a ship carrying six times its legal capacity", WIDE, "04-27"),
    ("The General Slocum fire (1904), where 1,021 people died beside life preservers that had rotted in place for thirteen years", WIDE, "06-15"),
    ("The SS Eastland disaster (1915), the Chicago steamer that rolled over at its dock with 2,500 people aboard, made top-heavy by the lifeboats added after Titanic", WIDE, "07-24"),
    ("The Herald of Free Enterprise capsizing (1987), the ferry that left Zeebrugge with its bow doors open", WIDE, "03-06"),
    ("The sinking of MS Estonia (1994), where the bow visor tore off in a Baltic storm and the ferry sank in under an hour", WIDE, "09-28"),
    ("The loss of the Kursk (2000), the submarine sunk by its own torpedo propellant leaking in the tube", WIDE, "08-12"),
    ("The loss of USS Thresher (1963), the nuclear submarine lost on a test dive after a silver-brazed pipe joint failed", WIDE, "04-10"),
    ("The Alexander L. Kielland platform capsizing (1980), where a fatigue crack from one badly welded hydrophone fitting brought down a North Sea rig and killed 123", NARROW, "03-27"),
    ("The Ocean Ranger sinking (1982), the 'unsinkable' drilling rig lost off Newfoundland after a storm broke a porthole into its ballast control room", NARROW, "02-15"),
    ("The sinking of the SS Edmund Fitzgerald (1975), the Great Lakes freighter that vanished in a storm without a distress call", WIDE, "11-10"),
    ("The sinking of the Titanic (1912) and the rivets, the bulkheads that stopped short of the deck, and the lifeboat count that met the law", SATURATED, "04-15"),
    ("The sinking of HMS Hood (1941), the battlecruiser lost in about three minutes with 1,415 men and three survivors because its deck armour could not stop plunging fire", WIDE, "05-24"),
    ("The SS Marine Electric sinking (1983), the rusted-out bulk carrier whose loss in a storm exposed a broken ship inspection system", NARROW, "02-12"),
]

# THE MACHINE — aircraft, rockets, spacecraft, trains, software.
_MACHINE = [
    ("The Challenger disaster (1986) and the engineers who argued against launching in the cold the night before", WIDE, "01-28"),
    ("The Columbia disaster (2003), where a piece of foam insulation broke the wing at launch, and managers decided nothing could be done", WIDE, "02-01"),
    ("The Apollo 1 fire (1967), where a pure-oxygen cabin and an inward-opening hatch trapped three astronauts during a ground test", WIDE, "01-27"),
    ("The Nedelin catastrophe (1960), where a Soviet rocket was fuelled and worked on at the same time and ignited on the pad", WIDE, "10-24"),
    ("The Ariane 5 Flight 501 explosion (1996), destroyed 39 seconds after launch by reused software converting a number into a variable too small to hold it", WIDE, "06-04"),
    ("The Mars Climate Orbiter (1999), lost because one team worked in pound-force and the other in newtons", WIDE, "09-23"),
    ("The de Havilland Comet crashes (1954), when the world's first jet airliners broke apart in mid-air from metal fatigue at the corners of their windows", WIDE, "01-10"),
    ("The Gimli Glider (1983), Air Canada Flight 143, the airliner that ran out of fuel at 41,000 feet after a conversion between pounds and kilograms", WIDE, "07-23"),
    ("Japan Airlines Flight 123 (1985), the deadliest single-aircraft crash in history, caused by a pressure bulkhead repaired with one row of rivets instead of two", WIDE, "08-12"),
    ("Aloha Airlines Flight 243 (1988), where an eighteen-foot section of a Boeing 737's roof tore off at 24,000 feet", WIDE, "04-28"),
    ("United Airlines Flight 232 (1989), the DC-10 that lost all three hydraulic systems when one fan disk shattered, and the crew who steered it with engine thrust", WIDE, "07-19"),
    ("American Airlines Flight 191 (1979), where a forklift shortcut in maintenance cracked an engine pylon and the engine tore off on takeoff", WIDE, "05-25"),
    ("Turkish Airlines Flight 981 (1974), the DC-10 whose cargo door could look locked when it was not", NARROW, "03-03"),
    ("The Hindenburg disaster (1937), the hydrogen airship that burned in 34 seconds while landing in New Jersey", SATURATED, "05-06"),
    ("The R101 airship disaster (1930), Britain's giant airship sent to India before its trials were finished", NARROW, "10-05"),
    ("The Eschede train disaster (1998), where one fatigued wheel tyre derailed a German high-speed train into a bridge at 200 km/h", WIDE, "06-03"),
    ("The Therac-25 accidents (1985-1987), the radiation therapy machine whose software race condition gave patients a hundred times the intended dose", WIDE, None),
    ("The Patriot missile failure at Dhahran (1991), where a clock error of a third of a second let a Scud missile through and killed 28 soldiers", WIDE, "02-25"),
    ("The Northeast blackout of 2003, where a software bug silenced the alarms while 50 million people lost power", WIDE, "08-14"),
    ("The Kings Cross fire (1987), where a match dropped through a wooden escalator onto decades of grease and lint", WIDE, "11-18"),
    ("Soyuz 11 (1971), the only people to die in space, killed when a valve opened during separation", NARROW, "06-30"),
    ("The Air France Flight 447 crash (2009), where iced-over speed sensors handed a confused crew an airliner in a stall they did not recognise", WIDE, "06-01"),
]


def _interleave(*pools):
    """Round-robins the formats so consecutive uploads change object.

    The rotation walks CORE_TOPICS in order, so concatenating the formats would
    publish twenty collapses and then twenty sinkings. Alternating means every
    week samples the whole channel.
    """
    out = []
    for row in zip(*(list(p) for p in pools)):
        out.extend(row)
    longest = max(len(p) for p in pools)
    for i in range(min(len(p) for p in pools), longest):
        for pool in pools:
            if i < len(pool):
                out.append(pool[i])
    return out


_CORE = _interleave(_COLLAPSE, _BLAST, _MACHINE, _BREACH, _SINKING)

# Kept as an empty lane so EXPERIMENT_EVERY has somewhere to point later.
_EXPERIMENT = []

# Topics already covered before this pool existed. Empty on a new channel;
# the long-form encore lane matches the best-performing Short's title against
# ALL_TOPICS, so a topic published outside the pool belongs here.
PUBLISHED_TOPICS = []

CORE_TOPICS = [t[0] for t in _CORE]
EXPERIMENT_TOPICS = [t[0] for t in _EXPERIMENT]

# Every rated topic, by rating. Anything absent is treated as NARROW, which is
# the cautious answer.
REACH = {t[0]: t[1] for t in _CORE + _EXPERIMENT}

# "MM-DD" of the failure, for the anniversary fallback.
ANNIVERSARY = {t[0]: t[2] for t in _CORE + _EXPERIMENT if len(t) > 2 and t[2]}

ALL_TOPICS = CORE_TOPICS + EXPERIMENT_TOPICS + PUBLISHED_TOPICS

# Which episode format a topic belongs to. The pool groups are the source of
# truth; see src/formats.py for what each promises.
FORMAT_BY_TOPIC = {}
for _group, _key in ((_COLLAPSE, "collapse"), (_BREACH, "breach"),
                     (_BLAST, "blast"), (_SINKING, "sinking"),
                     (_MACHINE, "machine")):
    for _entry in _group:
        FORMAT_BY_TOPIC[_entry[0]] = _key

_PUBLISHED_FORMATS = {}

# Only for topics that are in no list at all: the trend lane writes its own
# topic sentences. Checked in this order, first match wins; strong signals only,
# because a mis-formatted episode promises one object and shows another.
_FORMAT_HINTS = (
    ("breach", ("dam ", "dam's", "dam,", "dam failure", "reservoir", "levee",
                "tailings", "flood", "storage tank", "molasses", "floodwall")),
    ("sinking", ("sank", "sinking", "capsiz", "ship", "ferry", "submarine",
                 "vessel", "platform", "rig ", "shipwreck", "steamer")),
    ("machine", ("flight ", "airliner", "aircraft", "plane", "crash", "rocket",
                 "launch", "shuttle", "spacecraft", "satellite", "orbiter",
                 "train", "derail", "railway", "software", "airship")),
    ("blast", ("explosion", "exploded", "blast", "fire", "refinery", "plant",
               "reactor", "mine ", "mining", "colliery", "chemical", "gas leak",
               "pipeline", "factory", "boiler", "detonat")),
    ("collapse", ("collapse", "bridge", "building", "roof", "walkway", "tower",
                  "crane", "stadium", "structural")),
)


def format_of(topic: str) -> str:
    """The episode format for a topic. Never raises and never returns None: an
    untagged topic must still produce a video."""
    known = FORMAT_BY_TOPIC.get(topic) or _PUBLISHED_FORMATS.get(topic)
    if known:
        return known
    low = f" {(topic or '').lower()} "
    for key, hints in _FORMAT_HINTS:
        if any(h in low for h in hints):
            return key
    return "collapse"


def reach_of(topic: str) -> str:
    """WIDE / NARROW / SATURATED. Unknown topics are NARROW: cautious, and never
    excluded outright."""
    return REACH.get(topic, NARROW)


def anniversary_topics(day: datetime.date = None, window: int = 3,
                       exclude=()) -> list:
    """Pool topics whose failure happened within `window` days of `day` (any
    year), closest first, then WIDE before NARROW before SATURATED. The trend
    lane's fallback when no engineering failure is in the news this week."""
    day = day or datetime.date.today()
    exclude = set(exclude or ())
    found = []
    for topic, mmdd in ANNIVERSARY.items():
        if topic in exclude:
            continue
        try:
            month, dom = (int(x) for x in mmdd.split("-"))
        except ValueError:
            continue
        best = None
        for year in (day.year - 1, day.year, day.year + 1):
            try:
                gap = abs((datetime.date(year, month, dom) - day).days)
            except ValueError:      # 02-29 in a non-leap year
                continue
            best = gap if best is None else min(best, gap)
        if best is not None and best <= window:
            found.append((best, REACH_ORDER.index(reach_of(topic)), topic))
    return [t for _, _, t in sorted(found)]


def _allowed_tiers(floor: str) -> set:
    """Every tier from the best down to `floor`. 'all' means no gate."""
    if floor == "all":
        return set(REACH_ORDER)
    if floor not in REACH_ORDER:
        print(f"⚠️ Unknown REACH_FLOOR {floor!r} — falling back to {WIDE!r}.")
        floor = WIDE
    return set(REACH_ORDER[:REACH_ORDER.index(floor) + 1])


def _topic_for_slot(slot: int) -> str:
    """The pool entry a given rotation slot maps to."""
    if EXPERIMENT_EVERY and slot % EXPERIMENT_EVERY == 0 and EXPERIMENT_TOPICS:
        return EXPERIMENT_TOPICS[(slot // EXPERIMENT_EVERY) % len(EXPERIMENT_TOPICS)]

    # Subtract the slots already spent on experiments so the core pool advances
    # by exactly one each time it is used, instead of skipping every 7th entry.
    core_slot = slot - (slot // EXPERIMENT_EVERY if EXPERIMENT_EVERY else 0)
    return CORE_TOPICS[core_slot % len(CORE_TOPICS)]


def _rotate(slot: int, exclude: set, tiers: set):
    """The first topic at or after `slot` that is unpublished and in `tiers`."""
    for step in range(len(CORE_TOPICS) + len(EXPERIMENT_TOPICS) + 1):
        topic = _topic_for_slot(slot + step)
        if topic in exclude or reach_of(topic) not in tiers:
            continue
        if step:
            print(f"↪️  Skipped {step} pool entr(ies): already published, or "
                  f"below the {'/'.join(sorted(tiers))} reach floor.")
        return topic
    return None


def pick_topic(offset: int = 0, exclude=(), floor: str = None) -> str:
    """The topic for today's slot: unpublished, and worth publishing.

    Two gates, and they are different problems.

    Deduplication (`exclude`) stops the channel republishing itself. The date
    rotation alone is not memory: two runs on the same day land on the same slot
    and therefore the same subject, which is how four Light Brigade Shorts, two
    Ariane 5s and two Great Fires happened.

    Reach (`floor`) is the hit-rate gate. Nothing about the pipeline separates a
    600-view upload from a 10-view one — the scripts, the voice and the render
    are identical. What separates them is whether anyone was ever going to
    watch a video about that subject. Topics below the floor stay in the pool
    and are used only once the better ones are gone, rather than being deleted:
    a NARROW topic is not a bad topic, it is one that needs help this channel
    cannot give it yet.

    Returns None only when the pool is genuinely finished at every tier.
    """
    exclude = {e.strip() for e in exclude if isinstance(e, str) and e.strip()}
    slot = datetime.date.today().toordinal() + offset
    floor = floor or REACH_FLOOR

    topic = _rotate(slot, exclude, _allowed_tiers(floor))
    if topic:
        return topic

    # Nothing left in the preferred tiers. Widening beats publishing nothing,
    # but say so plainly — it means the pool needs new WIDE entries.
    for wider in REACH_ORDER[REACH_ORDER.index(NARROW):]:
        if wider == SATURATED and floor != "all":
            break
        topic = _rotate(slot, exclude, _allowed_tiers(wider))
        if topic:
            print(f"⚠️ No unpublished {WIDE} topic left — falling back to "
                  f"{wider}. Add recognisable subjects to CORE_TOPICS.")
            return topic

    print("❌ Every topic in the pool has already been published.")
    return None


if __name__ == "__main__":
    # Preview the next three weeks of scheduling.
    # Each preview day excludes what the days before it published, which is what
    # published_history does at runtime. Without that the preview shows the same
    # topic twice whenever a skip lands on it from two different slots.
    published = set()
    for i in range(21):
        day = datetime.date.today() + datetime.timedelta(days=i)
        picked = pick_topic(i, exclude=published)
        tag = reach_of(picked) if picked else "-"
        print(f"{day} [{tag:9}] {(picked or '(pool exhausted)')[:80]}")
        published.add(picked)
