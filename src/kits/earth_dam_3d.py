"""
Water kit, variant "earth_dam", in 3D (Blender's free bpy module, CPU only):
the 2D kit's partner. A zoned earthfill dam across a canyon of jointed
rock, the reservoir full behind it (the proportions of Teton Dam: 305 ft
high, its crest nearly across a steep canyon), built in vertical slices so
the part at the right abutment can wash out.

One continuous camera path, in shots (canonical seconds, kits/timemap.py):

    establish   0-7     downstream of the dam, looking upstream: the canyon,
                        the dam, the full reservoir behind
    load_path   7-13    in on the right abutment (screen left): a wet spot on
                        the face, then muddy water leaving it
    connection  13-20   push-in on the leak: it grows into a hole, eating
                        upward toward the crest
    fall        20-28   pull back; the crest drops into the hole, the breach
                        widens along the abutment and the reservoir pours
                        through

Right and left are named looking downstream, as the investigation does: the
right abutment is at -x, on screen left from the downstream camera. Water
flows toward -y. For every frame it records where the labelled parts are on
screen (anchors JSON).

    python -m kits.earth_dam_3d sheet.json out_dir [--first N --last M] [--samples S]
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
SHORT = __import__("kits.timemap", fromlist=["SHORT"]).SHORT["earth_dam"]   # the tall Short cameras
CREST_Z = 93.0                       # 305 ft above the riverbed
CREST_W = 10.0
UP_SLOPE, DOWN_SLOPE = 3.0, 2.5      # horizontal per vertical, upstream and downstream faces
# the canyon across the valley (x, height above the riverbed), from the 2D kit's profile
_VAL2D = [(80, 120), (150, 170), (230, 250), (330, 420), (430, 560), (520, 600), (760, 600),
          (860, 540), (960, 400), (1060, 250), (1140, 170), (1200, 120)]
VALLEY = [((x - 640) * 0.8, (600 - y) * 0.24) for x, y in _VAL2D]
LEAK_Z = 52.0                        # El. 5200, where the hole grew
DX = 10.0                            # dam slice width


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


def key(socket, values):
    for sec, v in values:
        socket.default_value = v
        socket.keyframe_insert("default_value", frame=s(sec))


def mesh(name, verts, faces, material, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    for p in me.polygons:
        p.use_smooth = smooth
    return o


def ground_z(x):
    """The canyon floor or wall height at x."""
    for (xa, za), (xb, zb) in zip(VALLEY, VALLEY[1:]):
        if xa <= x <= xb:
            return za + (zb - za) * (x - xa) / (xb - xa)
    return VALLEY[0][1] if x < VALLEY[0][0] else VALLEY[-1][1]


def wall_x(z, side=-1):
    """Where the canyon wall reaches height z, on the right (-1) or left (+1) side."""
    xs = [x / 2 for x in range(-900, 901)]
    xs = xs if side < 0 else xs[::-1]
    for x in xs:
        if ground_z(x) <= z:
            return x
    return 0.0


def face_y(z):
    """The downstream face's y at height z (downstream is -y)."""
    return -CREST_W / 2 - (CREST_Z - z) * DOWN_SLOPE


