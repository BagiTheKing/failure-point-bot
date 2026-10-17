"""
The Hyatt beat in 3D with Blender (the free `bpy` module, no GPU needed):
the atrium, a push-in to the 4th-floor connection, the nut that carries
both walkways turning red and pulling through, then the fall. Our 2D labels
are drawn over the rendered frames afterwards (tools/style_samples.py).

    pip install bpy        # Blender as a Python module, ~400 MB
    python tools/blender_demo.py out_dir [--frames N] [--samples N]
"""

import argparse
import math
import os
import shutil
import subprocess
import sys

import bpy
from mathutils import Vector

FPS = 30
# world in metres. Walkways run along x; the three rod lines are at x = -12, 0, 12
WALK_L, WALK_W, DECK_T = 36.0, 2.6, 0.28
Z4, Z2, ROOF = 12.0, 5.0, 19.5
RODX = (-12.0, 0.0, 12.0)
RODY = (-1.45, 1.45)
BEAM_H, BEAM_D = 0.36, 0.22
ROD_R = 0.016
NUT = 0.07

T_FALL = 12.4           # seconds: the 4th-floor walkway lets go


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


def see_through(m):
    """A material whose opacity can be animated (the cutaway of the box beam)."""
    b = m.node_tree.nodes["Principled BSDF"]
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    return b.inputs["Alpha"]


def box(name, loc, size, material, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    o.data.materials.append(material)
    if parent:
        o.parent = parent
    return o


def cyl(name, x, y, z0, z1, r, material, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=z1 - z0, vertices=16,
                                        location=(x, y, (z0 + z1) / 2))
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    if parent:
        o.parent = parent
    return o


def empty(name):
    bpy.ops.object.empty_add(location=(0, 0, 0))
    o = bpy.context.object
    o.name = name
    return o


def person(x, y, z, material, parent):
    h = 1.55 + (hash((round(x, 2), round(y, 2))) % 30) / 100
    cyl("body", x, y, z, z + h * 0.82, 0.17, material, parent)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(x, y, z + h * 0.92),
                                         segments=12, ring_count=8)
    o = bpy.context.object
    o.data.materials.append(material)
    o.parent = parent


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    concrete = mat("concrete", (0.30, 0.32, 0.36), 0.85)
    steel = mat("steel", (0.55, 0.58, 0.63), 0.4, 0.5)
    deck_m = mat("deck", (0.45, 0.46, 0.5), 0.7)
    glass = mat("glass", (0.6, 0.75, 0.85), 0.1)
    crowd = mat("people", (0.32, 0.36, 0.44), 0.8)
    hot = mat("nut_hot", (0.62, 0.64, 0.68), 0.35, 0.8, emit=(1.0, 0.16, 0.08))
    floor_m = mat("floor", (0.22, 0.21, 0.2), 0.7)

    # atrium: floor, back wall, side walls, roof frame
    box("floor", (0, 4, -0.1), (60, 30, 0.2), floor_m)
    box("backwall", (0, 9, 10), (48, 0.4, 22), concrete)
    for x in (-22, 22):
        box("sidewall", (x, 4, 10), (0.6, 10, 22), concrete)
    for x in range(-20, 21, 4):
        box("truss", (x, 2, ROOF + 0.4), (0.25, 12, 0.5), steel)
    for y in (-3.5, 0, 3.5, 7):
        box("purlin", (0, y, ROOF + 0.9), (42, 0.18, 0.18), steel)
    box("skylight", (0, 2, ROOF + 1.1), (42, 12, 0.05), glass)
    # 4th / 2nd floor slabs on the back wall side, where the walkways start and end
    for z in (Z2, Z4, Z4 + 3.5):
        box("slab", (-20, 2, z - 0.25), (4, 8, 0.5), concrete)
        box("slab", (20, 2, z - 0.25), (4, 8, 0.5), concrete)

    w4, w2 = empty("walk4"), empty("walk2")
    lower_rods = empty("lower_rods")
    lower_rods.parent = w4
    ppl4, ppl2 = empty("ppl4"), empty("ppl2")
    ppl4.parent, ppl2.parent = w4, w2
    cut = mat("beam_cut", (0.55, 0.58, 0.63), 0.4, 0.5)
    for z, root in ((Z4, w4), (Z2, w2)):
        box("deck", (0, 0, z - DECK_T / 2), (WALK_L, WALK_W, DECK_T), deck_m, root)
        for y in (-WALK_W / 2, WALK_W / 2):
            box("rail", (0, y, z + 1.0), (WALK_L, 0.05, 0.05), steel, root)
            box("stringer", (0, y, z - DECK_T - 0.2), (WALK_L, 0.12, 0.4),
                cut if z == Z4 else steel, root)
            for x in range(-18, 19, 2):
                box("post", (x, y, z + 0.5), (0.04, 0.04, 1.0), steel, root)
        for x in RODX:
            m = steel
            if x == 0 and z == Z4:
                m = cut
            box("beam", (x, 0, z - DECK_T - BEAM_H / 2), (BEAM_D, 3.3, BEAM_H), m, root)
    nuts = {}
    for x in RODX:
        for y in RODY:
            # as built: upper rod roof -> under the 4th-floor beam
            cyl("rod_up", x - 0.05, y, Z4 - DECK_T - BEAM_H - 0.08, ROOF, ROD_R, steel)
            # lower rod: from the 4th-floor beam down to under the 2nd-floor beam
            cyl("rod_lo", x + 0.05, y, Z2 - DECK_T - BEAM_H - 0.08, Z4 - DECK_T - BEAM_H + 0.06,
                ROD_R, steel, lower_rods)
            # its nut rests on the 4th-floor beam's bottom flange, inside the box
            box("nut4in", (x + 0.05, y, Z4 - DECK_T - BEAM_H + 0.02 + NUT / 2),
                (NUT * 1.6, NUT * 1.6, NUT), steel, w4)
            n4 = box("nut4", (x - 0.05, y, Z4 - DECK_T - BEAM_H - NUT / 2), (NUT * 1.6, NUT * 1.6, NUT),
                     hot if (x == 0 and y == RODY[0]) else steel)
            nuts[(x, y)] = n4      # stays on its rod: the beam pulls off over it
            box("nut2", (x + 0.05, y, Z2 - DECK_T - BEAM_H - NUT / 2), (NUT * 1.6, NUT * 1.6, NUT),
                steel, w2)
    # crowd: lobby floor and both walkways
    import random
    rnd = random.Random(4)
    for _ in range(150):
        person(rnd.uniform(-19, 19), rnd.uniform(-8, 6), 0, crowd, None)
    for root, z, n in ((ppl4, Z4, 16), (ppl2, Z2, 20)):
        for _ in range(n):
            person(rnd.uniform(-17, 17), rnd.uniform(-0.9, 0.9), z, crowd, root)

    # light: soft sky through the skylight + a warm key
    world = bpy.data.worlds.new("world")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.07, 0.13, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 40))
    sun = bpy.context.object
    sun.data.energy = 2.4
    sun.rotation_euler = (math.radians(35), math.radians(-20), math.radians(25))
    bpy.ops.object.light_add(type="AREA", location=(0, -14, 14))
    fill = bpy.context.object
    fill.data.energy = 4000
    fill.data.size = 20
    fill.rotation_euler = (math.radians(70), 0, 0)
    return sc, w4, w2, hot


