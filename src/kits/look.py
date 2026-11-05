"""
The models' finish (owner, 2026-11-05: "make every aspect of the video as
best as it can be"; next to Sabin Civil Engineering's Silver Bridge our
renders read as drafts: flat grey sky, plastic steel, boxes for cars, a
mirror for a river). Everything here is built in Blender: a physical sky
with the sun where it was, surfaces made of noise (paint, grime, rust,
ripples, dead grass), cars with a body, a cabin, glass and wheels, and a
lens with depth. No downloads, so the free runners render it as they are.

    from kits import look
    look.sky(scene, elevation_deg=2.0, azimuth_deg=238)      # 15 Dec 1967, 4:58 pm, Point Pleasant
    steel = look.painted_steel("steel", paint=(0.62, 0.63, 0.64))
    car = look.car("car3", "sedan", paint=(0.55, 0.10, 0.08), at=(x, y, z))
"""

import math
import os

import bpy
from mathutils import Vector


def enabled():
    """The finish is on unless FP_LOOK=0 (a quick draft render)."""
    return os.getenv("FP_LOOK", "1") != "0"


def _nodes(m):
    m.use_nodes = True
    nt = m.node_tree
    return nt, nt.nodes["Principled BSDF"]


def _noise(nt, scale, detail=6.0, roughness=0.6, coords="Object", stretch=(1, 1, 1)):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = roughness
    if stretch != (1, 1, 1):
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = stretch
        nt.links.new(tc.outputs[coords], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    else:
        nt.links.new(tc.outputs[coords], n.inputs["Vector"])
    return n


def _ramp(nt, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (pos, col) in zip(els, stops):
        e.position = pos
        e.color = (*col, 1)
    return r


def _bump(nt, b, height, strength, distance=0.1):
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = distance
    nt.links.new(height, bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])


def painted_steel(name, paint=(0.62, 0.63, 0.64), grime=(0.34, 0.32, 0.29), rust=(0.30, 0.15, 0.07),
                  metal=0.7, emit=None):
    """Steel under aluminium paint after forty years: the paint, grime in
    patches, a little rust where it gathers. Scale in model units (feet)."""
    m = bpy.data.materials.new(name)
    nt, b = _nodes(m)
    n = _noise(nt, 0.06, 8.0, 0.62)
    r = _ramp(nt, [(0.0, paint), (0.52, paint), (0.68, grime), (0.86, rust)])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    fine = _noise(nt, 1.5, 4.0, 0.5)
    rr = _ramp(nt, [(0.0, (0.28, 0.28, 0.28)), (1.0, (0.62, 0.62, 0.62))])
    nt.links.new(fine.outputs["Fac"], rr.inputs["Fac"])
    nt.links.new(rr.outputs["Color"], b.inputs["Roughness"])
    b.inputs["Metallic"].default_value = metal
    _bump(nt, b, fine.outputs["Fac"], 0.15, 0.05)
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 0.0
    return m


def river(name, color=(0.045, 0.075, 0.07)):
    """A wide river under a low sun: dark, glossy, rippled across the flow
    so it breaks the sky's reflection into streaks."""
    m = bpy.data.materials.new(name)
    nt, b = _nodes(m)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Metallic"].default_value = 0.0
    n = _noise(nt, 0.05, 10.0, 0.65, stretch=(3.0, 0.6, 1.0))
    _bump(nt, b, n.outputs["Fac"], 0.35, 0.5)
    return m


def ground(name, a=(0.15, 0.13, 0.08), b_=(0.09, 0.10, 0.06)):
    """December banks: dead grass and earth in patches."""
    m = bpy.data.materials.new(name)
    nt, b = _nodes(m)
    n = _noise(nt, 0.01, 8.0, 0.65)
    r = _ramp(nt, [(0.3, a), (0.7, b_)])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    fine = _noise(nt, 0.8, 6.0, 0.6)
    _bump(nt, b, fine.outputs["Fac"], 0.4, 0.3)
    return m


def concrete(name, color=(0.50, 0.48, 0.45)):
    m = bpy.data.materials.new(name)
    nt, b = _nodes(m)
    n = _noise(nt, 0.3, 8.0, 0.6)
    r = _ramp(nt, [(0.2, color), (0.8, tuple(c * 0.72 for c in color))])
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    _bump(nt, b, n.outputs["Fac"], 0.25, 0.2)
    return m


def car_paint(name, color):
    m = bpy.data.materials.new(name)
    nt, b = _nodes(m)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.35
    b.inputs["Metallic"].default_value = 0.2
    if "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = 0.6
    return m


_SHARED = {}


def _shared(name, color, rough, metal=0.0):
    if name not in _SHARED or _SHARED[name].name not in bpy.data.materials:
        m = bpy.data.materials.new(name)
        nt, b = _nodes(m)
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        _SHARED[name] = m
    return _SHARED[name]


def _box(verts, faces, x0, x1, y0, y1, z0, z1, mi, mats):
    k = len(verts)
    verts += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
              (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        faces.append(tuple(k + i for i in f))
        mats.append(mi)


def _wheel(verts, faces, cx, cy, r, w, mi, mats, n=10):
    k = len(verts)
    for side in (cy - w / 2, cy + w / 2):
        for i in range(n):
            a = 2 * math.pi * i / n
            verts.append((cx + r * math.cos(a), side, r + r * math.sin(a)))
    faces.append(tuple(k + i for i in range(n))[::-1])
    mats.append(mi)
    faces.append(tuple(k + n + i for i in range(n)))
    mats.append(mi)
    for i in range(n):
        j = (i + 1) % n
        faces.append((k + i, k + j, k + n + j, k + n + i))
        mats.append(mi)


def car(name, kind, paint, at, heading=1):
    """A 1960s vehicle in one mesh, its origin under its middle at road
    level (so it falls and turns about itself): "sedan", long and low, or
    "truck", a cab and a box. heading: +1 drives along +x, -1 along -x."""
    verts, faces, mats = [], [], []
    if kind == "truck":
        L, W = 30.0, 7.6
        _box(verts, faces, -L / 2, L / 2 - 8, -W / 2, W / 2, 1.6, 12.5, 0, mats)          # the box
        _box(verts, faces, L / 2 - 7.5, L / 2, -W / 2, W / 2, 1.6, 6.0, 0, mats)           # the cab
        _box(verts, faces, L / 2 - 6.5, L / 2 - 1.5, -W / 2 + 0.3, W / 2 - 0.3, 6.0, 9.0, 1, mats)
        axles = (-L / 2 + 4, -L / 2 + 8, L / 2 - 4)
        r = 1.6
    else:
        L, W = 17.5, 6.6
        _box(verts, faces, -L / 2, L / 2, -W / 2, W / 2, 1.1, 3.6, 0, mats)                # the body
        _box(verts, faces, -L / 2 + 4.6, L / 2 - 5.2, -W / 2 + 0.45, W / 2 - 0.45, 3.6, 5.3, 1, mats)
        axles = (-L / 2 + 3.3, L / 2 - 3.3)
        r = 1.15
    for ax in axles:
        for sy in (-1, 1):
            _wheel(verts, faces, ax, sy * (W / 2 - 0.5), r, 0.9, 2, mats)
    if heading < 0:
        verts = [(-x, -y, z) for x, y, z in verts]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.materials.append(car_paint(name + "_paint", paint))
    me.materials.append(_shared("glass", (0.02, 0.025, 0.03), 0.05, 0.0))
    me.materials.append(_shared("tyre", (0.02, 0.02, 0.02), 0.85, 0.0))
    for p, mi in zip(me.polygons, mats):
        p.material_index = mi
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.location = at
    return o


def sky(sc, elevation_deg, azimuth_deg, strength=0.22, sun_energy=3.0, warm=(1.0, 0.78, 0.55)):
    """A physical sky with the sun where it stood (azimuth from north, +y,
    clockwise), and a sun lamp along the same line so the shading and the
    glow agree. Low sun: long shadows, warm light, a pale blue overhead."""
    world = sc.world or bpy.data.worlds.new("world")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    sk = nt.nodes.new("ShaderNodeTexSky")
    for t in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
        try:
            sk.sky_type = t
            break
        except TypeError:
            continue
    el, az = math.radians(elevation_deg), math.radians(azimuth_deg)
    sun_vec = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    if hasattr(sk, "sun_elevation"):
        sk.sun_elevation = el
        # the sky's sun_rotation turns the sun about the zenith from +x, counter-clockwise
        sk.sun_rotation = math.atan2(sun_vec.y, sun_vec.x)
        sk.sun_disc = True
        if hasattr(sk, "aerosol_density"):
            sk.aerosol_density = 1.2                        # a little haze over a river valley in winter
    else:
        sk.sun_direction = sun_vec
    nt.links.new(sk.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    for o in [o for o in sc.objects if o.type == "LIGHT" and o.data.type == "SUN"]:
        bpy.data.objects.remove(o)
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 500))
    sun = bpy.context.object
    sun.data.energy = sun_energy
    sun.data.color = warm
    sun.data.angle = math.radians(1.0)
    sun.rotation_mode = "QUATERNION"
    sun.rotation_quaternion = (-sun_vec).to_track_quat("-Z", "Y")
    return sun


def lens(cam, target, fstop=4.0):
    """Depth of field on the target the camera tracks: a close-up softens
    what is behind the joint; a wide shot, hundreds of feet out, stays sharp."""
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = target
    cam.data.dof.aperture_fstop = fstop


def finish(sc, motion_blur=True):
    """Render settings for the finish: motion blur on falling parts, a
    filmic contrast."""
    sc.render.use_motion_blur = motion_blur
    sc.render.motion_blur_shutter = 0.5
    looks = [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items]
    for want in ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Punchy"):
        if want in looks:
            sc.view_settings.look = want
            break


def valley(name, river_axis="y", floor=1200.0, rise=3500.0, base_z=11.5, height=280.0, extent=12000.0, n=320):
    """Wooded winter hills either side of a river valley (the Ohio at Point
    Pleasant runs between hills a few hundred feet high): flat valley floor
    within `floor` of the river's line, rising to `height` by `rise`, so the
    horizon is hills instead of the edge of the world."""
    def smooth(a, b, v):
        t = min(1.0, max(0.0, (v - a) / (b - a)))
        return t * t * (3 - 2 * t)

    verts, faces = [], []
    for i in range(n + 1):
        for j in range(n + 1):
            u = -extent + 2 * extent * i / n
            v = -extent + 2 * extent * j / n
            across, along = (u, v) if river_axis == "y" else (v, u)
            k = smooth(floor, rise, abs(across))
            h = k * (height + 90 * math.sin(along / 900.0 + across / 1300.0) + 60 * math.sin(along / 370.0)
                     + 35 * math.sin(across / 210.0 + along / 520.0)
                     # ridges and hollows, so the slopes are not smooth dunes
                     + 22 * math.sin(along / 140.0 + 2.1 * math.sin(across / 300.0))
                     + 14 * math.sin(across / 95.0 + along / 160.0))
            verts.append((u, v, base_z + max(0.0, h)))
    for i in range(n):
        for j in range(n):
            a = i * (n + 1) + j
            quad = (a, a + n + 1, a + n + 2, a + 1)
            # no floor over the river and its banks: the model's own meshes are there
            if max(abs(verts[q][0 if river_axis == "y" else 1]) for q in quad) < floor * 0.75:
                continue
            faces.append(quad)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    m = bpy.data.materials.new(name + "_mat")
    nt, b = _nodes(m)
    # bare winter woods: grey-brown crowns, darker hollows, clumped at the scale of trees
    trees = _noise(nt, 0.12, 10.0, 0.75)
    woods = _noise(nt, 0.0016, 6.0, 0.6)                      # whole woods, a few hundred feet across
    r = _ramp(nt, [(0.35, (0.030, 0.034, 0.026)), (0.50, (0.060, 0.052, 0.040)), (0.65, (0.045, 0.050, 0.035))])
    nt.links.new(woods.outputs["Fac"], r.inputs["Fac"])
    fine = _ramp(nt, [(0.25, (0.55, 0.55, 0.55)), (0.75, (1.0, 1.0, 1.0))])
    nt.links.new(trees.outputs["Fac"], fine.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    nt.links.new(r.outputs["Color"], mix.inputs[6])
    nt.links.new(fine.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 1.0
    _bump(nt, b, trees.outputs["Fac"], 1.0, 14.0)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    return o
