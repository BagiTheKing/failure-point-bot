"""
Aircraft kit, variant "fuselage", in 3D (Blender's free bpy module, CPU
only): the 2D kit's partner. A twin-jet airliner in flight over the sea (the
proportions of a Boeing 737-200, no livery), its skin built in pieces so the
section above the floor can tear away.

One continuous camera path, in shots (canonical seconds, kits/timemap.py):

    establish   0-7     alongside the aircraft in flight, the cabin, the wings
    load_path   7-13    the cabin pressure: the frames round the section glow
                        amber, the skin is a balloon stretched every flight
    connection  13-20   push-in on the lap joint: its rivet row turns red hot,
                        a crack runs along it
    fall        20-28   pull back; the skin above the floor tears away in
                        pieces, the cabin lies open to the sky

For every frame it also records where the labelled parts are on screen
(anchors JSON), so the 2D labels drawn later follow the model.

    python -m kits.fuselage_3d sheet.json out_dir [--first N --last M] [--samples S]
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
R = 1.88                              # fuselage radius (m)
X_NOSE, X_TAIL = -15.8, 15.5          # nose forward (-x): seen from the left (-y) it faces left, like the 2D
X_CAB0, X_CAB1 = -10.6, 9.0           # the constant-section cabin
FLOOR_Z = 0.35
SEAM_A = math.radians(140)            # the lap joint's angle round the fuselage (upper left)


def s(sec):
    from kits import timemap
    return timemap.CURRENT.frame(sec)


def mat(name, color, rough=0.5, metal=0.0, emit=None, alpha=1.0):
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


def box(loc, size, material, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object
    o.scale = size
    o.data.materials.append(material)
    if parent:
        o.parent = parent
        o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o


def empty(name, loc=(0, 0, 0), parent=None):
    bpy.ops.object.empty_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.parent = parent
    return o


def shell(name, x0, x1, a0, a1, material, r=R, r1=None, thick=0.06, nx=12, na=24, z1=0.0, profile=None,
          z0=0.0):
    """A piece of the fuselage skin: the surface r(x) round the x axis
    between angles a0..a1 (0 = the right side, pi/2 = the top), x0..x1;
    r1 and z1 taper and lift it towards x1, along `profile` (k -> 0..1 of
    the taper done; straight when None)."""
    r1 = r if r1 is None else r1
    verts, faces = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        k = i / nx
        q = profile(k) if profile else k
        rr, zz = max(0.02, r + (r1 - r) * q), z0 + (z1 - z0) * q
        for j in range(na + 1):
            a = a0 + (a1 - a0) * j / na
            verts.append((x, rr * math.cos(a), zz + rr * math.sin(a)))
    for i in range(nx):
        for j in range(na):
            p = i * (na + 1) + j
            faces.append((p, p + 1, p + na + 2, p + na + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    sol = o.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = thick
    for p in me.polygons:
        p.use_smooth = True
    return o


def surface(name, outline, material, thick=0.2):
    """A flat part (wing, fin, stabiliser) from its outline [(x, y, z)]."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(outline, [], [list(range(len(outline)))])
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    sol = o.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = thick
    sol.offset = 0
    return o


NOSE_R1, NOSE_Z1 = 0.22, -0.6


def nose_profile(k):
    """An airliner nose: it narrows slowly, then faster towards the tip."""
    return k ** 1.8


def nose_at(x):
    """The nose's radius and centre height at x (for parts on its surface)."""
    q = nose_profile(max(0.0, min(1.0, (X_CAB0 - x) / (X_CAB0 - X_NOSE))))
    return R + (NOSE_R1 - R) * q, NOSE_Z1 * q


def cyl_x(x0, x1, y, z, r, material, parent=None, verts=24):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=x1 - x0, vertices=verts,
                                        location=((x0 + x1) / 2, y, z), rotation=(0, math.radians(90), 0))
    o = bpy.context.object
    o.data.materials.append(material)
    o.parent = parent
    return o


