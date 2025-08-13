import math, mido, threading, time
import definitions, push2_python
from display_utils import show_text
from definitions import pb_to_db, db_to_pb, MCU_SYSEX_PREFIX, MCU_MODEL_ID, MCU_METERS_ON, MCU_METERS_OFF
from push2_python import constants as P2
from typing import Optional  # put this at the top with imports
from push2_python.constants import ANIMATION_STATIC

# Color helpers (choose safe fallbacks if a name isn't defined in your palette)
_SKY = getattr(definitions, "SKY_BLUE", getattr(definitions, "SKYBLUE", getattr(definitions, "CYAN", "cyan")))
_CYAN = _SKY
_YELLOW = getattr(definitions, "YELLOW", "yellow")
_RED = getattr(definitions, "RED", "red")
_ORANGE = getattr(definitions, "ORANGE", "orange")
_GREEN = getattr(definitions, "GREEN", "green")
_OFF = getattr(definitions, "BLACK", "black")
_DARK = getattr(definitions, "GRAY_DARK", "gray")


def _row_buttons(row_index: int):
    # Return pad IDs as (row, col) tuples for pads.set_pad_color
    return [(row_index, c) for c in range(8)]


def _mcu_note_for(row: int, col: int) -> Optional[int]:
    """Rows 0..3 map to SELECT / MUTE / SOLO / REC (MCU notes)."""
    if not (0 <= col < 8):
        return None
    if row == 0:  # SELECT
        return 24 + col
    if row == 1:  # MUTE
        return 16 + col
    if row == 2:  # SOLO
        return 8 + col
    if row == 3:  # REC
        return 0 + col
    return None


# === Mode constants ===
MODE_VOLUME = "volume"
MODE_MUTE = "mute"
MODE_SOLO = "solo"
MODE_PAN = "pan"
MODE_VPOT = "vpot"
MODE_EXTRA1 = "extra1"
MODE_EXTRA2 = "extra2"
MODE_EXTRA3 = "extra3"

MODE_LABELS = {
    MODE_VOLUME: "VOL",
    MODE_MUTE: "MUTE",
    MODE_SOLO: "SOLO",
    MODE_PAN: "PAN",
    MODE_VPOT: "VPOT",
    MODE_EXTRA1: "X1",
    MODE_EXTRA2: "X2",
    MODE_EXTRA3: "X3",
}

LOWER_ROW_MODES = [
    MODE_VOLUME, MODE_MUTE, MODE_SOLO, MODE_PAN,
    MODE_VPOT, MODE_EXTRA1, MODE_EXTRA2, MODE_EXTRA3,
]

