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
AI_START_CANON = 21.8          # on the wide shot, held still just before the fall
T_FALL = 22.0                  # the canonical second the fall begins
# each model's tall Short cameras (kits/*_3d.py short_camera): canonical seconds they cover
SHORT = {"hanging_walkways": {"fall": (21.0, 26.0), "close": (11.5, 23.6)},
         "fuselage": {"fall": (21.0, 26.0), "close": (11.5, 23.8)}}


class TimeMap:
    def __init__(self, seconds=None):
        seconds = seconds or {}
        self.knots_c, self.knots_r = [0.0], [0.0]
        for name, a, b in CANON:
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
        spans = {"fall": (20.0, 28.0), **{n: (a, b) for n, a, b in CANON}}
        a, b = spans[name]
        return self.real(a), self.real(b)


CURRENT = TimeMap()


def use(sheet):
    """Sets the map from a sheet (model_3d.shot_seconds) and returns it."""
    global CURRENT
    CURRENT = TimeMap((sheet or {}).get("model_3d", {}).get("shot_seconds"))
    return CURRENT


def of(sheet):
    return TimeMap((sheet or {}).get("model_3d", {}).get("shot_seconds"))


def ai_start_frame(sheet):
    return of(sheet).frame(AI_START_CANON)
