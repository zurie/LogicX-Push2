"""
Reusable single-column strip renderer for the Push2 Mackie GUI.
Draws one 120×strip_h channel strip: name + mode graphic + value + badges.

Public API:
    draw_column(ctx, x0, y0, col_w, h, vm, active_mode)
"""
import math
import definitions
from .base import StripVM, StripBadge

# Active modes (keep in sync with mackie_control_mode.py)
MODE_VOLUME = "volume"
MODE_PAN    = "pan"
MODE_MUTE   = "mute"
MODE_SOLO   = "solo"

# Unity gain position on MCU fader scale (pb=12443 / 16383)
_UNITY_NORM = 12443 / 16383.0

_PAD_X   = 5    # horizontal padding
_NAME_H  = 16   # track name zone height (px)
_GFX_H   = 62   # graphic zone height (px)
_VAL_H   = 16   # value label zone height (px)
_BADGE_H = 12   # badge row height (px)
# Total strip content = 4 + NAME_H + 4 + GFX_H + 4 + VAL_H + 4 + BADGE_H + 4 = 120


# ─── color helpers ────────────────────────────────────────────────────────────

def _rgb255(color_rgb):
    """(r,g,b) 0..255  →  (r,g,b) 0..1"""
    return color_rgb[0] / 255.0, color_rgb[1] / 255.0, color_rgb[2] / 255.0


def _dim(cr, factor=0.35):
    return (cr[0] * factor, cr[1] * factor, cr[2] * factor)


# ─── main entry ───────────────────────────────────────────────────────────────

def draw_column(ctx, x0: float, y0: float, col_w: float, h: float,
                vm: StripVM, active_mode: str) -> None:
    """
    Draw one channel strip column into `ctx`.

    Parameters
    ----------
    ctx         Cairo context
    x0          Left edge of this column in pixels
    y0          Top of strip area (below header, above mode bar)
    col_w       Column width (typically 120.0)
    h           Strip height (typically ~116)
    vm          StripVM data object
    active_mode One of "volume", "pan", "mute", "solo", "vpot", …
    """
    cr = _rgb255(vm.color_rgb)

    # layout: anchor name at top, badges+value at bottom, graphic fills middle
    y_name  = y0 + 3
    y_badge = y0 + h - _BADGE_H - 2
    y_val   = y_badge - _VAL_H - 2
    y_gfx   = y_name + _NAME_H + 3
    gfx_h   = max(20, y_val - 2 - y_gfx)

    # ── column background & selection fill ───────────────────────────────────
    _draw_background(ctx, x0, y0, col_w, h, cr, vm.badge)

    # ── divider (right edge hairline) ────────────────────────────────────────
    ctx.save()
    ctx.set_source_rgba(0.18, 0.18, 0.18, 1.0)
    ctx.set_line_width(1)
    ctx.move_to(x0 + col_w - 0.5, y0)
    ctx.line_to(x0 + col_w - 0.5, y0 + h)
    ctx.stroke()
    ctx.restore()

    # ── track name ───────────────────────────────────────────────────────────
    _draw_name(ctx, x0, y_name, col_w, _NAME_H, vm.name, cr, vm.badge.selected)

    # ── mode graphic ─────────────────────────────────────────────────────────
    gfx = getattr(vm, "gfx", None)
    if gfx == "bipolar":
        _draw_param_bar(ctx, x0, y_gfx, col_w, gfx_h, vm.normalized, cr, bipolar=True)
    elif gfx == "unipolar":
        _draw_param_bar(ctx, x0, y_gfx, col_w, gfx_h, vm.normalized, cr, bipolar=False)
    elif active_mode == MODE_VOLUME:
        _draw_level_bar(ctx, x0, y_gfx, col_w, gfx_h, vm.normalized, cr)
    elif active_mode == MODE_PAN:
        _draw_pan_bar(ctx, x0, y_gfx, col_w, gfx_h, vm.normalized, cr)
    elif active_mode == MODE_MUTE:
        _draw_state_block(ctx, x0, y_gfx, col_w, gfx_h, vm.badge.mute, "M", cr)
    elif active_mode == MODE_SOLO:
        _draw_state_block(ctx, x0, y_gfx, col_w, gfx_h, vm.badge.solo, "S", cr)
    else:
        _draw_vpot_value(ctx, x0, y_gfx, col_w, gfx_h, vm.value_label, cr)

    # ── value label ──────────────────────────────────────────────────────────
    if active_mode not in (MODE_MUTE, MODE_SOLO):
        _draw_value_label(ctx, x0, y_val, col_w, _VAL_H, vm.value_label, cr,
                          vm.badge.selected)

    # ── state badges ─────────────────────────────────────────────────────────
    _draw_badges(ctx, x0, y_badge, col_w, _BADGE_H, vm.badge)