MODE_COLORS = {
    "volume": getattr(definitions, "GREEN", "green"),
    "mute": _SKY,
    "solo": _YELLOW,
    "pan": getattr(definitions, "KARMA", getattr(definitions, "ORANGE", "orange")),
    "vpot": getattr(definitions, "PINK", "pink"),
    "extra1": getattr(definitions, "GRAY_DARK", "gray"),
    "extra2": getattr(definitions, "GREEN_LIGHT", getattr(definitions, "GREEN", "green")),
    "extra3": getattr(definitions, "RED_LIGHT", getattr(definitions, "RED", "red")),
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _bank(idx: int) -> int:
    """Return the 0-7 index within the current 8-channel MCU bank."""
    return idx % 8


PAD_COLUMNS = [[(row, col)  # 0-based, bottom-row = 0
                for row in range(8)]
               for col in range(8)]


# ──────────────────────────────────────────────────────────────────────────────
# TrackStrip
# ──────────────────────────────────────────────────────────────────────────────
class TrackStrip:
    """A little data-object plus draw / update helpers."""

    def __init__(
            self,
            app,
            index,
            name,
            get_color_func,
            get_volume_func,
            set_volume_func,
            get_pan_func,
    ):
        self.app = app
        self.index = index  # 0-63 absolute
        self.name = name
        self.get_color_func = get_color_func
        self.get_volume_func = get_volume_func
        self.set_volume_func = set_volume_func
        self.get_pan_func = get_pan_func
        self.vmin = 0.0
        self.vmax = 1.0

    # ---------------------------------------------------------------------- UI
    def draw(self, ctx, x_part, selected=False):
        margin_top = 25
        name_h = 20
        val_h = 30
        meter_h = 55
        radius = meter_h / 2

        display_w = push2_python.constants.DISPLAY_LINE_PIXELS
        display_h = push2_python.constants.DISPLAY_N_LINES
        col_width = display_w // 8
        x = int(col_width * x_part)
        y = 0  # top

        color = self.get_color_func(self.index)
        volume = self.get_volume_func(self.index)
        db = MackieControlMode._level_to_db(volume)
        label = "-∞ dB" if db == float('-inf') else f"{db:+.1f} dB"

        # highlight selected track
        if selected:
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.OFF_BLACK))
            ctx.rectangle(x, y, col_width, display_h)
            ctx.fill()
            ctx.restore()

        # horizontal centring
        content_x = x + col_width * 0.25
        xc = content_x + radius + 3
        yc = margin_top + name_h + val_h + radius + 5

        show_text(ctx, x_part, margin_top, self.name,
                  height=name_h, font_color=color)
        show_text(ctx, x_part, margin_top + name_h, label,
                  height=val_h, font_color=color)

        start_rad = math.radians(130)
        arc_rad = start_rad + (math.radians(280) * volume)

        ctx.save()
        # background arc
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(xc, yc)
        ctx.stroke()

        ctx.arc(xc, yc, radius, start_rad, math.radians(50))
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.set_line_width(1)
        ctx.stroke()

        # value arc
        ctx.arc(xc, yc, radius, start_rad, arc_rad)
        ctx.set_source_rgb(*definitions.get_color_rgb_float(color))
        ctx.set_line_width(3)
        ctx.stroke()
        ctx.restore()

        # --- pan (green number + green indents driven by smooth pan) ---
        pan_f = float(self.get_pan_func(self.index))  # −64..+63 from Logic
        pan_clamped = max(-64.0, min(64.0, pan_f))

        # 15-tick ring, continuous segment from center to current, center detent lights within ±1
        ticks = 15
        center = (ticks - 1) // 2

        # normalize −64..+64 → 0..1 → 0..(ticks-1)
        norm = (pan_clamped + 64.0) / 128.0
        if norm < 0.0: norm = 0.0
        if norm > 1.0: norm = 1.0
        cur_idx = int(round(norm * (ticks - 1)))

        inner_r = radius - 6
        tick_len = 6
        for i in range(ticks):
            ang = start_rad + math.radians(280) * i / (ticks - 1)
            x1 = xc + inner_r * math.cos(ang)
            y1 = yc + inner_r * math.sin(ang)
            x2 = xc + (inner_r - tick_len) * math.cos(ang)
            y2 = yc + (inner_r - tick_len) * math.sin(ang)

            # light a solid segment from center to current; always light center within deadband
            lit = ((cur_idx == center and i == center) or
                   (cur_idx < center and center >= i >= cur_idx) or
                   (cur_idx > center and center <= i <= cur_idx) or
                   (abs(pan_clamped) <= 1 and i == center))

            col = definitions.GREEN if lit else definitions.GRAY_DARK
            ctx.set_source_rgb(*definitions.get_color_rgb_float(col))
            ctx.set_line_width(2)
            ctx.move_to(x1, y1)
            ctx.line_to(x2, y2)
            ctx.stroke()

        # green pan text
        pan_text = f"{int(pan_clamped):+d}" if pan_clamped.is_integer() else f"{pan_clamped:+.1f}"
        ctx.save()
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GREEN))
        ctx.select_font_face("Helvetica", 0, 0)
        ctx.set_font_size(14)
        xb, yb, tw, th, xadv, yadv = ctx.text_extents(pan_text)
        tx = xc - (tw / 2.0) - xb
        ty = yc - (th / 2.0) - yb
        ctx.move_to(tx, ty)
        ctx.show_text(pan_text)
        ctx.restore()

    # ------------------------------------------------------------------ values
    def update_value(self, increment):
        """
        Normal turn   : coarse   (0.5 dB)
        SHIFT held    : fine     (0.05 dB)
        SHIFT+SELECT  : super-fine (0.01 dB)
        """
        base_step = 0.007  # ~0.5 dB around unity
        mult = 1.0
        if self.app.shift_held:
            mult = 0.1
            if self.app.select_held:
                mult = 0.02
        step = base_step * mult
        new_val = max(
            self.vmin,
            min(self.vmax, self.get_volume_func(self.index) + increment * step),
        )
        self.set_volume_func(self.index, new_val)