class Model:
    def __init__(self, sheet):
        m = sheet.get("model_3d", {})
        self.sec = [float(x) for x in m.get("section_x", [-8.6, -3.1])]   # the piece that tears away
        self.seam_x = float(m.get("seam_x", -6.0))                       # where the camera pushes in
        a = SEAM_A
        self.seam = Vector((self.seam_x, R * math.cos(a), R * math.sin(a)))

    # ------------------------------------------------------------------ scene
    def build(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        skin = mat("skin", (0.86, 0.87, 0.88), 0.35, 0.35)
        belly = mat("belly", (0.62, 0.64, 0.67), 0.4, 0.5)
        dark = mat("glass", (0.03, 0.05, 0.08), 0.15)
        seat_m = mat("seats", (0.16, 0.22, 0.38), 0.8)
        people = mat("people", (0.42, 0.34, 0.30), 0.8)
        floor_m = mat("floor", (0.30, 0.30, 0.32), 0.8)
        engine = mat("engine", (0.7, 0.71, 0.73), 0.3, 0.6)
        sea = mat("sea", (0.03, 0.12, 0.22), 0.25)
        cloud = mat("cloud", (0.95, 0.96, 0.98), 0.9)
        self.ring_m = mat("frames_glow", (0.86, 0.87, 0.88), 0.35, 0.35, emit=(1.0, 0.62, 0.1))
        self.seam_m = mat("seam_hot", (0.7, 0.7, 0.72), 0.3, 0.6, emit=(1.0, 0.16, 0.08))
        self.crack_m = mat("crack", (0.1, 0.02, 0.02), 0.5, 0.0, emit=(1.0, 0.1, 0.05))
        x0s, x1s = self.sec
        lo_a0, lo_a1 = math.radians(172), math.radians(368)      # below the floor line, all round the belly
        up_a0, up_a1 = math.radians(8), math.radians(172)        # above it: what tears away

        # the fuselage: nose cone, cabin before / the section / after, tail cone
        shell("nose", X_CAB0, X_NOSE, 0, 2 * math.pi, skin, R, NOSE_R1, nx=24, na=32, z1=NOSE_Z1,
              profile=nose_profile)
        # the windscreen: a dark band on the nose's surface, round the top
        (ra, za), (rb, zb) = nose_at(X_CAB0 - 1.9), nose_at(X_CAB0 - 2.7)
        shell("windscreen", X_CAB0 - 1.9, X_CAB0 - 2.7, math.radians(28), math.radians(152), dark,
              ra + 0.09, rb + 0.09, thick=0.015, nx=3, na=16, z0=za, z1=zb)    # outside the skin's thickness
        shell("cab_front", X_CAB0, x0s, 0, 2 * math.pi, skin, nx=4, na=32)
        shell("cab_rear", x1s, X_CAB1, 0, 2 * math.pi, skin, nx=16, na=32)
        shell("tail", X_CAB1, X_TAIL, 0, 2 * math.pi, skin, R, 0.3, nx=16, na=32, z1=1.0,
              profile=lambda k: k ** 1.6)
        shell("sec_low", x0s, x1s, lo_a0, lo_a1, skin, nx=8, na=24)
        self.panels = []
        n = 4
        for i in range(n):                                       # the section's upper lobe, in pieces
            xa = x0s + (x1s - x0s) * i / n
            xb = x0s + (x1s - x0s) * (i + 1) / n
            root = empty(f"panel_root_{i}", ((xa + xb) / 2, 0, 1.0))
            for a0, a1 in ((up_a0, math.radians(90)), (math.radians(90), up_a1)):
                p = shell(f"panel_{i}_{int(math.degrees(a0))}", xa, xb, a0, a1, skin, nx=3, na=10)
                p.parent = root
                p.matrix_parent_inverse = root.matrix_world.inverted()
            self.panels.append(root)

        # windows: both sides, a dark row; cockpit glass
        for side in (-1, 1):
            for x in [X_CAB0 + 1.4 + 0.53 * i for i in range(36)]:
                box((x, side * (R + 0.005), 0.55), (0.22, 0.02, 0.3), dark,
                    self.panels[min(3, max(0, int((x - x0s) / ((x1s - x0s) / 4))))] if x0s < x < x1s else None)
        # cabin interior where it will lie open: floor, seats, people
        box(((x0s + x1s) / 2, 0, FLOOR_Z - 0.04), (x1s - x0s + 3, 2 * R - 0.25, 0.08), floor_m)
        rnd = random.Random(3)
        for x in [x0s - 1.0 + 0.82 * i for i in range(int((x1s - x0s + 2) / 0.82))]:
            for y in (-1.05, -0.6, 0.6, 1.05):           # inside the skin: heads stay under the roof
                box((x, y, FLOOR_Z + 0.22), (0.42, 0.4, 0.44), seat_m)
                box((x + 0.19, y, FLOOR_Z + 0.62), (0.07, 0.4, 0.5), seat_m)
                if rnd.random() < 0.75:
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(x + 0.05, y, FLOOR_Z + 0.95),
                                                         segments=10, ring_count=6)
                    o = bpy.context.object
                    o.data.materials.append(people)
        # the frames round the section (they glow with the cabin pressure)
        self.rings = []
        for x in [x0s + i * 0.55 for i in range(int((x1s - x0s) / 0.55) + 1)]:
            bpy.ops.mesh.primitive_torus_add(major_radius=R + 0.02, minor_radius=0.025, location=(x, 0, 0),
                                             rotation=(0, math.radians(90), 0), major_segments=48, minor_segments=6)
            o = bpy.context.object
            o.data.materials.append(self.ring_m)
            self.rings.append(o)
        # the lap joint: a row of rivet heads along the seam, the whole cabin length
        for x in [X_CAB0 + 0.6 + 0.09 * i for i in range(int((X_CAB1 - X_CAB0 - 1.2) / 0.09))]:
            a = SEAM_A
            par = None
            if x0s < x < x1s:
                par = self.panels[min(3, int((x - x0s) / ((x1s - x0s) / 4)))]
            o = box((x, (R + 0.012) * math.cos(a), (R + 0.012) * math.sin(a)), (0.035, 0.035, 0.012), self.seam_m,
                    par, rot=(a - math.pi / 2, 0, 0))
        # the crack: a thin red line along the seam that grows from the push-in point
        self.crack = box((self.seam_x, (R + 0.02) * math.cos(SEAM_A), (R + 0.02) * math.sin(SEAM_A) - 0.04),
                         (0.01, 0.012, 0.012), self.crack_m, rot=(SEAM_A - math.pi / 2, 0, 0))
        # wings (swept back, a little dihedral), engines under them, the tail
        for side in (-1, 1):
            surface(f"wing_{side}", [(-3.2, side * 1.6, -1.0), (2.4, side * 1.6, -1.0),
                                     (8.6, side * 14.4, -0.25), (6.9, side * 14.4, -0.25)], belly, 0.26)
            cyl_x(-4.8, -0.9, side * 4.4, -1.5, 0.6, engine)          # slung close under the wing
            cyl_x(-4.9, -4.7, side * 4.4, -1.5, 0.48, dark)
            box((-2.0, side * 4.4, -1.0), (2.2, 0.14, 0.35), belly)
            surface(f"stab_{side}", [(12.2, side * 0.4, 1.0), (14.6, side * 0.4, 1.0),
                                     (15.9, side * 6.2, 1.25), (14.9, side * 6.2, 1.25)], skin, 0.16)
        fin = surface("fin", [(10.4, 0, 1.5), (14.4, 0, 1.6), (15.6, 0, 7.4), (13.9, 0, 7.4)], skin, 0.24)
        fin.rotation_euler = (math.radians(90), 0, 0)
        fin.location = (0, 0, 0)

        # the world: the sea far below, clouds streaming past, a bright sky
        self.sea = box((0, 0, -900), (40000, 40000, 1), sea)
        self.clouds = empty("clouds")
        for _ in range(55):                          # puffy clusters, well below and around
            cx, cy, cz = rnd.uniform(-4800, 900), rnd.uniform(-300, 1600), rnd.uniform(-260, -90)
            size = rnd.uniform(18, 45)
            for _ in range(rnd.randint(5, 9)):
                bpy.ops.mesh.primitive_ico_sphere_add(radius=1, subdivisions=2,
                                                      location=(cx + rnd.uniform(-1.6, 1.6) * size,
                                                                cy + rnd.uniform(-0.8, 0.8) * size,
                                                                cz + rnd.uniform(0, 0.7) * size))
                o = bpy.context.object
                r_ = size * rnd.uniform(0.5, 1.0)
                o.scale = (r_ * 1.3, r_, r_ * 0.75)
                o.data.materials.append(cloud)
                bpy.ops.object.shade_smooth()
                o.parent = self.clouds
        world = bpy.data.worlds.new("world")
        sc.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (0.32, 0.5, 0.78, 1)
        bg.inputs["Strength"].default_value = 0.9
        bpy.ops.object.light_add(type="SUN", location=(0, 0, 50))
        sun = bpy.context.object
        sun.data.energy = 3.2
        sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(-30))
        self.sc = sc

    # -------------------------------------------------------------- animation
    def animate(self):
        sc = self.sc
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        sc.camera = cam
        self.cam = cam
        cam.data.clip_end = 5000
        target = empty("target")
        c = cam.constraints.new("TRACK_TO")
        c.target = target
        c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
        seam, sx = self.seam, self.seam_x
        mid = (self.sec[0] + self.sec[1]) / 2

        def cam_key(sec, loc, look, lens):
            cam.location = loc
            cam.keyframe_insert("location", frame=s(sec))
            target.location = look
            target.keyframe_insert("location", frame=s(sec))
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=s(sec))

        out = Vector((0, -1, 0.35)).normalized()
        cam_key(0, (-34, -38, 5), (0, 0, 0), 32)                              # establish
        cam_key(6.0, (-18, -40, 6), (0, 0, 0.5), 32)
        cam_key(8.5, (mid - 3, -15, 3.2), (mid, 0, 0.6), 35)                 # load path
        cam_key(12.5, (mid - 1.5, -13.5, 3.8), (mid, 0, 0.8), 35)
        cam_key(15.0, seam + out * 2.6 + Vector((-0.9, 0, 0)), seam, 45)    # connection
        cam_key(19.6, seam + out * 2.2 + Vector((-0.6, 0, 0)), seam, 45)
        cam_key(21.4, (mid - 6, -27, 5.5), (mid + 3, 0, 0.5), 32)            # fall
        cam_key(T_FALL + 1.4, (mid - 5.5, -26, 6), (mid + 2.5, 0, 0.6), 32)
        cam_key(SECONDS, (mid - 3, -16, 8.5), (mid, 0, 0.6), 34)

        b = lambda m: m.node_tree.nodes["Principled BSDF"]
        key(b(self.ring_m).inputs["Emission Strength"], ((8.4, 0), (9.8, 3.0), (12.6, 3.0), (13.6, 0)))
        key(b(self.seam_m).inputs["Emission Strength"], ((13.2, 0), (14.6, 2.5), (17.0, 5.0), (19.6, 8.0),
                                                         (T_FALL, 8.0), (T_FALL + 0.4, 0)))
        key(b(self.crack_m).inputs["Emission Strength"], ((16.0, 0), (16.6, 6.0), (SECONDS, 6.0)))
        # the crack runs along the seam both ways
        cr = self.crack
        for sec, sx_ in ((16.0, 0.01), (19.6, 3.0), (T_FALL, 3.4)):
            cr.scale = (sx_, 0.012, 0.012)
            cr.keyframe_insert("scale", frame=s(sec))
        # the tear: the pieces lift, fold back into the airstream and go, front first
        rnd = random.Random(8)
        for i, p in enumerate(self.panels):
            t0 = T_FALL + 0.15 + i * 0.12
            p.keyframe_insert("location", frame=s(t0))
            p.keyframe_insert("rotation_euler", frame=s(t0))
            base = Vector(p.location)
            p.location = base + Vector((0.6, 0, 0.5))
            p.rotation_euler = (rnd.uniform(-0.2, 0.2), math.radians(25), 0)
            p.keyframe_insert("location", frame=s(t0 + 0.35))
            p.keyframe_insert("rotation_euler", frame=s(t0 + 0.35))
            p.location = base + Vector((rnd.uniform(38, 55), rnd.uniform(-6, 6), rnd.uniform(5, 12)))
            p.rotation_euler = (rnd.uniform(-3, 3), rnd.uniform(2, 5), rnd.uniform(-2, 2))
            p.keyframe_insert("location", frame=s(t0 + 1.6))
            p.keyframe_insert("rotation_euler", frame=s(t0 + 1.6))
        # the frames' glow is a picture of the pressure, not structure: gone with the skin
        for o in self.rings:
            o.hide_render = False
            o.keyframe_insert("hide_render", frame=s(T_FALL))
            o.hide_render = True
            o.keyframe_insert("hide_render", frame=s(T_FALL + 0.2))
        # the aircraft flies on: the clouds stream past below it, at a steady speed
        prefs = bpy.context.preferences.edit
        was, prefs.keyframe_new_interpolation_type = prefs.keyframe_new_interpolation_type, "LINEAR"
        self.clouds.keyframe_insert("location", frame=s(0))
        self.clouds.location = (4200.0, 0, 0)
        self.clouds.keyframe_insert("location", frame=s(SECONDS))
        prefs.keyframe_new_interpolation_type = was
        sc.frame_start, sc.frame_end = 1, s(SECONDS) - 1

    # ---------------------------------------------------------------- anchors
    def anchors(self, first, last):
        sc, seam = self.sc, self.seam
        mid = (self.sec[0] + self.sec[1]) / 2
        pts = {
            "joint": seam,
            "cabin": Vector((mid, -R, 0.6)),
            "skin": Vector((mid + 6.0, R * math.cos(math.radians(150)), R * math.sin(math.radians(150)))),
            "wing": Vector((2.5, -9.0, -0.5)),
            "cockpit": Vector((X_CAB0 - 2.3, -0.95, 0.95)),
            "opening": Vector((mid, 0, R)),
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
    sc.view_settings.exposure = -0.3
    views = [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = "AgX" if "AgX" in views else "Filmic"


def render(sheet, out_dir, first=1, last=None, samples=16, still=0):
    from kits import timemap
    timemap.use(sheet)
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
