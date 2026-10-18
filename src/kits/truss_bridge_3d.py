"""
Structure kit, variant "truss bridge", in 3D (Blender's free bpy module, CPU
only): a steel deck truss on piers over a river, the joint that fails, the
loads over it. The 2D kit's partner (kits/truss_bridge.py); proportions come
from the sheet's "model_3d" block, the joint and spans from its "kit" block.

The same shot windows as every 3D model (kits/common.py SHOTS_3D):

    establish   0-7     wide drift along the river, the whole bridge, the traffic
    load_path   7-13    the main span: the members meeting at the failed joint
                        glow as the load flows into it
    connection  13-20   push-in on the gusset plate at the joint; it heats, then bows
    fall        20-28   pull back to the wide shot and hold: the AI collapse starts
                        from kits.timemap AI_START_CANON; after T_FALL the accurate
                        3D fall stands in when there is no AI clip

    python -m kits.render3d sheet.json out_dir [--first N --last M] [--samples S]
"""

import json
import math
import os
import random

import bpy
import bmesh  # noqa: E402  (bmesh exists only once bpy is loaded)
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

from kits.hanging_walkway_3d import FPS, s, mat, key, setup_render

SECONDS = 28
T_FALL = 22.0
DECK_Z = 0.0
CHORD, WEB = 0.7, 0.45          # member sizes (m)


def _box_into(bm, p, q, w, h):
    """A box from p to q (world points) with cross-section w x h, into bm."""
    p, q = Vector(p), Vector(q)
    d = q - p
    L = d.length
    if L < 1e-6:
        return
    z = d.normalized()
    up = Vector((0, 0, 1)) if abs(z.z) < 0.95 else Vector((0, 1, 0))
    x = up.cross(z).normalized()
    y = z.cross(x)
    M = Matrix((x, y, z)).transposed()
    verts = []
    for dz in (0, L):
        for dx, dy in ((-w, -h), (w, -h), (w, h), (-w, h)):
            verts.append(bm.verts.new(p + M @ Vector((dx / 2, dy / 2, dz))))
    for f in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([verts[i] for i in f])


