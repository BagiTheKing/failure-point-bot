"""
Structure kit, variant "hanging walkways", in 3D (Blender's free bpy module,
CPU only). The 2D kit's partner: the same structure, for the analysis shots
and the accurate fall. Dimensions come from the sheet's "model_3d" block.

One continuous camera path, in shots (seconds):

    establish   0-7     wide drift across the atrium, the crowd, the walkways
    load_path   7-13    the middle rod line: the lower rods glow, the load climbs
                        to the 4th-floor beam
    connection  13-20   push-in on the failed connection, the beam turns
                        see-through, the nut heats; at the end it starts to pull through
    fall        20-28   pull back; the upper deck drops onto the lower, both fall

For every frame it also records where the labelled parts are on screen
(anchors JSON), so the 2D labels drawn later follow the 3D model.

    python -m kits.hanging_walkway_3d sheet.json out_dir [--first N --last M] [--samples S]
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
SHOTS = {"establish": (0, 7), "load_path": (7, 13), "connection": (13, 20), "fall": (20, 28)}
SECONDS = 28
T_FALL = 22.0
DECK_T, BEAM_H, BEAM_D, ROD_R, NUT = 0.28, 0.36, 0.22, 0.016, 0.07


def s(sec):
    return int(round(sec * FPS)) + 1


def mat(name, color, rough=0.6, metal=0.0, emit=None):
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


def key(socket, frames_values):
    for sec, v in frames_values:
        socket.default_value = v
        socket.keyframe_insert("default_value", frame=s(sec))


def box(loc, size, material, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.scale = size
    o.data.materials.append(material)
    o.parent = parent
    return o


def cyl(x, y, z0, z1, r, material, parent=None, verts=16):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=z1 - z0, vertices=verts,
                                        location=(x, y, (z0 + z1) / 2))
    o = bpy.context.object
    o.data.materials.append(material)
    o.parent = parent
    return o


def empty(name, parent=None):
    bpy.ops.object.empty_add(location=(0, 0, 0))
    o = bpy.context.object
    o.name = name
    o.parent = parent
    return o


class Model:
    def __init__(self, sheet):
        m = sheet.get("model_3d", {})
        k = sheet["kit"]
        self.L = float(m.get("walk_length", 36.0))
        self.Wd = float(m.get("walk_width", 2.6))
        self.z_up, self.z_lo = [float(z) for z in m.get("level_z", [12.0, 5.0])]
        self.roof = float(m.get("roof_z", 19.5))
        n = int(k.get("rod_lines", 3))
        self.rodx = [-self.L / 2 + self.L / n * (i + 0.5) for i in range(n)]
        self.fx = self.rodx[int(k.get("failed_line", n // 2))]
        self.rody = (-(self.Wd / 2 + 0.15), self.Wd / 2 + 0.15)
        self.conn = Vector((self.fx, self.rody[0], self.z_up - DECK_T - BEAM_H))

    # ------------------------------------------------------------------ scene
    def build(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        concrete = mat("concrete", (0.30, 0.32, 0.36), 0.85)
        steel = mat("steel", (0.55, 0.58, 0.63), 0.4, 0.5)
        deck_m = mat("deck", (0.45, 0.46, 0.5), 0.7)
        glass = mat("glass", (0.6, 0.75, 0.85), 0.1)
        crowd = mat("people", (0.32, 0.36, 0.44), 0.8)
        floor_m = mat("floor", (0.22, 0.21, 0.2), 0.7)
        self.hot = mat("nut_hot", (0.62, 0.64, 0.68), 0.35, 0.8, emit=(1.0, 0.16, 0.08))
        self.glow = mat("rod_glow", (0.55, 0.58, 0.63), 0.4, 0.5, emit=(1.0, 0.62, 0.1))
        self.cut = mat("beam_cut", (0.55, 0.58, 0.63), 0.4, 0.5)
        L, half = self.L, self.L / 2
        span = L + 12
        box((0, 4, -0.1), (span + 24, 30, 0.2), floor_m)
        box((0, 9, 10), (span, 0.4, 22), concrete)
        for x in (-span / 2, span / 2):
            box((x, 4, 10), (0.6, 10, 22), concrete)
        for x in range(int(-span / 2) + 2, int(span / 2) - 1, 4):
            box((x, 2, self.roof + 0.4), (0.25, 12, 0.5), steel)
        for y in (-3.5, 0, 3.5, 7):
            box((0, y, self.roof + 0.9), (span - 2, 0.18, 0.18), steel)
        box((0, 2, self.roof + 1.1), (span - 2, 12, 0.05), glass)
        for z in (self.z_lo, self.z_up, self.z_up + 3.5):
            for x in (-(half + 2), half + 2):
                box((x, 2, z - 0.25), (4, 8, 0.5), concrete)

        self.w_up, self.w_lo = empty("walk_up"), empty("walk_lo")
        lower_rods = empty("lower_rods", self.w_up)
        for z, root in ((self.z_up, self.w_up), (self.z_lo, self.w_lo)):
            box((0, 0, z - DECK_T / 2), (L, self.Wd, DECK_T), deck_m, root)
            for y in (-self.Wd / 2, self.Wd / 2):
                box((0, y, z + 1.0), (L, 0.05, 0.05), steel, root)
                box((0, y, z - DECK_T - 0.2), (L, 0.12, 0.4),
                    self.cut if z == self.z_up else steel, root)
                for x in range(int(-half), int(half) + 1, 2):
                    box((x, y, z + 0.5), (0.04, 0.04, 1.0), steel, root)
            for x in self.rodx:
                m = self.cut if (x == self.fx and z == self.z_up) else steel
                box((x, 0, z - DECK_T - BEAM_H / 2), (BEAM_D, self.Wd + 0.7, BEAM_H), m, root)
        for x in self.rodx:
            for y in self.rody:
                # as built: the upper rod ends under the upper beam (its nut stays on it)
                cyl(x - 0.05, y, self.z_up - DECK_T - BEAM_H - 0.08, self.roof, ROD_R, steel)
                hot = x == self.fx and y == self.rody[0]
                box((x - 0.05, y, self.z_up - DECK_T - BEAM_H - NUT / 2), (NUT * 1.6, NUT * 1.6, NUT),
                    self.hot if hot else steel)
                # the lower rod hangs from a nut inside the upper beam
                cyl(x + 0.05, y, self.z_lo - DECK_T - BEAM_H - 0.08,
                    self.z_up - DECK_T - BEAM_H + 0.06, ROD_R,
                    self.glow if x == self.fx else steel, lower_rods)
                box((x + 0.05, y, self.z_up - DECK_T - BEAM_H + 0.02 + NUT / 2),
                    (NUT * 1.6, NUT * 1.6, NUT), steel, self.w_up)
                box((x + 0.05, y, self.z_lo - DECK_T - BEAM_H - NUT / 2),
                    (NUT * 1.6, NUT * 1.6, NUT), steel, self.w_lo)
        rnd = random.Random(4)

        def person(px, py, pz, parent):
            h = 1.55 + rnd.random() * 0.3
            cyl(px, py, pz, pz + h * 0.82, 0.17, crowd, parent, 10)
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(px, py, pz + h * 0.92),
                                                 segments=10, ring_count=6)
            o = bpy.context.object
            o.data.materials.append(crowd)
            o.parent = parent
        for _ in range(160):
            person(rnd.uniform(-half - 1, half + 1), rnd.uniform(-8, 6), 0, None)
        for root, z, n in ((self.w_up, self.z_up, 16), (self.w_lo, self.z_lo, 20)):
            for _ in range(n):
                person(rnd.uniform(-half + 1, half - 1), rnd.uniform(-0.9, 0.9), z, root)

        world = bpy.data.worlds.new("world")
        sc.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.035, 0.07, 0.13, 1)
        bg.inputs["Strength"].default_value = 0.6
        bpy.ops.object.light_add(type="SUN", location=(0, 0, 40))
        sun = bpy.context.object
        sun.data.energy = 2.4
        sun.rotation_euler = (math.radians(35), math.radians(-20), math.radians(25))
        bpy.ops.object.light_add(type="AREA", location=(0, -14, 14))
        fill = bpy.context.object
        fill.data.energy = 4000
        fill.data.size = 20
        fill.rotation_euler = (math.radians(70), 0, 0)
        self.sc = sc

    # -------------------------------------------------------------- animation
    def animate(self):
        sc = self.sc
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        sc.camera = cam
        self.cam = cam
        target = empty("target")
        c = cam.constraints.new("TRACK_TO")
        c.target = target
        c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        conn, fx = self.conn, self.fx
        mid_z = (self.z_up + self.z_lo) / 2

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        look_c = conn + Vector((0, 0, 0.12))
        cam_key(0, (fx - 14, -26, 7), (fx, 2, 10), 28)                       # establish
        cam_key(6.0, (fx - 6, -24, 8), (fx, 2, 10), 28)
        cam_key(8.5, (fx - 8.0, -14.0, mid_z + 0.5), (fx, 0, mid_z), 32)     # load path
        cam_key(12.5, (fx - 6.5, -12.5, mid_z + 0.8), (fx, 0, mid_z + 0.5), 32)
        cam_key(15.0, conn + Vector((-1.0, -2.3, -0.5)), look_c, 50)        # connection
        cam_key(19.6, conn + Vector((-0.85, -2.0, -0.45)), look_c, 50)
        cam_key(21.4, (fx - 4, -25, 6.5), (fx, 2, 8), 28)                    # fall
        cam_key(T_FALL + 1.2, (fx - 3.5, -24.5, 6.4), (fx, 2, 7), 28)
        cam_key(SECONDS, (fx - 2.5, -21.0, 5.5), (fx, 2, 4), 30)
        # a short shake at impact
        for i, dz in enumerate((0.0, 0.18, -0.14, 0.08, -0.04, 0.0)):
            cam.location = Vector((fx - 3.5, -24.5, 6.4 + dz))
            cam.keyframe_insert("location", frame=s(T_FALL + 1.0) + i * 2)

        b = lambda m: m.node_tree.nodes["Principled BSDF"]
        # the load path: the lower rods on the failed line glow, then the nut
        key(b(self.glow).inputs["Emission Strength"], ((8.6, 0), (10.0, 4.0), (12.6, 4.0), (13.6, 0)))
        key(b(self.hot).inputs["Emission Strength"], ((10.8, 0), (12.4, 3.0), (15.2, 3.0),
                                                      (17.4, 7.0), (19.4, 9.0), (SECONDS, 9.0)))
        # the cutaway
        alpha = b(self.cut).inputs["Alpha"]
        if hasattr(self.cut, "surface_render_method"):
            self.cut.surface_render_method = "BLENDED"
        key(alpha, ((13.6, 1.0), (15.0, 0.22), (19.8, 0.22), (20.8, 1.0)))
        # pull-through: the upper deck sags a few cm over the nut, then the fall
        gap = self.z_up - self.z_lo - (DECK_T + BEAM_H + 0.1)
        drop = self.z_lo - 0.6
        wu, wl = self.w_up, self.w_lo
        for obj, sec, z, rot in ((wu, 17.6, 0.0, 0.0), (wu, 19.4, -0.06, 0.0),
                                 (wu, T_FALL, -0.06, 0.0),
                                 (wu, T_FALL + 0.45, -gap, 0.0),
                                 (wu, T_FALL + 0.95, -gap - drop, 1.5),
                                 (wl, T_FALL + 0.45, 0.0, 0.0), (wl, T_FALL + 0.95, -drop, 0.0)):
            obj.location = (0, 0, z)
            obj.rotation_euler = (math.radians(rot), 0, 0)
            obj.keyframe_insert("location", frame=s(sec))
            obj.keyframe_insert("rotation_euler", frame=s(sec))
        sc.frame_start, sc.frame_end = 1, s(SECONDS) - 1

    # ---------------------------------------------------------------- anchors
    def anchors(self, first, last):
        """Screen position (0-1, y down) of the labelled parts, per frame."""
        sc, conn, fx = self.sc, self.conn, self.fx
        pts = {
            "nut": conn + Vector((-0.05, 0, -0.04)),
            "upper_rod": conn + Vector((-0.05, 0, 0.55)),
            "lower_rod": conn + Vector((0.05, 0, -0.3)),
            "lower_rods_mid": Vector((fx + 0.05, self.rody[0], (self.z_up + self.z_lo) / 2)),
            "upper_deck": Vector((fx - 6, 0, self.z_up)),
            "lower_deck": Vector((fx - 6, 0, self.z_lo)),
        }
        out = {}
        for f in range(first, last + 1):
            sc.frame_set(f)
            row = {}
            for k, p in pts.items():
                if k in ("upper_deck",):
                    p = p + self.w_up.matrix_world.translation
                v = world_to_camera_view(sc, self.cam, p)
                row[k] = [round(v.x, 4), round(1 - v.y, 4), round(v.z, 3)]
            out[f] = row
        return out


def setup_render(sc, samples):
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.fps = FPS
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.render.use_persistent_data = True
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.exposure = -0.6
    views = [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = "AgX" if "AgX" in views else "Filmic"


def render(sheet, out_dir, first=1, last=None, samples=16, still=0):
    m = Model(sheet)
    m.build()
    m.animate()
    setup_render(m.sc, samples)
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
    a = ap.parse_args()
    render(json.load(open(a.sheet)), a.out_dir, a.first, a.last or None, a.samples, a.still)