def key_cam(cam, target, frame, loc, look):
    cam.location = loc
    cam.keyframe_insert("location", frame=frame)
    target.location = look
    target.keyframe_insert("location", frame=frame)


def animate(sc, w4, w2, hot, frames):
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    sc.camera = cam
    cam.data.lens = 28
    target = empty("target")
    c = cam.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis, c.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    conn = Vector((0, RODY[0], Z4 - DECK_T - BEAM_H))
    s = lambda sec: int(sec * FPS) + 1
    # establishing: slow drift across the atrium
    key_cam(cam, target, s(0), (-14, -26, 7), (0, 2, 10))
    key_cam(cam, target, s(3.2), (-6, -24, 8), (0, 2, 10))
    # push in on the middle 4th-floor connection
    look = conn + Vector((0, 0, 0.12))
    key_cam(cam, target, s(6.0), conn + Vector((-1.0, -2.3, -0.5)), look)
    key_cam(cam, target, s(9.6), conn + Vector((-0.85, -2.0, -0.45)), look)
    for sec, lens in ((3.2, 28), (6.0, 50), (9.6, 50), (11.4, 28)):
        cam.data.lens = lens
        cam.data.keyframe_insert("lens", frame=s(sec))
    # pull back out for the fall
    key_cam(cam, target, s(11.4), (-4, -25, 6.5), (0, 2, 8))
    key_cam(cam, target, s(15), (-3, -24.5, 6.5), (0, 2, 7))
    for fc in (cam.animation_data.action.fcurves if hasattr(cam.animation_data.action, "fcurves") else []):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    # the box beam turns see-through in the close-up so both nuts show
    alpha = see_through(bpy.data.materials["beam_cut"])
    for sec, v in ((5.0, 1.0), (6.4, 0.22), (10.0, 0.22), (11.0, 1.0)):
        alpha.default_value = v
        alpha.keyframe_insert("default_value", frame=s(sec))
    # the nut heats up, then pulls through
    em = hot.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for sec, v in ((6.4, 0.0), (8.6, 6.0), (9.6, 9.0), (15, 9.0)):
        em.default_value = v
        em.keyframe_insert("default_value", frame=s(sec))
    # the fall: the 4th-floor walkway drops onto the 2nd, then both to the floor
    gap = Z4 - Z2 - (DECK_T + BEAM_H + 0.1)
    w4.location = (0, 0, 0)
    w4.keyframe_insert("location", frame=s(T_FALL))
    w2.keyframe_insert("location", frame=s(T_FALL))
    w4.location = (0, 0, -gap)
    w4.keyframe_insert("location", frame=s(T_FALL + 0.5))
    w2.location = (0, 0, 0)
    w2.keyframe_insert("location", frame=s(T_FALL + 0.5))
    drop = Z2 - 0.6
    w4.location = (0, 0, -gap - drop)
    w2.location = (0, 0, -drop)
    w4.rotation_euler = (math.radians(1.5), 0, 0)
    w4.keyframe_insert("location", frame=s(T_FALL + 0.95))
    w4.keyframe_insert("rotation_euler", frame=s(T_FALL + 0.95))
    w2.keyframe_insert("location", frame=s(T_FALL + 0.95))
    sc.frame_start, sc.frame_end = 1, frames


