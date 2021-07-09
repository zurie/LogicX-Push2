import cairocffi as cairo
import definitions
import push2_python


def show_title(ctx, x, h, text, color=[1, 1, 1]):
    text = str(text)
    ctx.set_source_rgb(*color)
    ctx.select_font_face("Apple SD Gothic Neo", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    font_size = h // 12
    ctx.set_font_size(font_size)
    ctx.move_to(x + 3, 20)
    ctx.show_text(text)


def show_value(ctx, x, h, text, color=[1, 1, 1]):
    text = str(text)
    ctx.set_source_rgb(*color)
    ctx.select_font_face("Apple SD Gothic Neo", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    font_size = h // 8
    ctx.set_font_size(font_size)
    ctx.move_to(x + 3, 45)
    ctx.show_text(text)


def show_bigvalue(ctx, x, h, text, color=[1, 1, 1]):
    text = str(text)
    ctx.set_source_rgb(*color)
    ctx.select_font_face("Apple SD Gothic Neo", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    font_size = h // 2
    ctx.set_font_size(font_size)
    ctx.move_to(x + 3, 100)
    ctx.show_text(text)


def draw_text_at(ctx, x, y, text, font_size=12, color=[1, 1, 1]):
    text = str(text)
    ctx.set_source_rgb(*color)
    ctx.select_font_face("Apple SD Gothic Neo", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(font_size)
    ctx.move_to(x, y)
    ctx.show_text(text)


def show_text(ctx, x_part, pixels_from_top, text, height=20, font_color=definitions.WHITE, background_color=None,
              margin_left=4, margin_top=4, font_size_percentage=0.8, center_vertically=True,
              center_horizontally=definitions.CENTER_LABELS, rectangle_padding=0, rectangle_width_percentage=1.0):
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
        ctx.rectangle(x1 + rectangle_padding, y1 + rectangle_padding,
                      rectangle_width_percentage * (part_w - rectangle_padding * 2), height - rectangle_padding * 2)
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
            ctx.move_to(x1 + part_w / 2 - l_width / 2, y1 + font_size * (i + 1) + margin_top - 2)
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


def show_help(ctx, title, hotkey, path, description, color, opacity=1.0):
    ctx.save()

    # Background
    display_w = push2_python.constants.DISPLAY_LINE_PIXELS
    display_h = push2_python.constants.DISPLAY_N_LINES
    initial_bg_opacity = 1
    ctx.set_source_rgba(0.0, 0.0, 0.0, initial_bg_opacity * opacity)
    ctx.rectangle(0, 0, display_w, display_h)
    ctx.fill()

    ctx.set_source_rgba(0.10, 0.10, 0.10, initial_bg_opacity * opacity)
    ctx.rectangle(0, 0, 200, display_h)
    ctx.fill()

    ctx.set_source_rgba(0.2, 0.2, 0.2, initial_bg_opacity * opacity)
    ctx.rectangle(0, display_h/3, 200, (display_h/3))
    ctx.fill()

    ctx.set_source_rgba(*definitions.get_color_rgb_float(color), initial_bg_opacity * opacity)
    ctx.set_line_width(2)
    ctx.line_to(0, display_h/3)
    ctx.line_to(201, display_h/3)
    ctx.stroke()

    ctx.set_source_rgba(*definitions.get_color_rgb_float(color), initial_bg_opacity * opacity)
    ctx.set_line_width(2)
    ctx.line_to(0, (display_h/3)*2)
    ctx.line_to(201, (display_h/3)*2)
    ctx.stroke()

    ctx.set_source_rgba(*definitions.get_color_rgb_float(color), initial_bg_opacity * opacity)
    ctx.set_line_width(2)
    ctx.line_to(201, 0)
    ctx.line_to(201, display_h)
    ctx.stroke()


    # Text
    initial_text_opacity = 1.0
    ctx.set_source_rgba(1.0, 1.0, 1.0, initial_text_opacity * opacity)
    font_size = display_h // 8
    ctx.set_font_size(font_size)
    margin_left = 8
    ctx.move_to(margin_left, 1.0 * font_size)
    ctx.set_font_size(font_size/1.5)
    ctx.show_text("BUTTON NAME:")
    ctx.set_font_size(font_size)
    ctx.move_to(margin_left * 2, 2.0 * font_size)
    ctx.show_text(title)

    ctx.move_to(margin_left, 3.6 * font_size)
    ctx.set_font_size(font_size/1.5)
    ctx.show_text("LOGIC HOTKEY:")
    ctx.set_font_size(font_size)
    ctx.move_to(margin_left * 2, 4.6 * font_size)
    ctx.show_text(hotkey)

    ctx.move_to(margin_left, 6.4 * font_size)
    ctx.set_font_size(font_size/1.5)
    ctx.show_text("OSC PATH:")
    ctx.set_font_size(font_size)
    ctx.move_to(margin_left * 2, 7.4 * font_size)
    ctx.show_text(path)

    ctx.move_to(margin_left + 201, 1.0 * font_size)
    ctx.set_font_size(font_size/1.5)
    ctx.show_text("Description:")
    ctx.set_font_size(font_size)
    ctx.move_to((margin_left * 2) + 201, 3.6 * font_size)
    ctx.show_text(description)

    ctx.restore()
