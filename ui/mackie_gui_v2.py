# ui/mackie_gui_v2.py
import math, time
import definitions
from .base import Renderer

MONO_FONTS = (
    getattr(definitions, "MC_DEBUG_FONT", "Menlo"),
    "Menlo", "Monaco", "Courier New", "Courier"
)

def _pick_mono(ctx):
    for fam in MONO_FONTS:
        try:
            ctx.select_font_face(fam, 0, 0); return
        except Exception:
            continue
    ctx.select_font_face("Courier New", 0, 0)

class MackieGuiV2(Renderer):
    """
    Mackie v2 GUI:
      • Top: header tokens (Mode / Bank / Page / Flip / Sel)
      • Middle: 8×(title,value) using the MCU 56-char scribble data (8*7)
                with a local LCD cache + dirty-col redraw (Mackie-like)
      • Bottom: legacy-style mode buttons (VOL/MUTE/SOLO/…)
    """
    def __init__(self, mode):
        self.mode = mode
        self.w, self.h = 960, 160
        # layout cache
        self._col_w = None
        self._bar_h = 22
        self._header_h = 20
        self._header_y = 2
        self._mid_top = 0
        self._mid_h = 0
        # LCD cache (56 chars each)
        self._lcd_top = " " * 56
        self._lcd_bot = " " * 56
        self._dirty_cols = set()  # which of the 8 columns need repaint
        # focus hint
        self._focus_idx = None
        self._focus_until = 0.0
        # font sizes
        self._title_size = None
        self._value_size = None
        self._cell_font_h_key = None

    # ───────────────────────────────────────────────────────────── lifecycle
    def on_resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self._col_w = w / 8.0
        self._mid_top = self._header_y + self._header_h + 2
        self._mid_h   = max(28, int((h - self._bar_h - 2) - self._mid_top))
        self._title_size = None
        self._value_size = None
        self._cell_font_h_key = None

    # ───────────────────────────────────────────────────────────── public fast-paths
    def update_scribble_cell(self, ch: int, *, top=None, bottom=None):
        """Patch 7-char window for strip ch and mark it dirty."""
        if not (0 <= ch < 8): return
        off = ch * 7
        if top is not None:
            seg = (str(top) + " " * 7)[:7]
            self._lcd_top = self._lcd_top[:off] + seg + self._lcd_top[off + 7:]
        if bottom is not None:
            seg = (str(bottom) + " " * 7)[:7]
            self._lcd_bot = self._lcd_bot[:off] + seg + self._lcd_bot[off + 7:]
        self._dirty_cols.add(ch)

    def on_strip_touch(self, ch: int):
        self._focus_idx = ch
        self._focus_until = time.time() + 0.6

    def on_strip_release(self, ch: int):
        if self._focus_idx == ch:
            self._focus_until = time.time() + 0.15  # brief linger

    # ───────────────────────────────────────────────────────────── render
    def render(self, ctx, w: int, h: int) -> None:
        # background
        ctx.rectangle(0, 0, w, h); ctx.set_source_rgb(0, 0, 0); ctx.fill()

        # keep minimal MCU sync
        if hasattr(self.mode, "_flush_pending_tx"): self.mode._flush_pending_tx()
        if hasattr(self.mode, "_sync_pan_from_logic"): self.mode._sync_pan_from_logic()

        # layout refresh on size change
        if self._col_w is None: self.on_resize(w, h)

        # header
        self._draw_header(ctx, w, self._header_y, self._header_h)

        # LCD cache: pull from MCU (full 56-char lines)
        self._pull_mcu_lcd()

        # middle band: draw either dirty columns quickly or full strip set
        if self._dirty_cols:
            for col in list(self._dirty_cols):
                self._draw_strip_cells(ctx, col)
            self._dirty_cols.clear()
        else:
            for col in range(8):
                self._draw_strip_cells(ctx, col)

        # focus outline (optional)
        self._draw_focus_hint(ctx)

        # bottom bar
        self._draw_bottom_mode_labels(ctx, w, h)

    # ───────────────────────────────────────────────────────────── header
    def _hdr_text(self, ctx, x, y, s, size=11):
        ctx.select_font_face("Arial", 0, 0)
        ctx.set_font_size(size); ctx.move_to(x, y); ctx.show_text(s)

    def _hdr_token(self, ctx, x, y, label):
        pad_x, pad_y = 6, 3
        ctx.set_source_rgb(0.15, 0.15, 0.15)
        approx_w = int(len(label) * 6.2) + pad_x * 2
        approx_h = 16
        ctx.rectangle(x, y - approx_h + pad_y, approx_w, approx_h); ctx.fill()
        ctx.set_source_rgb(1, 1, 1)
        self._hdr_text(ctx, x + pad_x, y - 4, label, size=11)
        return approx_w

    def _draw_header(self, ctx, w, y, header_h):
        mm = getattr(self.mode.app, "mcu_manager", None)
        assignment = getattr(self.mode, "active_mode", "volume").upper()
        subview = "A"
        page_idx = getattr(mm, "page_index", 1) or 1
        page_cnt = getattr(mm, "page_count", 1) or 1
        flip_on  = bool(getattr(mm, "flip", False))
        bank_s   = (getattr(mm, "bank_start", 0) or 0) + 1
        bank_e   = getattr(mm, "bank_end", 8) or 8
        sel_idx  = getattr(mm, "selected_track_idx", None)
        sel_lab  = f"T{sel_idx + 1}" if sel_idx is not None else "-"

        x = 8
        x += self._hdr_token(ctx, x, y + header_h, f"MODE: {assignment} • Sub: {subview}") + 10
        x += self._hdr_token(ctx, x, y + header_h, f"Bank: {bank_s}–{bank_e}") + 10
        x += self._hdr_token(ctx, x, y + header_h, f"Page: {page_idx}/{page_cnt}") + 10
        x += self._hdr_token(ctx, x, y + header_h, f"FLIP: {'ON' if flip_on else 'OFF'}") + 10
        _    = self._hdr_token(ctx, x, y + header_h, f"SEL: {sel_lab}")

    # ───────────────────────────────────────────────────────────── scribble (middle)
    def _pull_mcu_lcd(self):
        """Bring 56-char lines from MCU into our cache; mark dirty if changed."""
        mm = getattr(self.mode.app, "mcu_manager", None)
        if not mm: return
        top = ((getattr(mm, "last_lcd_text", "") or "").ljust(56))[:56]
        bot = ((getattr(mm, "last_lcd_bottom_text", "") or "").ljust(56))[:56]
        if top != self._lcd_top:
            self._lcd_top = top; self._dirty_cols.update(range(8))
        if bot != self._lcd_bot:
            self._lcd_bot = bot; self._dirty_cols.update(range(8))

    def _slice56_to_cells(self, s56: str):
        return [(s56[i*7:(i+1)*7]).rstrip() for i in range(8)]

    def _fit_font_width(self, ctx, target_w, sample_chars, min_size=8, max_size=16, cache_attr=None):
        size = getattr(self, cache_attr) if cache_attr else None
        if size:
            ctx.set_font_size(size); return size
        size = max_size; ctx.set_font_size(size)
        _, _, tw, _, _, _ = ctx.text_extents("M" * sample_chars)
        while tw > target_w and size > min_size:
            size -= 0.5; ctx.set_font_size(size)
            _, _, tw, _, _, _ = ctx.text_extents("M" * sample_chars)
        if cache_attr: setattr(self, cache_attr, size)
        return size

    def _draw_strip_cells(self, ctx, col: int):
        """Draw one column (title, value) from cached LCD into the middle band."""
        if not (0 <= col < 8): return
        titles = self._slice56_to_cells(self._lcd_top)
        values = self._slice56_to_cells(self._lcd_bot)

        col_w   = self._col_w
        pad_x   = int(getattr(definitions, "MC_TEST_PAD_X", 4))
        x0      = int(col * col_w)
        y_top   = self._mid_top
        height  = self._mid_h

        _pick_mono(ctx)
        title_size = self._fit_font_width(ctx, col_w - pad_x*2, 7, 8, 14, "_title_size")
        value_size = self._fit_font_width(ctx, col_w - pad_x*2, 7, 8, 16, "_value_size")

        title_h = int(title_size) + 4
        value_h = int(value_size) + 6
        row_gap = max(2, height - (title_h + value_h))
        title_baseline = y_top + title_h
        value_baseline = title_baseline + row_gap + value_h

        # clip to this column’s band
        ctx.save()
        ctx.rectangle(x0, y_top, int(col_w), height); ctx.clip()

        # selection fill
        mm = getattr(self.mode.app, "mcu_manager", None)
        sel_rel = None
        if mm and isinstance(getattr(mm, "selected_track_idx", None), int):
            base = (getattr(self.mode, "current_page", 0) or 0) * getattr(self.mode, "tracks_per_page", 8)
            if base <= mm.selected_track_idx < base + 8:
                sel_rel = mm.selected_track_idx - base
        if sel_rel == col:
            colr = self.mode.MODE_COLORS.get(self.mode.active_mode, definitions.GRAY_DARK)
            ctx.set_source_rgb(*definitions.get_color_rgb_float(colr))
            ctx.rectangle(x0 + 1, y_top + 1, int(col_w) - 2, height - 2); ctx.fill()

        # title
        title = titles[col]
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.BLACK if sel_rel == col else definitions.WHITE))
        ctx.set_font_size(title_size)
        ctx.move_to(x0 + pad_x, title_baseline)
        ctx.show_text(title)

        # value (numeric right-aligned)
        val = values[col]
        is_num = any(ch.isdigit() for ch in val) or val.strip().startswith(("+", "-"))
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.BLACK if sel_rel == col
                                                            else getattr(definitions, "GREEN", "green")))
        ctx.set_font_size(value_size)
        xb, yb, tw, th, _, _ = ctx.text_extents(val or "")
        tx = (x0 + col_w - pad_x - tw - xb) if is_num else (x0 + pad_x - xb)
        ctx.move_to(tx, value_baseline)
        ctx.show_text(val or "")
        ctx.restore()

    def _draw_focus_hint(self, ctx):
        if self._focus_idx is None: return
        if time.time() > self._focus_until:
            self._focus_idx = None; return
        x0 = int(self._focus_idx * self._col_w)
        y  = self._mid_top
        ctx.save()
        ctx.set_source_rgba(1, 1, 1, 0.25)
        ctx.set_line_width(2.0)
        ctx.rectangle(x0 + 2, y + 2, int(self._col_w) - 4, self._mid_h - 4)
        ctx.stroke()
        ctx.restore()

    # ───────────────────────────────────────────────────────────── bottom bar
    def _draw_bottom_mode_labels(self, ctx, w, h):
        col_w = self._col_w
        bar_h = self._bar_h
        bar_y = h - bar_h - 2
        corner = 6

        for i, mode_key in enumerate(self.mode.LOWER_ROW_MODES):
            x = int(i * col_w) + 1
            width = int(col_w) - 2

            selected = (mode_key == self.mode.active_mode)
            fill_col = self.mode.MODE_COLORS.get(mode_key, definitions.GRAY_DARK) if selected else definitions.GRAY_DARK
            text_col = definitions.BLACK if selected else self.mode.MODE_COLORS.get(mode_key, definitions.GRAY_LIGHT)

            # pill
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(fill_col))
            ctx.new_sub_path()
            ctx.arc(x + width - corner, bar_y + corner, corner, math.radians(-90), math.radians(0))
            ctx.arc(x + width - corner, bar_y + bar_h - corner, corner, math.radians(0), math.radians(90))
            ctx.arc(x + corner, bar_y + bar_h - corner, corner, math.radians(90), math.radians(180))
            ctx.arc(x + corner, bar_y + corner, corner, math.radians(180), math.radians(270))
            ctx.close_path(); ctx.fill()
            ctx.restore()

            # label
            label = self.mode.MODE_LABELS.get(mode_key, mode_key.upper())
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(text_col))
            ctx.select_font_face("Helvetica", 0, 0); ctx.set_font_size(12)
            xb, yb, tw, th, _, _ = ctx.text_extents(label)
            tx = x + (width - tw) / 2.0 - xb
            ty = bar_y + (bar_h - th) / 2.0 - yb
            ctx.move_to(tx, ty); ctx.show_text(label)
            ctx.restore()
