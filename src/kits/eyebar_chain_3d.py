"""
Bridge kit, variant "eyebar_chain", in 3D (Blender's free bpy module, CPU
only): the 2D kit's partner. A suspension bridge hung from two chains of
steel eyebars, two bars to a link, pinned at the joints; hangers down to two
stiffening trusses and the deck; towers on piers in the river (the
proportions of the Silver Bridge, NTSB HAR-71-1: 380 ft side spans and a
700 ft main span; one unit is one foot).

One continuous camera path, in shots (canonical seconds, kits/timemap.py):

    establish   0-7     from upstream, the whole bridge over the river,
                        traffic on the deck
    load_path   7-13    along the north chain of the Ohio side span toward
                        the Ohio tower
    connection  13-20   in on joint C13N, the first chain joint west of the
                        Ohio tower: the pin through four eyes, the two bars
                        of each link; a mark glows where the crack grows at
                        the pinhole of the outer bar
    fall        20-28   the eye breaks, the bar swings away, its sister
                        slides off the pin; pull back: the Ohio side span
                        drops, the towers go and the collapse runs east

Ohio (west) is -x, West Virginia +x; upstream (north) is +y. For every frame
it records where the labelled parts are on screen (anchors JSON).

    python -m kits.eyebar_chain_3d sheet.json out_dir [--first N --last M] [--samples S]
"""

import argparse
import json
import math
import os
import random

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

FPS = 30
SECONDS = 28
T_FALL = 22.0
SHORT = __import__("kits.timemap", fromlist=["SHORT"]).SHORT["eyebar_chain"]   # the tall Short cameras

XA0, XT0, XT1, XA1 = -730.0, -350.0, 350.0, 730.0     # anchorages and towers: 380 + 700 + 380 ft
DECK_Z, U_Z, TOP_Z = 70.0, 95.0, 200.0                # deck (truss lower chord), truss upper chord, saddles
CHAIN_Y = 16.0                                        # the chains (and trusses) at y = +-16
SIDE_LINKS, MAIN_LINKS = 8, 14
BANK0, BANK1 = -420.0, 420.0                          # the river between its banks
BAR_H, BAR_T, BAR_GAP = 2.4, 0.5, 1.6                 # an eyebar's depth and thickness, gap between bars
EYE_R, PIN_R = 2.4, 0.9                               # (drawn heavier than life so the chain reads at a distance)


def s(sec):
    from kits import timemap
    return timemap.CURRENT.frame(sec)


def mat(name, color, rough=0.8, metal=0.0, emit=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 0.0
    return m


def mesh(name, verts, faces, material, smooth=False, at=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    o.location = at
    for p in me.polygons:
        p.use_smooth = smooth
    return o


BOX_FACES = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]


def beam(name, p0, p1, w, h, material):
    """A straight member from p0 to p1, w wide (across y) and h deep, its
    origin at its middle so it can fall and turn about itself."""
    p0, p1 = Vector(p0), Vector(p1)
    c = (p0 + p1) / 2
    d = (p1 - p0)
    ln = d.length or 1e-3
    d.normalize()
    side = Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((1, 0, 0))
    up = d.cross(side).normalized()
    side = up.cross(d).normalized()
    verts = []
    for a in (-ln / 2, ln / 2):
        for sw, sh in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(tuple(d * a + side * (sw * w / 2) + up * (sh * h / 2)))
    order = [0, 1, 2, 3, 4, 5, 6, 7]
    return mesh(name, [verts[i] for i in order], BOX_FACES, material, at=tuple(c))


def disc(name, centre, r, thick, material, axis="y"):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=thick, location=centre, vertices=28)
    o = bpy.context.object
    o.name = name
    if axis == "y":
        o.rotation_euler = (math.radians(90), 0, 0)
    o.data.materials.append(material)
    return o


def floor_z(x):
    return 0.0 if BANK0 < x < BANK1 else 12.0


