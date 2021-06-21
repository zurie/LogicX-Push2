import cairo
import definitions
import push2_python


def show_title(ctx, x, h, text, color=[1, 1, 1]):
    text = str(text)
    ctx.set_source_rgb(*color)
    ctx.select_font_face("Apple SD Gothic Neo", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    font_size = h//12
    ctx.set_font_size(font_size)
    ctx.move_to(x + 3, 20)
    ctx.show_text(text)


def show_value(ctx, x, h, text, color=[1, 1, 1]):
    text = str(text)
    ctx.set_source_rgb(*color)
    ctx.select_font_face("Apple SD Gothic Neo", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    font_size = h//8
    ctx.set_font_size(font_size)
    ctx.move_to(x + 3, 45)
    ctx.show_text(text)


def draw_text_at(ctx, x, y, text, font_size = 12, color=[1, 1, 1]):
    text = str(text)
    ctx.set_source_rgb(*color)
    ctx.select_font_face("Apple SD Gothic Neo", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(font_size)
    ctx.move_to(x, y)
    ctx.show_text(text)


def show_text(ctx, x_part, pixels_from_top, text, height=20, font_color=definitions.WHITE, background_color=None, margin_left=4, margin_top=4, font_size_percentage=0.8, center_vertically=True, center_horizontally=definitions.CENTER_LABELS, rectangle_padding=0, rectangle_width_percentage=1.0):
    assert 0 <= x_part < 8
    assert type(x_part) == int

    display_w = push2_python.constants.DISPLAY_LINE_PIXELS
    display_h = push2_python.constants.DISPLAY_N_LINES
    part_w = display_w // 8
    x1 = part_w * x_part
    y1 = pixels_from_top

    ctx.save()

    if background_color is not None:
        ctx.set_source_rgb(*definitions.get_color_rgb_float(background_color))
        ctx.rectangle(x1 + rectangle_padding, y1 + rectangle_padding, rectangle_width_percentage * (part_w - rectangle_padding * 2), height - rectangle_padding * 2)
        ctx.fill()
    ctx.set_source_rgb(*definitions.get_color_rgb_float(font_color))
    ctx.select_font_face("Apple SD Gothic Neo", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    font_size = round(int(height * font_size_percentage))
    text_lines = text.split('\n')
    n_lines = len(text_lines)
    if center_vertically:
        margin_top = (height - font_size * n_lines) // 2
    ctx.set_font_size(font_size)
    for i, line in enumerate(text_lines):
        if center_horizontally:
            (_, _, l_width, _, _, _) = ctx.text_extents(line)
            ctx.move_to(x1 + part_w/2 - l_width/2, y1 + font_size * (i + 1) + margin_top - 2)
        else:
            ctx.move_to(x1 + margin_left, y1 + font_size * (i + 1) + margin_top - 2)
        ctx.show_text(line)

    ctx.restore()

def show_notification(ctx, text, opacity=1.0):
    ctx.save()

    # Background
    display_w = push2_python.constants.DISPLAY_LINE_PIXELS
    display_h = push2_python.constants.DISPLAY_N_LINES
    initial_bg_opacity = 0.8
    ctx.set_source_rgba(0.0, 0.0, 0.0, initial_bg_opacity * opacity)
    ctx.rectangle(0, 0, display_w, display_h)
    ctx.fill()

    # Text
    initial_text_opacity = 1.0
    ctx.set_source_rgba(1.0, 1.0, 1.0, initial_text_opacity * opacity)
    font_size = display_h // 4
    ctx.set_font_size(font_size)
    margin_left = 8
    ctx.move_to(margin_left, 2.2 * font_size)
    ctx.show_text(text)

    ctx.restore()