# ─── sub-draw helpers ─────────────────────────────────────────────────────────

def _draw_background(ctx, x0, y0, col_w, h, cr, badge: StripBadge):
    ctx.save()
    if badge.selected:
        # Bright tint for selected track
        ctx.set_source_rgba(cr[0] * 0.30, cr[1] * 0.30, cr[2] * 0.30, 1.0)
    elif badge.mute:
        # Subtly darker for muted tracks
        ctx.set_source_rgba(0.04, 0.04, 0.04, 1.0)
    else:
        ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.rectangle(x0, y0, col_w, h)
    ctx.fill()
    ctx.restore()


def _draw_name(ctx, x0, y0, col_w, h, name: str, cr, selected: bool):
    ctx.save()
    ctx.rectangle(x0 + _PAD_X, y0, col_w - _PAD_X * 2, h)
    ctx.clip()
    ctx.select_font_face("Helvetica", 0, 0)
    ctx.set_font_size(12)
    # Selected → black text on colored bg; otherwise track color
    ctx.set_source_rgb(0.0, 0.0, 0.0) if selected else ctx.set_source_rgb(*cr)
    xb, yb, tw, th, _, _ = ctx.text_extents(name or "")
    ctx.move_to(x0 + _PAD_X - xb, y0 + (h - th) / 2.0 - yb)
    ctx.show_text(name or "")
    ctx.restore()


def _draw_level_bar(ctx, x0, y0, col_w, h, level: float, cr):
    """
    Vertical fader-style level bar, bottom-up.
    level 0..1 linear (from mm.fader_levels).
    A white tick marks unity gain (0 dB) at _UNITY_NORM.
    """
    bar_w = max(10, int(col_w * 0.45))
    bar_x = x0 + (col_w - bar_w) / 2.0
    bar_y = y0 + 3
    bar_h = h - 6
    level = max(0.0, min(1.0, level))

    ctx.save()

    # background track
    ctx.set_source_rgb(0.08, 0.08, 0.08)
    _rounded_rect(ctx, bar_x, bar_y, bar_w, bar_h, 3)
    ctx.fill()

    # filled portion (bottom-up)
    fill_h = bar_h * level
    if fill_h > 0.5:
        ctx.set_source_rgb(*cr)
        # Clip to bar area then draw from bottom
        ctx.save()
        _rounded_rect(ctx, bar_x, bar_y, bar_w, bar_h, 3)
        ctx.clip()
        ctx.rectangle(bar_x, bar_y + bar_h - fill_h, bar_w, fill_h)
        ctx.fill()
        ctx.restore()

    # unity gain tick (white hairline)
    tick_y = bar_y + bar_h * (1.0 - _UNITY_NORM)
    ctx.set_source_rgba(0.8, 0.8, 0.8, 0.7)
    ctx.set_line_width(1.0)
    ctx.move_to(bar_x - 3, tick_y)
    ctx.line_to(bar_x + bar_w + 3, tick_y)
    ctx.stroke()

    ctx.restore()


