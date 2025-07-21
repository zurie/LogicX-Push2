# splash_screen.py

import cairocffi as cairo
import time
from push2_python.constants import DISPLAY_LINE_PIXELS, DISPLAY_N_LINES
from push2_python.constants import FRAME_FORMAT_RGB565

def draw_splash_screen(push_display):
    WIDTH, HEIGHT = DISPLAY_LINE_PIXELS, DISPLAY_N_LINES
    surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)

    # Background
    ctx.set_source_rgb(0.05, 0.05, 0.05)
    ctx.rectangle(0, 0, WIDTH, HEIGHT)
    ctx.fill()

    # App title
    ctx.set_source_rgb(1, 1, 1)
    ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(42)
    ctx.move_to(30, 60)
    ctx.show_text("Logic  •  Push2")

    # Author + credit
    ctx.set_font_size(24)
    ctx.move_to(30, 100)
    ctx.show_text("by Zurie  •  https://github.com/zurie/LogicX-Push2")

    # Version
    ctx.set_font_size(20)
    ctx.move_to(30, 135)
    ctx.show_text("v1.1  •  July 2025")

    # Send to Push2 screen
    buf = surface.get_data()
    import numpy as np
    frame = np.ndarray(shape=(HEIGHT, WIDTH), dtype=np.uint16, buffer=buf).transpose()
    push_display.display_frame(frame, input_format=FRAME_FORMAT_RGB565)

    time.sleep(2)