# ──────────────────────────────────────────────────────────────────────────────
# MackieControlMode
# ──────────────────────────────────────────────────────────────────────────────
class MackieControlMode(definitions.LogicMode):
    xor_group = "pads"
    # === NEW: mode state ======================================================
    active_mode = MODE_VOLUME  # default
    _polling_active = False
    # Pad brightness policy: OFF = dimmed gray, ON = full
    _PAD_OFF_COLOR = _DARK                 # GRAY_DARK from your palette
    _PAD_OFF_BRIGHT = 1.0                # tweak: 0.35..0.6 depending on taste
    _PAD_ON_BRIGHT = 1.0
    # Pan state: view is the green number (−64..+63), ring is 0..11 from Logic echo
    _pan_view = [0.0] * 8
    _pan_ring = [6] * 8
    _last_pan = [None] * 8

    _name_cache = [""] * 8
    _last_names_print = 0  # throttle debug printing
    _last_grid_snapshot = None
    # ---------------------------------------------------------------- helpers
    def _draw_top_mute_solo_header(self, ctx, w, h):
        mm = getattr(self.app, "mcu_manager", None)
        if not mm:
            return

        header_h = 22
        y = 0
        col_w = w / 8.0

        sky = getattr(definitions, "SKYBLUE", getattr(definitions, "CYAN", definitions.BLUE))
        yellow = definitions.YELLOW

        for i in range(8):
            strip_idx = self.current_page * self.tracks_per_page + i
            mute = bool(mm.mute_states[strip_idx]) if strip_idx < len(mm.mute_states) else False
            solo = bool(mm.solo_states[strip_idx]) if strip_idx < len(mm.solo_states) else False

            x = int(i * col_w)
            half = int(col_w / 2)

            # Left half = MUTE
            mute_bg = sky if mute else definitions.BLACK
            mute_fg = definitions.BLACK if mute else sky

            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(mute_bg))
            ctx.rectangle(x, y, half, header_h)
            ctx.fill()
            ctx.restore()

            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(mute_fg))
            ctx.select_font_face("Helvetica", 0, 0)
            ctx.set_font_size(11)
            label = "MUTE"
            xb, yb, tw, th, xadv, yadv = ctx.text_extents(label)
            tx = x + (half - tw) / 2.0 - xb
            ty = y + (header_h - th) / 2.0 - yb
            ctx.move_to(tx, ty)
            ctx.show_text(label)
            ctx.restore()

            # Right half = SOLO
            solo_bg = yellow if solo else definitions.BLACK
            solo_fg = definitions.BLACK if solo else yellow

            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(solo_bg))
            ctx.rectangle(x + half, y, half, header_h)
            ctx.fill()
            ctx.restore()

            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(solo_fg))
            ctx.select_font_face("Helvetica", 0, 0)
            ctx.set_font_size(11)
            label = "SOLO"
            xb, yb, tw, th, xadv, yadv = ctx.text_extents(label)
            tx = x + half + (half - tw) / 2.0 - xb
            ty = y + (header_h - th) / 2.0 - yb
            ctx.move_to(tx, ty)
            ctx.show_text(label)
            ctx.restore()

    def _tap_mcu_button(self, note_num: int):
        port = self.app.mcu_manager.output_port or getattr(self.app, "midi_out", None)
        if not port:
            return
        port.send(mido.Message('note_on', note=note_num, velocity=127, channel=0))
        port.send(mido.Message('note_on', note=note_num, velocity=0, channel=0))

    @staticmethod
    def _level_to_db(level: float) -> float:
        return pb_to_db(int(level * 16383))

    @staticmethod
    def _db_to_level(db: float) -> float:
        return db_to_pb(db) / 16383.0

    buttons_used = [
        # upper row
        push2_python.constants.BUTTON_UPPER_ROW_1,
        push2_python.constants.BUTTON_UPPER_ROW_2,
        push2_python.constants.BUTTON_UPPER_ROW_3,
        push2_python.constants.BUTTON_UPPER_ROW_4,
        push2_python.constants.BUTTON_UPPER_ROW_5,
        push2_python.constants.BUTTON_UPPER_ROW_6,
        push2_python.constants.BUTTON_UPPER_ROW_7,
        push2_python.constants.BUTTON_UPPER_ROW_8,
        # lower row
        push2_python.constants.BUTTON_LOWER_ROW_1,
        push2_python.constants.BUTTON_LOWER_ROW_2,
        push2_python.constants.BUTTON_LOWER_ROW_3,
        push2_python.constants.BUTTON_LOWER_ROW_4,
        push2_python.constants.BUTTON_LOWER_ROW_5,
        push2_python.constants.BUTTON_LOWER_ROW_6,
        push2_python.constants.BUTTON_LOWER_ROW_7,
        push2_python.constants.BUTTON_LOWER_ROW_8,
    ]
    # current_page = 0
    n_pages = 1

    tracks_per_page = 8
    track_strips = []

    encoder_names = [
        push2_python.constants.ENCODER_TRACK1_ENCODER,
        push2_python.constants.ENCODER_TRACK2_ENCODER,
        push2_python.constants.ENCODER_TRACK3_ENCODER,
        push2_python.constants.ENCODER_TRACK4_ENCODER,
        push2_python.constants.ENCODER_TRACK5_ENCODER,
        push2_python.constants.ENCODER_TRACK6_ENCODER,
        push2_python.constants.ENCODER_TRACK7_ENCODER,
        push2_python.constants.ENCODER_TRACK8_ENCODER,
    ]

    # ---------------------------------------------------------------- helpers
    def _sync_pan_from_logic(self):
        """
        Ensure GUI matches Logic even if Logic changed pan via typing/automation.
        Uses continuous float from mm.pan_levels (no detent snapping).
        """
        mm = getattr(self.app, "mcu_manager", None)
        if not (mm and hasattr(mm, "pan_levels")):
            return

        for i in range(8):
            try:
                val = float(mm.pan_levels[i])  # <-- continuous from Logic
            except Exception:
                continue

            if self._last_pan[i] is None or abs(val - float(self._last_pan[i])) > 0.01:
                self._last_pan[i] = val
                self._pan_view[i] = val
                # Update ring to match the new value (0..127 for Push ring)
                led = int(((val + 64.0) / 128.0) * 127.0)
                self._set_ring(i, led)
                self.app.display_dirty = True

    def _set_pad_color(self, pad_id, color):
        # pad_id = (row, col)
        # STATIC avoids the pre-black frame
        self.push.pads.set_pad_color(
            pad_id,
            color,
            animation=ANIMATION_STATIC,
            optimize_num_messages=True
        )

    def _draw_bottom_mode_labels(self, ctx, w, h):
        # Mirror track_selection_mode.py proportions
        display_w = w
        display_h = h
        col_w = display_w / 8.0

        bar_h = 22  # match TS look
        bar_y = display_h - bar_h - 2
        corner = 6

        for i, mode in enumerate(LOWER_ROW_MODES):
            x = int(i * col_w) + 1
            width = int(col_w) - 2

            selected = (mode == self.active_mode)
            fill_col = MODE_COLORS.get(mode, definitions.GRAY_DARK) if selected else definitions.GRAY_DARK
            text_col = definitions.BLACK if selected else MODE_COLORS.get(mode, definitions.GRAY_LIGHT)

            # rounded rect
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(fill_col))
            # draw rounded rect
            ctx.new_sub_path()
            ctx.arc(x + width - corner, bar_y + corner, corner, math.radians(-90), math.radians(0))
            ctx.arc(x + width - corner, bar_y + bar_h - corner, corner, math.radians(0), math.radians(90))
            ctx.arc(x + corner, bar_y + bar_h - corner, corner, math.radians(90), math.radians(180))
            ctx.arc(x + corner, bar_y + corner, corner, math.radians(180), math.radians(270))
            ctx.close_path()
            ctx.fill()
            ctx.restore()

            # label centered
            label = MODE_LABELS.get(mode, mode.upper())
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(text_col))
            ctx.select_font_face("Helvetica", 0, 0)
            ctx.set_font_size(12)

            xb, yb, tw, th, xadv, yadv = ctx.text_extents(label)
            tx = x + (width - tw) / 2.0 - xb
            ty = bar_y + (bar_h - th) / 2.0 - yb
            ctx.move_to(tx, ty)
            ctx.show_text(label)
            ctx.restore()

    def _blank_track_row_buttons(self):
        for btn in self.buttons_used:
            self.push.buttons.set_button_color(btn, definitions.OFF_BTN_COLOR)

    # === NEW: selector row paint + mode switch ================================
    def _set_mode(self, mode: str):
        if mode not in MODE_LABELS:
            return
        self.active_mode = mode
        self.update_buttons()
        self.update_encoders()
        self._paint_selector_row()
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def _paint_lower_selector(self):
        """Color the lower row buttons as mode selector."""
        for i, mode in enumerate(LOWER_ROW_MODES):
            btn = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}", None)
            if not btn:
                continue
            col = MODE_COLORS.get(mode, definitions.GRAY_DARK)
            self.push.buttons.set_button_color(btn, col if mode == self.active_mode else definitions.GRAY_DARK)

    def _paint_selector_row(self):
        """
        Repaint the bottom row pads (hardware row=7) after PadMeter runs.
        Selected mode = brighter.
        """
        bottom_row = 7
        for col, mode in enumerate(LOWER_ROW_MODES):
            pad_id = (bottom_row, col)
            colr = MODE_COLORS.get(mode, definitions.GRAY_DARK)
            if mode == self.active_mode:
                self.push.pads.set_pad_color(pad_id, colr)
            else:
                self.push.pads.set_pad_color(pad_id, definitions.GRAY_DARK)

    def _send_mcu_vpot_delta(self, channel: int, increment: int):
        """
        Basic MCU V-Pot delta:
        CC 16–23, value 1..63 = CW, 65..127 = CCW. We'll send a single tick.
        """
        mcu = getattr(self.app, "mcu_manager", None)
        port = mcu.output_port if (mcu and mcu.output_port) else getattr(self.app, "midi_out", None)
        if port is None:
            return
        cc = 16 + channel
        val = 1 if increment > 0 else 65
        port.send(mido.Message('control_change', control=cc, value=val))

    def activate_mix_mode(self):
        """Call this when entering Mix mode."""
        self._render_mix_grid("activate_mix_mode")

        # === Rendering ===
    def _render_mix_grid(self, msg: str = ""):
        """
        Paint rows 0..3 as a bank of 8:
          base  = GRAY_DARK everywhere,
          row 0 = active track GREEN,
          row 1 = MUTE  -> SKY,
          row 2 = SOLO  -> YELLOW,
          row 3 = REC   -> RED.
        Skips repaint if nothing changed (snapshot).
        """


        mcu = getattr(self.app, "mcu_manager", None)
        if not mcu:
            return

        base = (getattr(self, "current_page", 0) or 0) * 8
        top  = base + 8

        # Defensive arrays
        mute_states = getattr(mcu, "mute_states", []) or []
        solo_states = getattr(mcu, "solo_states", []) or []
        rec_states  = getattr(mcu, "recarm_states", []) or []

        def _state(arr, abs_idx):
            try:
                return bool(arr[abs_idx]) if 0 <= abs_idx < len(arr) else False
            except Exception:
                return False

        # Selected track (relative within visible bank)
        sel_rel = -1
        sel_abs = getattr(mcu, "selected_track_idx", None)
        if isinstance(sel_abs, (int, float)):
            sel_abs = int(sel_abs)
            if base <= sel_abs < top:
                sel_rel = sel_abs - base

        # --- build snapshot of visible state (for no-op early return) ---
        m_row = tuple(_state(mute_states, base + i) for i in range(8))
        s_row = tuple(_state(solo_states, base + i) for i in range(8))
        r_row = tuple(_state(rec_states,  base + i) for i in range(8))
        snapshot = (base, sel_rel, m_row, s_row, r_row)

        if snapshot == getattr(self, "_last_grid_snapshot", None):
            return  # nothing changed; skip writes
        if msg:
            print(f"[MCP RENDERMIX] From: {msg}")
        self._last_grid_snapshot = snapshot

        # Row pad IDs
        row_select = _row_buttons(0)
        row_mute   = _row_buttons(1)
        row_solo   = _row_buttons(2)
        row_rec    = _row_buttons(3)

        # Build paint list (pairs: ((row,col), color))
        to_set = []

        # 1) Base layer: dim gray everywhere on rows 0..3
        for row in (row_select, row_mute, row_solo, row_rec):
            for pad_id in row:
                to_set.append((pad_id, _DARK))

        # 2) Selected track (row 0)
        if 0 <= sel_rel < 8:
            to_set.append((row_select[sel_rel], _GREEN))

        # 3) Per-track overlays (rows 1..3)
        for i in range(8):
            abs_idx = base + i
            if _state(mute_states, abs_idx):
                to_set.append((row_mute[i], _SKY))
            if _state(solo_states, abs_idx):
                to_set.append((row_solo[i], _YELLOW))
            if _state(rec_states, abs_idx):
                to_set.append((row_rec[i], _RED))

        # Apply in order (later writes override base)
        self._apply_pad_colors(to_set)
        self.app.pads_need_update = True


