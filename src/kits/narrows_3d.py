"""
Tacoma Narrows Bridge (1940) in 3D, Blender's free bpy module, CPU only.

Built to the level of the best channels in the niche (owner, 9 Nov 2026:
"similar quality or even better", the 3D model animation only), part by
part, from what the 1940 film and the Board of Engineers' report show:

    towers      two steel towers, 425 ft above the water, on concrete piers;
                legs of riveted plate, struts and X bracing between them
    cables      two main cables 39 ft apart, cable bands with bolts at
                every hanger, saddles on the towers, concrete anchorages
    hangers     pairs of wire ropes every 50 ft
    deck        two lanes and two sidewalks, carried by two solid plate
                girders 8 ft deep (the flaw: a solid wall the wind could not
                pass through), floor beams and lateral bracing below,
                railings and lamp posts
    world       the Narrows: grey-green water whipped by a 42 mph wind,
                steep bluffs under fir forest, an overcast November sky

The bridge was four months old (opened 1 July 1940): clean paint, no rust.

Motion is driven, not hand-keyed per part: one geometry-nodes group moves
every vertex of the deck, hangers and cables from two numbers per frame,
the twist and the heave, through the bridge's own mode shapes:
    twist   the first antisymmetric torsional mode: one node at midspan,
            one half of the main span rolling one way while the other
            rolls the other (about 0.2 Hz on 7 Nov 1940)
    heave   vertical waves along the span (the months of "Galloping Gertie")
The deck turns rigidly about its own axis; the hangers lean between the
deck edge and the cable; the cables only rise and fall.

Units: one unit is one foot. x along the bridge (Tacoma, east, is +x;
Gig Harbor, west, is -x), y across it (north +y), z up from the water.
"""

import math
import os
import random

import bpy
from mathutils import Euler, Vector

from kits import look
SHORT = __import__("kits.timemap", fromlist=["SHORT"]).SHORT["flutter"]   # the tall Short cameras

FPS = 30

# the bridge (feet)
HALF = 1400.0                    # half the 2,800 ft main span: towers at x = +-1400
SIDE = 1100.0                    # side spans to the anchorages at x = +-2500
ANCHOR_X = HALF + SIDE
GIRDER_Y = 19.5                  # girders and cables 39 ft apart
ROAD_Z = 195.0                   # roadway at midspan, about 195 ft over the water
GIRDER_D = 8.0                   # the plate girders, 8 ft deep
G_TOP = ROAD_Z + 2.5             # girder top flange, a little above the road (they were the deck's edge walls)
G_BOT = G_TOP - GIRDER_D
AXIS_Z = (G_TOP + G_BOT) / 2     # the deck turns about its middle
TOWER_TOP = 425.0
SADDLE_Z = TOWER_TOP - 6.0
CABLE_LOW = ROAD_Z + 9.0         # the cables dip to a few feet over the road at midspan
ANCHOR_Z = ROAD_Z - 10.0         # where the side-span cables enter the anchorages
HANGER_DX = 50.0
CABLE_R = 0.75                   # 17.5 in cables, drawn a little heavier so they read at a distance
SHORE_X = 2050.0                 # where the bluffs meet the water


def cable_z(x):
    """Height of a main cable at x: a parabola in the main span, a shallow
    one in each side span."""
    ax = abs(x)
    if ax <= HALF:
        return CABLE_LOW + (SADDLE_Z - CABLE_LOW) * (ax / HALF) ** 2
    u = (ax - HALF) / SIDE                       # 0 at the tower, 1 at the anchorage
    chord = SADDLE_Z + (ANCHOR_Z - SADDLE_Z) * u
    return chord - 30.0 * 4 * u * (1 - u)        # 30 ft of sag in the side spans


def road_z(x):
    """The roadway: level across the main span, and the side spans too
    (the approaches met the bluffs at about deck level)."""
    return ROAD_Z


# ------------------------------------------------------------------ meshes
class MeshBuilder:
    """Collects boxes, tubes and plates into one mesh with several
    materials and a per-vertex "rigid" attribute (1: turns with the deck;
    0: a hanger or cable, which only leans and rises)."""

    def __init__(self):
        self.v, self.f, self.mi, self.rigid = [], [], [], []

    def _add(self, verts, faces, mi, rigid):
        k = len(self.v)
        self.v += [tuple(p) for p in verts]
        self.rigid += [rigid] * len(verts)
        for f in faces:
            self.f.append(tuple(k + i for i in f))
            self.mi.append(mi)

    def box(self, x0, x1, y0, y1, z0, z1, mi=0, rigid=1.0):
        verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                 (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self._add(verts, faces, mi, rigid)

    def beam(self, p0, p1, w, h, mi=0, rigid=1.0, up_hint=(0, 0, 1)):
        """A straight member of w x h section from p0 to p1."""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        if d.length < 1e-6:
            return
        d.normalize()
        up = Vector(up_hint)
        if abs(d.dot(up)) > 0.95:
            up = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0))
        side = d.cross(up).normalized()
        up = side.cross(d).normalized()
        verts = []
        for p in (p0, p1):
            for sw, sh in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                verts.append(p + side * (sw * w / 2) + up * (sh * h / 2))
        faces = [(0, 1, 2, 3)[::-1], (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self._add(verts, faces, mi, rigid)

    def tube(self, pts, r, n=8, mi=0, rigid=0.0, caps=True):
        """A round member along a polyline (cables, hangers, rails)."""
        pts = [Vector(p) for p in pts]
        verts, faces = [], []
        for i, p in enumerate(pts):
            d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
            u = d.cross(a).normalized()
            w = d.cross(u).normalized()
            for k in range(n):
                t = 2 * math.pi * k / n
                verts.append(p + (u * math.cos(t) + w * math.sin(t)) * r)
        for i in range(len(pts) - 1):
            for k in range(n):
                a, b = i * n + k, i * n + (k + 1) % n
                faces.append((a, b, b + n, a + n))
        if caps:
            faces.append(tuple(range(n))[::-1])
            last = (len(pts) - 1) * n
            faces.append(tuple(last + k for k in range(n)))
        self._add(verts, faces, mi, rigid)

    def shell(self, pts, y0, y1, thick, mi=0, rigid=1.0):
        """A curved plate along a polyline in the x-z plane, from y0 to y1
        across, `thick` thick (a fender, a cowl)."""
        pts = [Vector(p) for p in pts]
        verts, faces = [], []
        for i, p in enumerate(pts):
            d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)])
            nrm = Vector((-d.z, 0, d.x)).normalized()          # outward in x-z
            for o in (0.0, -thick):
                for y in (y0, y1):
                    verts.append((p.x + nrm.x * o, y, p.z + nrm.z * o))
        for i in range(len(pts) - 1):
            a, b = 4 * i, 4 * (i + 1)
            faces += [(a, a + 1, b + 1, b), (a + 3, a + 2, b + 2, b + 3),
                      (a + 2, a, b, b + 2), (a + 1, a + 3, b + 3, b + 1)]
        k = 4 * (len(pts) - 1)
        faces += [(0, 2, 3, 1), (k, k + 1, k + 3, k + 2)]
        self._add(verts, faces, mi, rigid)

    def cylinder(self, c, r, length, axis="y", n=16, mi=0, rigid=1.0):
        c = Vector(c)
        d = {"x": Vector((1, 0, 0)), "y": Vector((0, 1, 0)), "z": Vector((0, 0, 1))}[axis]
        self.tube([c - d * length / 2, c + d * length / 2], r, n=n, mi=mi, rigid=rigid)

    def build(self, name, materials, smooth=False, bevel=0.0):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        for m in materials:
            me.materials.append(m)
        for p, mi in zip(me.polygons, self.mi):
            p.material_index = mi
            p.use_smooth = smooth
        at = me.attributes.new("rigid", "FLOAT", "POINT")
        at.data.foreach_set("value", self.rigid)
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        if bevel > 0:
            bv = o.modifiers.new("bevel", "BEVEL")
            bv.width = bevel
            bv.segments = 2
            bv.limit_method = "ANGLE"
            bv.angle_limit = math.radians(40)
            bv.harden_normals = False
        return o


# --------------------------------------------------------------- materials
def _p(m):
    m.use_nodes = True
    return m.node_tree, m.node_tree.nodes["Principled BSDF"]


