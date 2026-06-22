# ui/mackie_gui_v3.py
"""
MackieGuiV3 — Push2 Mackie mode renderer using adaptive column strips.

Layout (960 × 160 px):
  y 0–20   Header bar   (mode, bank, flip, sel)
  y 20–136 Strip area   (8 × column_strip.draw_column)
  y 136–160 Mode bar    (VOL / MUTE / SOLO / PAN / …)
"""
import math
import time
import definitions
from .base import Renderer, StripVM, StripBadge
from .column_strip import draw_column

_HEADER_H = 20
_BAR_H    = 24
_STRIP_Y  = _HEADER_H   # strip area starts here

# Surround Channel View V-Pot layout (matches Logic's Controller Assignments).
# (display name, bipolar?) — bipolar params draw a centered bar, others fill bar.
# Value text comes from Logic's LCD; arc position from the V-Pot ring.
_SURROUND_SPECS = [
    ("Pan",       True),   # -64..+63
    ("Diversity", False),  # 0..100 %
    ("LFE",       False),  # mute..+6 dB
    ("Spread",    True),   # -180..+179°
    ("Surr X",    True),   # -1000..+1000
    ("Surr Y",    True),   # -1000..+1000
    ("Size",      False),  # 0..100  (Object Size)
    ("Elevation", True),   # -90..+90°
]