class Model:
    def __init__(self, sheet):
        self.x_right = wall_x(CREST_Z, -1)
        self.x_left = wall_x(CREST_Z, +1)
        xr = wall_x(LEAK_Z, -1)
        self.hole = Vector((xr + 28.0, face_y(LEAK_Z) - 0.5, LEAK_Z))

    # ------------------------------------------------------------------ scene
    def build(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        rock = mat("rock", (0.16, 0.13, 0.11), 0.9)
        earth = mat("embankment", (0.36, 0.29, 0.20), 0.95)
        crest_m = mat("crest", (0.30, 0.28, 0.25), 0.9)
        self.water_m = mat("reservoir", (0.05, 0.16, 0.24), 0.08, 0.0)
        self.mud_m = mat("mud", (0.30, 0.21, 0.12), 0.25)
        nt = self.mud_m.node_tree                       # churned water: a rough, moving surface
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 0.08
        noise.inputs["Detail"].default_value = 10
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.9
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], nt.nodes["Principled BSDF"].inputs["Normal"])
        self.mud_noise = noise
        ramp = nt.nodes.new("ShaderNodeValToRGB")          # foam where the surface churns
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.55, 0.75
        ramp.color_ramp.elements[0].color = (0.30, 0.21, 0.12, 1)
        ramp.color_ramp.elements[1].color = (0.78, 0.72, 0.62, 1)
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        self.wet_m = mat("wet", (0.22, 0.19, 0.15), 0.4)
        dark = mat("hole", (0.03, 0.025, 0.02), 0.9)
        grass = mat("plain", (0.36, 0.38, 0.22), 0.95)

        # the canyon: the valley profile carried upstream and downstream, with the plain beyond
        ys = (-900.0, 1400.0)
        prof = VALLEY
        verts, faces = [], []
        for y in ys:
            for x, z in prof:
                verts.append((x, y, z))
        n = len(prof)
        for i in range(n - 1):
            faces.append((i, i + 1, n + i + 1, n + i))
        mesh("canyon", verts, faces, rock)
        for side in (-1, 1):                                       # the plain on each rim
            x0 = prof[0][0] if side < 0 else prof[-1][0]
            z0 = prof[0][1] if side < 0 else prof[-1][1]
            x1 = x0 + side * 2500
            mesh(f"plain_{side}", [(x0, ys[0], z0), (x1, ys[0], z0), (x1, ys[1], z0), (x0, ys[1], z0)],
                 [(0, 1, 2, 3)], grass)
        # joints in the abutment rock: dark streaks on the walls
        rnd = random.Random(5)
        jm = mat("joints", (0.12, 0.10, 0.09), 0.9)
        for _ in range(260):
            side = -1 if rnd.random() < 0.55 else 1
            z = rnd.uniform(4, 112)
            x = wall_x(z, side) + side * rnd.uniform(0.0, 2.0)
            y = rnd.uniform(-700, 900)
            ln = rnd.uniform(4, 16)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x - side * 0.3, y, z))
            o = bpy.context.object
            o.scale = (0.4, 0.5, ln) if rnd.random() < 0.6 else (0.4, ln, 0.5)
            o.data.materials.append(jm)

        # the dam in vertical slices across the canyon
        self.slices = []
        x = self.x_right
        while x < self.x_left:
            xa, xb = x, min(x + DX, self.x_left)
            zb = min(ground_z(xa), ground_z(xb)) - 4.0          # sunk into the rock: no steps at the walls
            if zb < CREST_Z - 1:
                v = []
                for xx in (xa, xb):
                    for z in (zb, CREST_Z):
                        v.append((xx, face_y(z), z))                          # downstream face
                        v.append((xx, CREST_W / 2 + (CREST_Z - z) * UP_SLOPE, z))   # upstream face
                # 0: xa down-base, 1: xa up-base, 2: xa down-crest, 3: xa up-crest; 4..7 the same at xb
                f = [(0, 2, 6, 4), (1, 5, 7, 3), (2, 3, 7, 6), (0, 4, 5, 1), (0, 1, 3, 2), (4, 6, 7, 5)]
                o = mesh(f"slice_{len(self.slices):03d}", v, f, earth)
                o.data.materials.append(crest_m)
                o.data.polygons[2].material_index = 1
                self.slices.append((o, (xa + xb) / 2))
            x = xb

        # the reservoir, full to just below the crest, and the river downstream
        self.reservoir = mesh("reservoir", [(-700, 0, 0), (700, 0, 0), (700, 1400, 0), (-700, 1400, 0)],
                              [(0, 1, 2, 3)], self.water_m)
        self.reservoir.location.z = CREST_Z - 1.0
        mesh("river", [(-60, -900, 0.6), (60, -900, 0.6), (60, -240, 0.6), (-60, -240, 0.6)], [(0, 1, 2, 3)],
             self.water_m)

        # the leak: a wet spot, then a hole with muddy water leaving it, down the face
        h = self.hole
        face_tilt = math.atan2(DOWN_SLOPE, -1.0)                       # the spheres' thin axis along the face's normal
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=h, segments=24, ring_count=12)
        self.wet = bpy.context.object
        self.wet.rotation_euler = (face_tilt, 0, 0)
        self.wet.data.materials.append(self.wet_m)
        self.wet.scale = (0.01, 0.01, 0.01)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=h, segments=24, ring_count=12)
        self.hole_o = bpy.context.object
        self.hole_o.rotation_euler = (face_tilt, 0, 0)
        self.hole_o.data.materials.append(dark)
        self.hole_o.scale = (0.01, 0.01, 0.01)
        # the outflow: a muddy tongue running down the face from the hole
        down = (Vector((h.x, face_y(4), 4)) - h)
        self.outflow = mesh("outflow", [(-0.5, 0, 0), (0.5, 0, 0), (0.7, 0, -1), (-0.7, 0, -1)], [(0, 1, 2, 3)],
                            self.mud_m)
        self.outflow.location = h + Vector((0, -0.4, 0))
        self.outflow.rotation_euler = (math.atan2(-DOWN_SLOPE, 1.0), 0, 0)   # lying down the face, downhill
        self.outflow_len = down.length
        self.outflow.scale = (0.01, 0.01, 0.01)
        # the flood through the breach: a muddy torrent, grown at the failure
        prof = [(80, CREST_Z - 10), (0, CREST_Z - 22), (-80, 62), (-200, 38), (-320, 24), (-500, 17), (-900, 12)]
        verts, faces = [], []
        for y, z in prof:
            verts += [(0, y, z), (1, y, z)]
        for i in range(len(prof) - 1):
            faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
        self.flood = mesh("flood", verts, faces, self.mud_m, smooth=True)
        sub = self.flood.modifiers.new("smooth", "SUBSURF")
        sub.levels = sub.render_levels = 2
        self.flood.scale = (0.01, 1, 0.01)

        world = bpy.data.worlds.new("world")
        sc.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.55, 0.68, 0.85, 1)
        bg.inputs["Strength"].default_value = 0.55
        bpy.ops.object.light_add(type="SUN", location=(0, 0, 500))
        sun = bpy.context.object
        sun.data.energy = 2.6
        sun.rotation_euler = (math.radians(45), math.radians(-20), math.radians(-35))
        self.sc = sc

    # -------------------------------------------------------------- animation
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
        h = self.hole

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        cam_key(0, (180, -1050, 260), (0, 0, 45), 35)                       # establish
        cam_key(6.5, (40, -950, 210), (-60, 0, 45), 35)
        cam_key(8.5, h + Vector((160, -420, 90)), h + Vector((20, 0, 10)), 42)   # the right abutment
        cam_key(12.5, h + Vector((120, -360, 70)), h + Vector((10, 0, 5)), 42)
        cam_key(15.0, h + Vector((50, -150, 25)), h, 45)                     # the leak
        cam_key(19.6, h + Vector((32, -100, 18)), h, 48)
        cam_key(21.4, (160, -1150, 230), (-120, 0, 40), 32)                 # the breach
        cam_key(T_FALL + 1.4, (150, -1130, 220), (-120, 0, 38), 32)
        cam_key(SECONDS, (90, -1250, 260), (-100, 0, 30), 30)

        def scale(o, values, base=(1, 1, 1)):
            for sec, k in values:
                o.scale = tuple(b * kk for b, kk in zip(base, k if isinstance(k, tuple) else (k, k, k)))
                o.keyframe_insert("scale", frame=s(sec))

        # the wet spot, the hole, the outflow: growing from the first signs to the breach
        scale(self.wet, ((8.0, 0.01), (9.5, 4.0), (12.5, 9.0), (T_FALL, 14.0)), (1, 0.015, 0.8))   # a stain, flat on the face
        scale(self.hole_o, ((11.0, 0.01), (13.5, 2.0), (17.0, 7.0), (20.0, 13.0), (T_FALL, 18.0)), (1, 0.06, 1.1))
        L = self.outflow_len
        scale(self.outflow, ((10.0, (0.01, 1, 0.01)), (12.0, (3.0, 1, L * 0.5)), (17.0, (9.0, 1, L)),
                             (T_FALL, (18.0, 1, L))))
        # the breach: the slices nearest the right abutment drop and wash out, one after another
        x_end = self.x_right + 240
        for o, xc in self.slices:
            if xc > x_end:
                continue
            k = (xc - self.x_right) / (x_end - self.x_right)
            t0 = T_FALL - 0.3 + 2.6 * k
            o.keyframe_insert("location", frame=s(t0))
            o.location = (0, -30, -25)
            o.keyframe_insert("location", frame=s(t0 + 0.8))
            o.location = (0, -260, -CREST_Z - 20)
            o.keyframe_insert("location", frame=s(t0 + 2.4))
            o.hide_render = False
            o.keyframe_insert("hide_render", frame=s(t0 + 2.3))
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=s(t0 + 2.4))
        for o in (self.wet, self.hole_o, self.outflow):
            o.hide_render = False
            o.keyframe_insert("hide_render", frame=s(T_FALL + 0.2))
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=s(T_FALL + 0.3))
        # the torrent through the gap, and the reservoir going down
        fl = self.flood
        fl.location = (self.x_right - 5, 0, 0)
        fl.keyframe_insert("location", frame=s(T_FALL - 0.2))
        scale(fl, ((T_FALL - 0.2, (0.01, 1, 0.2)), (T_FALL + 1.0, (60.0, 1, 0.7)),
                   (T_FALL + 3.0, (240.0, 1, 1.0)), (SECONDS, (250.0, 1, 0.92))))
        # the churned surface keeps moving downstream
        prefs = bpy.context.preferences.edit
        was, prefs.keyframe_new_interpolation_type = prefs.keyframe_new_interpolation_type, "LINEAR"
        nv = self.mud_noise.inputs["W"] if "W" in self.mud_noise.inputs else None
        if nv is not None:
            self.mud_noise.noise_dimensions = "4D"
            key(nv, ((0, 0.0), (SECONDS, 14.0)))
        prefs.keyframe_new_interpolation_type = was
        r = self.reservoir
        r.keyframe_insert("location", frame=s(T_FALL))
        r.location.z = CREST_Z - 30
        r.keyframe_insert("location", frame=s(SECONDS))
        sc.frame_start, sc.frame_end = 1, s(SECONDS) - 1

    # ----------------------------------------------------------------- Shorts
    def short_camera(self, mode):
        """A tall camera for a Short (owner, 2026-10-22: rendered for the
        phone), on the canonical timeline: "fall", from downstream, the right
        abutment and the face filling the frame, the crest dropping into the
        hole and the reservoir pouring out at the bottom; "close", in on the
        leak as it grows to a hole and eats up toward the crest."""
        cam, target = self.cam, bpy.data.objects["target"]
        for o in (cam, cam.data, target):
            o.animation_data_clear()
        h = self.hole

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        a, b = SHORT[mode]
        if mode == "fall":
            cam_key(a, (-60, -900, 140), (-230, 0, 45), 28)
            cam_key(T_FALL + 0.5, (-50, -920, 130), (-220, 0, 40), 28)
            cam_key(b, (-30, -980, 120), (-200, -100, 25), 26)
        else:
            cam_key(a, h + Vector((90, -260, 50)), h + Vector((0, 0, 10)), 40)
            cam_key(15.0, h + Vector((40, -140, 22)), h, 46)
            cam_key(T_FALL - 0.2, h + Vector((30, -110, 20)), h + Vector((0, 0, 8)), 48)
            cam_key(b, h + Vector((120, -420, 70)), h + Vector((40, 0, 20)), 36)
        self.sc.frame_start, self.sc.frame_end = s(a), s(b)

    # ---------------------------------------------------------------- anchors
    def anchors(self, first, last):
        sc = self.sc
        pts = {
            "hole": self.hole,
            "dam": Vector(((self.x_right + self.x_left) / 2, -CREST_W / 2, CREST_Z)),
            "abutment": Vector((wall_x(70, -1) - 10, -200, 70)),
            "reservoir": Vector((60, 400, CREST_Z - 1)),
            "face": Vector((80, face_y(45), 45)),
        }
        out = {}
        for f in range(first, last + 1):
            sc.frame_set(f)
            row = {}
            for k, p in pts.items():
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
    sc.view_settings.exposure = -0.5
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