def _draw_pan_bar(ctx, x0, y0, col_w, h, normalized: float, cr):
    """
    Horizontal pan bar. normalized=0.5 → center (C).
    Colored segment runs from center to current position.
    """
    bar_h_px = 10
    pad      = _PAD_X + 2
    bar_x    = x0 + pad
    bar_w    = col_w - pad * 2
    bar_y    = y0 + (h - bar_h_px) / 2.0
    cx       = bar_x + bar_w / 2.0  # center x pixel
    norm     = max(0.0, min(1.0, normalized))
    cur_x    = bar_x + norm * bar_w

    ctx.save()

    # background track
    ctx.set_source_rgb(0.08, 0.08, 0.08)
    _rounded_rect(ctx, bar_x, bar_y, bar_w, bar_h_px, 4)
    ctx.fill()

    # colored segment from center to position
    seg_x = min(cx, cur_x)
    seg_w = abs(cur_x - cx)
    if seg_w > 0.5:
        ctx.set_source_rgb(*cr)
        ctx.save()
        _rounded_rect(ctx, bar_x, bar_y, bar_w, bar_h_px, 4)
        ctx.clip()
        ctx.rectangle(seg_x, bar_y, seg_w, bar_h_px)
        ctx.fill()
        ctx.restore()

    # center notch (white tick)
    ctx.set_source_rgba(0.9, 0.9, 0.9, 0.8)
    ctx.set_line_width(1.5)
    ctx.move_to(cx, bar_y - 3)
    ctx.line_to(cx, bar_y + bar_h_px + 3)
    ctx.stroke()

    # L / R labels at edges
    ctx.select_font_face("Helvetica", 0, 0)
    ctx.set_font_size(9)
    ctx.set_source_rgba(0.45, 0.45, 0.45, 1.0)
    ctx.move_to(bar_x - 1, bar_y + bar_h_px + 10)
    ctx.show_text("L")
    ctx.move_to(bar_x + bar_w - 6, bar_y + bar_h_px + 10)
    ctx.show_text("R")

    ctx.restore()


def _draw_param_bar(ctx, x0, y0, col_w, h, normalized: float, cr, bipolar: bool):
    """Horizontal parameter bar for Surround V-Pots.
    bipolar=True  → segment from center + center notch (Pan, Spread, X/Y, Elevation)
    bipolar=False → fill from left (Diversity, LFE, Object Size).
    """
    bar_h_px = 10
    pad      = _PAD_X + 2
    bar_x    = x0 + pad
    bar_w    = col_w - pad * 2
    bar_y    = y0 + (h - bar_h_px) / 2.0
    norm     = max(0.0, min(1.0, normalized))

    ctx.save()
    # background track
    ctx.set_source_rgb(0.08, 0.08, 0.08)
    _rounded_rect(ctx, bar_x, bar_y, bar_w, bar_h_px, 4)
    ctx.fill()

    # colored fill (clipped to rounded track)
    ctx.set_source_rgb(*cr)
    ctx.save()
    _rounded_rect(ctx, bar_x, bar_y, bar_w, bar_h_px, 4)
    ctx.clip()
    if bipolar:
        cx    = bar_x + bar_w / 2.0
        cur_x = bar_x + norm * bar_w
        seg_x = min(cx, cur_x)
        seg_w = abs(cur_x - cx)
        if seg_w > 0.5:
            ctx.rectangle(seg_x, bar_y, seg_w, bar_h_px)
            ctx.fill()
    else:
        ctx.rectangle(bar_x, bar_y, norm * bar_w, bar_h_px)
        ctx.fill()
    ctx.restore()

    # center notch for bipolar params
    if bipolar:
        cx = bar_x + bar_w / 2.0
        ctx.set_source_rgba(0.9, 0.9, 0.9, 0.8)
        ctx.set_line_width(1.5)
        ctx.move_to(cx, bar_y - 3)
        ctx.line_to(cx, bar_y + bar_h_px + 3)
        ctx.stroke()

    ctx.restore()