def bridge_paint(name, colour=(0.36, 0.40, 0.38)):
    """New paint on riveted steel: an even coat, slight sheen, faint rivet
    rows and plate seams in the bump (object space, feet)."""
    m = bpy.data.materials.new(name)
    nt, b = _p(m)
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Metallic"].default_value = 0.35
    b.inputs["Roughness"].default_value = 0.42
    tc = nt.nodes.new("ShaderNodeTexCoord")
    # rivets: a fine grid of dots (a Voronoi distance, sharpened)
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "F1"
    vor.inputs["Scale"].default_value = 1.6
    if "Randomness" in vor.inputs:
        vor.inputs["Randomness"].default_value = 0.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["From Min"].default_value = 0.08
    rr.inputs["From Max"].default_value = 0.16
    rr.inputs["To Min"].default_value = 1.0
    rr.inputs["To Max"].default_value = 0.0
    nt.links.new(vor.outputs["Distance"], rr.inputs["Value"])
    # paint unevenness, large and soft
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 0.08
    n.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (*[c * 0.86 for c in colour], 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (*[min(1, c * 1.08) for c in colour], 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.04
    nt.links.new(rr.outputs["Result"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def plain(name, colour, rough=0.6, metal=0.0):
    m = bpy.data.materials.new(name)
    nt, b = _p(m)
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def wire_rope(name):
    """A cable or hanger: steel wire laid in a helix, read as fine streaks."""
    m = bpy.data.materials.new(name)
    nt, b = _p(m)
    b.inputs["Base Color"].default_value = (0.30, 0.31, 0.31, 1)
    b.inputs["Metallic"].default_value = 0.8
    b.inputs["Roughness"].default_value = 0.38
    tc = nt.nodes.new("ShaderNodeTexCoord")
    w = nt.nodes.new("ShaderNodeTexWave")
    w.wave_type = "BANDS"
    w.inputs["Scale"].default_value = 2.5
    w.inputs["Distortion"].default_value = 1.0
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    bump.inputs["Distance"].default_value = 0.02
    nt.links.new(w.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def roadway(name):
    """1940 concrete pavement: pale, weathered in patches, joints across it
    every 20 ft, one solid white centre line."""
    m = bpy.data.materials.new(name)
    nt, b = _p(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 0.25
    n.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.32, 0.31, 0.29, 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.44, 0.43, 0.40, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs["Fac"])
    # centre line: |y| < 0.25 ft, dashed along x
    ay = nt.nodes.new("ShaderNodeMath")
    ay.operation = "ABSOLUTE"
    nt.links.new(sep.outputs["Y"], ay.inputs[0])
    line = nt.nodes.new("ShaderNodeMath")
    line.operation = "LESS_THAN"
    line.inputs[1].default_value = 0.25
    nt.links.new(ay.outputs[0], line.inputs[0])
    dash = nt.nodes.new("ShaderNodeMath")
    dash.operation = "PINGPONG"
    dash.inputs[1].default_value = 10.0
    nt.links.new(sep.outputs["X"], dash.inputs[0])
    dgt = nt.nodes.new("ShaderNodeMath")
    dgt.operation = "GREATER_THAN"
    dgt.inputs[1].default_value = 4.0
    nt.links.new(dash.outputs[0], dgt.inputs[0])
    # the 1940 film shows one solid white centre line, not a dashed one
    paint = nt.nodes.new("ShaderNodeMath")
    paint.operation = "MULTIPLY"
    nt.links.new(line.outputs[0], paint.inputs[0])
    paint.inputs[1].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(paint.outputs[0], mix.inputs[0])
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (0.85, 0.84, 0.78, 1)
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    # expansion joints across the road every 20 ft
    jm = nt.nodes.new("ShaderNodeMath")
    jm.operation = "PINGPONG"
    jm.inputs[1].default_value = 10.0
    nt.links.new(sep.outputs["X"], jm.inputs[0])
    jl = nt.nodes.new("ShaderNodeMath")
    jl.operation = "LESS_THAN"
    jl.inputs[1].default_value = 0.06
    nt.links.new(jm.outputs[0], jl.inputs[0])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    bump.inputs["Distance"].default_value = 0.05
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(jl.outputs[0], inv.inputs[1])
    nt.links.new(inv.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.85
    return m


def sea(name):
    """Puget Sound in a 42 mph wind: grey-green, short steep waves running
    with the wind (from the south-west), whitecaps in streaks."""
    m = bpy.data.materials.new(name)
    nt, b = _p(m)
    deep = (0.020, 0.040, 0.040, 1)
    b.inputs["Base Color"].default_value = deep
    b.inputs["Metallic"].default_value = 0.0
    if "IOR" in b.inputs:
        b.inputs["IOR"].default_value = 1.33
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(35))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])

    def waves(scale, distortion, rot):
        r = nt.nodes.new("ShaderNodeMapping")
        r.inputs["Rotation"].default_value = (0, 0, math.radians(rot))
        nt.links.new(mp.outputs["Vector"], r.inputs["Vector"])
        w = nt.nodes.new("ShaderNodeTexWave")
        w.wave_type = "BANDS"
        w.wave_profile = "SAW" if hasattr(w, "wave_profile") else w.wave_profile
        w.inputs["Scale"].default_value = scale
        w.inputs["Distortion"].default_value = distortion
        w.inputs["Detail"].default_value = 4.0
        w.inputs["Detail Scale"].default_value = 1.5
        nt.links.new(r.outputs["Vector"], w.inputs["Vector"])
        return w.outputs["Fac"]

    w1 = waves(0.012, 9.0, 0)            # wind waves about 40 ft apart
    w2 = waves(0.027, 7.0, 28)           # a cross sea, shorter
    w3 = waves(0.09, 4.0, -20)           # chop
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY_ADD"
    m1.inputs[1].default_value = 0.6
    nt.links.new(w2, m1.inputs[0])
    nt.links.new(w1, m1.inputs[2])
    m2 = nt.nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY_ADD"
    m2.inputs[1].default_value = 0.25
    nt.links.new(w3, m2.inputs[0])
    nt.links.new(m1.outputs[0], m2.inputs[2])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.9
    bump.inputs["Distance"].default_value = 2.0
    nt.links.new(m2.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    # whitecaps: on the crests, broken up by noise into streaks along the wind
    caps = nt.nodes.new("ShaderNodeTexNoise")
    caps.inputs["Scale"].default_value = 0.02
    caps.inputs["Detail"].default_value = 12.0
    cm = nt.nodes.new("ShaderNodeMapping")
    cm.inputs["Scale"].default_value = (1.0, 4.0, 1.0)
    nt.links.new(mp.outputs["Vector"], cm.inputs["Vector"])
    nt.links.new(cm.outputs["Vector"], caps.inputs["Vector"])
    crest = nt.nodes.new("ShaderNodeMath")
    crest.operation = "MULTIPLY"
    nt.links.new(m2.outputs[0], crest.inputs[0])
    nt.links.new(caps.outputs["Fac"], crest.inputs[1])
    fr = nt.nodes.new("ShaderNodeMapRange")
    fr.inputs["From Min"].default_value = 0.62
    fr.inputs["From Max"].default_value = 0.78
    nt.links.new(crest.outputs[0], fr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(fr.outputs["Result"], mix.inputs[0])
    mix.inputs[6].default_value = deep
    mix.inputs[7].default_value = (0.60, 0.63, 0.63, 1)
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    rmix = nt.nodes.new("ShaderNodeMapRange")
    rmix.inputs["To Min"].default_value = 0.16
    rmix.inputs["To Max"].default_value = 0.8
    nt.links.new(fr.outputs["Result"], rmix.inputs["Value"])
    nt.links.new(rmix.outputs["Result"], b.inputs["Roughness"])
    return m


def fir_mesh(name, material):
    """A Douglas fir: tiers of drooping, ragged branches round a trunk,
    one unit tall, its base at the origin."""
    verts, faces = [], []
    rnd = random.Random(11)
    tiers, n = 7, 14
    for t in range(tiers):
        z0 = 0.12 + 0.82 * t / tiers
        z1 = min(1.0, z0 + 0.26)
        r = 0.32 * (1 - t / tiers) ** 0.9 + 0.03
        k = len(verts)
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * (t % 2)) / n
            rr = r * (1.0 if i % 2 == 0 else 0.62) * rnd.uniform(0.85, 1.15)
            verts.append((rr * math.cos(a), rr * math.sin(a), z0 - 0.04 * rr / 0.3))   # branch tips droop
        verts.append((0, 0, z1))
        top = len(verts) - 1
        for i in range(n):
            faces.append((k + i, k + (i + 1) % n, top))
        faces.append(tuple(k + i for i in range(n))[::-1])
    # the trunk, showing below the lowest branches
    k = len(verts)
    for z in (0.0, 0.2):
        for i in range(5):
            a = 2 * math.pi * i / 5
            verts.append((0.025 * math.cos(a), 0.025 * math.sin(a), z))
    for i in range(5):
        faces.append((k + i, k + (i + 1) % 5, k + 5 + (i + 1) % 5, k + 5 + i))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.materials.append(material)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def forest(name):
    """Douglas fir, dark blue-green, with lighter tips and darker gaps."""
    m = bpy.data.materials.new(name)
    nt, b = _p(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 0.35
    n.inputs["Detail"].default_value = 10.0
    nt.links.new(tc.outputs["Generated"], n.inputs["Vector"])
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.012, 0.028, 0.018, 1)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.05, 0.085, 0.045, 1)
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "MULTIPLY_ADD"
    add.inputs[1].default_value = 0.5
    nt.links.new(n.outputs["Fac"], add.inputs[0])
    # each tree a little different (the instance's random value)
    nt.links.new(oi.outputs["Random"], add.inputs[2])
    half = nt.nodes.new("ShaderNodeMath")
    half.operation = "MULTIPLY"
    half.inputs[1].default_value = 0.7
    nt.links.new(add.outputs[0], half.inputs[0])
    nt.links.new(half.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    nt.links.new(n.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


# ----------------------------------------------------------- the motion
class _E:
    """A tiny expression builder over geometry-node Math nodes."""

    def __init__(self, g, sock):
        self.g, self.s = g, sock

    def _op(self, op, other=None, rev=False):
        n = self.g.nodes.new("ShaderNodeMath")
        n.operation = op
        a, b = (other, self) if rev else (self, other)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, _E):
                self.g.links.new(v.s, n.inputs[i])
            else:
                n.inputs[i].default_value = float(v)
        return _E(self.g, n.outputs[0])

    def __add__(self, o): return self._op("ADD", o)
    def __radd__(self, o): return self._op("ADD", o, True)
    def __sub__(self, o): return self._op("SUBTRACT", o)
    def __rsub__(self, o): return self._op("SUBTRACT", o, True)
    def __mul__(self, o): return self._op("MULTIPLY", o)
    def __rmul__(self, o): return self._op("MULTIPLY", o, True)
    def __truediv__(self, o): return self._op("DIVIDE", o)
    def sin(self): return self._op("SINE")
    def cos(self): return self._op("COSINE")
    def abs(self): return self._op("ABSOLUTE")
    def lt(self, o): return self._op("LESS_THAN", o)
    def max(self, o): return self._op("MAXIMUM", o)
    def min(self, o): return self._op("MINIMUM", o)


def twist_mode(x):
    """The torsional mode shape: zero at the towers and at midspan, largest
    at the quarter points, opposite signs either side of the middle."""
    return -math.sin(math.pi * x / HALF) if abs(x) < HALF else 0.0


def heave_mode(x, waves):
    return math.sin(waves * math.pi * (x + HALF) / (2 * HALF)) if abs(x) < HALF else 0.0


def deck_transform(x, y, z, twist, heave, waves):
    """The same displacement the node group applies, for rigid riders (a
    car on the deck): returns the new (y, z) and the roll angle."""
    th = twist * twist_mode(x)
    rel = z - AXIS_Z
    yy = y * math.cos(th) - rel * math.sin(th)
    zz = AXIS_Z + y * math.sin(th) + rel * math.cos(th) + heave * heave_mode(x, waves)
    return yy, zz, th


def motion_group():
    """Geometry nodes: moves each point by the frame's twist and heave
    (modifier inputs, keyed per frame) through the mode shapes."""
    if "narrows_motion" in bpy.data.node_groups:
        return bpy.data.node_groups["narrows_motion"]
    g = bpy.data.node_groups.new("narrows_motion", "GeometryNodeTree")
    io = g.interface
    io.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    io.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for nm in ("Twist", "Heave", "Waves", "OffX", "OffY", "OffZ", "Snap", "SideSag"):
        io.new_socket(nm, in_out="INPUT", socket_type="NodeSocketFloat")
    gi = g.nodes.new("NodeGroupInput")
    go = g.nodes.new("NodeGroupOutput")
    pos = g.nodes.new("GeometryNodeInputPosition")
    sep = g.nodes.new("ShaderNodeSeparateXYZ")
    g.links.new(pos.outputs[0], sep.inputs[0])
    attr = g.nodes.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "FLOAT"
    attr.inputs["Name"].default_value = "rigid"
    E = lambda s: _E(g, s)
    X = E(sep.outputs["X"]) + E(gi.outputs["OffX"])
    Y = E(sep.outputs["Y"]) + E(gi.outputs["OffY"])
    Z = E(sep.outputs["Z"]) + E(gi.outputs["OffZ"])
    inmain = X.abs().lt(HALF)
    tmode = (X * (math.pi / HALF)).sin() * -1.0 * inmain
    th = E(gi.outputs["Twist"]) * tmode
    vmode = ((X + HALF) * (math.pi / (2 * HALF)) * E(gi.outputs["Waves"])).sin() * inmain
    H = E(gi.outputs["Heave"]) * vmode
    rel = Z - AXIS_Z
    s, c = th.sin(), th.cos()
    # the deck and all on it: a rigid turn about the deck's axis
    dyr = Y * (c - 1.0) - rel * s
    dzr = Y * s + rel * (c - 1.0)
    # a hanger: its foot goes with the girder top, its head only rises and
    # falls with the cable, and it stays straight between them
    zc = (X * (1.0 / HALF)) * (X * (1.0 / HALF)) * (SADDLE_Z - CABLE_LOW) + CABLE_LOW
    b = ((Z - G_TOP) / (zc - G_TOP).max(1.0)).max(0.0).min(1.0)
    rel0 = G_TOP - AXIS_Z
    foot = 1.0 - b
    dyh = (Y * (c - 1.0) - s * rel0) * foot
    dzh = Y * s + (c - 1.0) * rel0 * foot
    rig = E(attr.outputs["Attribute"])
    ny = Y + dyh + (dyr - dyh) * rig
    nz = Z + dzh + (dzr - dzh) * rig + H
    # the side spans sag once the main span is gone (its pull on the towers
    # gone, the towers lean back toward the shore and the side cables slacken)
    ax_ = X.abs()
    inside_side = (1.0 - ax_.lt(HALF)) * ax_.lt(ANCHOR_X)
    smode = ((ax_ - HALF) * (math.pi / SIDE)).sin() * inside_side
    nz = nz - E(gi.outputs["SideSag"]) * smode
    # a parted segment's hangers: snapped at the cable, they fold down
    # onto the falling deck and swing out (Snap 0 to 1)
    snap = E(gi.outputs["Snap"]) * (1.0 - rig)
    up = (Z - G_TOP).max(0.0)
    nz = nz - up * snap * 0.82
    ny = ny + up * snap * 0.35 * (Y * (1.0 / GIRDER_Y))
    comb = g.nodes.new("ShaderNodeCombineXYZ")
    comb.inputs["X"].default_value = 0.0
    g.links.new((ny - Y).s, comb.inputs["Y"])
    g.links.new((nz - Z).s, comb.inputs["Z"])
    sp = g.nodes.new("GeometryNodeSetPosition")
    g.links.new(gi.outputs["Geometry"], sp.inputs["Geometry"])
    g.links.new(comb.outputs[0], sp.inputs["Offset"])
    g.links.new(sp.outputs[0], go.inputs[0])
    return g


def set_input(o, mod, ident, value, frame=None):
    """Set (and with a frame, key) a geometry-nodes modifier input. Blender
    5 keeps them under mod.properties.inputs; Blender 4 as ID properties."""
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        sock = getattr(props.inputs, ident)
        sock.value = value
        if frame is not None:
            o.keyframe_insert(sock.path_from_id("value"), frame=frame)
    else:
        mod[ident] = value
        if frame is not None:
            mod.keyframe_insert(f'["{ident}"]', frame=frame)


def add_motion(o, off=(0, 0, 0)):
    mod = o.modifiers.new("motion", "NODES")
    mod.node_group = motion_group()
    ids = {it.name: it.identifier for it in mod.node_group.interface.items_tree
           if getattr(it, "in_out", None) == "INPUT" and it.socket_type == "NodeSocketFloat"}
    set_input(o, mod, ids["Waves"], 1.0)
    for nm, v in zip(("OffX", "OffY", "OffZ"), off):
        set_input(o, mod, ids[nm], v)
    # the motion comes before the bevel so the bevel follows the moved shape
    if "bevel" in o.modifiers:
        bpy.context.view_layer.objects.active = o
        o.modifiers.move(len(o.modifiers) - 1, 0)
    return mod, ids


# ------------------------------------------------------------------ car
def chrome(name="chrome"):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    return plain(name, (0.8, 0.8, 0.82), 0.12, 1.0)


def sedan_1930s(name, paint=(0.26, 0.265, 0.25)):
    """A late-1930s sedan as in the 1940 film (Coatsworth's: pale, a rounded
    roof and trunk), about 16 ft long, its origin on the road under
    its middle, nose toward +x: a rounded body (a smoothed cage of
    cross-sections with a crease at the beltline), the glasshouse above it,
    separate sweeping fenders, running boards, chrome grille, bumpers and
    headlamps, tyres with hubcaps."""
    # body: (x, half-width, bottom, beltline, top, roof taper)
    st = [(-8.0, 2.40, 1.75, 2.9, 3.0, 0.80), (-7.3, 2.75, 1.45, 3.45, 4.0, 0.80),
          (-5.4, 2.90, 1.35, 3.55, 5.2, 0.76), (-2.2, 2.95, 1.35, 3.6, 5.55, 0.80),
          (0.9, 2.95, 1.35, 3.6, 5.45, 0.80), (2.2, 2.85, 1.40, 3.6, 3.85, 0.90),
          (5.0, 2.05, 1.60, 3.55, 3.75, 0.88), (7.2, 1.75, 1.70, 3.35, 3.5, 0.84),
          (7.9, 1.45, 1.90, 3.0, 3.1, 0.80)]
    verts, faces, mats = [], [], []
    for x, hw, zb, zbelt, zt, tum in st:
        ring = [(-hw * 0.92, zb), (-hw, zbelt - 0.35), (-hw * 0.99, zbelt), (-hw * 0.93, zbelt + 0.08),
                (-hw * tum, zt), (hw * tum, zt), (hw * 0.93, zbelt + 0.08), (hw * 0.99, zbelt),
                (hw, zbelt - 0.35), (hw * 0.92, zb)]
        verts += [(x, y, z) for y, z in ring]
    n = 10
    for i in range(len(st) - 1):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            faces.append((a, b, b + n, a + n))
            side_window = i in (2, 3) and k in (3, 5)
            windshield = i == 4 and k == 4
            rear_window = i == 1 and k == 4
            mats.append(1 if (side_window or windshield or rear_window) else 0)
    faces.append(tuple(range(n))[::-1])
    mats.append(0)
    last = (len(st) - 1) * n
    faces.append(tuple(last + k for k in range(n)))
    mats.append(0)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.materials.append(look.car_paint(name + "_paint", paint))
    me.materials.append(plain("car_glass", (0.035, 0.04, 0.045), 0.04, 0.2))
    for p, mi in zip(me.polygons, mats):
        p.material_index = mi
        p.use_smooth = True
    body = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(body)
    sub = body.modifiers.new("smooth", "SUBSURF")
    sub.levels = sub.render_levels = 2
    mb = MeshBuilder()
    for wx in (-4.9, 4.4):
        for sy in (-1, 1):
            wy = sy * 2.45
            mb.cylinder((wx, wy, 1.35), 1.35, 0.85, axis="y", n=20, mi=0)          # tyre
            mb.cylinder((wx, wy + sy * 0.45, 1.35), 0.72, 0.08, axis="y", n=20, mi=1)  # hubcap
            # the fender: a smooth arch over the wheel; the front ones sweep
            # forward and down to the bumper, the rear ones back to the tail
            pts = []
            for j in range(15):
                a = math.pi * (0.04 + 0.92 * j / 14)
                pts.append((wx + 1.9 * math.cos(a), 1.35 + 1.75 * math.sin(a)))
            if wx > 0:
                pts = [(wx + 3.3, 1.55), (wx + 2.7, 1.75)] + pts[1:]
            else:
                pts = pts[:-1] + [(wx - 2.6, 1.75), (wx - 3.1, 1.6)]
            pts.sort(key=lambda q: -q[0])
            w0, w1 = sorted((wy - sy * 0.15, wy + sy * 0.95))
            mb.shell([(x, 0, z) for x, z in pts], w0, w1, 0.16, mi=2)
            if wx > 0:
                mb.cylinder((wx + 2.6, wy, 3.35), 0.45, 0.55, axis="x", n=16, mi=1)    # headlamp on the fender
    for sy in (-1, 1):
        mb.box(-2.9, 2.4, sy * 2.75 - 0.6, sy * 2.75 + 0.6, 1.0, 1.2, 2)            # running board
    for bx in (8.35, -8.35):
        mb.box(bx - 0.2, bx + 0.2, -3.0, 3.0, 1.2, 1.6, 1)                       # bumpers
    mb.box(7.85, 8.0, -1.0, 1.0, 1.9, 3.3, 1)                                    # grille shell
    for k in range(9):
        y = -0.85 + 0.2125 * k
        mb.box(7.98, 8.1, y - 0.035, y + 0.035, 2.0, 3.2, 3)
    det = mb.build(name + "_parts", [plain("tyre", (0.025, 0.025, 0.025), 0.85), chrome(),
                                    me.materials[0], plain("grille_dark", (0.02, 0.02, 0.02), 0.4, 0.5)],
                   smooth=False, bevel=0.04)
    det.parent = body
    return body


def delivery_truck_1930s(name, paint=(0.10, 0.11, 0.10)):
    """A 1930s delivery truck (the Rapid Transfer Company's, which tipped
    over on the deck), about 20 ft long, origin on the road under its middle,
    nose toward +x: a rounded hood and cab in front of a tall box body,
    fenders over the front wheels, twin rear wheels."""
    # hood and cab: a smoothed cage like the sedan's
    st = [(2.0, 3.0, 1.6, 7.2, 0.86), (4.6, 3.0, 1.6, 7.0, 0.84), (5.6, 2.6, 1.8, 4.6, 0.9),
          (8.6, 1.9, 2.0, 4.3, 0.86), (9.6, 1.6, 2.2, 3.8, 0.8)]
    verts, faces, mats = [], [], []
    for x, hw, zb, zt, tum in st:
        zm = zb + 0.6 * (zt - zb)
        for y, z in ((-hw, zb), (-hw, zm), (-hw * tum, zt), (hw * tum, zt), (hw, zm), (hw, zb)):
            verts.append((x, y, z))
    n = 6
    for i in range(len(st) - 1):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            faces.append((a, b, b + n, a + n))
            mats.append(1 if (i == 1 and k in (1, 2, 3)) else 0)
    faces.append(tuple(range(n))[::-1])
    mats.append(0)
    last = (len(st) - 1) * n
    faces.append(tuple(last + k for k in range(n)))
    mats.append(0)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.materials.append(look.car_paint(name + "_paint", paint))
    me.materials.append(plain("car_glass", (0.035, 0.04, 0.045), 0.04, 0.2))
    for p, mi in zip(me.polygons, mats):
        p.material_index = mi
        p.use_smooth = True
    cab = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(cab)
    sub = cab.modifiers.new("smooth", "SUBSURF")
    sub.levels = sub.render_levels = 2
    mb = MeshBuilder()
    mb.box(-10.0, 1.8, -3.4, 3.4, 1.9, 9.6, 2)                          # the box body
    for zz in (2.3, 9.0):
        mb.box(-10.15, 1.95, -3.5, 3.5, zz, zz + 0.3, 1)                 # rub rails
    mb.box(-10.2, 9.0, -1.4, 1.4, 1.0, 1.9, 1)                           # chassis frame
    for wx, twin in ((7.0, False), (-6.6, True)):
        for sy in (-1, 1):
            for k in ((0.0, 0.85) if twin else (0.0,)):
                wy = sy * (2.7 + k)
                mb.cylinder((wx, wy, 1.5), 1.5, 0.8, axis="y", n=18, mi=3)
                mb.cylinder((wx, wy + sy * 0.42, 1.5), 0.65, 0.08, axis="y", n=18, mi=1)
        if not twin:
            for sy in (-1, 1):
                wy = sy * 2.7
                pts = [(wx + 2.1 * math.cos(math.pi * (0.05 + 0.9 * j / 12)), 1.5 + 1.9 * math.sin(math.pi * (0.05 + 0.9 * j / 12)))
                       for j in range(13)]
                pts = [(wx + 3.0, 1.7)] + pts[1:]
                pts.sort(key=lambda q: -q[0])
                w0, w1 = sorted((wy - sy * 0.1, wy + sy * 1.0))
                mb.shell([(x, 0, z) for x, z in pts], w0, w1, 0.16, mi=0)
    mb.box(9.7, 10.0, -1.3, 1.3, 2.3, 3.8, 1)                            # radiator shell
    for sy in (-1, 1):
        mb.cylinder((9.4, sy * 2.3, 3.7), 0.42, 0.5, axis="x", n=14, mi=1)  # headlamps
    mb.box(10.1, 10.5, -3.0, 3.0, 1.2, 1.6, 1)                           # bumper
    det = mb.build(name + "_parts", [me.materials[0], chrome(), plain("truck_box", (0.30, 0.31, 0.29), 0.7),
                                    plain("tyre", (0.025, 0.025, 0.025), 0.85)], smooth=False, bevel=0.05)
    det.parent = cab
    return cab


# ------------------------------------------------------------- the water
G = 32.2                      # ft/s^2


def spray_material(name, colour=(0.86, 0.88, 0.88), alpha=0.85):
    """Thrown water: white, a little translucent, fading as the drops
    fall back (the instance's "fade" attribute, 0 to 1)."""
    m = bpy.data.materials.new(name)
    nt, b = _p(m)
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Roughness"].default_value = 0.5
    # white water scatters light every way: it never goes dark on its
    # shadowed side, so a little of the sky's light is given back as glow
    b.inputs["Emission Color"].default_value = (*colour, 1)
    b.inputs["Emission Strength"].default_value = 0.35
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = "INSTANCER"
    at.attribute_name = "fade"
    # alpha * (1 - fade): fully gone by the end of each drop's life
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(at.outputs["Fac"], inv.inputs[1])
    sc_ = nt.nodes.new("ShaderNodeMath")
    sc_.operation = "MULTIPLY"
    sc_.inputs[1].default_value = alpha
    nt.links.new(inv.outputs[0], sc_.inputs[0])
    clamp = nt.nodes.new("ShaderNodeClamp")
    nt.links.new(sc_.outputs[0], clamp.inputs["Value"])
    out = clamp.outputs[0]
    if name != "foam":
        # solid in the middle, soft only at the rim: a ray stops at the first
        # puff it meets instead of passing through hundreds (a splash frame
        # took 11 minutes with see-through puffs, about 30 s without)
        lw = nt.nodes.new("ShaderNodeLayerWeight")
        lw.inputs["Blend"].default_value = 0.5
        rim = nt.nodes.new("ShaderNodeMapRange")
        rim.inputs["From Min"].default_value = 0.55
        rim.inputs["From Max"].default_value = 0.95
        rim.inputs["To Min"].default_value = 1.0
        rim.inputs["To Max"].default_value = 0.0
        nt.links.new(lw.outputs["Facing"], rim.inputs["Value"])
        life = nt.nodes.new("ShaderNodeMath")
        life.operation = "MULTIPLY"
        nt.links.new(inv.outputs[0], life.inputs[0])
        nt.links.new(rim.outputs["Result"], life.inputs[1])
        clamp2 = nt.nodes.new("ShaderNodeClamp")
        nt.links.new(life.outputs[0], clamp2.inputs["Value"])
        out = clamp2.outputs[0]
    if name == "foam":
        # foam: broken into patches, thinning out to nothing at the ring's edge
        tc = nt.nodes.new("ShaderNodeTexCoord")
        ln = nt.nodes.new("ShaderNodeVectorMath")
        ln.operation = "LENGTH"
        nt.links.new(tc.outputs["Object"], ln.inputs[0])
        edge = nt.nodes.new("ShaderNodeMapRange")
        edge.inputs["From Min"].default_value = 0.45
        edge.inputs["From Max"].default_value = 1.0
        edge.inputs["To Min"].default_value = 1.0
        edge.inputs["To Max"].default_value = 0.0
        nt.links.new(ln.outputs["Value"], edge.inputs["Value"])
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 6.0
        nz.inputs["Detail"].default_value = 8.0
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        patch = nt.nodes.new("ShaderNodeMapRange")
        patch.inputs["From Min"].default_value = 0.42
        patch.inputs["From Max"].default_value = 0.62
        nt.links.new(nz.outputs["Fac"], patch.inputs["Value"])
        m1 = nt.nodes.new("ShaderNodeMath")
        m1.operation = "MULTIPLY"
        nt.links.new(out, m1.inputs[0])
        nt.links.new(edge.outputs["Result"], m1.inputs[1])
        m2 = nt.nodes.new("ShaderNodeMath")
        m2.operation = "MULTIPLY"
        nt.links.new(m1.outputs[0], m2.inputs[0])
        nt.links.new(patch.outputs["Result"], m2.inputs[1])
        out = m2.outputs[0]
    nt.links.new(out, b.inputs["Alpha"])
    return m


def splash_group(name, count, speed, spread, drag, life, size, rise=1.0, ring=False, gravity=1.0, tumble=3.14,
                 drift=0.0):
    """Geometry nodes, no simulation: every impact point (a vertex with
    "t_hit" in seconds and "width" in feet) throws `count` drops whose
    positions are worked out from the time since the hit (ballistic with
    air drag), so any frame renders on its own, in any shard."""
    g = bpy.data.node_groups.new(name, "GeometryNodeTree")
    io = g.interface
    io.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    io.new_socket("Drop", in_out="INPUT", socket_type="NodeSocketObject")
    io.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi, go = g.nodes.new("NodeGroupInput"), g.nodes.new("NodeGroupOutput")
    E = lambda sck: _E(g, sck)
    dup = g.nodes.new("GeometryNodeDuplicateElements")
    dup.domain = "POINT"
    dup.inputs["Amount"].default_value = count
    g.links.new(gi.outputs["Geometry"], dup.inputs["Geometry"])
    tnode = g.nodes.new("GeometryNodeInputSceneTime")
    th = g.nodes.new("GeometryNodeInputNamedAttribute")
    th.data_type = "FLOAT"
    th.inputs["Name"].default_value = "t_hit"
    wd = g.nodes.new("GeometryNodeInputNamedAttribute")
    wd.data_type = "FLOAT"
    wd.inputs["Name"].default_value = "width"
    idx = g.nodes.new("GeometryNodeInputIndex")

    def rnd(seed, lo=0.0, hi=1.0):
        r = g.nodes.new("FunctionNodeRandomValue")
        r.data_type = "FLOAT"
        r.inputs["Min"].default_value = lo
        r.inputs["Max"].default_value = hi
        r.inputs["Seed"].default_value = seed
        g.links.new(idx.outputs[0], r.inputs["ID"])
        return E(r.outputs[0])

    # each drop's own start: spread along the impact's width, a little later for some
    age = E(tnode.outputs["Seconds"]) - E(th.outputs["Attribute"]) - rnd(5, 0.0, 0.35)
    a = age.max(0.0)
    ang = rnd(1, 0.0, 6.2832)
    up = rnd(2, 0.45, 1.0)
    sp = rnd(3, 0.35, 1.0) * speed
    vh = sp * spread * rnd(4, 0.2, 1.0)
    vz = sp * up * rise
    # drag: distance travelled is v (1 - e^(-k a)) / k
    k = drag
    ek = (a * -k)
    expn = g.nodes.new("ShaderNodeMath")
    expn.operation = "EXPONENT"
    g.links.new(ek.s, expn.inputs[0])
    fall = (1.0 - E(expn.outputs[0])) * (1.0 / k)
    off_x = (rnd(6, -0.5, 0.5) * E(wd.outputs["Attribute"])) + ang.cos() * vh * fall
    off_y = ang.sin() * vh * fall + rnd(7, -6.0, 6.0) + a * drift      # carried by the wind
    off_z = vz * fall - a * a * (G * gravity / 2.0)
    pos = g.nodes.new("GeometryNodeInputPosition")
    sep = g.nodes.new("ShaderNodeSeparateXYZ")
    g.links.new(pos.outputs[0], sep.inputs[0])
    z = E(sep.outputs["Z"]) + off_z
    # alive: born, not past its life, and not back under the water
    alive = (age * -1.0).lt(0.0) * age.lt(life) * (z * -1.0).lt(1.0)
    comb = g.nodes.new("ShaderNodeCombineXYZ")
    g.links.new((E(sep.outputs["X"]) + off_x).s, comb.inputs["X"])
    g.links.new((E(sep.outputs["Y"]) + off_y).s, comb.inputs["Y"])
    g.links.new(z.s, comb.inputs["Z"])
    setp = g.nodes.new("GeometryNodeSetPosition")
    g.links.new(dup.outputs["Geometry"], setp.inputs["Geometry"])
    g.links.new(comb.outputs[0], setp.inputs["Position"])
    # drop the dead and the unborn
    dele = g.nodes.new("GeometryNodeDeleteGeometry")
    dele.domain = "POINT"
    g.links.new(setp.outputs[0], dele.inputs["Geometry"])
    g.links.new((1.0 - alive).s, dele.inputs["Selection"])
    inst = g.nodes.new("GeometryNodeInstanceOnPoints")
    g.links.new(dele.outputs[0], inst.inputs["Points"])
    oi = g.nodes.new("GeometryNodeObjectInfo")
    g.links.new(gi.outputs["Drop"], oi.inputs["Object"])
    g.links.new(oi.outputs["Geometry"], inst.inputs["Instance"])
    # size: big blobs near the water early, fine spray later and higher; a ring grows
    fade = (a * (1.0 / life)).min(1.0)
    if ring:
        rs = (a * 2.0 + 0.3) * size
        scl = g.nodes.new("ShaderNodeCombineXYZ")
        g.links.new(rs.s, scl.inputs["X"])
        g.links.new(rs.s, scl.inputs["Y"])
        scl.inputs["Z"].default_value = 1.0
        g.links.new(scl.outputs[0], inst.inputs["Scale"])
    else:
        sz = rnd(8, 0.4, 1.0) * size * (1.0 + a * 0.8)
        g.links.new(sz.s, inst.inputs["Scale"])
    rotr = g.nodes.new("FunctionNodeRandomValue")
    rotr.data_type = "FLOAT_VECTOR"
    rotr.inputs["Min"].default_value = (-tumble, -tumble, 0.0)
    rotr.inputs["Max"].default_value = (tumble, tumble, 6.28)
    g.links.new(idx.outputs[0], rotr.inputs["ID"])
    if not ring:
        g.links.new(rotr.outputs[0], inst.inputs["Rotation"])
    store = g.nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type = "FLOAT"
    store.domain = "INSTANCE"
    store.inputs["Name"].default_value = "fade"
    g.links.new(inst.outputs[0], store.inputs["Geometry"])
    vin = [i for i in store.inputs if i.name == "Value"][0]
    g.links.new(fade.s, vin)
    g.links.new(store.outputs[0], go.inputs[0])
    return g


# ----------------------------------------------------------------- model
class Model:
    def __init__(self, sheet=None):
        self.sheet = sheet or {}
        self.sc = bpy.context.scene
        self.movers = []            # (object, modifier, socket ids)
        self.segments = []          # main-span deck segments: (object, x0, x1)

    def clear(self):
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)

    # -- parts
    def materials(self):
        self.m_paint = bridge_paint("tower_paint")
        self.m_deck_paint = bridge_paint("deck_paint")
        self.m_rope = wire_rope("wire_rope")
        self.m_road = roadway("roadway")
        self.m_conc = look.concrete("concrete", (0.52, 0.50, 0.46))
        self.m_dark = plain("dark_steel", (0.08, 0.08, 0.08), 0.5, 0.6)
        self.m_glass = plain("lamp_glass", (0.85, 0.85, 0.75), 0.2)
        self.m_sea = sea("sea")
        self.m_forest = forest("forest")
        self.m_ground = look.ground("bluff", (0.10, 0.09, 0.06), (0.06, 0.07, 0.04))

    def towers(self):
        for tx in (-HALF, HALF):
            mb = MeshBuilder()
            base = 18.0
            for gy in (-GIRDER_Y, GIRDER_Y):
                # each leg: a cellular column of riveted plate, tapering, with a cap
                lw0, lw1 = 9.0, 6.5
                mb.beam((tx, gy, base), (tx, gy, TOWER_TOP - 4), lw0, lw0 * 1.3, 0, 1.0, up_hint=(1, 0, 0))
                # vertical stiffening ribs up each face
                for sx in (-1, 1):
                    mb.beam((tx + sx * lw0 * 0.66, gy, base), (tx + sx * lw1 * 0.66, gy, TOWER_TOP - 6), 0.8, 2.2,
                            0, 1.0, up_hint=(0, 1, 0))
                mb.box(tx - 7.5, tx + 7.5, gy - 6, gy + 6, TOWER_TOP - 4, TOWER_TOP, 0)       # cap
                # the saddle the cable rests in
                mb.box(tx - 6, tx + 6, gy - 2.2, gy + 2.2, TOWER_TOP, TOWER_TOP + 3.5, 1)
            # as in the 1940 film: no diagonal bracing; solid plate struts between
            # the legs: a deep one at the top, one at about two-thirds height,
            # one under the deck. Each strut is a riveted panel with a rim.
            for z0, z1 in ((TOWER_TOP - 30.0, TOWER_TOP - 6.0), (318.0, 336.0), (G_BOT - 14.0, G_BOT - 4.0)):
                mb.box(tx - 2.2, tx + 2.2, -GIRDER_Y + 4.0, GIRDER_Y - 4.0, z0, z1, 0)
                for zz in (z0, z1 - 1.2):
                    mb.box(tx - 3.0, tx + 3.0, -GIRDER_Y + 4.0, GIRDER_Y - 4.0, zz, zz + 1.2, 0)
            o = mb.build(f"tower_{'w' if tx < 0 else 'e'}", [self.m_paint, self.m_dark], bevel=0.25)
            # the pier: a concrete caisson out of the water with a fender-shaped nose
            pm = MeshBuilder()
            pm.box(tx - 30, tx + 30, -GIRDER_Y - 26, GIRDER_Y + 26, -40, base, 0)
            pm.box(tx - 18, tx + 18, -GIRDER_Y - 14, GIRDER_Y + 14, base - 2, base + 1, 0)
            pm.build(f"pier_{'w' if tx < 0 else 'e'}", [self.m_conc], bevel=0.6)

    def cables(self):
        n = 400
        for gy in (-GIRDER_Y, GIRDER_Y):
            mb = MeshBuilder()
            xs = [-ANCHOR_X + 2 * ANCHOR_X * i / n for i in range(n + 1)]
            mb.tube([(x, gy, cable_z(x)) for x in xs], CABLE_R, n=14, mi=0, rigid=0.0)
            # cable bands with bolts at every hanger
            x = -ANCHOR_X + HANGER_DX
            while x < ANCHOR_X - 1:
                if abs(abs(x) - HALF) > 10:
                    z = cable_z(x)
                    mb.cylinder((x, gy, z), CABLE_R * 1.18, 2.0, axis="x", n=14, mi=2, rigid=0.0)
                    for bz in (-1, 1):
                        mb.box(x - 0.7, x + 0.7, gy - CABLE_R * 1.5, gy + CABLE_R * 1.5,
                               z + bz * CABLE_R * 1.05 - 0.08, z + bz * CABLE_R * 1.05 + 0.08, 1, 0.0)
                x += HANGER_DX
            o = mb.build(f"cable_{'n' if gy > 0 else 's'}", [self.m_rope, self.m_dark, self.m_paint], smooth=True)
            self.movers.append((o,) + add_motion(o))

    def anchorages(self):
        for sx in (-1, 1):
            ax = sx * ANCHOR_X
            mb = MeshBuilder()
            mb.box(ax - (0 if sx > 0 else 90), ax + (90 if sx > 0 else 0), -GIRDER_Y - 25, GIRDER_Y + 25,
                   60, ANCHOR_Z + 12, 0)
            mb.build(f"anchorage_{sx}", [self.m_conc], bevel=0.8)

    def _deck_piece(self, mb, x0, x1, hangers=True):
        """The deck from x0 to x1 into a MeshBuilder: girders with
        stiffeners, floor beams, bracing, road slab, sidewalks, railings,
        lamp posts and the hangers above it."""
        # plate girders: web, top and bottom flanges
        for gy in (-GIRDER_Y, GIRDER_Y):
            mb.box(x0, x1, gy - 0.25, gy + 0.25, G_BOT, G_TOP, 0)
            for fz in (G_BOT, G_TOP - 0.6):
                mb.box(x0, x1, gy - 1.2, gy + 1.2, fz, fz + 0.6, 0)
            # vertical stiffeners every 10 ft, both faces
            x = math.ceil(x0 / 10.0) * 10.0
            while x < x1:
                for sy in (-1, 1):
                    mb.box(x - 0.25, x + 0.25, gy + sy * 0.25, gy + sy * 0.95, G_BOT + 0.6, G_TOP - 0.6, 0)
                x += 10.0
        # floor beams under the slab every 20 ft, X bracing between the bottom flanges
        x = math.ceil(x0 / 20.0) * 20.0
        while x < x1:
            mb.box(x - 0.6, x + 0.6, -GIRDER_Y, GIRDER_Y, ROAD_Z - 5.0, ROAD_Z - 0.8, 0)
            if x + 20 <= x1 + 1e-6:
                for a in (-1, 1):
                    mb.beam((x, a * (GIRDER_Y - 1), G_BOT + 0.4), (x + 20, -a * (GIRDER_Y - 1), G_BOT + 0.4),
                            0.6, 0.6, 0, 1.0)
            x += 20.0
        # the slab: two 13 ft lanes; sidewalks 5 ft each side, a little higher
        mb.box(x0, x1, -13.0, 13.0, ROAD_Z - 0.8, ROAD_Z, 2)
        for sy in (-1, 1):
            y0, y1 = sorted((sy * 13.0, sy * (GIRDER_Y - 1.3)))
            mb.box(x0, x1, y0, y1, ROAD_Z - 0.8, ROAD_Z + 0.6, 3)
            # curb face
            mb.box(x0, x1, sy * 13.0 - 0.3, sy * 13.0 + 0.3, ROAD_Z, ROAD_Z + 0.75, 3)
        # railings on top of the girders: posts every 8 ft, two rails
        for gy in (-GIRDER_Y, GIRDER_Y):
            x = math.ceil(x0 / 8.0) * 8.0
            while x < x1:
                mb.box(x - 0.15, x + 0.15, gy - 0.15, gy + 0.15, G_TOP, G_TOP + 3.4, 0)
                x += 8.0
            for rz in (G_TOP + 1.7, G_TOP + 3.4):
                mb.box(x0, x1, gy - 0.18, gy + 0.18, rz - 0.18, rz + 0.18, 0)
        # lamp posts every 150 ft, alternating sides, arm over the road
        x = math.ceil((x0 + 75) / 150.0) * 150.0 - 75
        while x < x1:
            sy = 1 if int(round((x + 75) / 150.0)) % 2 else -1
            gy = sy * (GIRDER_Y - 1.6)
            mb.tube([(x, gy, ROAD_Z + 0.6), (x, gy, ROAD_Z + 22), (x, gy - sy * 4.5, ROAD_Z + 23.5)], 0.32, 8, 1, 1.0)
            mb.box(x - 0.8, x + 0.8, gy - sy * 5.6 - 0.8, gy - sy * 5.6 + 0.8, ROAD_Z + 22.4, ROAD_Z + 23.6, 4)
            x += 150.0
        if not hangers:
            return
        # hangers: a pair of ropes from each cable band down to the girder
        x = math.ceil(x0 / HANGER_DX) * HANGER_DX
        while x < x1:
            if abs(abs(x) - HALF) > 10 and abs(x) < ANCHOR_X - 1:
                for gy in (-GIRDER_Y, GIRDER_Y):
                    top = cable_z(x) - CABLE_R
                    for dx in (-0.45, 0.45):
                        n = max(2, int((top - G_TOP) / 12) + 1)
                        pts = [(x + dx, gy, G_TOP + (top - G_TOP) * i / n) for i in range(n + 1)]
                        mb.tube(pts, 0.11, 6, 5, 0.0, caps=False)
                    # the socket where the ropes meet the girder
                    mb.box(x - 0.8, x + 0.8, gy - 0.6, gy + 0.6, G_TOP, G_TOP + 1.2, 1)
            x += HANGER_DX

    def deck(self):
        mats = [self.m_deck_paint, self.m_dark, self.m_road, self.m_conc, self.m_glass, self.m_rope]
        # the main span in 50 ft segments (they can part and fall one by one)
        nseg = int(2 * HALF / 50.0)
        for i in range(nseg):
            x0 = -HALF + 50.0 * i
            x1 = x0 + 50.0
            mb = MeshBuilder()
            self._deck_piece(mb, x0, x1)
            cx = (x0 + x1) / 2
            mb.v = [(vx - cx, vy, vz - AXIS_Z) for vx, vy, vz in mb.v]   # origin at the segment's middle
            o = mb.build(f"deck_{i:02d}", mats, bevel=0.0)
            o.location = (cx, 0, AXIS_Z)
            self.movers.append((o,) + add_motion(o, (cx, 0, AXIS_Z)))
            self.segments.append((o, x0, x1))
        # the side spans, one piece each, and the approaches onto the bluffs
        for sx in (-1, 1):
            mb = MeshBuilder()
            a, b_ = sorted((sx * HALF, sx * ANCHOR_X))
            self._deck_piece(mb, a, b_)
            a2, b2 = sorted((sx * ANCHOR_X, sx * (ANCHOR_X + 900)))
            self._deck_piece(mb, a2, b2, hangers=False)
            o = mb.build(f"side_{'w' if sx < 0 else 'e'}", mats)
            self.movers.append((o,) + add_motion(o))

    def world(self):
        sc = self.sc
        # water
        bpy.ops.mesh.primitive_plane_add(size=60000, location=(0, 0, 0))
        w = bpy.context.object
        w.name = "narrows"
        w.data.materials.append(self.m_sea)
        # bluffs: steep from the shore line to about 300 ft, then rolling
        n, ext = 220, 16000.0
        verts, faces = [], []
        for i in range(n + 1):
            for j in range(n + 1):
                u = -ext + 2 * ext * i / n          # x, across the water
                v = -ext + 2 * ext * j / n          # y, along the Narrows
                shore = SHORE_X + 160 * math.sin(v / 1300.0) + 90 * math.sin(v / 470.0 + (1 if u > 0 else 0))
                d = abs(u) - shore
                if d < 0:
                    h = -30.0 + d * 0.05
                else:
                    t = min(1.0, d / 700.0)
                    h = 290.0 * (1 - (1 - t) ** 2.2) + 60.0 * max(0.0, (d - 700) / 3000.0)
                    h += 28 * math.sin(v / 380.0 + u / 900.0) * t + 14 * math.sin(v / 140.0 + u / 260.0) * t
                verts.append((u, v, h))
        for i in range(n):
            for j in range(n):
                a = i * (n + 1) + j
                faces.append((a, a + n + 1, a + n + 2, a + 1))
        me = bpy.data.meshes.new("bluffs")
        me.from_pydata(verts, [], faces)
        me.update()
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(self.m_ground)
        land = bpy.data.objects.new("bluffs", me)
        sc.collection.objects.link(land)
        self.forest(land)
        # sky: November overcast, low and even, brighter toward the south
        world = sc.world or bpy.data.worlds.new("world")
        sc.world = world
        world.use_nodes = True
        nt = world.node_tree
        bg = nt.nodes["Background"]
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        grad = nt.nodes.new("ShaderNodeValToRGB")
        grad.color_ramp.elements[0].position = 0.0
        grad.color_ramp.elements[0].color = (0.50, 0.53, 0.56, 1)
        grad.color_ramp.elements[1].position = 0.45
        grad.color_ramp.elements[1].color = (0.30, 0.33, 0.37, 1)
        nt.links.new(sep.outputs["Z"], grad.inputs["Fac"])
        cl = nt.nodes.new("ShaderNodeTexNoise")
        cl.inputs["Scale"].default_value = 2.2
        cl.inputs["Detail"].default_value = 12.0
        cl.inputs["Roughness"].default_value = 0.62
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0, 1.0, 3.5)
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], cl.inputs["Vector"])
        cr = nt.nodes.new("ShaderNodeMapRange")
        cr.inputs["From Min"].default_value = 0.35
        cr.inputs["From Max"].default_value = 0.75
        cr.inputs["To Min"].default_value = 0.7
        cr.inputs["To Max"].default_value = 1.25
        nt.links.new(cl.outputs["Fac"], cr.inputs["Value"])
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "SCALE"
        nt.links.new(grad.outputs["Color"], mul.inputs[0])
        nt.links.new(cr.outputs["Result"], mul.inputs["Scale"])
        nt.links.new(mul.outputs[0], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 1.0
        # the sun behind the cloud: a soft key from the south-east, low (11 am, 7 November)
        bpy.ops.object.light_add(type="SUN", location=(0, 0, 1000))
        sun = bpy.context.object
        sun.data.energy = 1.4
        sun.data.angle = math.radians(25)              # overcast: wide, soft shadows
        sun.data.color = (0.95, 0.96, 1.0)
        sun.rotation_euler = (math.radians(62), 0, math.radians(150))

    def forest(self, land):
        """Fir trees scattered over the bluffs (geometry nodes: points on the
        slopes above the shore, a cone of foliage instanced on each)."""
        cone = fir_mesh("fir", self.m_forest)
        g = bpy.data.node_groups.new("firs", "GeometryNodeTree")
        g.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        g.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        gi, go = g.nodes.new("NodeGroupInput"), g.nodes.new("NodeGroupOutput")
        # keep only the land above the waterline and within reach of the cameras
        pos = g.nodes.new("GeometryNodeInputPosition")
        sep = g.nodes.new("ShaderNodeSeparateXYZ")
        g.links.new(pos.outputs[0], sep.inputs[0])
        E = lambda s: _E(g, s)
        far = (E(sep.outputs["Y"]).abs().lt(9000.0)) * (E(sep.outputs["X"]).abs().lt(9000.0))
        dens = E(sep.outputs["Z"]).lt(12.0)               # 1 under the shore line
        keep = far * (1.0 - dens)
        dist = g.nodes.new("GeometryNodeDistributePointsOnFaces")
        dist.distribute_method = "RANDOM"
        g.links.new(gi.outputs[0], dist.inputs["Mesh"])
        dm = (keep * 0.0016).s
        g.links.new(dm, dist.inputs["Density"])
        dist.inputs["Seed"].default_value = 7
        inst = g.nodes.new("GeometryNodeInstanceOnPoints")
        g.links.new(dist.outputs["Points"], inst.inputs["Points"])
        oi = g.nodes.new("GeometryNodeObjectInfo")
        oi.inputs["Object"].default_value = cone
        g.links.new(oi.outputs["Geometry"], inst.inputs["Instance"])
        # size: 60 to 150 ft tall, about a third as wide
        rv = g.nodes.new("FunctionNodeRandomValue")
        rv.data_type = "FLOAT"
        rv.inputs["Min"].default_value = 60.0
        rv.inputs["Max"].default_value = 150.0
        h = E(rv.outputs[0])
        sc_ = g.nodes.new("ShaderNodeCombineXYZ")
        g.links.new((h * 0.6).s, sc_.inputs["X"])
        g.links.new((h * 0.6).s, sc_.inputs["Y"])
        g.links.new(h.s, sc_.inputs["Z"])
        g.links.new(sc_.outputs[0], inst.inputs["Scale"])
        # the cone's origin is its middle: lift it by half its height
        tr = g.nodes.new("GeometryNodeTranslateInstances")
        g.links.new(inst.outputs[0], tr.inputs["Instances"])
        off = g.nodes.new("ShaderNodeCombineXYZ")
        off.inputs["Z"].default_value = -2.0
        g.links.new(off.outputs[0], tr.inputs["Translation"])
        tr.inputs["Local Space"].default_value = False
        rot = g.nodes.new("GeometryNodeRotateInstances")
        g.links.new(tr.outputs[0], rot.inputs["Instances"])
        rr = g.nodes.new("FunctionNodeRandomValue")
        rr.data_type = "FLOAT_VECTOR"
        rr.inputs["Min"].default_value = (-0.06, -0.06, 0.0)
        rr.inputs["Max"].default_value = (0.06, 0.06, 6.28)
        rr.inputs["Seed"].default_value = 3
        g.links.new(rr.outputs[0], rot.inputs["Rotation"])
        join = g.nodes.new("GeometryNodeJoinGeometry")
        g.links.new(rot.outputs[0], join.inputs[0])
        g.links.new(gi.outputs[0], join.inputs[0])
        g.links.new(join.outputs[0], go.inputs[0])
        mod = land.modifiers.new("firs", "NODES")
        mod.node_group = g
        cone.hide_render = True
        cone.hide_viewport = True

    def build(self):
        self.clear()
        self.materials()
        self.towers()
        self.cables()
        self.anchorages()
        self.deck()
        self.world()

    # -- motion
    def key_motion(self, frames, twist_of, heave_of, waves=1.0):
        """Key every mover's twist and heave for each frame (radians, feet)."""
        for o, mod, ids in self.movers:
            set_input(o, mod, ids["Waves"], waves)
            for f in frames:
                set_input(o, mod, ids["Twist"], twist_of(f), f)
                set_input(o, mod, ids["Heave"], heave_of(f), f)

    def place_vehicles(self, frames, twist_of, heave_of, waves=1.0, car_x=-560.0, truck_x=-610.0):
        """The two vehicles of 7 November, as the 1940 film shows them:
        Coatsworth's pale sedan stopped against the curb, and beside it, in
        the other lane, the Rapid Transfer Company's delivery truck lying on
        its side. Both ride the deck (keyed each frame with its roll and
        rise where they stand); collapse() carries them down with the piece
        they stand on."""
        car = sedan_1930s("car")
        truck = delivery_truck_1930s("truck")
        # (object, x, y, height of its origin over the road, its own turn)
        self.riders = [(car, car_x, -9.5, 0.0, (0.0, 0.0, 0.0)),
                       (truck, truck_x, 4.0, 3.4, (math.radians(-88), 0.0, math.radians(-12)))]
        for o, x, y, h, rot in self.riders:
            o.rotation_mode = "XYZ"
            for f in frames:
                ny, nz, th = deck_transform(x, y, ROAD_Z + h, twist_of(f), heave_of(f), waves)
                o.location = (x, ny, nz)
                o.rotation_euler = (th + rot[0], rot[1], rot[2])
                o.keyframe_insert("location", frame=f)
                o.keyframe_insert("rotation_euler", frame=f)
        self.car, self.truck = car, truck
        return car, truck

    def collapse(self, stages, twist_of, heave_of, end_frame, fps=FPS, seed=5, frame_of=None):
        """The main span tears away and falls. stages: [(x0, x1, t_start,
        t_spread, piece_ft)], model seconds: the deck between x0 and x1
        parts into pieces about piece_ft long, the middle piece first and
        the others outward over t_spread seconds.

        A piece keeps the twisted shape it had at that instant (one rigid
        ribbon). It first swings down about the edge still holding (the
        hinge), lets go, and falls freely under gravity with the spin it
        had, about 3.5 s from 195 ft. Where each 50 ft of it meets the water
        is written down for the splashes."""
        from mathutils import Matrix
        rnd = random.Random(seed)
        self.hits = []
        self.breaks = []
        movers = {o.name: (mod, ids) for o, mod, ids in self.movers}
        segs = sorted(self.segments, key=lambda t: t[1])
        riders = list(getattr(self, "riders", []))
        last_break = 0.0
        for stage in stages:
            x0, x1, t0, spread, piece_ft = stage[:5]
            hang = stage[5] if len(stage) > 5 else False
            inside = [sg for sg in segs if x0 <= (sg[1] + sg[2]) / 2 <= x1]
            # cut into pieces of varied length (whole segments)
            pieces, i = [], 0
            per = max(1, int(round(piece_ft / 50.0)))
            while i < len(inside):
                n = max(1, per + rnd.choice((-1, 0, 0, 1)))
                pieces.append(inside[i:i + n])
                i += n
            mid = (x0 + x1) / 2
            half = max(1.0, (x1 - x0) / 2)
            for pc in pieces:
                px0, px1 = pc[0][1], pc[-1][2]
                pcx = (px0 + px1) / 2
                tb = t0 + spread * abs(pcx - mid) / half + rnd.uniform(0.0, 0.25)
                fb = frame_of(tb) if frame_of else int(round(tb * fps)) + 1
                tb_real = (fb - 1) / fps                # seconds on the render's own clock
                # it hinges on the edge toward the nearer tower (still attached)
                pivot_x = px0 if pcx < 0 else px1
                side = -1 if pcx < 0 else 1           # the free end is toward the middle
                # the last piece by a tower may stay hanging from it (the film: a
                # stub of deck hung down from the tower into the water)
                hangs = hang and abs(abs(pivot_x) - HALF) < 1.0
                last_break = max(last_break, tb_real)
                if abs(pcx - mid) < 60:
                    pivot_x, side = None, 0          # the first piece drops nearly flat
                tw, hv = twist_of(fb), heave_of(fb)
                th_rate = (twist_of(fb + 1) - tw) * fps * twist_mode(pcx)
                for ex in (px0, px1):                     # both torn ends shed debris
                    self.breaks.append(((ex, 0.0, AXIS_Z), tb_real + 1.0 / fps, 40.0))
                t_h = rnd.uniform(0.45, 0.8)
                phi_h = math.radians(rnd.uniform(20, 38)) * (1 if side else 0)
                w_h = 2 * phi_h / t_h                 # its swing rate at release
                rnd_cap = rnd.uniform(38, 62)
                vy = rnd.uniform(-3, 3) + 4.0         # pushed north by the wind
                yaw_r = math.radians(rnd.uniform(-6, 6))
                P = Vector((pivot_x if pivot_x is not None else pcx, 0.0, AXIS_Z))
                done = set()

                def pose(tau):
                    """(rotation matrix, translation) of the piece at tau s after the break."""
                    if hangs:
                        # swings down on its hinge and settles, rocking, about 70 degrees down
                        cap = math.radians(70)
                        phi = cap * (1 - math.exp(-tau / 0.7) * math.cos(2.2 * tau))
                        return Matrix.Rotation(-side * phi, 4, "Y"), Vector((0, 0, 0)), phi
                    if tau <= t_h or not side:
                        phi = phi_h * (tau / t_h) ** 2 if side else 0.0
                        R = Matrix.Rotation(-side * phi, 4, "Y") if side else Matrix.Identity(4)
                        roll = th_rate * 0.5 * tau
                        drop = 0.0 if side else 0.5 * G * tau * tau
                        T = Vector((0, vy * tau * 0.3, -drop))
                        return Matrix.Rotation(roll, 4, "X") @ R, T, phi
                    u = tau - t_h
                    # the swing carries on but slows (air, and the torn end's drag): it
                    # falls tilted, not standing on end
                    cap = math.radians(rnd_cap)
                    phi = phi_h + (cap - phi_h) * (1 - math.exp(-w_h * u / max(1e-3, cap - phi_h)))
                    R = Matrix.Rotation(-side * phi, 4, "Y")
                    roll = th_rate * 0.5 * tau
                    # the centre of the piece at release, then free flight
                    T = Vector((0, vy * (t_h * 0.3 + u), -0.5 * G * u * u))
                    return Matrix.Rotation(roll, 4, "X") @ R @ Matrix.Rotation(yaw_r * u, 4, "Z"), T, phi

                for o, sx0, sx1 in pc:
                    mod, ids = movers[o.name]
                    o.rotation_mode = "XYZ"
                    o.keyframe_insert("location", frame=fb - 1)
                    o.keyframe_insert("rotation_euler", frame=fb - 1)
                    o.hide_render = False
                    o.keyframe_insert("hide_render", frame=fb - 1)
                hit_t, hit_z, sunk = {}, {}, {}
                # vehicles standing on this piece go with it
                on = []
                for r in list(riders):            # a copy: riders are taken off it as they board
                    o_, x_, y_, h_, rot_ = r
                    if px0 <= x_ <= px1:
                        ny_, nz_, th_ = deck_transform(x_, y_, ROAD_Z + h_, tw, hv, 1.0)
                        rest = Vector((x_, ny_, nz_))
                        base = Euler((th_ + rot_[0], rot_[1], rot_[2]), "XYZ").to_matrix()
                        on.append((o_, rest, base))
                        riders.remove(r)
                        # visible until it goes under (one "hidden" key alone would
                        # hide it on every frame)
                        o_.hide_render = False
                        o_.keyframe_insert("hide_render", frame=max(1, fb - 1))
                self.hanger_stubs(pc, fb, rnd)
                for f in range(fb, end_frame + 1):
                    tau = (f - fb) / fps
                    R, T, _ = pose(tau)
                    for o, sx0, sx1 in pc:
                        if o.name in sunk:
                            continue
                        mod, ids = movers[o.name]
                        set_input(o, mod, ids["Twist"], tw, f)
                        set_input(o, mod, ids["Heave"], hv, f)
                        set_input(o, mod, ids["Snap"], min(1.0, tau / 0.8), f)
                        c = Vector(((sx0 + sx1) / 2, 0.0, AXIS_Z))
                        loc = P + (R @ (c - P)) + T
                        # in the water: it slows, settles and goes under
                        if o.name in hit_t:
                            u = tau - hit_t[o.name]
                            loc.z = hit_z[o.name] - 16 * (1 - math.exp(-u / 0.45)) - 5 * u
                        elif loc.z < 6.0:
                            hit_t[o.name] = tau
                            hit_z[o.name] = loc.z
                            self.hits.append(((loc.x, loc.y, 0.0), tb_real + tau + 1.0 / fps, sx1 - sx0))
                        o.location = loc
                        o.rotation_euler = R.to_euler("XYZ")
                        o.keyframe_insert("location", frame=f)
                        o.keyframe_insert("rotation_euler", frame=f)
                        if loc.z < -50:
                            sunk[o.name] = True
                            o.hide_render = True
                            o.keyframe_insert("hide_render", frame=f)
                    for o_, rest, base in on:
                        if o_.name in sunk:
                            continue
                        loc = P + (R @ (rest - P)) + T
                        if o_.name in hit_t:
                            u = tau - hit_t[o_.name]
                            loc.z = hit_z[o_.name] - 10 * (1 - math.exp(-u / 0.4)) - 4 * u
                        elif loc.z < 4.0:
                            hit_t[o_.name], hit_z[o_.name] = tau, loc.z
                            self.hits.append(((loc.x, loc.y, 0.0), tb_real + tau + 1.0 / fps, 18.0))
                        o_.location = loc
                        o_.rotation_euler = (R.to_3x3() @ base).to_euler("XYZ")
                        o_.keyframe_insert("location", frame=f)
                        o_.keyframe_insert("rotation_euler", frame=f)
                        if loc.z < -30:
                            sunk[o_.name] = True
                            for oo in [o_] + list(o_.children):
                                oo.hide_render = False
                                oo.keyframe_insert("hide_render", frame=max(1, fb - 1))
                                oo.hide_render = True
                                oo.keyframe_insert("hide_render", frame=f)
                    if len(sunk) == len(pc) + len(on) or (hangs and tau > 6.0):
                        break
        self.side_sag(last_break + 0.6, end_frame, fps)
        self.debris()
        self.splashes()

    def side_sag(self, t0, end_frame, fps=FPS, depth=28.0):
        """After the main span is gone the side spans drop and settle,
        rocking (the film's last shots: the side span sagging in a curve)."""
        f0 = int(round(t0 * fps)) + 1
        for o, mod, ids in self.movers:
            if not (o.name.startswith("side_") or o.name.startswith("cable_")):
                continue
            set_input(o, mod, ids["SideSag"], 0.0, f0 - 1)
            for f in range(f0, end_frame + 1, 2):
                u = (f - f0) / fps
                v = depth * (1 - math.exp(-u / 1.2) * math.cos(1.6 * u))
                set_input(o, mod, ids["SideSag"], v, f)

    def hanger_stubs(self, piece, f_show, rnd):
        """Where a piece tore away, the snapped hangers hang from the cable,
        a few feet to sixty feet long, some bent (the film's aftermath)."""
        mb = MeshBuilder()
        x0, x1 = piece[0][1], piece[-1][2]
        x = math.ceil(x0 / HANGER_DX) * HANGER_DX
        while x < x1:
            for gy in (-GIRDER_Y, GIRDER_Y):
                if rnd.random() < 0.8:
                    top = cable_z(x) - CABLE_R
                    ln = rnd.uniform(5, 60)
                    kink = Vector((rnd.uniform(-3, 3), rnd.uniform(-6, 6), 0))
                    pts = [Vector((x, gy, top)), Vector((x, gy, top - ln * 0.6)) + kink * 0.4,
                           Vector((x, gy, top - ln)) + kink]
                    mb.tube(pts, 0.12, 6, 0, 1.0, caps=True)
            x += HANGER_DX
        if not mb.v:
            return
        o = mb.build(f"stubs_{piece[0][0].name}", [self.m_rope])
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=1)
        o.keyframe_insert("hide_render", frame=max(1, f_show - 1))
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=f_show)

    def debris(self):
        """Concrete and steel shed from the torn ends as each piece lets go:
        chunks thrown a little outward, then falling under gravity."""
        if not getattr(self, "breaks", None):
            return
        me = bpy.data.meshes.new("breaks")
        me.from_pydata([b[0] for b in self.breaks], [], [])
        me.update()
        a = me.attributes.new("t_hit", "FLOAT", "POINT")
        a.data.foreach_set("value", [b[1] for b in self.breaks])
        w = me.attributes.new("width", "FLOAT", "POINT")
        w.data.foreach_set("value", [b[2] for b in self.breaks])
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, -9000))
        chunk = bpy.context.object
        chunk.name = "chunk"
        for v in chunk.data.vertices:          # an irregular lump, not a cube
            v.co.x *= 1.0 + 0.6 * (v.co.y > 0)
            v.co.z *= 0.6
        chunk.data.materials.append(self.m_conc)
        chunk.hide_render = True
        grp = splash_group("debris", 120, 22.0, 1.0, 0.15, 6.0, 0.9, rise=0.5)
        o = bpy.data.objects.new("debris", me)
        self.sc.collection.objects.link(o)
        mod = o.modifiers.new("debris", "NODES")
        mod.node_group = grp
        ident = [it.identifier for it in grp.interface.items_tree
                 if getattr(it, "in_out", None) == "INPUT" and it.name == "Drop"][0]
        set_input(o, mod, ident, chunk)

    def splashes(self):
        """One vertex per hit, carrying its time and width, fed to three
        layers: heavy sheets of water, fine spray that hangs and drifts,
        and a ring of foam spreading on the surface."""
        if not self.hits:
            return
        me = bpy.data.meshes.new("hits")
        me.from_pydata([h[0] for h in self.hits], [], [])
        me.update()
        a = me.attributes.new("t_hit", "FLOAT", "POINT")
        a.data.foreach_set("value", [h[1] for h in self.hits])
        w = me.attributes.new("width", "FLOAT", "POINT")
        w.data.foreach_set("value", [h[2] for h in self.hits])
        drop_mat = spray_material("spray")
        mist_mat = spray_material("mist", (0.86, 0.88, 0.89), 0.4)
        foam_mat = spray_material("foam", (0.75, 0.78, 0.78), 0.9)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0, location=(0, 0, -9000))
        drop = bpy.context.object
        for v in drop.data.vertices:
            v.co.z *= 2.4                     # a streak of water, not a ball
        drop.name = "drop"
        drop.data.materials.append(drop_mat)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=(0, 0, -9000))
        puff = bpy.context.object
        puff.name = "puff"
        puff.data.materials.append(mist_mat)
        bpy.ops.mesh.primitive_circle_add(vertices=24, radius=1.0, fill_type="NGON", location=(0, 0, -9000))
        disc = bpy.context.object
        disc.name = "foam_disc"
        disc.data.materials.append(foam_mat)
        for o in (drop, puff, disc):
            o.hide_render = True
        layers = (
            ("sheets", splash_group("sheets", 900, 195.0, 0.55, 0.6, 5.0, 0.95, tumble=0.8, drift=6.0), drop),
            # the film: a white cloud that rolls up past the deck and drifts off downwind
            ("spray", splash_group("spray", 380, 170.0, 0.9, 1.2, 10.0, 7.5, 1.0, gravity=0.07, drift=14.0), puff),
            ("foam", splash_group("foam", 1, 0.0, 0.0, 1.0, 14.0, 22.0, 0.0, ring=True, gravity=0.0), disc),
        )
        for name, grp, inst in layers:
            o = bpy.data.objects.new(f"splash_{name}", me if name == "sheets" else me.copy())
            self.sc.collection.objects.link(o)
            if name == "foam":
                o.location.z = 0.4
            mod = o.modifiers.new(name, "NODES")
            mod.node_group = grp
            ident = [it.identifier for it in grp.interface.items_tree
                     if getattr(it, "in_out", None) == "INPUT" and it.name == "Drop"][0]
            set_input(o, mod, ident, inst)

    def camera(self, loc, look_at, lens=35.0):
        cam = self.sc.camera
        if cam is None:
            bpy.ops.object.camera_add()
            cam = bpy.context.object
            self.sc.camera = cam
        cam.location = loc
        d = Vector(look_at) - Vector(loc)
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        cam.data.clip_start = 0.5
        cam.data.clip_end = 60000
        return cam


