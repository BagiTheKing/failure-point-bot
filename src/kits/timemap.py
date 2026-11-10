"""
Step 5b: the 3D shots last as long as their narration.

Every 3D model is animated on one canonical timeline (kits/common.py
SHOTS_3D): establish 0-7 s, load path 7-13, connection 13-20, then the
pull-back 20-21.4, the hold on the wide shot 21.4-22 (the AI collapse starts
here) and the 3D fall 22-28. A TimeMap stretches each segment to the length
the pipeline asks for (the sheet's model_3d.shot_seconds), piecewise
linearly, so camera moves slow down or speed up with the voice. The 3D
render, the label overlay and the assembler all use the same map, so the
labels, the captions and the AI start frame stay on their parts.

Pure Python (no bpy): the assembler imports it too.
"""

FPS = 30
CANON = [("establish", 0.0, 7.0), ("load_path", 7.0, 13.0), ("connection", 13.0, 20.0),
         ("pull", 20.0, 21.4), ("hold", 21.4, 22.0), ("drop", 22.0, 28.0)]
T_FALL = 22.0                  # the canonical second the fall begins
# a model whose collapse is the centrepiece runs a longer drop (owner,
# 2026-11-09: the collapse 30 to 60 s, close, step by step, from many angles;
# the Tacoma Narrows model, kits/narrows_3d.py, variant "flutter")
CANONS = {"flutter": CANON[:-1] + [("drop", 22.0, 70.0)]}
# each model's tall Short cameras (kits/*_3d.py short_camera): canonical seconds they cover
SHORT = {"hanging_walkways": {"fall": (21.0, 26.0), "close": (11.5, 23.6)},
         "orbiter": {"fall": (21.0, 26.5), "close": (11.5, 23.8)},
         "earth_dam": {"fall": (21.0, 27.0), "close": (11.5, 23.5)},
         "eyebar_chain": {"fall": (21.0, 27.0), "close": (11.5, 23.0)},
         "fuselage": {"fall": (21.0, 26.0), "close": (11.5, 23.8)},
         "flutter": {"fall": (21.0, 30.0), "close": (13.0, 22.0)}}


class TimeMap:
    def __init__(self, seconds=None, canon=None):
        seconds = seconds or {}
        self.canon_list = canon or CANON
        self.end = self.canon_list[-1][2]          # the canonical last second (28, or longer)
        self.knots_c, self.knots_r = [0.0], [0.0]
        for name, a, b in self.canon_list:
            dur = float(seconds.get(name) or (b - a))
            self.knots_c.append(b)
            self.knots_r.append(self.knots_r[-1] + max(0.2, dur))
        self.total = self.knots_r[-1]

    @staticmethod
    def _interp(x, xs, ys):
        if x <= xs[0]:
            return ys[0] + (x - xs[0])
        for i in range(1, len(xs)):
            if x <= xs[i]:
                f = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
                return ys[i - 1] + f * (ys[i] - ys[i - 1])
        return ys[-1] + (x - xs[-1])

    def real(self, canon_t):
        return self._interp(canon_t, self.knots_c, self.knots_r)

    def canon(self, real_t):
        return self._interp(real_t, self.knots_r, self.knots_c)

    def frame(self, canon_t):
        return int(round(self.real(canon_t) * FPS)) + 1

    def window(self, name):
        """A canonical shot (or segment) window in real seconds."""
        spans = {"fall": (20.0, self.end), **{n: (a, b) for n, a, b in self.canon_list}}
        a, b = spans[name]
        return self.real(a), self.real(b)


CURRENT = TimeMap()


def use(sheet):
    """Sets the map from a sheet (model_3d.shot_seconds) and returns it."""
    global CURRENT
    CURRENT = of(sheet)
    return CURRENT


def canon_of(sheet):
    return CANONS.get(((sheet or {}).get("kit") or {}).get("variant"), CANON)


def of(sheet):
    return TimeMap((sheet or {}).get("model_3d", {}).get("shot_seconds"), canon_of(sheet))

