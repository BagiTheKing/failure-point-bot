"""
Spaceflight kit, variant "orbiter", in 3D (Blender's free bpy module, CPU
only): the 2D kit's partner. A winged orbiter on re-entry, high over the
Earth, nose up (the proportions of the Space Shuttle, no markings), built in
pieces so it can come apart; the left wing's leading edge is a row of 22
heat-shield panels, one of them holed.

One continuous camera path, in shots (canonical seconds, kits/timemap.py):

    establish   0-7     alongside the orbiter, the Earth's curve below
    load_path   7-13    from ahead and below: re-entry heat wraps the belly,
                        the nose and the wings' leading edges, glowing
    connection  13-20   push-in on the holed panel: the glow gets inside,
                        the wing behind it turns red hot
    fall        20-28   pull back; the left wing's outer part goes, then the
                        whole orbiter breaks apart into burning streaks

For every frame it also records where the labelled parts are on screen
(anchors JSON), so the 2D labels drawn later follow the model.

    python -m kits.orbiter_3d sheet.json out_dir [--first N --last M] [--samples S]
"""

import argparse
import json
import math
import os
import random

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

FPS = 30
SECONDS = 28
T_FALL = 22.0
SHORT = __import__("kits.timemap", fromlist=["SHORT"]).SHORT["orbiter"]   # the tall Short cameras
PITCH = math.radians(40)              # nose up: the attitude it re-enters at
ATT = Matrix.Rotation(PITCH, 3, "Y")  # orbiter frame -> world (nose forward is -x, the left wing -y)
N_PANELS = 22
# one wing's outline (x, |y|) in the orbiter's frame: glove root, glove/main edge kink, tip, trailing edge
WING = [(-11.5, 2.4), (-2.5, 4.4), (12.0, 11.9), (14.3, 11.9), (15.3, 2.4)]
WING_Z = -1.4
CUT_Y = 8.5                           # where the left wing's outer part comes away
HOT = (1.0, 0.42, 0.16)


def s(sec):
    from kits import timemap
    return timemap.CURRENT.frame(sec)


def mat(name, color, rough=0.5, metal=0.0, emit=None):
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