class Model:
    def __init__(self, sheet):
        m = sheet.get("model_3d", {})
        k = sheet["kit"]
        spans = [float(v) for v in m.get("span_m", [80, 140, 80])]
        self.L = sum(spans)
        self.x0 = -self.L / 2
        self.piers, x = [], self.x0
        for v in spans[:-1]:
            x += v
            self.piers.append(x)
        self.main = (self.piers[0], self.piers[-1]) if len(self.piers) >= 2 else (self.x0, -self.x0)
        self.n = int(k.get("panels", 24))
        self.dx = self.L / self.n
        self.fail_i = int(k.get("failed_node", self.n // 3))
        self.fail_x = self.x0 + self.fail_i * self.dx
        self.deck_w = float(m.get("deck_width_m", 30))
        self.plane_y = self.deck_w * 0.32
        dmin, dmax = [float(v) for v in m.get("truss_depth_m", [9, 18])]
        self.dmin, self.dmax = dmin, dmax
        self.water = float(m.get("water_level_m", -30))
        self.bed = self.water - 12
        self.with_load = bool(k.get("load_near_node"))

    def depth(self, x):
        d = min(abs(x - p) for p in self.piers) if self.piers else 1e9
        return self.dmin + (self.dmax - self.dmin) * max(0.0, 1 - d / 45) ** 1.5

    def group_of(self, x):
        if x < self.main[0]:
            return "side_l"
        if x > self.main[1]:
            return "side_r"
        return "main"

    def pivot(self, g):
        return {"side_l": Vector((self.x0, 0, DECK_Z)), "side_r": Vector((-self.x0, 0, DECK_Z)),
                "main": Vector(((self.main[0] + self.main[1]) / 2, 0, DECK_Z))}[g]

    # ------------------------------------------------------------------ scene
    def build(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        self.sc = sc
        steel = mat("steel", (0.42, 0.50, 0.48), 0.45, 0.5)       # weathered green-grey paint
        concrete = mat("concrete", (0.36, 0.37, 0.40), 0.85)
        asphalt = mat("asphalt", (0.10, 0.10, 0.11), 0.8)
        land = mat("land", (0.14, 0.16, 0.13), 0.95)
        water = mat("water", (0.02, 0.07, 0.12), 0.08)
        self.hot = mat("plate_hot", (0.45, 0.52, 0.50), 0.4, 0.5, emit=(1.0, 0.16, 0.08))
        self.glow = mat("member_glow", (0.42, 0.50, 0.48), 0.45, 0.5, emit=(1.0, 0.62, 0.1))
        sand = mat("load", (0.75, 0.55, 0.22), 0.9)
        cars = [mat(f"car{i}", c, 0.4, 0.3) for i, c in
                enumerate(((0.6, 0.6, 0.62), (0.15, 0.16, 0.2), (0.5, 0.12, 0.1), (0.75, 0.75, 0.7)))]

        def obj(name, bm, material, g=None):
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            o = bpy.data.objects.new(name, me)
            sc.collection.objects.link(o)
            o.data.materials.append(material)
            if g:
                o.parent = self.roots[g]
            return o

        def box(center, size, material, g=None, name="box"):
            """A box whose origin is its own centre (so it turns about itself)."""
            bm = bmesh.new()
            bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
            o = obj(name, bm, material, g)
            o.location = Vector(center) - (self.pivot(g) if g else Vector())
            return o

        self.roots = {}
        for g in ("side_l", "main", "side_r"):
            e = bpy.data.objects.new(f"root_{g}", None)
            sc.collection.objects.link(e)
            e.location = self.pivot(g)
            self.roots[g] = e

        # terrain: river gorge, banks, water
        box((0, 0, self.bed - 2), (self.L * 3, 600, 4), land)
        box((0, 0, self.water), (self.L * 3, 600, 0.02), water, name="water")
        for sgn in (-1, 1):
            x_edge = -self.x0 * sgn
            box((x_edge + sgn * 150, 0, (self.bed - 6 + DECK_Z - 3) / 2),
                (300, 600, DECK_Z - 3 - self.bed + 6), land)
            box((x_edge + sgn * 4, 0, (DECK_Z - 1 + self.bed) / 2),
                (8, self.deck_w + 4, DECK_Z - 1 - self.bed), concrete)          # abutment
        for x in self.piers:
            top = DECK_Z - 1 - self.depth(x)
            for y in (-self.plane_y, self.plane_y):
                box((x, y, (top + self.bed) / 2), (4, 4, top - self.bed), concrete)
            box((x, 0, top - 1), (5, self.plane_y * 2 + 4, 2), concrete)

        # the truss, one mesh per span group (so each group can fall on its own)
        up = [(self.x0 + i * self.dx, DECK_Z - 1) for i in range(self.n + 1)]
        lo = [(x, DECK_Z - 1 - self.depth(x)) for x, _ in up]
        groups = {g: bmesh.new() for g in self.roots}
        self.diag_at_fail = []
        for y in (-self.plane_y, self.plane_y):
            for i in range(self.n):
                xm = (up[i][0] + up[i + 1][0]) / 2
                g = self.group_of(xm)
                piv = self.pivot(g)
                P = lambda pt: Vector((pt[0], y, pt[1])) - piv
                _box_into(groups[g], P(up[i]), P(up[i + 1]), CHORD, CHORD)
                _box_into(groups[g], P(lo[i]), P(lo[i + 1]), CHORD, CHORD)
                left = i < self.n / 2
                a, b = (up[i], lo[i + 1]) if (i % 2 == 0) == left else (lo[i], up[i + 1])
                if self.fail_i in (i, i + 1) and (a == up[self.fail_i] or b == up[self.fail_i]):
                    self.diag_at_fail.append((Vector((a[0], y, a[1])), Vector((b[0], y, b[1])), g))
                else:
                    _box_into(groups[g], P(a), P(b), WEB, WEB)
            for i in range(self.n + 1):
                g = self.group_of(up[i][0] + (0.01 if i < self.n / 2 else -0.01))
                piv = self.pivot(g)
                _box_into(groups[g], Vector((up[i][0], y, up[i][1])) - piv,
                          Vector((lo[i][0], y, lo[i][1])) - piv, WEB, WEB)
        for i in range(self.n + 1):                     # cross bracing between the planes
            g = self.group_of(up[i][0] + (0.01 if i < self.n / 2 else -0.01))
            piv = self.pivot(g)
            for (x, z) in (up[i], lo[i]):
                _box_into(groups[g], Vector((x, -self.plane_y, z)) - piv,
                          Vector((x, self.plane_y, z)) - piv, WEB, WEB)
        for g, bm in groups.items():
            obj(f"truss_{g}", bm, steel, g)
        for a, b, g in self.diag_at_fail:               # the members meeting at the joint
            bm = bmesh.new()
            _box_into(bm, a - self.pivot(g), b - self.pivot(g), WEB, WEB)
            obj("diag_fail", bm, self.glow, g)

        # gusset plates at every top joint, both planes; the failed ones hot
        self.plates = []
        for i in range(self.n + 1):
            x = self.x0 + i * self.dx
            g = self.group_of(x + (0.01 if i < self.n / 2 else -0.01))
            for y in (-self.plane_y, self.plane_y):
                yy = y + (-0.45 if y < 0 else 0.45)
                o = box((x, yy, DECK_Z - 1.6), (2.6, 0.12, 2.2),
                        self.hot if i == self.fail_i else steel, g, name=f"plate_{i}")
                if i == self.fail_i and y < 0:
                    self.near_plate = o
                    for bx in (-0.9, -0.3, 0.3, 0.9):
                        for bz in (-0.7, 0.0, 0.7):
                            r = box((0, 0, 0), (0.16, 0.12, 0.16), steel, None, name="rivet")
                            r.parent = o
                            r.location = Vector((bx, -0.12, bz))
        # deck, barriers, traffic, the load parked over the joint
        rnd = random.Random(3)
        for g, (xa, xb) in (("side_l", (self.x0, self.main[0])), ("main", self.main),
                            ("side_r", (self.main[1], -self.x0))):
            box(((xa + xb) / 2, 0, DECK_Z - 0.5), (xb - xa - 0.3, self.deck_w, 1.0), asphalt, g)
            for y in (-self.deck_w / 2, 0, self.deck_w / 2):
                box(((xa + xb) / 2, y, DECK_Z + 0.5), (xb - xa - 0.3, 0.4, 1.0), concrete, g)
        lanes = [-14, -10.5, -7, -3.5, 3.5, 7, 10.5, 14]
        for k in range(46):
            x = rnd.uniform(self.x0 + 4, -self.x0 - 4)
            y = rnd.choice(lanes)
            if self.with_load and abs(x - self.fail_x - 10) < 14 and y < 0:
                continue
            box((x, y, DECK_Z + 0.75), (4.5, 1.9, 1.5), rnd.choice(cars), self.group_of(x))
        if self.with_load:
            for k, (dx_, w) in enumerate(((2, 6), (9, 5), (16, 7), (22, 4))):
                x = self.fail_x + dx_
                box((x, -7, DECK_Z + 1.0), (w, 5, 2.0), sand, self.group_of(x), name="load")
        world = bpy.data.worlds.new("world")
        sc.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.05, 0.09, 0.16, 1)
        bg.inputs["Strength"].default_value = 0.8
        bpy.ops.object.light_add(type="SUN", location=(0, 0, 100))
        sun = bpy.context.object
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), math.radians(-25), math.radians(30))

    # -------------------------------------------------------------- animation
    def animate(self):
        sc = self.sc
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        sc.camera = cam
        self.cam = cam
        cam.data.clip_end = 3000
        bpy.ops.object.empty_add()
        target = bpy.context.object
        c = cam.constraints.new("TRACK_TO")
        c.target = target
        c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        fx = self.fail_x
        plate = Vector((fx, -self.plane_y - 0.45, DECK_Z - 1.6))

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        mid = Vector((0, 0, DECK_Z - 12))
        cam_key(0, (-170, -250, 22), mid, 28)                                     # establish
        cam_key(6.0, (-70, -235, 16), mid, 28)
        cam_key(8.5, (fx - 45, -70, 4), (fx, 0, DECK_Z - 8), 32)                  # load path
        cam_key(12.5, (fx - 35, -58, 6), (fx, 0, DECK_Z - 6), 32)
        look_p = plate + Vector((0, 0, -0.6))
        cam_key(15.0, plate + Vector((-9, -15, -4.0)), look_p, 40)               # connection
        cam_key(19.6, plate + Vector((-7, -12, -3.2)), look_p, 40)
        wide_loc, wide_look = (fx - 70, -215, 12), (fx + 40, 0, DECK_Z - 14)
        cam_key(21.4, wide_loc, wide_look, 28)                                    # pull back, hold
        cam_key(T_FALL, wide_loc, wide_look, 28)
        cam_key(SECONDS, (fx - 60, -200, 10), (fx + 40, 0, DECK_Z - 20), 28)

        b = lambda m_: m_.node_tree.nodes["Principled BSDF"]
        key(b(self.glow).inputs["Emission Strength"], ((8.6, 0), (10.0, 5.0), (12.6, 5.0), (13.8, 0)))
        key(b(self.hot).inputs["Emission Strength"], ((10.4, 0), (12.2, 1.5), (15.2, 1.5),
                                                      (17.4, 3.0), (19.4, 4.5), (SECONDS, 4.5)))
        # the plate bows: a slight out-of-plane twist and bulge
        p = self.near_plate
        for sec, rz, sy in ((17.0, 0, 1.0), (19.4, 7, 1.6), (SECONDS, 7, 1.6)):
            p.rotation_euler = (0, 0, math.radians(rz))
            p.scale = (1, sy, 1)
            p.keyframe_insert("rotation_euler", frame=s(sec))
            p.keyframe_insert("scale", frame=s(sec))
        # the accurate 3D fall (stands in when there is no AI clip)
        drop = self.water + 3 - DECK_Z
        R = self.roots
        for g, sec, z, ry in (("main", T_FALL, 0, 0), ("main", T_FALL + 1.1, drop, -2.5),
                              ("side_l", T_FALL + 0.3, 0, 0), ("side_l", T_FALL + 1.5, 0, 14),
                              ("side_r", T_FALL + 0.3, 0, 0), ("side_r", T_FALL + 1.5, 0, -14)):
            o = R[g]
            o.location = self.pivot(g) + Vector((0, 0, z))
            o.rotation_euler = (0, math.radians(ry), 0)
            o.keyframe_insert("location", frame=s(sec))
            o.keyframe_insert("rotation_euler", frame=s(sec))
        sc.frame_start, sc.frame_end = 1, s(SECONDS) - 1

    # ---------------------------------------------------------------- anchors
    def anchors(self, first, last):
        sc, fx = self.sc, self.fail_x
        pts = {
            "node": Vector((fx, -self.plane_y - 0.45, DECK_Z - 1.6)),
            "diag": Vector((fx + self.dx * 0.5, -self.plane_y, DECK_Z - 1 - self.depth(fx) * 0.5)),
            "load": Vector((fx + 12, -7, DECK_Z + 2)),
            "deck": Vector((self.x0 + 30, -self.deck_w / 2, DECK_Z)),
            "truss": Vector((0, -self.plane_y, DECK_Z - 6)),
            "pier": Vector((self.piers[-1], -self.plane_y, (self.water + DECK_Z - self.dmax) / 2)),
            "river": Vector((self.piers[-1] + 30, -80, self.water)),
        }
        out = {}
        for f in range(first, last + 1):
            sc.frame_set(f)
            row = {}
            for k_, p in pts.items():
                v = world_to_camera_view(sc, self.cam, p)
                row[k_] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
            out[f] = row
        return out


def render(sheet, out_dir, first=1, last=None, samples=16, still=0):
    from kits import timemap
    timemap.use(sheet)
    m = Model(sheet)
    m.build()
    m.animate()
    setup_render(m.sc, samples)
    m.sc.view_settings.exposure = -0.2
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