def setup_render(sc, samples=32, size=(1280, 720)):
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.fps = FPS
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    # layered spray and mist: enough transparent bounces that stacked drops
    # never run out and render black
    sc.cycles.transparent_max_bounces = 24
    sc.render.use_persistent_data = True
    sc.render.image_settings.file_format = "PNG"
    views = [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = "AgX" if "AgX" in views else "Filmic"
    look.finish(sc, motion_blur=False)


# ======================================================================
# The episode: one canonical timeline (kits/timemap.py, variant "flutter")
# ======================================================================
#
#     establish   0-7     the bridge in service, its deck rising and falling
#                         in waves ("Galloping Gertie"): from the water, then
#                         along the road
#     load_path   7-13    the solid plate girder, close, and under the deck
#     connection  13-20   7 November 1940: the twist begins and grows; on the
#                         road behind the abandoned car and truck, then from
#                         the Tacoma shore, where the film was shot
#     pull, hold  20-22   the twist at its worst, from under the deck
#     drop        22-70   the collapse, the centrepiece, in shots of 4 s from
#                         a dozen angles: the hangers let go, the middle of the
#                         span falls, the splash; the rest goes, car and truck
#                         with it; a stub hangs from the tower; the side spans
#                         sag; snapped hangers; the empty span
#
# The motion runs on the canonical clock (the twist at its true 0.2 Hz); the
# fall on the render's own clock (real gravity, whatever the time map).

T_WAVES_END = 13.0            # the waves of the summer give way to the twist
T_TWIST_FULL = 21.0           # the twist at its worst
T_BREAK1 = 26.0               # the middle of the main span lets go
T_BREAK2 = 43.0               # the rest of it (seven minutes later in fact; told across a cut)
TWIST_MAX = math.radians(28)  # the roll at the quarter points


def frame_of(sec):
    from kits import timemap
    return timemap.CURRENT.frame(sec)


def canon_of_frame(f):
    from kits import timemap
    return timemap.CURRENT.canon((f - 1) / FPS)


def _twist_amp(t):
    """The roll amplitude (radians) at canonical second t: none in the summer,
    growing from 7 November's first twisting to its worst."""
    if t < T_WAVES_END - 1.0:
        return 0.0
    grow = min(1.0, max(0.0, (t - (T_WAVES_END - 1.0)) / (T_TWIST_FULL - T_WAVES_END + 1.0)))
    return TWIST_MAX * (0.12 + 0.88 * grow ** 1.4)


def twist_at_frame(f):
    """The roll at frame f: its amplitude follows the story (canonical
    clock), its swing the real one (12 cycles a minute on the screen,
    however long the narration holds a shot)."""
    return _twist_amp(canon_of_frame(f)) * math.sin(2 * math.pi * 0.2 * (f - 1) / FPS)


def heave_at_frame(f):
    """The summer's waves (feet), fading as the twist takes over."""
    t = canon_of_frame(f)
    fade = 1.0 - min(1.0, max(0.0, (t - (T_WAVES_END - 2.0)) / 3.0))
    return 4.5 * fade * math.sin(2 * math.pi * 0.22 * (f - 1) / FPS)


def _cable_z_at(x):
    return cable_z(x)


# Camera angles for each part of the story: (from, to, look from, look to,
# lens). A part gets as many shots of about 4.6 s as its narration needs,
# taking these angles in turn (owner, 2026-11-09: no shot over about 8 s).
POOLS = {
    "establish": [   # the bridge in service, its deck rising and falling in waves
        ((1500, -2600, 50), (1350, -2450, 70), (-200, 0, 230), (-300, 0, 220), 30),
        ((-1100, 6, 203), (-980, 6, 204), (600, 0, 200), (700, 0, 200), 26),
        ((-2400, 2100, 820), (-2250, 1950, 780), (0, 0, 200), (100, 0, 200), 35),
        ((-1350, -70, 40), (-1340, -60, 60), (-1400, 0, 420), (-1250, 0, 360), 20),
        ((1900, -260, 300), (1860, -240, 296), (0, 0, 200), (-60, 0, 200), 40),
        ((-1405, -30, 440), (-1395, -30, 438), (0, 0, 200), (-100, 0, 200), 28),
    ],
    "load_path": [   # the solid girder
        ((-760, -48, 186), (-700, -44, 188), (-640, -19.5, 192), (-600, -19.5, 192), 30),
        ((-930, -8, 176), (-880, -8, 176), (-400, 0, 187), (-350, 0, 187), 22),
        ((-500, -170, 120), (-470, -160, 125), (-420, -19.5, 192), (-400, -19.5, 192), 35),
        ((-300, -17, 199.5), (-270, -17, 199.5), (200, -19, 198), (230, -19, 198), 30),
        ((-612, -42, 236), (-604, -40, 234), (-600, -19.5, 240), (-600, -19.5, 238), 40),
    ],
    "connection": [  # 7 November: the twist begins and grows
        ((-470, -14, 205), (-482, -14, 205), (-650, -4, 199), (-660, -4, 199), 30),
        ((1750, -650, 240), (1720, -630, 236), (-200, 0, 195), (-230, 0, 195), 48),
        ((-700, -600, 40), (-690, -590, 45), (-700, 0, 190), (-700, 0, 192), 32),
        ((-1380, 20, 250), (-1380, 20, 252), (-500, 0, 195), (-520, 0, 195), 30),
        ((-560, -90, 262), (-540, -84, 256), (-570, -2, 198), (-570, -2, 198), 30),
    ],
    "pull": [        # the twist at its worst
        ((-760, -150, 120), (-740, -150, 124), (-680, 0, 192), (-680, 0, 192), 20),
        ((1600, -560, 230), (1580, -545, 228), (-400, 0, 195), (-420, 0, 195), 50),
    ],
}

# the collapse: its own 48 s at a shot every 4 s (canonical seconds, kept 1:1)
DROP_SHOTS = [
    (22.0, 26.0, (-60, 10, 204), (-90, 10, 204), (250, 0, 205), (250, 0, 205), 28),       # the road at midspan
    (26.0, 30.0, (60, -60, 230), (50, -64, 232), (0, -19.5, 215), (0, -19.5, 205), 30),    # the hangers let go
    (30.0, 34.0, (-260, -430, 55), (-250, -420, 50), (-20, 0, 120), (-20, 0, 80), 22),     # the middle falls
    (34.0, 38.0, (-200, -760, 18), (-185, -740, 20), (0, 0, 60), (0, 0, 70), 26),         # the splash, at the water
    (38.0, 42.0, (-200, -1300, 380), (-150, -1260, 370), (-150, 0, 170), (-120, 0, 170), 36),   # the gap from above
    (42.0, 46.0, (-470, 10, 203), (-480, 10, 203), (-650, -4, 199), (-650, -4, 195), 30),   # the road west, car and truck
    (46.0, 50.0, (-1250, -700, 70), (-1240, -690, 72), (-650, 0, 130), (-650, 0, 100), 28),  # they go
    (50.0, 54.0, (-900, -900, 15), (-890, -890, 18), (-700, 0, 50), (-700, 0, 60), 24),     # the splash, west
    (54.0, 58.0, (-1300, -420, 140), (-1290, -410, 138), (-1330, 0, 150), (-1320, 0, 140), 24),   # the stub at the tower
    (58.0, 62.0, (-1750, -1400, 90), (-1730, -1370, 92), (-1950, 0, 175), (-1950, 0, 170), 32),   # the side span sags
    (62.0, 66.0, (-200, -120, 250), (-180, -110, 250), (0, -19.5, 230), (0, -19.5, 225), 32),     # snapped hangers
    (66.0, 70.0, (1400, -3200, 40), (1300, -3150, 45), (0, 0, 190), (0, 0, 190), 26),    # the empty span
]


def shot_list():
    """[(first frame, last frame, from, to, look from, look to, lens)] for
    the whole timeline under the current time map."""
    from kits import timemap
    tm = timemap.CURRENT
    out = []
    parts = [("establish", 0.0, 7.0), ("load_path", 7.0, 13.0), ("connection", 13.0, 20.0), ("pull", 20.0, 22.0)]
    for name, a, b in parts:
        ra, rb = tm.real(a), tm.real(b)
        n = max(1, int(round((rb - ra) / 4.6)))
        pool = POOLS[name]
        for i in range(n):
            s0, s1 = ra + (rb - ra) * i / n, ra + (rb - ra) * (i + 1) / n
            l0, l1, k0, k1, lens = pool[i % len(pool)]
            out.append((int(round(s0 * FPS)) + 1, int(round(s1 * FPS)), l0, l1, k0, k1, lens))
    for a, b, l0, l1, k0, k1, lens in DROP_SHOTS:
        out.append((tm.frame(a), tm.frame(b) - 1, l0, l1, k0, k1, lens))
    return out


def _cam_at_frame(shots, f):
    for fa, fb, l0, l1, k0, k1, lens in shots:
        if fa <= f <= fb:
            u = (f - fa) / max(1, fb - fa)
            return Vector(l0).lerp(Vector(l1), u), Vector(k0).lerp(Vector(k1), u), lens
    fa, fb, l0, l1, k0, k1, lens = shots[-1]
    return Vector(l1), Vector(k1), lens


def _project(loc, look, lens, p, aspect=16 / 9):
    """Where world point p falls on screen (x, y from the top-left, 0..1, and
    depth), for a camera at loc looking at look (36 mm sensor width)."""
    d = (look - loc).normalized()
    right = d.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(d)
    v = Vector(p) - loc
    z = v.dot(d)
    if z <= 0.1:
        return [0.0, 0.0, -1.0]
    f = lens / 36.0
    x = 0.5 + f * v.dot(right) / z
    y = 0.5 - f * aspect * v.dot(up) / z
    return [round(x, 4), round(y, 4), round(z, 1)]


def _episode_animate(self):
    """Motion, the fall and the cameras for the episode's whole timeline."""
    from kits import timemap
    sc = self.sc
    tm = timemap.CURRENT
    last = tm.frame(tm.end)
    frames = range(1, last + 1)
    tw, hv = twist_at_frame, heave_at_frame
    self.key_motion(frames, tw, hv, waves=2.0)
    self.place_vehicles(frames, tw, hv, car_x=-560.0, truck_x=-610.0)
    # the middle 600 ft first; then the rest, the last piece by each tower left hanging
    self.collapse([(-300, 300, T_BREAK1, 0.8, 150),
                   (-1400, -300, T_BREAK2, 2.2, 150, True),
                   (300, 1400, T_BREAK2 + 0.4, 2.2, 150, True)],
                  tw, hv, last, fps=FPS, frame_of=frame_of)
    # the cameras
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    self.cam = cam
    cam.data.clip_start, cam.data.clip_end = 0.5, 60000
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.sensor_width = 36.0
    target = bpy.data.objects.new("target", None)
    sc.collection.objects.link(target)
    c = cam.constraints.new("TRACK_TO")
    c.target, c.track_axis, c.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    look.lens(cam, target, fstop=5.6)
    self.shots = shot_list()
    for fa, fb, l0, l1, k0, k1, lens in self.shots:
        fb = max(fa + 1, fb)
        for f, loc_, look_ in ((fa, l0, k0), (fb, l1, k1)):
            cam.location = loc_
            target.location = look_
            cam.data.lens = lens
            cam.keyframe_insert("location", frame=f)
            target.keyframe_insert("location", frame=f)
            cam.data.keyframe_insert("lens", frame=f)
    for o in (cam, target, cam.data):
        _linear(o)
    sc.frame_start, sc.frame_end = 1, last
    self.last = last


def _linear(o):
    """Steady camera moves: every key linear (a cut is two keys a frame apart)."""
    ad = o.animation_data
    if not ad or not ad.action:
        return
    curves = getattr(ad.action, "fcurves", None)
    if curves is None:                          # Blender 5: layered actions
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"


def _episode_anchors(self, first, last):
    """Each labelled part's place on screen, every frame, from the camera
    path itself (no scene evaluation: the forest and the motion make that
    slow)."""
    pts = {"bridge": (0, -GIRDER_Y, ROAD_Z), "tower": (HALF, -GIRDER_Y, TOWER_TOP - 20),
           "girder": (-640, -GIRDER_Y, ROAD_Z - 2), "quarter": (-700, -GIRDER_Y, ROAD_Z),
           "car": (-560, -9.5, ROAD_Z + 3)}
    out = {}
    shots = getattr(self, "shots", None) or shot_list()
    for f in range(first, last + 1):
        loc, at, lens = _cam_at_frame(shots, f)
        out[f] = {k: _project(loc, at, lens, p) for k, p in pts.items()}
    return out


def _episode_short_camera(self, mode):
    """A tall camera for a Short: "fall", the middle of the span going into
    the water; "close", on the road behind the car as the twist grows."""
    from kits import timemap
    cam = self.cam
    target = bpy.data.objects["target"]
    for o in (cam, cam.data, target):
        o.animation_data_clear()
    a, b = timemap.SHORT["flutter"][mode]
    keys = ({"fall": [(a, (-170, -300, 120), (0, 0, 175), 30), (b, (-160, -290, 70), (0, 0, 60), 28)],
             "close": [(a, (-480, -16, 205), (-650, -4, 199), 26), (b, (-488, -16, 205), (-660, -4, 197), 26)]}
            [mode])
    for sec, loc_, look_, lens in keys:
        f = timemap.CURRENT.frame(sec)
        cam.location, target.location, cam.data.lens = loc_, look_, lens
        cam.keyframe_insert("location", frame=f)
        target.keyframe_insert("location", frame=f)
        cam.data.keyframe_insert("lens", frame=f)
    self.sc.frame_start, self.sc.frame_end = timemap.CURRENT.frame(a), timemap.CURRENT.frame(b)


Model.animate = _episode_animate
Model.anchors = _episode_anchors
Model.short_camera = _episode_short_camera


def render(sheet, out_dir, first=1, last=None, samples=16, still=0, short=None, size=None):
    """Renders the episode's frames (first..last, 1-based) or one still;
    writes the label anchors beside them."""
    import json
    from kits import timemap
    timemap.use({"kit": {"variant": "flutter"}} if short else sheet)
    m = Model(sheet)
    m.build()
    m.animate()
    if short:
        m.short_camera(short)
        first = max(first, m.sc.frame_start)
    setup_render(m.sc, samples, size or ((1080, 1920) if short else (1280, 720)))
    m.sc.render.use_motion_blur = True          # the falls and the spray; cuts are rare frames
    last = min(last or m.sc.frame_end, m.sc.frame_end)
    os.makedirs(out_dir, exist_ok=True)
    if still:
        m.sc.frame_set(still)
        m.sc.render.filepath = os.path.join(out_dir, f"still_{still:04d}.png")
        bpy.ops.render.render(write_still=True)
        return
    json.dump(m.anchors(first, last), open(os.path.join(out_dir, f"anchors_{first:04d}.json"), "w"))
    m.sc.frame_start, m.sc.frame_end = first, last
    m.sc.render.filepath = os.path.join(out_dir, "")
    bpy.ops.render.render(animation=True)