def glow(name, color, strength=0.0, tube=False):
    """Hot gas: a glowing volume with no surface, brightest at its core and
    fading to nothing at its edge (its object's unit ball, or for a streak
    the unit tube round its x axis). Returns the material and its strength
    socket, for keyframes."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vec = tc.outputs["Object"]
    if tube:
        mul = nt.nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = (0, 1, 1)
        nt.links.new(vec, mul.inputs[0])
        vec = mul.outputs[0]
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    nt.links.new(vec, ln.inputs[0])
    inv = nt.nodes.new("ShaderNodeMath")                 # 1 - r, never below 0
    inv.operation, inv.use_clamp = "SUBTRACT", True
    inv.inputs[0].default_value = 1.0
    nt.links.new(ln.outputs["Value"], inv.inputs[1])
    sq = nt.nodes.new("ShaderNodeMath")
    sq.operation = "POWER"
    sq.inputs[1].default_value = 2.5
    nt.links.new(inv.outputs[0], sq.inputs[0])
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    k.inputs[1].default_value = strength
    nt.links.new(sq.outputs[0], k.inputs[0])
    nt.links.new(k.outputs[0], em.inputs["Strength"])
    nt.links.new(em.outputs[0], out.inputs["Volume"])
    return m, k.inputs[1]


def streak(name, color):
    """A cheap glow for the many streaks: a see-through surface whose light
    is strongest where it faces the camera and fades to nothing at its
    edges, so a tube reads as a soft line of fire. Returns the material and
    its strength socket."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation, inv.use_clamp = "SUBTRACT", True
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    sq = nt.nodes.new("ShaderNodeMath")
    sq.operation = "POWER"
    sq.inputs[1].default_value = 3.0
    nt.links.new(inv.outputs[0], sq.inputs[0])
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    k.inputs[1].default_value = 0.0
    nt.links.new(sq.outputs[0], k.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    nt.links.new(k.outputs[0], em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m, k.inputs[1]


def key(socket, values):
    for sec, v in values:
        socket.default_value = v
        socket.keyframe_insert("default_value", frame=s(sec))


def adopt(o, parent):
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def box(loc, size, material, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = size
    o.data.materials.append(material)
    return adopt(o, parent)


def ball(loc, scale, material, parent=None, subdiv=3):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1, subdivisions=subdiv, location=loc)
    o = bpy.context.object
    o.scale = scale
    o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return adopt(o, parent)


def empty(name, loc=(0, 0, 0)):
    bpy.ops.object.empty_add(location=loc)
    o = bpy.context.object
    o.name = name
    return o


def mesh(name, verts, faces, materials, parent=None, smooth=True, mat_index=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    for m in materials:
        o.data.materials.append(m)
    for i, p in enumerate(me.polygons):
        p.use_smooth = smooth
        if mat_index:
            p.material_index = mat_index(p)
    return adopt(o, parent)


def loft(name, stations, materials, parent=None, na=40, n=2.6, belly_frac=0.35, cap=True):
    """A body of boxy cross-sections (superellipses, exponent n) through
    stations (x, half width, half height, centre z); with two materials, the
    faces low on the body take the second (the black belly tiles)."""
    verts, faces = [], []
    for x, wy, wz, zc in stations:
        for j in range(na):
            a = 2 * math.pi * j / na
            c, sn = math.cos(a), math.sin(a)
            verts.append((x, wy * math.copysign(abs(c) ** (2 / n), c), zc + wz * math.copysign(abs(sn) ** (2 / n), sn)))
    for i in range(len(stations) - 1):
        for j in range(na):
            p, q = i * na + j, i * na + (j + 1) % na
            faces.append((p, q, q + na, p + na))
    if cap:
        faces.append(tuple(range(na))[::-1])
        faces.append(tuple(range((len(stations) - 1) * na, len(stations) * na)))

    def idx(p):
        if len(materials) < 2:
            return 0
        z = sum(verts[v][2] for v in p.vertices) / len(p.vertices)
        x = sum(verts[v][0] for v in p.vertices) / len(p.vertices)
        st = min(stations, key=lambda r: abs(r[0] - x))
        return 1 if z < st[3] - st[2] * (1 - 2 * belly_frac) else 0
    return mesh(name, verts, faces, materials, parent, mat_index=idx)


def slab(name, outline, z, thick, material, parent=None):
    """A flat part (a wing's skin) from its outline [(x, y)] at height z."""
    n = len(outline)
    verts = [(x, y, z + thick / 2) for x, y in outline] + [(x, y, z - thick / 2) for x, y in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return mesh(name, verts, faces, [material], parent, smooth=False)


def edge_at(k, side=-1):
    """A point on the wing's main leading edge, k 0..1 root to tip, and the
    edge's direction there (orbiter frame)."""
    (x0, y0), (x1, y1) = WING[1], WING[2]
    p = Vector((x0 + (x1 - x0) * k, side * (y0 + (y1 - y0) * k), WING_Z))
    d = Vector((x1 - x0, side * (y1 - y0), 0)).normalized()
    return p, d


def trail_mesh(name, material):
    """A unit streak along +x: wide at its head (x = 0), thin at its tail."""
    na = 12
    verts = []
    for x, r in ((0.0, 1.0), (1.0, 0.12)):
        for j in range(na):
            a = 2 * math.pi * j / na
            verts.append((x, r * math.cos(a), r * math.sin(a)))
    faces = [(j, (j + 1) % na, na + (j + 1) % na, na + j) for j in range(na)]
    return mesh(name, verts, faces, [material])


class Model:
    def __init__(self, sheet):
        m = sheet.get("model_3d", {})
        self.panel = int(sheet.get("kit", {}).get("panel", 8) or 8)
        self.pk = (self.panel - 0.5) / N_PANELS                       # the holed panel along the edge
        self.roots = {}
        self.c = {}

    # ------------------------------------------------------------------ scene
    def root(self, name, c):
        r = empty(name, c)
        self.roots[name] = r
        self.c[name] = Vector(c)
        bpy.context.view_layer.update()
        return r

    def world(self, name, p_local):
        """A point given in the orbiter's frame, carried by the named piece."""
        r = self.roots[name]
        return r.matrix_world @ (Vector(p_local) - self.c[name])

    def build(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        white = mat("tiles_white", (0.88, 0.88, 0.86), 0.55)
        black = mat("tiles_black", (0.035, 0.035, 0.04), 0.7)
        rcc = mat("rcc", (0.3, 0.31, 0.33), 0.5, 0.2)
        dark = mat("glass", (0.02, 0.03, 0.05), 0.15)
        engine = mat("engine", (0.45, 0.46, 0.48), 0.35, 0.8)
        self.hole_m = mat("hole", (0.0, 0.0, 0.0), 0.9, 0.0, emit=HOT)
        self.hot_m, self.hot_k = glow("wing_hot", (1.0, 0.16, 0.05))
        self.sheath_m, self.sheath = glow("sheath", (1.0, 0.36, 0.14))
        self.jet_m, self.jet = glow("jet", (1.0, 0.62, 0.3))
        self.wake_m, self.wake = streak("wake", (1.0, 0.55, 0.38))
        self.trail_m, self.trail = streak("trail", (1.0, 0.8, 0.6))
        self.flash_m, self.flash = glow("flash", (1.0, 0.9, 0.75))
        self.bit_m = mat("bits", (1.0, 0.9, 0.8), 0.5, 0.0, emit=(1.0, 0.85, 0.65))
        self.bit_m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 12.0

        # the pieces it will come apart into, each a root at its centre (orbiter frame for now)
        nose = self.root("nose", (-14.5, 0, 0.3))
        midb = self.root("mid", (-3.5, 0, 0.3))
        aft = self.root("aft", (11.0, 0, 1.5))
        lin = self.root("lwing_in", (2.0, -5.5, WING_Z))
        lout = self.root("lwing_out", (11.0, -10.0, WING_Z))
        rw = self.root("rwing", (3.0, 6.5, WING_Z))

        # the body: crew module and nose, the payload bay, the aft fuselage
        nose_st = [(-18.5, 0.08, 0.08, -0.4), (-18.1, 0.85, 0.75, -0.3), (-17.2, 1.55, 1.35, -0.1),
                   (-15.8, 2.15, 1.9, 0.1), (-13.8, 2.5, 2.25, 0.3), (-11.0, 2.6, 2.4, 0.3)]
        loft("crew", nose_st, [white, black], nose)
        ball((-18.35, 0, -0.38), (0.32, 0.55, 0.5), rcc, nose)                   # the nose cap
        for y in (-0.9, -0.3, 0.3, 0.9):                                          # cockpit windows
            box((-15.3, y, 1.95), (0.55, 0.5, 0.08), dark, nose, rot=(0, math.radians(-35), 0))
        loft("bay", [(-11.0, 2.6, 2.4, 0.3), (4.0, 2.6, 2.4, 0.3)], [white, black], midb, cap=False)
        for x in (-7.5, -4.0, -0.5):                                              # the payload bay doors' hinge lines
            box((x, 0, 2.66), (0.05, 2.0, 0.03), dark, midb)
        box((-3.5, 0, 2.67), (15.0, 0.04, 0.03), dark, midb)
        loft("aft", [(4.0, 2.6, 2.4, 0.3), (15.3, 2.6, 2.4, 0.3)], [white, black], aft)
        for side in (-1, 1):                                                      # the engine pods
            loft(f"oms_{side}", [(8.0, 0.05, 0.05, 2.1), (9.5, 0.75, 0.7, 2.3), (15.6, 0.9, 0.85, 2.3)],
                 [white], aft, n=2.0)
            for i in range(3):
                pass
        fin = [(9.0, 0, 2.6), (15.3, 0, 2.6), (17.4, 0, 10.4), (15.7, 0, 10.4)]
        mesh("fin", fin + [(x, 0.18, z) for x, _, z in fin],
             [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)], [white], aft,
             smooth=False)
        aft.children[-1].location.y -= 0.09
        for y, z in ((0, 1.6), (-1.3, -0.3), (1.3, -0.3)):                        # main engines
            bpy.ops.mesh.primitive_cone_add(radius1=0.45, radius2=1.15, depth=2.2, vertices=24,
                                            location=(16.4, y, z), rotation=(0, math.radians(90), 0))
            o = bpy.context.object
            o.data.materials.append(engine)
            adopt(o, aft)
        box((16.2, 0, -1.9), (1.8, 5.0, 0.35), black, aft)                         # the body flap

        # the wings: white above, black below; the left one in two parts
        for side, parts in ((-1, (("lwing_in", lin, 0, CUT_Y), ("lwing_out", lout, CUT_Y, 99))), (1, (("rwing", rw, 0, 99),))):
            for name, r, y0, y1 in parts:
                pts = self._wing_part(y0, y1)
                pts = [(x, side * y) for x, y in pts]
                if side < 0:
                    pts = pts[::-1]
                slab(f"{name}_top", pts, WING_Z + 0.18, 0.3, white, r)
                slab(f"{name}_bot", pts, WING_Z - 0.17, 0.3, black, r)
            # the leading edge: the glove's edge, then 22 panels along the main edge
            (gx0, gy0), (gx1, gy1) = WING[0], WING[1]
            mid_ = Vector(((gx0 + gx1) / 2, side * (gy0 + gy1) / 2, WING_Z))
            ln = math.dist(WING[0], WING[1])
            box(mid_, (ln, 0.34, 0.62), rcc, lin if side < 0 else rw,
                rot=(0, 0, math.atan2(side * (gy1 - gy0), gx1 - gx0)))
            for i in range(1, N_PANELS + 1):
                k = (i - 0.5) / N_PANELS
                p, d = edge_at(k, side)
                outn = Vector((d.y, -d.x, 0)) * (1 if side < 0 else -1)            # ahead of the edge, outboard
                L = math.dist(WING[1], WING[2]) / N_PANELS
                r = (lin if (side < 0 and abs(p.y) < CUT_Y) else lout if side < 0 else rw)
                o = box(p + outn * 0.14, (L * 0.97, 0.36, 0.62), rcc, r, rot=(0, 0, math.atan2(d.y, d.x)))
                if side < 0 and i == self.panel:
                    # the hole, low on the panel's face, where the debris struck
                    self.hole_at = p + outn * 0.33 + Vector((0, 0, -0.16))
                    box(self.hole_at, (L * 0.5, 0.06, 0.22), self.hole_m, r, rot=(0, 0, math.atan2(d.y, d.x)))
                    self.jet_o = ball(self.hole_at - outn * 0.3, (1.1, 1.1, 0.8), self.jet_m, r)
                    # the wing behind it, heating from inside: a red glow spreading through the wing
                    self.hot_o = ball(p - outn * 1.1, (L * 2.6, 1.5, 0.45), self.hot_m, r, subdiv=2)
            # the re-entry glow along this wing's leading edge
            p0, d = edge_at(0.0, side)
            p1, _ = edge_at(1.0, side)
            for k0, k1 in ((0.0, CUT_Y), (CUT_Y, 99)) if side < 0 else ((0.0, 99),):
                ka = max(0.0, (k0 - WING[1][1]) / (WING[2][1] - WING[1][1]))
                kb = min(1.0, (k1 - WING[1][1]) / (WING[2][1] - WING[1][1]))
                pa, _ = edge_at(ka, side)
                pb, _ = edge_at(kb, side)
                c = (pa + pb) / 2 + Vector((-0.3, 0, -0.25))
                r = lin if (side < 0 and k0 == 0) else lout if side < 0 else rw
                o = ball(c, ((pb - pa).length / 2 + 0.3, 0.75, 0.7), self.sheath_m, r, subdiv=2)
                o.rotation_euler = (0, 0, math.atan2(d.y, d.x))
        # the glow under the belly and round the nose
        ball((-17.9, 0, -0.9), (2.2, 2.6, 2.2), self.sheath_m, nose)
        ball((-4.0, 0, -2.9), (13.0, 3.2, 0.9), self.sheath_m, midb)
        ball((4.0, -6.5, WING_Z - 0.7), (8.0, 3.6, 0.6), self.sheath_m, lin)
        ball((4.0, 6.5, WING_Z - 0.7), (8.0, 3.6, 0.6), self.sheath_m, rw)

        # now set every piece in the re-entry attitude: nose up, its centre carried round
        for name, r in self.roots.items():
            r.location = ATT @ self.c[name]
            r.rotation_euler = (0, PITCH, 0)
        bpy.context.view_layer.update()

        # the wake: the hot gas streaming back from it (world frame: it flies towards -x)
        w = trail_mesh("wake", self.wake_m)
        w.location = (6.0, 0, -1.5)
        w.scale = (140, 7.0, 4.5)
        # the debris' streaks, one per piece, and the small pieces
        rnd = random.Random(11)
        self.streaks = []
        for name in self.roots:
            t = trail_mesh(f"streak_{name}", self.trail_m)
            self.streaks.append((name, t, rnd.uniform(0.6, 1.1)))
        self.bits = []
        for i in range(36):
            b = ball((0, 0, 0), (0.1, 0.1, 0.1), self.bit_m, subdiv=2)
            t = trail_mesh(f"bit_streak_{i}", self.trail_m)
            self.bits.append((b, t))
        self.flash_o = ball((0.0, -1.0, -0.5), (0.1, 0.1, 0.1), self.flash_m)

        # the world: the Earth's curve far below, a black sky, the sun
        earth = mat("earth", (0.05, 0.16, 0.38), 0.6)
        nt = earth.node_tree
        noise = nt.nodes.new("ShaderNodeTexNoise")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        noise.inputs["Scale"].default_value = 0.012
        noise.inputs["Detail"].default_value = 8
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.55, 0.7
        ramp.color_ramp.elements[0].color = (0.04, 0.14, 0.34, 1)
        ramp.color_ramp.elements[1].color = (0.85, 0.88, 0.92, 1)
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=2500, segments=160, ring_count=80, location=(0, 0, -2620))
        e = bpy.context.object
        e.data.materials.append(earth)
        bpy.ops.object.shade_smooth()
        world = bpy.data.worlds.new("world")
        sc.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.004, 0.008, 0.02, 1)
        bg.inputs["Strength"].default_value = 1.0
        bpy.ops.object.light_add(type="SUN", location=(0, 0, 50))
        sun = bpy.context.object
        sun.data.energy = 3.6
        sun.rotation_euler = (math.radians(35), math.radians(-25), math.radians(-40))
        self.sc = sc

    @staticmethod
    def _wing_part(y0, y1):
        """The wing's outline (x, |y|) between spans y0 and y1."""
        def cut(a, b, y):
            k = (y - a[1]) / (b[1] - a[1])
            return (a[0] + (b[0] - a[0]) * k, y)
        le = WING[:3]
        te = [WING[4], WING[3]]                          # trailing edge, root to tip
        if y0 <= 0 and y1 >= 99:
            return WING
        if y0 <= 0:                                      # the inner part
            return [WING[0], WING[1], cut(WING[1], WING[2], y1), cut(te[0], te[1], y1), WING[4]]
        return [cut(le[1], le[2], y0), WING[2], WING[3], cut(te[0], te[1], y0)]

    # -------------------------------------------------------------- animation
    def animate(self):
        sc = self.sc
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        sc.camera = cam
        self.cam = cam
        cam.data.clip_end = 8000
        target = empty("target")
        c = cam.constraints.new("TRACK_TO")
        c.target = target
        c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        p8 = self.world("lwing_in", self.hole_at)

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        cam_key(0, (-38, -46, 10), (0, 0, -1), 35)                                  # establish
        cam_key(6.5, (-22, -46, 4), (0, 0, -1.5), 35)
        cam_key(8.5, (-40, -24, -17), (-2, 0, -2), 38)                              # the heat
        cam_key(12.5, (-35, -27, -12), (-1, 0, -2), 38)
        cam_key(15.0, p8 + Vector((-6.5, -5.5, -4.0)), p8, 42)                      # the holed panel
        cam_key(19.6, p8 + Vector((-3.4, -2.8, -2.0)), p8, 46)
        cam_key(21.4, (-26, -74, 4), (12, 0, -4), 32)                               # the breakup
        cam_key(T_FALL + 1.4, (-25, -76, 4), (14, 0, -5), 32)
        cam_key(SECONDS, (-18, -92, 1), (26, 0, -10), 30)

        # the heat: the sheath grows on re-entry, the hole's glow, the wing heating from inside
        key(self.sheath, ((0, 0.04), (5.0, 0.15), (9.0, 0.6), (T_FALL, 0.75), (T_FALL + 0.6, 0.1), (SECONDS, 0.04)))
        key(self.wake, ((0, 0.15), (9.0, 0.6), (T_FALL, 0.8), (T_FALL + 1.5, 0.0)))
        b = lambda m: m.node_tree.nodes["Principled BSDF"]
        key(b(self.hole_m).inputs["Emission Strength"], ((13.0, 0), (15.5, 3.0), (19.5, 8.0), (T_FALL, 10.0)))
        key(self.jet, ((13.5, 0), (16.0, 3.0), (20.0, 8.0), (T_FALL, 10.0), (T_FALL + 0.4, 0)))
        jo = self.jet_o
        base = tuple(jo.scale)
        for sec, k in ((13.5, 0.4), (19.0, 1.0), (T_FALL, 1.3)):
            jo.scale = tuple(v * k for v in base)
            jo.keyframe_insert("scale", frame=s(sec))
        key(self.hot_k, ((15.8, 0), (18.5, 1.5), (21.0, 4.0), (T_FALL, 5.0), (T_FALL + 0.6, 0)))
        ho = self.hot_o
        base_h = tuple(ho.scale)
        for sec, k in ((15.8, 0.5), (21.0, 1.0), (T_FALL, 1.25)):            # it spreads through the wing
            ho.scale = (base_h[0] * k, base_h[1] * k, base_h[2])
            ho.keyframe_insert("scale", frame=s(sec))

        # the breakup: the left wing's outer part first, then everything, each piece its own way
        rnd = random.Random(7)
        go = {"lwing_out": T_FALL - 1.0}
        for name, r in self.roots.items():
            t0 = go.get(name, T_FALL + rnd.uniform(0.0, 0.35))
            loc0, rot0 = Vector(r.location), Vector(r.rotation_euler)
            r.keyframe_insert("location", frame=s(t0))
            r.keyframe_insert("rotation_euler", frame=s(t0))
            back = rnd.uniform(25, 70) if name != "nose" else 18
            drift = Vector((back, rnd.uniform(-10, 10), -rnd.uniform(6, 26)))
            spin = Vector((rnd.uniform(-4, 4), rnd.uniform(-5, 5), rnd.uniform(-3, 3)))
            r.location = loc0 + drift * 0.08
            r.rotation_euler = rot0 + spin * 0.1
            r.keyframe_insert("location", frame=s(t0 + 0.7))
            r.keyframe_insert("rotation_euler", frame=s(t0 + 0.7))
            r.location = loc0 + drift
            r.rotation_euler = rot0 + spin
            r.keyframe_insert("location", frame=s(SECONDS))
            r.keyframe_insert("rotation_euler", frame=s(SECONDS))
        # each piece's streak follows it, pointing back along the flight path
        for name, t, width in self.streaks:
            r = self.roots[name]
            t0 = go.get(name, T_FALL)
            for sec in (0, t0, t0 + 0.7, T_FALL + 2.0, SECONDS):
                sc.frame_set(s(sec))
                t.location = r.matrix_world.translation
                L = 0.001 if sec <= t0 else min(1.0, (sec - t0) / 3.0) * 60 * width
                t.scale = (L, width, width)
                t.keyframe_insert("location", frame=s(sec))
                t.keyframe_insert("scale", frame=s(sec))
        # the small pieces: thrown out of the break, slowing, streaking
        for i, (bb, t) in enumerate(self.bits):
            origin = Vector((rnd.uniform(-4, 8), rnd.uniform(-5, 3), rnd.uniform(-3, 2)))
            v = Vector((rnd.uniform(15, 80), rnd.uniform(-16, 16), -rnd.uniform(2, 30)))
            t0 = T_FALL + rnd.uniform(-0.6, 0.6)
            for o in (bb, t):
                o.hide_render = True
                o.keyframe_insert("hide_render", frame=s(t0) - 1)
                o.hide_render = False
                o.keyframe_insert("hide_render", frame=s(t0))
            for sec, k in ((t0, 0.0), (t0 + 1.0, 0.25), (SECONDS, 1.0)):
                bb.location = origin + v * k
                bb.keyframe_insert("location", frame=s(sec))
                t.location = bb.location
                w = rnd.uniform(0.15, 0.35)
                t.scale = (max(0.001, k * rnd.uniform(15, 40)), w, w)
                t.keyframe_insert("location", frame=s(sec))
                t.keyframe_insert("scale", frame=s(sec))
        key(self.trail, ((T_FALL - 1.0, 0), (T_FALL - 0.7, 4.0), (T_FALL + 2.0, 3.0), (SECONDS, 2.0)))
        fo = self.flash_o
        for sec, sc_ in ((T_FALL - 0.05, 0.1), (T_FALL + 0.25, 6.0), (T_FALL + 1.0, 7.5)):
            fo.scale = (sc_, sc_, sc_)
            fo.keyframe_insert("scale", frame=s(sec))
        key(self.flash, ((T_FALL - 0.05, 0), (T_FALL + 0.15, 0.3), (T_FALL + 1.0, 0)))
        for sec, hide in ((0, True), (T_FALL - 0.1, False), (T_FALL + 1.05, True)):    # costs nothing when out
            fo.hide_render = hide
            fo.keyframe_insert("hide_render", frame=s(sec))
        sc.frame_start, sc.frame_end = 1, s(SECONDS) - 1

    # ----------------------------------------------------------------- Shorts
    def short_camera(self, mode):
        """A tall camera for a Short (owner, 2026-10-22: rendered for the
        phone), on the canonical timeline: "fall", from the side and a little
        ahead, the orbiter nose up in the frame, the left wing going and the
        pieces streaking back and down the frame; "close", in on the holed
        panel from ahead and below, the glow getting inside, held while the
        wing lets go."""
        cam, target = self.cam, bpy.data.objects["target"]
        for o in (cam, cam.data, target):
            o.animation_data_clear()
        self.sc.frame_set(1)
        p8 = self.world("lwing_in", self.hole_at)

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        a, b = SHORT[mode]
        if mode == "fall":
            cam_key(a, (-12, -62, 0), (6, 0, -4), 28)
            cam_key(T_FALL + 0.4, (-11, -64, -1), (9, 0, -6), 28)
            cam_key(b, (-8, -70, -3), (16, 0, -11), 26)
        else:
            cam_key(a, p8 + Vector((-9, -8, -5)), p8 + Vector((2, 0, 0.5)), 40)
            cam_key(15.0, p8 + Vector((-3.8, -3.2, -2.3)), p8, 46)
            cam_key(T_FALL - 0.2, p8 + Vector((-3.2, -2.7, -1.9)), p8, 50)
            cam_key(b, p8 + Vector((-12, -14, -4)), p8 + Vector((8, 0, -3)), 34)
        self.sc.frame_start, self.sc.frame_end = s(a), s(b)

    # ---------------------------------------------------------------- anchors
    def anchors(self, first, last):
        sc = self.sc
        pk = edge_at(0.5)[0]
        pts = {
            "panel": ("lwing_in", self.hole_at),
            "edge": ("lwing_in", pk),
            "wing": ("lwing_in", Vector((5.0, -6.5, WING_Z))),
            "nose": ("nose", Vector((-18.3, 0, -0.4))),
            "cabin": ("nose", Vector((-15.3, 0, 1.9))),
            "belly": ("mid", Vector((-4.0, 0, -2.2))),
            "tail": ("aft", Vector((16.4, 0, 9.8))),
        }
        out = {}
        for f in range(first, last + 1):
            sc.frame_set(f)
            row = {}
            for k, (piece, p) in pts.items():
                v = world_to_camera_view(sc, self.cam, self.world(piece, p))
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
    sc.cycles.transparent_max_bounces = 32
    sc.cycles.volume_step_rate = 4.0          # the glows are soft: coarse steps lose nothing
    sc.render.use_persistent_data = True
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.exposure = -0.2
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