class Model:
    def __init__(self, sheet):
        self.links = []          # (object, x at its middle)
        self.parts = []          # everything that falls: (object, x)

    # ------------------------------------------------------------------ geometry
    def chain_pts(self):
        pts = []
        for i in range(SIDE_LINKS + 1):
            u = i / SIDE_LINKS
            z = min(U_Z, U_Z + (TOP_Z - U_Z) * u - 58 * 4 * u * (1 - u))
            pts.append((0, i, XA0 + (XT0 - XA0) * u, z))
        for i in range(1, MAIN_LINKS + 1):
            u = i / MAIN_LINKS
            pts.append((1, i, XT0 + (XT1 - XT0) * u, TOP_Z - (TOP_Z - U_Z - 6) * 4 * u * (1 - u)))
        for i in range(1, SIDE_LINKS + 1):
            u = i / SIDE_LINKS
            z = min(U_Z, TOP_Z + (U_Z - TOP_Z) * u - 58 * 4 * u * (1 - u))
            pts.append((2, i, XT1 + (XA1 - XT1) * u, z))
        return pts

    def joint(self):
        """C13N: the north chain, the joint before the Ohio tower."""
        p = next(p for p in self.chain_pts() if (p[0], p[1]) == (0, SIDE_LINKS - 1))
        return Vector((p[2], CHAIN_Y, p[3]))

    # ------------------------------------------------------------------ scene
    def build(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        steel = mat("steel", (0.42, 0.44, 0.46), 0.45, 0.6)
        self.steel = steel
        self.bar330 = mat("bar330", (0.50, 0.52, 0.55), 0.4, 0.6, emit=(1.0, 0.18, 0.08))
        pin_m = mat("pin", (0.30, 0.31, 0.33), 0.35, 0.8)
        deck_m = mat("deck", (0.26, 0.26, 0.27), 0.85)
        conc = mat("concrete", (0.55, 0.53, 0.50), 0.9)
        water = mat("river", (0.07, 0.17, 0.22), 0.06)
        land = mat("bank", (0.30, 0.33, 0.20), 0.95)
        self.crack_m = mat("crack", (0.1, 0.02, 0.02), 0.5, emit=(1.0, 0.12, 0.05))
        car_cols = [(0.55, 0.10, 0.08), (0.12, 0.22, 0.45), (0.75, 0.72, 0.65), (0.15, 0.15, 0.16),
                    (0.60, 0.48, 0.12)]
        car_m = [mat(f"car{i}", c, 0.4, 0.3) for i, c in enumerate(car_cols)]

        # the river and its banks
        mesh("river", [(BANK0 - 60, -3000, 0), (BANK1 + 60, -3000, 0), (BANK1 + 60, 3000, 0),
                       (BANK0 - 60, 3000, 0)], [(0, 1, 2, 3)], water)
        for x0, x1 in ((-3000, BANK0), (BANK1, 3000)):
            mesh(f"bank{x0}", [(x0, -3000, 12), (x1, -3000, 12), (x1, 3000, 12), (x0, 3000, 12)],
                 [(0, 1, 2, 3)], land)
        # the anchorages
        for x in (XA0, XA1):
            beam(f"anchorage{x}", (x - 25 * (1 if x < 0 else -1), 0, 12), (x, 0, 12), 60, 2, conc)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 12 + U_Z / 2 - 6))
            a = bpy.context.object
            a.scale = (40, 60, U_Z - 6)
            a.data.materials.append(conc)

        # the towers: a pier in the river, a leg under each chain, bracing between
        self.towers = []
        for x in (XT0, XT1):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 8))
            pier = bpy.context.object
            pier.scale = (18, 50, 16)
            pier.data.materials.append(conc)
            parts = []
            for y in (-CHAIN_Y, CHAIN_Y):
                parts.append(beam(f"leg{x}{y}", (x, y, 16), (x, y, TOP_Z + 3), 3.0, 3.0, steel))
            for k in range(7):
                z0, z1 = 16 + (TOP_Z - 16) * k / 7, 16 + (TOP_Z - 16) * (k + 1) / 7
                parts.append(beam(f"brace{x}{k}a", (x, -CHAIN_Y, z0), (x, CHAIN_Y, z1), 1.0, 1.0, steel))
                parts.append(beam(f"brace{x}{k}b", (x, CHAIN_Y, z0), (x, -CHAIN_Y, z1), 1.0, 1.0, steel))
            parts.append(beam(f"strut{x}", (x, -CHAIN_Y - 2, TOP_Z + 3), (x, CHAIN_Y + 2, TOP_Z + 3), 3, 3, steel))
            self.towers.append((x, parts))

        # the chains: two eyebars to a link, a pin at each joint
        pts = self.chain_pts()
        j = self.joint()
        self.c13 = {}
        for y in (-CHAIN_Y, CHAIN_Y):
            for k in range(len(pts) - 1):
                (_, _, xa, za), (_, _, xb, zb) = pts[k], pts[k + 1]
                for b in (-1, 1):
                    yy = y + b * BAR_GAP / 2
                    o = beam(f"bar{y}_{k}_{b}", (xa, yy, za), (xb, yy, zb), BAR_T, BAR_H, steel)
                    self.parts.append((o, (xa + xb) / 2))
                    if y > 0 and abs(xb - j.x) < 0.1:        # the west link into C13N: eyebar 330 (north), 33
                        self.c13["330" if b > 0 else "33"] = o
                        o.data.materials[0] = self.bar330 if b > 0 else steel
                    if y > 0 and abs(xa - j.x) < 0.1:
                        self.c13.setdefault("east", []).append(o)
            for _, _, x, z in pts[1:-1]:
                p = disc(f"pin{y}{x:.0f}", (x, y, z), PIN_R, BAR_GAP * 2 + 0.8, pin_m)
                self.parts.append((p, x))
        # C13N up close: the eyes of the four bars on the pin, the hanger strap
        self.eyes = {}
        for name, dy in (("330", BAR_GAP / 2 + 0.3), ("33", -BAR_GAP / 2 - 0.3), ("e1", BAR_GAP / 2 - 0.25),
                         ("e2", -BAR_GAP / 2 + 0.25)):
            e = disc(f"eye{name}", (j.x, j.y + dy, j.z), EYE_R, BAR_T, self.bar330 if name == "330" else steel)
            self.eyes[name] = e
        # the crack: where the outer bar's eye bears on its pin, in the lower limb (a mark, not to scale)
        yf = j.y + BAR_GAP / 2 + 0.3 + BAR_T / 2 + 0.04          # just proud of the outer eye's face
        self.crack = beam("crack", (j.x, yf, j.z - PIN_R - 0.02), (j.x + 0.08, yf, j.z - PIN_R - 0.8),
                          0.12, 0.12, self.crack_m)
        # the hangers, the stiffening trusses and the deck
        for y in (-CHAIN_Y, CHAIN_Y):
            for _, _, x, z in pts:
                if z < U_Z - 4:
                    continue
                h = beam(f"hanger{y}{x:.0f}", (x, y, z), (x, y, U_Z), 0.9, 0.9, steel)
                self.parts.append((h, x))
            xs = [XA0 + (XA1 - XA0) * k / 58 for k in range(59)]
            for k in range(58):
                xa, xb = xs[k], xs[k + 1]
                for o in (beam(f"lo{y}{k}", (xa, y, DECK_Z), (xb, y, DECK_Z), 1.6, 2.2, steel),
                          beam(f"up{y}{k}", (xa, y, U_Z), (xb, y, U_Z), 1.2, 1.6, steel),
                          beam(f"v{y}{k}", (xa, y, DECK_Z), (xa, y, U_Z), 0.6, 0.6, steel),
                          beam(f"d{y}{k}", (xa, y, DECK_Z) if k % 2 else (xa, y, U_Z),
                               (xb, y, U_Z) if k % 2 else (xb, y, DECK_Z), 0.5, 0.5, steel)):
                    self.parts.append((o, (xa + xb) / 2))
        xs = [XA0 + (XA1 - XA0) * k / 29 for k in range(30)]
        for k in range(29):
            d = beam(f"deck{k}", (xs[k], 0, DECK_Z + 1.2), (xs[k + 1], 0, DECK_Z + 1.2), CHAIN_Y * 2 - 2, 0.8, deck_m)
            self.parts.append((d, (xs[k] + xs[k + 1]) / 2))
        # traffic: 37 vehicles were on the bridge (NTSB)
        rnd = random.Random(9)
        for i in range(37):
            x = rnd.uniform(XA0 + 30, XA1 - 30)
            lane = rnd.choice((-5.5, 5.5))
            c = beam(f"car{i}", (x - 7, lane, DECK_Z + 3.4), (x + 7, lane, DECK_Z + 3.4), 6, 4.2, rnd.choice(car_m))
            self.parts.append((c, x))

        world = bpy.data.worlds.new("world")
        sc.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.52, 0.58, 0.66, 1)      # a December late afternoon
        bg.inputs["Strength"].default_value = 0.5
        bpy.ops.object.light_add(type="SUN", location=(0, 0, 500))
        sun = bpy.context.object
        sun.data.energy = 2.2
        sun.rotation_euler = (math.radians(62), math.radians(15), math.radians(-150))
        self.sc = sc

    # -------------------------------------------------------------- animation
    def t0(self, x):
        """When a part at x starts to fall: the Ohio side span first, then
        east across the main span to the West Virginia side."""
        j = self.joint().x
        if x <= XT0:
            return T_FALL + 0.2 + 0.5 * abs(x - j) / (j - XA0)
        return T_FALL + 0.6 + 4.4 * (x - XT0) / (XA1 - XT0)

    def animate(self):
        sc = self.sc
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        sc.camera = cam
        self.cam = cam
        cam.data.clip_end = 20000
        target = bpy.data.objects.new("target", None)
        sc.collection.objects.link(target)
        c = cam.constraints.new("TRACK_TO")
        c.target = target
        c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        j = self.joint()

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        cam_key(0, (420, 820, 150), (-40, 0, 105), 26)                        # establish, from upstream
        cam_key(6.5, (160, 760, 140), (-160, 0, 110), 26)
        cam_key(8.0, (-560, 260, 140), (-470, CHAIN_Y, 120), 32)               # along the Ohio side span chain
        cam_key(12.8, (-470, 120, 170), (j.x - 10, CHAIN_Y, j.z), 38)
        cam_key(15.0, j + Vector((16, 26, 9)), j, 40)                           # C13N, from above and ahead
        cam_key(19.8, j + Vector((9, 15, 5)), j + Vector((0, 0, -0.5)), 45)       # so both bars of each link show
        cam_key(T_FALL - 0.3, j + Vector((11, 18, 6)), j, 42)
        cam_key(T_FALL + 1.2, (-520, 520, 210), (-300, 0, 90), 30)            # the Ohio side goes
        cam_key(SECONDS, (380, 900, 190), (-40, 0, 50), 24)                   # the whole bridge

        # the crack's mark glows as it grows (a mark at the spot; the real crack was about 1/8 inch)
        cb = self.crack_m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        for sec, v in ((14.5, 0.0), (17.0, 4.0), (T_FALL - 0.6, 14.0), (T_FALL, 30.0)):
            cb.default_value = v
            cb.keyframe_insert("default_value", frame=s(sec))
        self.crack.scale = (1, 1, 0.2)
        self.crack.keyframe_insert("scale", frame=s(14.5))
        self.crack.scale = (1, 1, 1.0)
        self.crack.keyframe_insert("scale", frame=s(T_FALL - 0.6))

        # the eye breaks: eyebar 330 swings away from the pin, its sister slides off
        for o, d0, off, rot in ((self.c13["330"], T_FALL - 0.4, Vector((-1.5, 3.0, -2.2)), 0.35),
                                (self.eyes["330"], T_FALL - 0.4, Vector((-1.5, 3.0, -2.2)), 0.35),
                                (self.c13["33"], T_FALL + 0.05, Vector((-2.0, -2.4, -2.6)), -0.25),
                                (self.eyes["33"], T_FALL + 0.05, Vector((-2.0, -2.4, -2.6)), -0.25)):
            o.keyframe_insert("location", frame=s(d0))
            o.keyframe_insert("rotation_euler", frame=s(d0))
            o.location = o.location + off
            o.rotation_euler.y += rot
            o.keyframe_insert("location", frame=s(d0 + 0.5))
            o.keyframe_insert("rotation_euler", frame=s(d0 + 0.5))
        for o in (self.crack,):
            o.hide_render = False
            o.keyframe_insert("hide_render", frame=s(T_FALL + 1.0))
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=s(T_FALL + 1.1))

        # the collapse: each part drops to the river or the bank, west to east
        rnd = random.Random(3)
        skip = {id(self.c13["330"]), id(self.c13["33"])}
        for o, x in self.parts + [(e, self.joint().x) for e in (self.eyes["e1"], self.eyes["e2"])]:
            if id(o) in skip:
                continue
            t0 = self.t0(x) + rnd.uniform(-0.1, 0.15)
            fall = o.location.z - floor_z(x) - 1.0
            o.keyframe_insert("location", frame=s(t0))
            o.keyframe_insert("rotation_euler", frame=s(t0))
            dur = 0.6 + 0.25 * math.sqrt(max(1.0, fall)) / 3
            o.location = (o.location.x + rnd.uniform(-4, 4), o.location.y + rnd.uniform(-6, 6), floor_z(x) + 1.0)
            o.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.4, 0.4), rnd.uniform(-0.2, 0.2))
            o.keyframe_insert("location", frame=s(t0 + dur))
            o.keyframe_insert("rotation_euler", frame=s(t0 + dur))
        for x, parts in self.towers:                 # off the rocker bearings: the towers go over
            t0 = self.t0(x) + 0.2
            sgn = 1 if x < 0 else -1
            for o in parts:
                o.keyframe_insert("location", frame=s(t0))
                o.keyframe_insert("rotation_euler", frame=s(t0))
                p = o.location.copy()
                a = math.radians(70) * sgn
                rel = p - Vector((x, p.y, 16))
                o.location = (x + rel.z * math.sin(a), p.y, 16 + rel.z * math.cos(a) * 0.3)
                o.rotation_euler.y += a
                o.keyframe_insert("location", frame=s(t0 + 1.6))
                o.keyframe_insert("rotation_euler", frame=s(t0 + 1.6))
        sc.frame_start, sc.frame_end = 1, s(SECONDS) - 1

    # ----------------------------------------------------------------- Shorts
    def short_camera(self, mode):
        """A tall camera for a Short, on the canonical timeline: "fall",
        the Ohio side span and tower filling the frame as they drop and the
        collapse runs on east; "close", in on joint C13N as the crack's mark
        grows, the eye breaks and the bars come off the pin."""
        cam, target = self.cam, bpy.data.objects["target"]
        for o in (cam, cam.data, target):
            o.animation_data_clear()
        j = self.joint()

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        a, b = SHORT[mode]
        if mode == "fall":
            cam_key(a, (-560, 640, 150), (-420, 0, 110), 26)
            cam_key(T_FALL + 1.0, (-540, 660, 140), (-380, 0, 80), 26)
            cam_key(b, (-420, 820, 160), (-150, 0, 50), 24)
        else:
            cam_key(a, j + Vector((14, 24, 9)), j, 38)
            cam_key(17.0, j + Vector((8, 14, 5)), j + Vector((0, 0, -0.5)), 44)
            cam_key(T_FALL - 0.3, j + Vector((9, 16, 6)), j, 42)
            cam_key(b, j + Vector((14, 40, 6)), j + Vector((0, 0, -3)), 34)
        self.sc.frame_start, self.sc.frame_end = s(a), s(b)

    # ---------------------------------------------------------------- anchors
    def anchors(self, first, last):
        sc = self.sc
        pts = self.chain_pts()
        mid = pts[SIDE_LINKS + MAIN_LINKS // 2]
        jt = self.joint()
        fixed = {
            "joint": jt,
            "bridge": Vector((0, -CHAIN_Y, DECK_Z)),
            "tower": Vector((XT0, CHAIN_Y, TOP_Z - 10)),
            "chain": Vector((mid[2] - 60, CHAIN_Y, mid[3] + 30)),
            "deck": Vector((200, -CHAIN_Y, DECK_Z)),
        }
        out = {}
        for f in range(first, last + 1):
            sc.frame_set(f)
            row = {}
            for k, p in fixed.items():
                v = world_to_camera_view(sc, self.cam, p)
                row[k] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
            out[f] = row
        return out


def setup_render(sc, samples, size=(1280, 720)):
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.fps = FPS
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.render.use_persistent_data = True
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.exposure = -0.4
    views = [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = "AgX" if "AgX" in views else "Filmic"


def render(sheet, out_dir, first=1, last=None, samples=16, still=0, short=None, size=None):
    """short: a Short's tall camera ("fall" or "close"), on the canonical
    timeline (one second of model time is one second of video)."""
    from kits import timemap
    timemap.use({} if short else sheet)
    m = Model(sheet)
    m.build()
    m.animate()
    if short:
        m.short_camera(short)
        first = max(first, m.sc.frame_start)
    setup_render(m.sc, samples, size or ((1080, 1920) if short else (1280, 720)))
    last = last or m.sc.frame_end
    os.makedirs(out_dir, exist_ok=True)
    if still:
        m.sc.frame_set(still)
        m.sc.render.filepath = os.path.join(out_dir, f"still_{still:04d}.png")
        bpy.ops.render.render(write_still=True)
        return
    json.dump(m.anchors(first, min(last, m.sc.frame_end)),
              open(os.path.join(out_dir, f"anchors_{first:04d}.json"), "w"))
    m.sc.frame_start, m.sc.frame_end = first, min(last, m.sc.frame_end)
    m.sc.render.filepath = os.path.join(out_dir, "")
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("out_dir")
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--still", type=int, default=0)
    ap.add_argument("--short", choices=sorted(SHORT), default=None)
    a = ap.parse_args()
    render(json.load(open(a.sheet)), a.out_dir, a.first, a.last or None, a.samples, a.still, a.short)
