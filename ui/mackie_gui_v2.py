import definitions
from .base import Renderer


class MackieGuiV2(Renderer):
    """
    New GUI surface (WIP).
    For now: clean header + per-strip name + mute/solo badges,
    while encoders/buttons keep working via MackieControlMode.
    """

    def __init__(self, mode):
        self.mode = mode
        self.w, self.h = 960, 160

    def on_resize(self, w: int, h: int) -> None:
        self.w, self.h = w, h

    # --- tiny text + token helpers
    def _text(self, ctx, x, y, s, size=12):
        ctx.select_font_face("Arial", 0, 0)
        ctx.set_font_size(size)
        ctx.move_to(x, y)
        ctx.show_text(s)

    def _hdr_token(self, ctx, x, y, label):
        pad = 6
        ctx.set_source_rgb(0.15, 0.15, 0.15)
        ctx.rectangle(x, y - 12, len(label) * 7 + pad * 2, 16)
        ctx.fill()
        ctx.set_source_rgb(1, 1, 1)
        self._text(ctx, x + pad, y, label)

    # --- header
    def _draw_header(self, ctx, w, h):
        mm = getattr(self.mode.app, "mcu_manager", None)
        assignment = getattr(self.mode, "active_mode", "volume").upper()
        subview = "A"  # keep simple for now
        page_idx = getattr(mm, "page_index", 1) or 1
        page_cnt = getattr(mm, "page_count", 1) or 1
        flip_on = bool(getattr(mm, "flip", False))
        bank_start = getattr(mm, "bank_start", 0) + 1
        bank_end = getattr(mm, "bank_end", 8)
        sel_track = getattr(mm, "selected_track_idx", None)
        sel_label = f"T{sel_track + 1}" if sel_track is not None else "-"

        x = 8
        y = 18
        self._hdr_token(ctx, x, y, f"MODE: {assignment} • Sub: {subview}")
        x += 210
        self._hdr_token(ctx, x, y, f"Bank: {bank_start}–{bank_end}")
        x += 140
        self._hdr_token(ctx, x, y, f"Page: {page_idx}/{page_cnt}")
        x += 130
        self._hdr_token(ctx, x, y, f"FLIP: {'ON' if flip_on else 'OFF'}")
        x += 120
        self._hdr_token(ctx, x, y, f"SEL: {sel_label}")

    # --- lightweight body (names + M/S badges + selection underline)
    def _draw_strips_mute_solo(self, ctx, w, h):
        mm = getattr(self.mode.app, "mcu_manager", None)
        if not mm:
            return
        col_w = w / 8.0
        for i in range(8):
            x = i * col_w
            y = 32
            try:
                name = mm.track_names[i]
                solo = mm.solo_states[i]
                mute = mm.mute_states[i]
                sel = (mm.selected_track_idx == i)
            except Exception:
                name, solo, mute, sel = "", False, False, False

            ctx.set_source_rgb(0.9, 0.9, 0.9 if not mute else 0.5)
            self._text(ctx, x + 6, y + 12, name[:10], 12)

            by = y + 28
            if solo:
                ctx.set_source_rgb(1.0, 0.9, 0.2)
                self._text(ctx, x + 6, by, "S", 12)
                x_badge = x + 18
            else:
                x_badge = x + 6
            if mute:
                ctx.set_source_rgb(0.3, 0.7, 1.0)
                self._text(ctx, x_badge, by, "M", 12)

            if sel:
                ctx.set_source_rgb(1, 1, 1)
                ctx.set_line_width(2.0)
                ctx.move_to(x + 4, h - 8)
                ctx.line_to(x + col_w - 4, h - 8)
                ctx.stroke()

    def render(self, ctx, w: int, h: int) -> None:
        # background
        ctx.rectangle(0, 0, w, h)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()

        # keep normal sync/value updates
        if hasattr(self.mode, "_flush_pending_tx"): self.mode._flush_pending_tx()
        if hasattr(self.mode, "_sync_pan_from_logic"): self.mode._sync_pan_from_logic()
        if hasattr(self.mode, "update_strip_values"): self.mode.update_strip_values()

        # draw
        self._draw_header(ctx, w, h)
        self._draw_strips_mute_solo(ctx, w, h)