def setup(sc, samples):
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.fps = FPS
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.render.use_persistent_data = True
    sc.view_settings.exposure = -0.6
    views = [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = "AgX" if "AgX" in views else "Filmic"


def render(out_dir, frames, samples, first=1, last=None):
    sc, w4, w2, hot = build()
    animate(sc, w4, w2, hot, frames)
    setup(sc, samples)
    sc.frame_start, sc.frame_end = first, last or frames
    sc.render.image_settings.file_format = "PNG"
    raw = os.path.join(out_dir, "_raw")
    os.makedirs(raw, exist_ok=True)
    sc.render.filepath = os.path.join(raw, "")
    bpy.ops.render.render(animation=True)
    return raw


def overlay(raw, out_dir):
    """Our 2D labels on top of the 3D frames."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import style_samples as S
    from PIL import Image, ImageDraw
    frames = os.path.join(out_dir, "_frames")
    os.makedirs(frames, exist_ok=True)
    files = sorted(f for f in os.listdir(raw) if f.endswith(".png"))
    for i, name in enumerate(files):
        t = i / FPS
        img = Image.open(os.path.join(raw, name)).convert("RGB").resize((S.W * S.SS, S.H * S.SS))
        f = S.Frame()
        f.img, f.d = img, ImageDraw.Draw(img, "RGBA")
        f.caption("Each walkway hung from steel rods fixed to the roof.",
                  S.prog(t, 0.6, 1.2) * (1 - S.prog(t, 3.6, 4.0)))
        la = S.prog(t, 6.6, 7.2) * (1 - S.prog(t, 10.2, 10.6))
        f.text("UPPER ROD  ·  roof to 4th floor", 700, 210, 22, S.CYAN, "Inter-Bold.otf",
               screen=True, alpha=la)
        f.text("LOWER ROD  ·  4th floor to 2nd floor", 700, 520, 22, S.CYAN, "Inter-Bold.otf",
               screen=True, alpha=la)
        lb = S.prog(t, 8.2, 8.8) * (1 - S.prog(t, 10.2, 10.6))
        f.text("2×", 330, 420, 80, S.RED, "InterDisplay-Black.otf", screen=True, alpha=lb, anchor="rs")
        f.text("LOAD ON ONE NUT", 330, 456, 22, S.RED, "Inter-Bold.otf", screen=True, alpha=lb,
               anchor="rs")
        f.caption("A change to the rods doubled the load on this one nut.",
                  S.prog(t, 7.0, 7.5) * (1 - S.prog(t, 10.2, 10.6)))
        lc = S.prog(t, 13.6, 14.2)
        f.text("114 KILLED · 216 INJURED", S.W / 2, 90, 34, S.RED, "Inter-Bold.otf",
               screen=True, alpha=lc, anchor="mm")
        f.done().save(os.path.join(frames, f"{i:05d}.png"))
    mp4 = os.path.join(out_dir, "blender_demo.mp4")
    S._encode(frames, mp4)
    shutil.rmtree(frames)
    return mp4


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--frames", type=int, default=int(15 * FPS))
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--still", type=int, default=0, help="render only this frame")
    ap.add_argument("--first", type=int, default=1, help="render a slice (parallel jobs)")
    ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--overlay", default="", help="only add the labels to rendered frames here")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    if a.overlay:
        print("video:", overlay(a.overlay, a.out_dir))
    elif a.still:
        sc, w4, w2, hot = build()
        animate(sc, w4, w2, hot, a.frames)
        setup(sc, a.samples)
        sc.frame_set(a.still)
        sc.render.filepath = os.path.join(a.out_dir, f"blender_still_{a.still}.png")
        bpy.ops.render.render(write_still=True)
    elif a.first > 1 or a.last:
        print("frames in:", render(a.out_dir, a.frames, a.samples, a.first, a.last or None))
    else:
        raw = render(a.out_dir, a.frames, a.samples)
        print("video:", overlay(raw, a.out_dir))