def _draw_state_block(ctx, x0, y0, col_w, h, is_active: bool, letter: str, cr):
    """
    Large rounded block showing mute or solo state.
    Active → filled with track color, large black letter.
    Inactive → dark fill, dim letter.
    """
    pad    = _PAD_X + 2
    bx     = x0 + pad
    bw     = col_w - pad * 2
    by     = y0 + 4
    bh     = h - 8

    ctx.save()
    if is_active:
        ctx.set_source_rgb(*cr)
    else:
        ctx.set_source_rgb(0.12, 0.12, 0.12)
    _rounded_rect(ctx, bx, by, bw, bh, 7)
    ctx.fill()

    # letter
    ctx.select_font_face("Helvetica", 0, 1)  # bold
    ctx.set_font_size(32)
    if is_active:
        ctx.set_source_rgb(0.0, 0.0, 0.0)
    else:
        ctx.set_source_rgba(0.35, 0.35, 0.35, 1.0)
    xb, yb, tw, th, _, _ = ctx.text_extents(letter)
    ctx.move_to(bx + (bw - tw) / 2.0 - xb, by + (bh - th) / 2.0 - yb)
    ctx.show_text(letter)
    ctx.restore()


def _draw_vpot_value(ctx, x0, y0, col_w, h, value_label: str, cr):
    """Fallback for VPOT/other modes — centered value text."""
    ctx.save()
    ctx.select_font_face("Menlo", 0, 0)
    ctx.set_font_size(13)
    ctx.set_source_rgb(*cr)
    lbl = value_label or ""
    xb, yb, tw, th, _, _ = ctx.text_extents(lbl)
    tx = x0 + (col_w - tw) / 2.0 - xb
    ty = y0 + (h - th) / 2.0 - yb
    ctx.move_to(tx, ty)
    ctx.show_text(lbl)
    ctx.restore()


def _draw_value_label(ctx, x0, y0, col_w, h, value_label: str, cr, selected: bool):
    """Small numeric/text value below the graphic."""
    ctx.save()
    ctx.rectangle(x0 + _PAD_X, y0, col_w - _PAD_X * 2, h)
    ctx.clip()
    ctx.select_font_face("Menlo", 0, 0)
    ctx.set_font_size(11)
    ctx.set_source_rgb(0.0, 0.0, 0.0) if selected else ctx.set_source_rgb(*cr)
    lbl = value_label or ""
    is_num = any(c.isdigit() for c in lbl) or lbl.strip().startswith(("+", "-", "∞"))
    xb, yb, tw, th, _, _ = ctx.text_extents(lbl)
    if is_num:
        tx = x0 + col_w - _PAD_X - tw - xb
    else:
        tx = x0 + _PAD_X - xb
    ctx.move_to(tx, y0 + (h - th) / 2.0 - yb)
    ctx.show_text(lbl)
    ctx.restore()


def _draw_badges(ctx, x0, y0, col_w, h, badge: StripBadge):
    """
    Small colored indicator dots for active Mute / Solo / Rec states.
    Only shown when the state is ON.
    """
    items = []
    if badge.rec:
        items.append(((1.0, 0.25, 0.25), "R"))
    if badge.mute:
        items.append(((0.0, 0.85, 0.85), "M"))
    if badge.solo:
        items.append(((1.0, 1.0, 0.0), "S"))

    if not items:
        return

    dot_r   = 4
    spacing = dot_r * 2 + 4
    total_w = len(items) * spacing - 4
    start_x = x0 + (col_w - total_w) / 2.0 + dot_r
    cy      = y0 + h / 2.0

    ctx.save()
    ctx.select_font_face("Helvetica", 0, 1)
    ctx.set_font_size(7)
    for i, (col, ltr) in enumerate(items):
        cx = start_x + i * spacing
        # dot
        ctx.set_source_rgb(*col)
        ctx.arc(cx, cy, dot_r, 0, math.pi * 2)
        ctx.fill()
        # letter
        ctx.set_source_rgb(0.0, 0.0, 0.0)
        xb, yb, tw, th, _, _ = ctx.text_extents(ltr)
        ctx.move_to(cx - tw / 2.0 - xb, cy - th / 2.0 - yb)
        ctx.show_text(ltr)
    ctx.restore()


# ─── geometry helper ──────────────────────────────────────────────────────────

def _rounded_rect(ctx, x, y, w, h, r):
    r = min(r, w / 2.0, h / 2.0)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r,     r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r,  0,            math.pi / 2)
    ctx.arc(x + r,     y + h - r, r,  math.pi / 2,  math.pi)
    ctx.arc(x + r,     y + r,     r,  math.pi,      3 * math.pi / 2)
    ctx.close_path()
