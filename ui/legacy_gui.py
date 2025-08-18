import math
import definitions
from .base import Renderer


class LegacyGui(Renderer):
    """
    Exact old Mackie GUI, but rendered from a separate class.
    NOTE: when you need app/MCU/state, use self.mode (NOT self).
    """

    def __init__(self, mode):
        self.mode = mode
        self.w, self.h = 960, 160

    def on_resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h

    def render(self, ctx, w: int, h: int) -> None:
        # Clear
        ctx.rectangle(0, 0, w, h)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()

        # Same pre-frame sync you used before
        if hasattr(self.mode, "_flush_pending_tx"):
            self.mode._flush_pending_tx()
        if hasattr(self.mode, "_sync_pan_from_logic"):
            self.mode._sync_pan_from_logic()
        if hasattr(self.mode, "update_strip_values"):
            self.mode.update_strip_values()

        mm = getattr(self.mode.app, "mcu_manager", None)
        if mm and hasattr(mm, "get_visible_track_names") and hasattr(self.mode, "set_visible_names"):
            self.mode.set_visible_names(mm.get_visible_track_names())

        start = getattr(self.mode, "current_page", 0) * getattr(self.mode, "tracks_per_page", 8)
        selected_idx = getattr(self.mode.app.mcu_manager, "selected_track_idx", None)

        # Draw the 8 strips exactly like before (TrackStrip.draw is still in mode file)
        for i in range(getattr(self.mode, "tracks_per_page", 8)):
            strip_idx = start + i
            if hasattr(self.mode, "track_strips") and strip_idx < len(self.mode.track_strips):
                self.mode.track_strips[strip_idx].draw(ctx, i, selected=(strip_idx == selected_idx))

        # Top header (labels for the upper row buttons)
        self._draw_top_button_labels(ctx, w, h)
        # Bottom mode bar
        self._draw_bottom_mode_labels(ctx, w, h)
        # Debug MCU scribble-strip overlay (optional)
        self._draw_debug_banner(ctx, w, h)

    # ──────────────────────────────────────────────────────────────────────
    # Helpers copied from your old implementation (adapted self→self.mode)
    # ──────────────────────────────────────────────────────────────────────
    def _draw_top_button_labels(self, ctx, w, h):
        label, col = self.mode._upper_row_label_and_color()
        header_h = 18
        y = 0
        col_w = w / 8.0
        corner = 5

        for i in range(8):
            x = int(i * col_w) + 1
            width = int(col_w) - 2

            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(col))
            ctx.new_sub_path()
            ctx.arc(x + width - corner, y + corner, corner, math.radians(-90), math.radians(0))
            ctx.arc(x + width - corner, y + header_h - corner, corner, math.radians(0), math.radians(90))
            ctx.arc(x + corner, y + header_h - corner, corner, math.radians(90), math.radians(180))
            ctx.arc(x + corner, y + corner, corner, math.radians(180), math.radians(270))
            ctx.close_path()
            ctx.fill()
            ctx.restore()

            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.BLACK))
            ctx.select_font_face("Helvetica", 0, 0)
            ctx.set_font_size(11)
            xb, yb, tw, th, _, _ = ctx.text_extents(label)
            tx = x + (width - tw) / 2.0 - xb
            ty = y + (header_h - th) / 2.0 - yb
            ctx.move_to(tx, ty)
            ctx.show_text(label)
            ctx.restore()

    def _draw_debug_banner(self, ctx, w, h):
        if not getattr(definitions, "MC_DRAW_DEBUG", False):
            return
        mcu = getattr(self.mode.app, "mcu_manager", None)
        if not mcu:
            return

        top56 = (getattr(mcu, "last_lcd_text", "") or "").ljust(56)[:56]
        bot56 = (getattr(mcu, "last_lcd_bottom_text", "") or "").ljust(56)[:56]
        if not (top56.strip() or bot56.strip()):
            return

        if not self.mode._lcd_accept(top56, bot56):
            return

        layout = getattr(definitions, "MC_DEBUG_LAYOUT", "continuous").lower()
        bh = int(getattr(definitions, "MC_DEBUG_HEIGHT", 22))
        alpha = float(getattr(definitions, "MC_DEBUG_ALPHA", 0.85))
        font = getattr(definitions, "MC_DEBUG_FONT", "Menlo")
        rows = 1 if not bot56.strip() else 2

        ctx.save()
        ctx.rectangle(0, 0, w, rows * bh)
        ctx.set_source_rgba(0, 0, 0, alpha)
        ctx.fill()

        for fam in (font, "Menlo", "Monaco", "Courier New", "Courier"):
            try:
                ctx.select_font_face(fam, 0, 0)
                break
            except Exception:
                continue

        if not hasattr(self, "_dbg_cache"):
            self._dbg_cache = {"cont_size": None, "cell_size": None, "w": None, "bh": None, "layout": None}

        def _ensure_size(sample_chars: int, target_width: float, key: str):
            if (self._dbg_cache.get(key) is not None and
                    self._dbg_cache["w"] == w and
                    self._dbg_cache["bh"] == bh and
                    self._dbg_cache["layout"] == layout):
                ctx.set_font_size(self._dbg_cache[key]); return self._dbg_cache[key]
            size = max(8, bh - 6)
            ctx.set_font_size(size)
            _, _, tw, _, _, _ = ctx.text_extents("M" * sample_chars)
            while tw > target_width and size > 8:
                size -= 0.5
                ctx.set_font_size(size)
                _, _, tw, _, _, _ = ctx.text_extents("M" * sample_chars)
            self._dbg_cache.update({key: size, "w": w, "bh": bh, "layout": layout})
            return size

        def _draw_guides(rows_to_draw):
            if not getattr(definitions, "MC_DEBUG_GUIDES", False):
                return
            ctx.save()
            ctx.set_source_rgba(1, 1, 1, 0.08)
            for i in range(1, 8):
                x = i * (w / 8.0)
                ctx.move_to(x, 0); ctx.line_to(x, rows_to_draw * bh)
            ctx.set_line_width(1); ctx.stroke(); ctx.restore()

        ctx.set_source_rgb(0, 1, 0)

        if layout == "continuous":
            pad_x = 4
            size = _ensure_size(56, w - pad_x * 2, "cont_size")
            ctx.set_font_size(size)

            def glue_units(s: str) -> str:
                return (s.replace(" dB", "\u202FdB")
                        .replace(" Hz", "\u202FHz")
                        .replace(" kHz", "\u202FkHz")
                        .replace(" %", "\u202F%"))

            ctx.move_to(pad_x, 1 * bh - 6); ctx.show_text(glue_units(top56))
            if rows == 2:
                ctx.move_to(pad_x, 2 * bh - 6); ctx.show_text(glue_units(bot56))
            _draw_guides(rows); ctx.restore(); return

        # cells layout
        import re
        col_w = w / 8.0; pad_x = 4
        size = _ensure_size(7, col_w - pad_x * 2, "cell_size")
        ctx.set_font_size(size)
        collapse = bool(getattr(definitions, "MC_DEBUG_COLLAPSE_SPACES", True))
        smart_glue = bool(getattr(definitions, "MC_DEBUG_SMART_GLUE", True))

        def _tight(s: str) -> str:
            return re.sub(r"\s{2,}", " ", s) if collapse else s

        def _row_to_cells(text56: str):
            cells = [(_tight(text56[i * 7:(i + 1) * 7]) + "       ")[:7] for i in range(8)]
            if not smart_glue:
                return cells
            for i in range(7):
                left = list(cells[i]); right = list(cells[i + 1])
                li = 6
                while li >= 0 and left[li] == " ": li -= 1
                ri = 0
                while ri < 7 and right[ri] == " ": ri += 1

                def pull_one():
                    nonlocal left, right, ri
                    if ri >= 7: return
                    ch = right[ri]; sp = "".join(left).rfind(" ")
                    if sp != -1: left[sp] = ch
                    else: left = left[1:] + [ch]
                    right.pop(ri); right.append(" ")

                if li >= 0 and ri < 7:
                    lch = left[li]; rch = right[ri]
                    if lch == "d" and rch == "B": pull_one()
                    if lch == "H" and rch == "z": pull_one()
                    if lch == "k" and rch == "H": pull_one()
                    if rch == "%": pull_one()
                cells[i] = ("".join(left) + "       ")[:7]
                cells[i + 1] = ("".join(right) + "       ")[:7]
            return cells

        def _looks_numeric(seg: str) -> bool:
            seg = seg.strip()
            return bool(seg) and (any(ch.isdigit() for ch in seg) or seg.startswith(("+", "-")))

        def _draw_row_cells(text56: str, row_idx: int):
            baseline = (row_idx + 1) * bh - 6
            cells = _row_to_cells(text56)
            for col, seg in enumerate(cells):
                x0 = col * col_w
                xb, yb, tw, th, _, _ = ctx.text_extents(seg)
                tx = (x0 + col_w - pad_x - tw - xb) if _looks_numeric(seg) else (x0 + pad_x - xb)
                ty = baseline - yb
                ctx.save(); ctx.rectangle(x0, row_idx * bh, col_w, bh); ctx.clip()
                ctx.move_to(tx, ty); ctx.show_text(seg); ctx.restore()

        _draw_row_cells(top56, 0)
        if rows == 2:
            _draw_row_cells(bot56, 1)
        _draw_guides(rows)
        ctx.restore()

    def _draw_bottom_mode_labels(self, ctx, w, h):
        col_w = w / 8.0
        bar_h = 22
        bar_y = h - bar_h - 2
        corner = 6

        for i, mode in enumerate(self.mode.LOWER_ROW_MODES):
            x = int(i * col_w) + 1
            width = int(col_w) - 2

            selected = (mode == self.mode.active_mode)
            fill_col = self.mode.MODE_COLORS.get(mode, definitions.GRAY_DARK) if selected else definitions.GRAY_DARK
            text_col = definitions.BLACK if selected else self.mode.MODE_COLORS.get(mode, definitions.GRAY_LIGHT)

            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(fill_col))
            ctx.new_sub_path()
            ctx.arc(x + width - corner, bar_y + corner, corner, math.radians(-90), math.radians(0))
            ctx.arc(x + width - corner, bar_y + bar_h - corner, corner, math.radians(0), math.radians(90))
            ctx.arc(x + corner, bar_y + bar_h - corner, corner, math.radians(90), math.radians(180))
            ctx.arc(x + corner, bar_y + corner, corner, math.radians(180), math.radians(270))
            ctx.close_path()
            ctx.fill()
            ctx.restore()

            label = self.mode.MODE_LABELS.get(mode, mode.upper())
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(text_col))
            ctx.select_font_face("Helvetica", 0, 0)
            ctx.set_font_size(12)
            xb, yb, tw, th, _, _ = ctx.text_extents(label)
            tx = x + (width - tw) / 2.0 - xb
            ty = bar_y + (bar_h - th) / 2.0 - yb
            ctx.move_to(tx, ty)
            ctx.show_text(label)
            ctx.restore()