class MackieGuiV3(Renderer):
    def __init__(self, mode):
        self.mode = mode
        self.w, self.h = 960, 160
        self._col_w      = None
        self._strip_h    = None
        # focus hint state (encoder touch overlay)
        self._focus_idx   = None
        self._focus_until = 0.0

    # ──────────────────────────────────────────────────────── lifecycle

    def on_resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self._col_w   = w / 8.0
        self._strip_h = h - _HEADER_H - _BAR_H

    # ──────────────────────────────────────────────────────── focus hints

    def on_strip_touch(self, ch: int) -> None:
        self._focus_idx   = ch
        self._focus_until = time.time() + 0.6

    def on_strip_release(self, ch: int) -> None:
        if self._focus_idx == ch:
            self._focus_until = time.time() + 0.15

    def poke_focus(self, ch: int) -> None:
        self._focus_idx   = ch
        self._focus_until = time.time() + 0.5

    # V2 compat shim — V3 pulls data live so no scribble cache needed
    def update_scribble_cell(self, ch: int, *, top=None, bottom=None) -> None:
        pass

    # ──────────────────────────────────────────────────────── render

    def render(self, ctx, w: int, h: int) -> None:
        if self._col_w is None:
            self.on_resize(w, h)

        # flush pending MCU tx before drawing
        if hasattr(self.mode, "_flush_pending_tx"):
            self.mode._flush_pending_tx()
        if hasattr(self.mode, "_sync_pan_from_logic"):
            self.mode._sync_pan_from_logic()

        # black canvas
        ctx.rectangle(0, 0, w, h)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()

        mm          = getattr(self.mode.app, "mcu_manager", None)
        active_mode = getattr(self.mode, "active_mode", "volume")
        base        = getattr(self.mode, "current_page", 0) * 8

        # build data for 8 strips
        vms = self._build_vms(mm, active_mode, base)

        # draw strips
        for col in range(8):
            draw_column(ctx,
                        x0=col * self._col_w,
                        y0=_STRIP_Y,
                        col_w=self._col_w,
                        h=self._strip_h,
                        vm=vms[col],
                        active_mode=active_mode)

        # focus outline (encoder touch)
        if self._focus_idx is not None:
            if time.time() < self._focus_until:
                self._draw_focus_outline(ctx)
            else:
                self._focus_idx = None

        # header and mode bar drawn on top so they're never clipped by strips
        self._draw_header(ctx, w, mm, active_mode)
        self._draw_mode_bar(ctx, w, h)

    # ──────────────────────────────────────────────────────── strip VMs

    def _build_vms(self, mm, active_mode: str, base: int):
        sel_abs = -1
        if mm and mm.selected_track_idx is not None:
            sel_abs = int(mm.selected_track_idx)

        # LCD cells for VPOT / fallback text
        top_cells = [""] * 8
        bot_cells  = [""] * 8
        if mm and hasattr(mm, "get_visible_lcd_lines"):
            top_cells, bot_cells = mm.get_visible_lcd_lines()

        # Parameter view (Surround / Channel View): the 8 V-Pots are parameters of
        # the selected track, so labels come from Logic's LCD, not track names.
        param_view = False
        _ipv = getattr(self.mode, "is_param_view", None)
        if callable(_ipv):
            try:
                param_view = bool(_ipv())
            except Exception:
                param_view = False

        # Surround view = PAN param sub-page. Verify against the live LCD: if Logic
        # reset to plain Pan (e.g. after tabbing out of Logic and back), the top
        # cells are track names, not surround params — resync our sub-page to Pan
        # base instead of rendering a stale surround layout over per-track data.
        # Surround = the PAN even sub-page (entered by re-pressing PAN). Driven
        # purely by our button state, NOT the LCD: on this rig "Display Mode:
        # Name" makes Logic show TRACK NAMES on the LCD even while in Surround, so
        # the LCD top row can't tell Surround from Pan Mixer. Trust the sub-page;
        # PAN re-press toggles back to per-track pan.
        surround_view = (active_mode == "pan" and param_view)

        vms = []
        for i in range(8):
            abs_idx = base + i
            spec = _SURROUND_SPECS[i] if (surround_view and i < len(_SURROUND_SPECS)) else None

            if surround_view:
                # name = fixed surround parameter name for this V-Pot
                name = spec[0]
            elif param_view:
                # name = LCD param name for this V-Pot
                name = top_cells[i] or f"VPot {i + 1}"
            else:
                # track name: prefer mm.track_names (visible bank, 8 entries),
                # fall back to LCD top cell, then generic label
                name = f"T{abs_idx + 1}"
                if mm and hasattr(mm, "track_names"):
                    try:
                        n = mm.track_names[i]
                        name = n if n else (top_cells[i] or name)
                    except Exception:
                        pass
                elif top_cells[i]:
                    name = top_cells[i]

            # track color
            color_rgb = (90, 90, 90)
            if mm and hasattr(mm, "track_colors"):
                try:
                    cname = mm.track_colors[i % len(mm.track_colors)]
                    rgb   = definitions.get_color_rgb(cname)
                    color_rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
                except Exception:
                    pass

            # states
            mute = bool(mm.mute_states[abs_idx]) if mm and abs_idx < len(mm.mute_states) else False
            solo = bool(mm.solo_states[abs_idx]) if mm and abs_idx < len(mm.solo_states) else False
            rec  = bool(mm.rec_states[abs_idx])  if mm and abs_idx < len(mm.rec_states)  else False
            selected = (abs_idx == sel_abs)

            # In param view the strips are parameters of one track, so per-track
            # rec/solo/mute/selected badges aren't meaningful — suppress them.
            if param_view:
                badge = StripBadge(rec=False, solo=False, mute=False, selected=False)
            else:
                badge = StripBadge(rec=rec, solo=solo, mute=mute, selected=selected)

            # mode-specific normalized value + display label
            gfx = None
            if surround_view:
                # Value text from Logic's LCD; arc position from the V-Pot ring
                # (Logic scales each parameter's range into the 0..11 LED ring).
                value_label = (bot_cells[i] or "").strip()
                normalized = 0.0
                ring = getattr(mm, "vpot_ring", None)
                if ring and i < len(ring):
                    try:
                        normalized = max(0.0, min(1.0, float(ring[i]) / 11.0))
                    except Exception:
                        normalized = 0.0
                gfx = "bipolar" if spec[1] else "unipolar"
            else:
                normalized, value_label = self._strip_value(mm, active_mode, i, abs_idx,
                                                             mute, solo, bot_cells[i])

            vms.append(StripVM(
                name=name,
                color_rgb=color_rgb,
                value_label=value_label,
                normalized=normalized,
                badge=badge,
                gfx=gfx,
            ))
        return vms

    def _strip_value(self, mm, active_mode: str, local_idx: int, abs_idx: int,
                     mute: bool, solo: bool, lcd_bot_cell: str):
        """Return (normalized 0..1, display_label) for the given mode and channel."""
        # Parameter view: value/label come straight from Logic's LCD; the arc
        # follows the V-Pot ring position Logic echoed (0..11), if available.
        _ipv = getattr(self.mode, "is_param_view", None)
        if callable(_ipv):
            try:
                if _ipv():
                    norm = 0.0
                    ring = getattr(mm, "vpot_ring", None)
                    if ring and local_idx < len(ring):
                        try:
                            norm = max(0.0, min(1.0, float(ring[local_idx]) / 11.0))
                        except Exception:
                            norm = 0.0
                    return norm, lcd_bot_cell
            except Exception:
                pass

        if active_mode == "volume":
            level = float(mm.fader_levels[local_idx]) if mm else 0.0
            level = max(0.0, min(1.0, level))
            if hasattr(self.mode, "_level_to_db"):
                db = self.mode._level_to_db(level)
                label = "-∞ dB" if db == float("-inf") else f"{db:+.1f} dB"
            else:
                label = f"{level * 100:.0f}%"
            return level, label

        if active_mode == "pan":
            pan_f = 0.0
            if hasattr(self.mode, "_pan_view"):
                try:
                    pan_f = float(self.mode._pan_view[local_idx])
                except Exception:
                    pass
            norm  = (pan_f + 64.0) / 128.0
            label = "C" if abs(pan_f) < 0.5 else f"{int(round(pan_f)):+d}"
            return norm, label

        if active_mode == "mute":
            return (1.0 if mute else 0.0), ("MUTED" if mute else "")

        if active_mode == "solo":
            return (1.0 if solo else 0.0), ("SOLO" if solo else "")

        # VPOT / other: use LCD bottom cell
        return 0.0, lcd_bot_cell

    # ──────────────────────────────────────────────────────── header

    def _draw_header(self, ctx, w: int, mm, active_mode: str) -> None:
        # solid dark background bar
        ctx.save()
        ctx.set_source_rgb(0.06, 0.06, 0.06)
        ctx.rectangle(0, 0, w, _HEADER_H)
        ctx.fill()
        ctx.restore()

        flip_on  = bool(getattr(mm, "flip", False)) if mm else False
        sel_idx  = mm.selected_track_idx if mm and mm.selected_track_idx is not None else None
        sel_lab  = f"T{sel_idx + 1}" if sel_idx is not None else "–"
        bank_s   = ((sel_idx or 0) // 8) * 8 + 1
        bank_e   = bank_s + 7
        mode_lab = active_mode.upper()
        _mi = getattr(self.mode, "mode_indicator_text", None)
        if callable(_mi):
            try:
                mode_lab = _mi()
            except Exception:
                pass

        x = 8
        x += self._hdr_token(ctx, x, mode_lab,
                              definitions.get_color_rgb_float(
                                  getattr(self.mode, "MODE_COLORS", {}).get(active_mode,
                                                                             definitions.GRAY_DARK))) + 8
        x += self._hdr_token(ctx, x, f"Bank {bank_s}–{bank_e}") + 8
        x += self._hdr_token(ctx, x, f"FLIP {'ON' if flip_on else 'OFF'}",
                              (0.2, 0.8, 0.2) if flip_on else None) + 8
        self._hdr_token(ctx, x, f"SEL {sel_lab}")

    def _hdr_token(self, ctx, x: float, label: str, fill_rgb=None) -> float:
        """Draw a small pill token at (x, header row) and return its width."""
        pad_x, pad_y = 6, 3
        ctx.save()
        ctx.select_font_face("Helvetica", 0, 0)
        ctx.set_font_size(10)
        xb, yb, tw, th, _, _ = ctx.text_extents(label)
        pill_w = tw + pad_x * 2
        pill_h = _HEADER_H - pad_y * 2
        pill_y = pad_y
        if fill_rgb:
            ctx.set_source_rgb(*fill_rgb)
        else:
            ctx.set_source_rgb(0.18, 0.18, 0.18)
        _pill(ctx, x, pill_y, pill_w, pill_h, 4)
        ctx.fill()
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(x + pad_x - xb, pill_y + (pill_h - th) / 2.0 - yb)
        ctx.show_text(label)
        ctx.restore()
        return pill_w

    # ──────────────────────────────────────────────────────── mode bar

    def _draw_mode_bar(self, ctx, w: int, h: int) -> None:
        col_w  = self._col_w
        bar_y  = h - _BAR_H
        corner = 5

        mode_labels = getattr(self.mode, "MODE_LABELS", {})
        mode_colors = getattr(self.mode, "MODE_COLORS", {})
        lower_modes = getattr(self.mode, "LOWER_ROW_MODES", [])
        active      = getattr(self.mode, "active_mode", "")

        for i, mode_key in enumerate(lower_modes):
            x      = int(i * col_w) + 1
            width  = int(col_w) - 2
            sel    = (mode_key == active)
            fill_c = mode_colors.get(mode_key, definitions.GRAY_DARK) if sel else definitions.GRAY_DARK
            text_c = definitions.BLACK if sel else mode_colors.get(mode_key, definitions.GRAY_LIGHT)

            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(fill_c))
            _pill(ctx, x, bar_y + 2, width, _BAR_H - 4, corner)
            ctx.fill()
            ctx.restore()

            label = mode_labels.get(mode_key, mode_key.upper())
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(text_c))
            ctx.select_font_face("Helvetica", 0, 0)
            ctx.set_font_size(11)
            xb, yb, tw, th, _, _ = ctx.text_extents(label)
            ctx.move_to(x + (width - tw) / 2.0 - xb,
                        bar_y + 2 + ((_BAR_H - 4) - th) / 2.0 - yb)
            ctx.show_text(label)
            ctx.restore()

    # ──────────────────────────────────────────────────────── focus outline

    def _draw_focus_outline(self, ctx) -> None:
        if self._focus_idx is None:
            return
        x0 = self._focus_idx * self._col_w
        ctx.save()
        ctx.set_source_rgba(1, 1, 1, 0.30)
        ctx.set_line_width(2.0)
        ctx.rectangle(x0 + 2, _STRIP_Y + 2,
                      self._col_w - 4, self._strip_h - 4)
        ctx.stroke()
        ctx.restore()


# ─── geometry helper ──────────────────────────────────────────────────────────

def _pill(ctx, x, y, w, h, r):
    r = min(r, w / 2.0, h / 2.0)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r,     r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r,  0,            math.pi / 2)
    ctx.arc(x + r,     y + h - r, r,  math.pi / 2,  math.pi)
    ctx.arc(x + r,     y + r,     r,  math.pi,      3 * math.pi / 2)
    ctx.close_path()