# Call this whenever MCU state changes (bank switch, external updates, etc.)
    def on_mcu_state_changed(self):
        self._render_mix_grid("mcu state changed")

    # ---------------------------------------------------------------- init/up
    def initialize(self, settings=None):
        """Build default strips and start meter timer."""
        super().initialize(settings) if hasattr(super(), "initialize") else None
        # self._pad_meter = PadMeter(self.push)
        self.track_strips = []
        self.current_page = 0
        self.tracks_per_page = 8

        # reset pan state
        self._pan_view = [0.0] * 8
        self._pan_ring = [6] * 8
        self._last_pan = [None] * 8

        def get_color(idx):
            mm = getattr(self.app, "mcu_manager", None)
            if mm and hasattr(mm, "track_colors"):
                return mm.track_colors[_bank(idx)]
            return definitions.GRAY_LIGHT

        def get_volume(idx):
            mm = getattr(self.app, "mcu_manager", None)
            return mm.fader_levels[_bank(idx)] if mm else 0.0

        def set_volume(idx, val):
            mm = getattr(self.app, "mcu_manager", None)
            if mm:
                bank_idx = _bank(idx)
                mm.fader_levels[bank_idx] = val
                mm.emit_event("fader", channel_idx=bank_idx, level=val)

        def get_pan(idx):
            return float(self._pan_view[_bank(idx)])

        for i in range(64):
            self.track_strips.append(
                TrackStrip(self.app, i, f"Track {i + 1}", get_color, get_volume, set_volume, get_pan)
            )

        # add listeners only once
        mm = getattr(self.app, "mcu_manager", None)
        if mm and not getattr(self, "_listeners_added", False):
            mm.add_listener("pan", self._on_mcu_pan)
            mm.add_listener("transport", self._on_mcu_transport)
            mm.add_listener("track_state", self._on_mcu_track_state)
            mm.add_listener("solo", self._on_mcu_track_state)
            mm.add_listener("mute", self._on_mcu_track_state)
            mm.add_listener("meter", self._on_mcu_meter)
            mm.add_listener("pan_text", self._on_mcu_pan_text)
            # current transport state
            self._playing = mm.transport.get("play", False)
            self._on_mcu_transport(state=mm.transport)
            self._on_mcu_meter()

            # self.pad_meter = PadMeter(self.push)
            self._listeners_added = True

    def _apply_pad_colors(self, pairs):
        # pairs: [((row, col), color), ...]
        for pad_id, col in pairs:
            self._set_pad_color(pad_id, col)

    def _on_mcu_transport(self, *, state, **_):
        self._playing = bool(state.get("play", False))
        if self.app.is_mode_active(self):
            self._render_mix_grid("on transport")             # render LAST
            self.app.pads_need_update = True

    def _on_mcu_pan_text(self, *, channel_idx: int, value, **_):
        # Use the precise value typed in Logic for the green number
        if channel_idx is None:
            return
        bi = channel_idx % 8
        if value is not None:
            self._pan_view[bi] = float(value)  # −64..+63 from Logic
            self.app.display_dirty = True
            self.update_strip_values()

    # Called by App when Logic sends the official V-Pot ring echo via SysEx
    def on_mcu_pan_echo(self, ch: int, ring_pos: int):
        if ch is None or not (0 <= ch < 8):
            return
        # Clamp and store 0..11
        rp = max(0, min(11, int(ring_pos)))
        self._pan_ring[ch] = rp
        # Update the physical Push ring immediately (convert 0..11 → 0..127)
        self._set_ring(ch, int(rp * 127 / 11))
        self.app.display_dirty = True

    # --- meters ------------------------------------------------------
    def _on_mcu_meter(self, **_):
        if not self.app.is_mode_active(self):
            return
        if not getattr(self, "_playing", False):
            return

        mm = self.app.mcu_manager
        if not mm or len(mm.meter_levels) < 8:  # <-- guard
            return
        num_banks = max(1, len(mm.meter_levels) // 8)
        raw = []
        for i in range(8):
            levels = [(mm.meter_levels[bank * 8 + i] & 0x0F)
                      for bank in range(num_banks)
                      if (bank * 8 + i) < len(mm.meter_levels)]
            if not levels:
                raw.append(0)
            else:
                raw.append(max(levels))
        MIN_RAW = 4
        MAX_RAW = 12

        scaled = []
        for v in raw:
            if v <= MIN_RAW:
                s = 0
            else:
                frac = (v - MIN_RAW) / (MAX_RAW - MIN_RAW)
                s = int(frac * 127)
                s = max(1, min(127, s))
            scaled.append(s)

        # self._pad_meter.update(scaled)

    # ---------------------------------------------------------------- ring helper
    def _set_ring(self, idx: int, value: int):
        """
        Set encoder ring LEDs. Handles multiple push2_python API variants.
        """
        enc = self.push.encoders
        name = self.encoder_names[idx]
        value = max(0, min(127, int(value)))

        if hasattr(enc, "set_ring_value"):
            enc.set_ring_value(name, value);
            return
        if hasattr(enc, "set_encoder_ring_value"):
            enc.set_encoder_ring_value(name, value);
            return
        if hasattr(enc, "set_encoder_value"):
            enc.set_encoder_value(name, value);
            return
        if hasattr(enc, "set_value"):
            enc.set_value(name, value);
            return

    def _on_mcu_pan(self, *, channel_idx: int, value: int, **_):
        """
        Logic's pan changed (mouse/automation). Keep both ring and green number in sync.
        Prefer mm.pan_levels (continuous) when available.
        """
        if channel_idx is None:
            return
        if channel_idx < self.current_page * 8 or channel_idx >= (self.current_page + 1) * 8:
            return

        bi = channel_idx % 8
        mm = getattr(self.app, "mcu_manager", None)

        if mm and hasattr(mm, "pan_levels"):
            try:
                val = float(mm.pan_levels[bi])  # −64..+63 (float)
            except Exception:
                val = float(value)
        else:
            val = float(value)

        # Update the Push ring (0..127) and our on‑screen number
        led_val = int(((val + 64.0) / 128.0) * 127.0)
        self._set_ring(bi, led_val)
        self._pan_view[bi] = val
        self._last_pan[bi] = val

        self.app.display_dirty = True
        self.update_strip_values()
        self._render_mix_grid("on pan")
        self.app.pads_need_update = True

    def set_visible_names(self, names):
        """
        Update track strip names from MCU, ignoring transient scribble-strip
        overlays (e.g., 'Volume', 'Pan') and empty strings. Keeps last good
        names so labels don't flicker while touching controls.
        """
        if not names:
            return False

        norm = [(n or "").strip() for n in names[:8]]
        overlays = sum(1 for n in norm if n and n.lower() in definitions.OVERLAY_TOKENS)

        if overlays > 2:
            return False

        changed = False
        for i in range(min(8, len(norm))):
            n = norm[i]
            if not n:
                if self._name_cache[i] and self.track_strips[i].name != self._name_cache[i]:
                    self.track_strips[i].name = self._name_cache[i]
                    changed = True
                continue

            if n.lower() in definitions.OVERLAY_TOKENS:
                if self._name_cache[i] and self.track_strips[i].name != self._name_cache[i]:
                    self.track_strips[i].name = self._name_cache[i]
                    changed = True
                continue

            if n != self.track_strips[i].name:
                self.track_strips[i].name = n
                self._name_cache[i] = n
                changed = True

        if changed:
            self.update_strip_values()
        return changed

    # -------------------------------------------------------------- navigation
    def move_to_next_page(self):
        self.app.buttons_need_update = True
        self.current_page += 1
        if self.current_page >= self.n_pages:
            self.current_page = 0
            # fallthrough
        self._last_grid_snapshot = None
        self._render_mix_grid("page change")
        return True

    def activate(self):
        self.initialize()
        self.current_page = 0
        self._last_grid_snapshot = None
        self.push.pads.reset_current_pads_state()
        if hasattr(self.app.mcu_manager, "get_visible_track_names"):
            names = self.app.mcu_manager.get_visible_track_names()
        else:
            names = getattr(self.app.mcu_manager, "track_names", [])[:self.tracks_per_page]

        self.set_visible_names(names)
        print("[TrackMode] Setting track names:", names)
        # Seed green numbers from Logic cache immediately
        if hasattr(self.app, "mcu_manager"):
            pans = self.app.mcu_manager.get_visible_pan_values()  # [-64..+63 floats]
            if hasattr(self, "set_strip_pan"):
                for i, pan in enumerate(pans):
                    try:
                        self.set_strip_pan(i, int(pan))
                    except Exception:
                        pass
            # repaint once
            if hasattr(self, "update_strip_values"):
                self.update_strip_values()
        self._sync_pan_from_logic()  # ← copy cached pan from MCU manager into UI
        self.update_strip_values()  # ← paint immediately
        self.push.pads.set_all_pads_to_color(
            color=definitions.BLACK,
            animation=ANIMATION_STATIC,
            animation_end_color='black'
        )
        self.update_encoders()
        self._blank_track_row_buttons()
        self.update_buttons()
        self._paint_selector_row()
        self._render_mix_grid("activate")
        # seed from Logic's current pan levels
        mm = getattr(self.app, "mcu_manager", None)
        if mm and hasattr(mm, "pan_levels"):
            for i in range(8):
                v = float(mm.pan_levels[i])
                self._pan_view[i] = v
                self._last_pan[i] = v
                self._set_ring(i, int((v + 64) * 127 / 128))

        # if mm and mm.transport.get("play", False):
        #     self._pad_meter.update(
        #         mm.meter_levels[self.current_page * 8: self.current_page * 8 + 8]
        #     )
        # else:
        #     self._pad_meter.update([0] * 8)

    def deactivate(self):
        super().deactivate()
        self.push.pads.set_all_pads_to_color(
            color=definitions.BLACK,
            animation=ANIMATION_STATIC,
            animation_end_color='black'
        )
        self._blank_track_row_buttons()
        self.app.pads_need_update = True




    def update_display(self, ctx, w, h):
        ctx.rectangle(0, 0, w, h)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()

        # reflect any external pan changes instantly
        self._sync_pan_from_logic()
        self.update_strip_values()
        mm = getattr(self.app, "mcu_manager", None)
        if mm and hasattr(mm, "get_visible_track_names"):
            self.set_visible_names(mm.get_visible_track_names())

        start = self.current_page * self.tracks_per_page
        selected_idx = getattr(self.app.mcu_manager, "selected_track_idx", None)

        for i in range(self.tracks_per_page):
            strip_idx = start + i
            if strip_idx < len(self.track_strips):
                self.track_strips[strip_idx].draw(
                    ctx, i, selected=(strip_idx == selected_idx)
                )

        self._draw_top_mute_solo_header(ctx, w, h)
        self._draw_bottom_mode_labels(ctx, w, h)
        self.update_buttons()
        #self._render_mix_grid("update display")

    def get_current_page(self) -> int:
        mm = getattr(self.app, "mcu_manager", None)
        sel = mm.selected_track_idx if mm else 0
        return (sel or 0) // 8

    def _send_mcu_pan_delta(self, channel: int, delta: int):
        """
        Send MCU V‑Pot relative for PAN on CC 16–23.
        Positive delta => 1..63, Negative delta => 65..127 (65 == -1).
        """
        if delta == 0:
            return
        mag = min(63, abs(int(delta)))
        value = mag if delta > 0 else 64 + mag
        cc_num = 16 + channel
        port = self.app.mcu_manager.output_port or getattr(self.app, "midi_out", None)
        if port:
            port.send(mido.Message('control_change', control=cc_num, value=value, channel=0))

    def update_strip_values(self):
        self.app.display_dirty = True

    def update_encoders(self):
        encoders = self.push.encoders
        for i in range(self.tracks_per_page):
            strip_idx = self.current_page * self.tracks_per_page + i
            if strip_idx >= len(self.track_strips):
                continue
            value = self.track_strips[strip_idx].get_volume_func(strip_idx)
            led_val = int(value * 127)
            encoder_name = self.encoder_names[i]

            if hasattr(encoders, "set_ring_value"):
                encoders.set_ring_value(encoder_name, led_val)
            elif hasattr(encoders, "set_encoder_ring_value"):
                encoders.set_encoder_ring_value(encoder_name, led_val)
            elif hasattr(encoders, "set_value"):
                encoders.set_value(encoder_name, led_val)

    # ---------------------------------------------------------------- inputs
    def update_buttons(self):
        mm = getattr(self.app, "mcu_manager", None)
        self._blank_track_row_buttons()

        if not mm:
            return

        for i in range(8):
            strip_idx = self.current_page * self.tracks_per_page + i

            # Defensive lookups (arrays can be longer than visible bank)
            solo = bool(mm.solo_states[strip_idx]) if strip_idx < len(mm.solo_states) else False
            mute = bool(mm.mute_states[strip_idx]) if strip_idx < len(mm.mute_states) else False

            upper = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
            lower = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")

            # UPPER ROW: per-mode actions/state
            if self.active_mode == MODE_SOLO:
                self.push.buttons.set_button_color(
                    upper,
                    definitions.YELLOW if solo else definitions.OFF_BTN_COLOR
                )
            elif self.active_mode == MODE_MUTE:
                self.push.buttons.set_button_color(
                    upper,
                    _SKY if mute else definitions.OFF_BTN_COLOR
                )
            elif self.active_mode in (MODE_VOLUME, MODE_PAN, MODE_VPOT):
                selected_idx = getattr(mm, "selected_track_idx", None)
                self.push.buttons.set_button_color(
                    upper,
                    definitions.GRAY_LIGHT if selected_idx == strip_idx else definitions.OFF_BTN_COLOR
                )
            else:
                self.push.buttons.set_button_color(upper, definitions.OFF_BTN_COLOR)

            # LOWER ROW: mode selectors
            mode = LOWER_ROW_MODES[i]
            col = MODE_COLORS.get(mode, definitions.GRAY_DARK)
            self.push.buttons.set_button_color(
                lower,
                col if mode == self.active_mode else definitions.GRAY_DARK
            )

    def on_button_pressed_raw(self, btn):
        # LOWER ROW = MODE SELECTORS
        for i in range(8):
            lower_btn = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")
            if btn == lower_btn:
                self._set_mode(LOWER_ROW_MODES[i])
                return True

        # UPPER ROW = TRACK ACTIONS (mode-dependent)
        for i in range(8):
            upper_btn = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
            if btn == upper_btn:
                if self.active_mode == MODE_SOLO:
                    mm = self.app.mcu_manager
                    if mm and mm.selected_track_idx is None:
                        mm.selected_track_idx = self.current_page * self.tracks_per_page + i
                    self._tap_mcu_button(8 + i)  # MCU SOLO notes 8..15
                    self.app.buttons_need_update = True
                    return True

                elif self.active_mode == MODE_MUTE:
                    mm = self.app.mcu_manager
                    if mm and mm.selected_track_idx is None:
                        mm.selected_track_idx = self.current_page * self.tracks_per_page + i
                    self._tap_mcu_button(16 + i)  # MCU MUTE notes 16..23
                    self.app.buttons_need_update = True
                    return True

                elif self.active_mode in (MODE_VOLUME, MODE_PAN, MODE_VPOT):
                    # In these modes, upper row = SELECT for that strip
                    mm = self.app.mcu_manager
                    if mm:
                        abs_idx = self.current_page * self.tracks_per_page + i  # bank-aware
                        mm.selected_track_idx = abs_idx
                    self._tap_mcu_button(24 + i)  # MCU SELECT notes 24..31
                    self._render_mix_grid("on button pressed raw")       # <-- add this so pads snap immediately
                    self.app.buttons_need_update = True
                    return True

        return btn in self.buttons_used

    def on_button_pressed(self, button_name, **_):
        return button_name in self.buttons_used

    def on_button_released(self, button_name):
        return button_name in self.buttons_used

    def on_button_released_raw(self, button_name):
        return button_name in self.buttons_used

    # ───────────────────────────────────────────────────────────────────── MIDI
    def _send_mcu_fader_move(self, channel: int, level: float):
        """
        Real MCU-style: fader movement sends only PITCHBEND.
        Touch down/up is handled by on_encoder_touched/on_encoder_released.
        """
        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if port is None:
            return
        level = max(0.0, min(1.0, float(level)))
        pb_value = int(level * 16383) - 8192  # −8192..+8191
        port.send(mido.Message('pitchwheel', pitch=pb_value, channel=channel))

    def set_bank_levels(self, levels):
        """levels = iterable of ≤8 linear floats.  Writes them to Logic and refreshes Push rings."""
        for ch, val in enumerate(levels[:8]):
            self.app.mcu_manager.fader_levels[ch] = val
            self._send_mcu_fader_move(ch, val)

        self.update_encoders()
        self.update_strip_values()

    # ---------------------------------------------------------------- MCU callbacks

    def _on_mcu_track_state(self, **_):
        if not self.app.is_mode_active(self): return
        self.update_buttons()
        self.update_strip_values()
        self._render_mix_grid("on mcu track state")                 # render LAST
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def on_encoder_rotated(self, encoder_name, increment):
        # Guard checks
        if encoder_name not in self.encoder_names:
            return False

        local_idx = self.encoder_names.index(encoder_name)  # 0–7 within page
        strip_idx = self.current_page * self.tracks_per_page + local_idx
        if strip_idx >= len(self.track_strips):
            return False

        # Encoders control VOLUME in VOL/SOLO/MUTE modes
        if self.active_mode in (MODE_VOLUME, MODE_SOLO, MODE_MUTE):
            self.track_strips[strip_idx].update_value(increment)
            level = self.app.mcu_manager.fader_levels[local_idx]
            self._send_mcu_fader_move(local_idx, level)
            return True

        # PAN mode: send relative delta only; UI updates via Logic echo
        if self.active_mode == MODE_PAN:
            if increment != 0:
                self._send_mcu_pan_delta(local_idx, 1 if increment > 0 else -1)
            return True

        return False

    def _visible_base(self) -> int:
        return (getattr(self, "current_page", 0) or 0) * 8

    def on_pad_pressed(self, pad_n, pad_ij, velocity, loop=False, quantize=False, shift=False, select=False,
                       long_press=False, double_press=False):
        row, col = pad_ij

        # Bottom row = mode selectors
        if row == 7 and 0 <= col < 8:
            mode = LOWER_ROW_MODES[col]
            self._set_mode(mode)
            return True

        note_num = _mcu_note_for(row, col)
        if note_num is None:
            return True

        mcu = getattr(self.app, "mcu_manager", None)

        # --- SELECT (row 0): optimistic local update so it’s instant ---
        if row == 0:
            base = self._visible_base()
            if mcu:
                mcu.selected_track_idx = base + col  # instant local select for pads
            self._render_mix_grid("on pad pressed")                  # show green immediately
            self._set_pad_color((row, col), _GREEN)  # pressed highlight

        # --- MUTE / SOLO / REC: pressed highlight only (state lands on release) ---
        elif row == 1:
            self._set_pad_color((row, col), _CYAN)
        elif row == 2:
            self._set_pad_color((row, col), _YELLOW)
        elif row == 3:
            self._set_pad_color((row, col), _RED)

        # Send MCU tap
        if mcu:
            port = mcu.output_port or getattr(self.app, "midi_out", None)
            if port:
                port.send(mido.Message('note_on', note=note_num, velocity=127, channel=0))
                port.send(mido.Message('note_on', note=note_num, velocity=0, channel=0))
        return True


    def on_pad_released(self, pad_n, pad_ij, **_):
        row, col = pad_ij
        # Repaint from actual MCU state the moment the finger lifts (no timers)
        if 0 <= row <= 3 and 0 <= col < 8:
            self._render_mix_grid("on_pad_released")
            self.app.pads_need_update = True
            self.app.buttons_need_update = True
        return True


    def _pull_lcd_labels_for_visible_bank(self):
        mm = getattr(self.app, "mcu_manager", None)
        if not mm or not hasattr(mm, "get_visible_lcd_lines"):
            return [""] * 8, [""] * 8
        return mm.get_visible_lcd_lines()

    def on_encoder_touched(self, encoder_name):
        """Send MCU fader touch ON immediately, no timers."""
        if encoder_name not in self.encoder_names:
            return False
        ch = self.encoder_names.index(encoder_name)  # 0..7

        if not hasattr(self, "_touch_state"):
            self._touch_state = [False] * 8

        if self._touch_state[ch]:
            return True  # already down

        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if port:
            touch_note = 0x68 + ch  # MCU fader touch notes 0x68–0x6F
            port.send(mido.Message('note_on', note=touch_note, velocity=127, channel=0))
            self._touch_state[ch] = True
        return True

    def on_encoder_released(self, encoder_name):
        """Send MCU fader touch OFF immediately, no timers."""
        if encoder_name not in self.encoder_names:
            return False
        ch = self.encoder_names.index(encoder_name)

        if not hasattr(self, "_touch_state") or not self._touch_state[ch]:
            return True  # already up

        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if port:
            touch_note = 0x68 + ch
            port.send(mido.Message('note_on', note=touch_note, velocity=0, channel=0))
            self._touch_state[ch] = False
        return True

    # ---------------------------------------------------------------- misc
    @property
    def total_pages(self):
        return max(1, math.ceil(len(self.track_strips) / self.tracks_per_page))

    def get_pad_button(self, col, row):
        try:
            return getattr(push2_python.constants, f"BUTTON_ROW_{row}_COL_{col}")
        except AttributeError:
            return None

    @staticmethod
    def _raw_to_signed(raw: float) -> float:
        # 0..127 -> −64..+63
        return float(raw) - 64.0

    @staticmethod
    def _signed_to_raw(signed: float) -> float:
        # −64..+63 -> 0..127
        return max(0.0, min(127.0, signed + 64.0))
