"""
The B -> C beat (building, zoom to the connection, doubled load, failure)
drawn with Manim, the free animation engine behind 3Blue1Brown's videos,
to compare against our own Pillow renderer (tools/style_samples.py).

    manim -qm --format mp4 -o manim_demo tools/manim_demo.py HyattBeat
"""

from manim import (DOWN, LEFT, RIGHT, UP, Arrow, Create, Dot, FadeIn, FadeOut,
                   Line, MovingCameraScene, NumberPlane, Rectangle, Text, VGroup,
                   Write, config, rate_functions, ManimColor)

BG = ManimColor.from_rgb((9, 22, 41))
LINE = ManimColor.from_rgb((226, 236, 255))
DIM = ManimColor.from_rgb((120, 146, 186))
RED = ManimColor.from_rgb((255, 75, 58))
AMBER = ManimColor.from_rgb((255, 176, 32))
CYAN = ManimColor.from_rgb((70, 210, 255))
GRIDC = ManimColor.from_rgb((27, 56, 96))

config.background_color = BG
config.pixel_width, config.pixel_height, config.frame_rate = 1280, 720, 30

S = 90.0          # px per Manim unit, so the A-F world coordinates carry over


def P(x, y):
    return [(x - 640) / S, (360 - y) / S, 0]


ROOF_Y, W4_Y, W2_Y, GROUND_Y = 120, 330, 540, 650
RODS = [380, 640, 900]


class HyattBeat(MovingCameraScene):
    def construct(self):
        grid = NumberPlane(x_range=[-12, 12, 0.45], y_range=[-7, 7, 0.45],
                           background_line_style={"stroke_color": GRIDC, "stroke_width": 1,
                                                  "stroke_opacity": 0.6},
                           axis_config={"stroke_opacity": 0})
        self.add(grid)
        walls = VGroup(Line(P(200, 90), P(200, GROUND_Y), color=DIM),
                       Line(P(1080, 90), P(1080, GROUND_Y), color=DIM),
                       Line(P(150, GROUND_Y), P(1130, GROUND_Y), color=LINE, stroke_width=4))
        roof = VGroup(Line(P(220, ROOF_Y), P(1060, ROOF_Y), color=LINE, stroke_width=4),
                      Line(P(220, ROOF_Y - 34), P(1060, ROOF_Y - 34), color=LINE))
        for i, x in enumerate(range(220, 1001, 60)):
            roof.add(Line(P(x, ROOF_Y - (34 if i % 2 else 0)),
                          P(x + 60, ROOF_Y - (0 if i % 2 else 34)), color=DIM, stroke_width=2))

        def walkway(y):
            g = VGroup(Rectangle(width=680 / S, height=10 / S, color=LINE, stroke_width=2)
                       .move_to(P(640, y - 5)))
            for x in RODS:
                g.add(Rectangle(width=44 / S, height=16 / S, color=LINE, stroke_width=2,
                                fill_color=ManimColor.from_rgb((18, 38, 66)), fill_opacity=1)
                      .move_to(P(x, y + 8)))
            return g

        w4, w2 = walkway(W4_Y), walkway(W2_Y)
        upper = VGroup(*[Line(P(x - 4, ROOF_Y), P(x - 4, W4_Y + 19), color=LINE, stroke_width=2)
                         for x in RODS])
        lower = VGroup(*[Line(P(x + 4, W4_Y + 14), P(x + 4, W2_Y + 19), color=LINE, stroke_width=2)
                         for x in RODS])
        nuts4 = VGroup(*[Rectangle(width=10 / S, height=4 / S, color=LINE, fill_opacity=1)
                         .move_to(P(x - 4, W4_Y + 18)) for x in RODS])
        nuts2 = VGroup(*[Rectangle(width=10 / S, height=4 / S, color=LINE, fill_opacity=1)
                         .move_to(P(x + 4, W2_Y + 18)) for x in RODS])
        people = VGroup()
        for y, xs in ((GROUND_Y, range(240, 1050, 34)), (W4_Y - 10, range(330, 960, 52)),
                      (W2_Y - 10, range(330, 960, 46))):
            for x in xs:
                people.add(Dot(P(x, y - 18), radius=3 / S, color=DIM),
                           Rectangle(width=5 / S, height=14 / S, color=DIM, fill_opacity=1,
                                     stroke_width=0).move_to(P(x, y - 7)))

        self.play(Create(walls), run_time=1.2)
        self.play(Create(roof), run_time=1.0)
        self.play(Create(upper), Create(lower), run_time=1.0)
        self.play(FadeIn(w4), FadeIn(w2), FadeIn(nuts4), FadeIn(nuts2), run_time=0.8)
        self.play(FadeIn(people, lag_ratio=0.02), run_time=0.8)
        cap = Text("Each walkway hung from steel rods fixed to the roof.", font_size=22,
                   color=LINE).to_edge(DOWN, buff=0.4)
        self.play(FadeIn(cap), run_time=0.4)
        self.wait(0.6)

        # zoom into the middle 4th-floor connection
        self.play(FadeOut(cap),
                  self.camera.frame.animate.set(width=14.22 / 6).move_to(P(640, W4_Y + 14)),
                  run_time=2.2, rate_func=rate_functions.ease_in_out_sine)
        z = 1 / 6
        a1 = Arrow(P(624, W4_Y - 32), P(624, W4_Y - 2), color=AMBER, buff=0,
                   stroke_width=5, max_tip_length_to_length_ratio=0.3)
        t1 = Text("4th-floor walkway", font_size=22 * z * 1.4, color=AMBER).next_to(a1, LEFT, 0.05)
        a2 = Arrow(P(652, W4_Y + 34), P(652, W4_Y + 60), color=AMBER, buff=0, stroke_width=5,
                   max_tip_length_to_length_ratio=0.3)
        t2 = Text("2nd-floor walkway", font_size=22 * z * 1.4, color=AMBER).next_to(a2, RIGHT, 0.05)
        self.play(Create(a1), Write(t1), run_time=0.9)
        self.play(Create(a2), Write(t2), run_time=0.9)
        nut = nuts4[1]
        big = Text("2× LOAD ON ONE NUT", font_size=30 * z * 1.4, color=RED).move_to(P(560, W4_Y + 50))
        self.play(nut.animate.set_color(RED), FadeIn(big), w4[2].animate.set_stroke(RED),
                  run_time=1.2)
        self.wait(0.5)

        # failure: zoom back out, the 4th-floor walkway falls onto the 2nd, both fall
        self.play(FadeOut(VGroup(a1, a2, t1, t2, big)),
                  self.camera.frame.animate.set(width=14.22).move_to(P(640, 360)),
                  run_time=1.4, rate_func=rate_functions.ease_in_out_sine)
        top_people = VGroup(*people[2 * len(range(240, 1050, 34)):
                                    2 * (len(range(240, 1050, 34)) + len(range(330, 960, 52)))])
        mid_people = VGroup(*people[2 * (len(range(240, 1050, 34)) + len(range(330, 960, 52))):])
        upper4 = VGroup(w4, nuts4, lower, top_people)
        gap = (W2_Y - W4_Y - 26) / S
        self.play(upper4.animate.shift(DOWN * gap), run_time=0.45, rate_func=rate_functions.ease_in_quad)
        both = VGroup(upper4, w2, nuts2, mid_people)
        self.play(both.animate.shift(DOWN * (GROUND_Y - W2_Y - 20) / S), run_time=0.45,
                  rate_func=rate_functions.ease_in_quad)
        end = Text("114 killed · 216 injured", font_size=34, color=RED).to_edge(UP, buff=0.9)
        self.play(FadeIn(end), run_time=0.6)
        self.wait(1.2)
