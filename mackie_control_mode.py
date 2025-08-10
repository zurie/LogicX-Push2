import math, mido, threading, time
import definitions, push2_python
from display_utils import show_text
from definitions import pb_to_db, db_to_pb, MCU_SYSEX_PREFIX, MCU_MODEL_ID, MCU_METERS_ON, MCU_METERS_OFF
from pad_meter import PadMeter

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

# Simple palette for the selector pads
MODE_COLORS = {
    MODE_VOLUME: definitions.GREEN,
    MODE_MUTE: definitions.SKYBLUE,
    MODE_SOLO: definitions.YELLOW,
    MODE_PAN: definitions.KARMA,
    MODE_VPOT: definitions.PINK,
    MODE_EXTRA1: definitions.GRAY_DARK,
    MODE_EXTRA2: definitions.GREEN_LIGHT,
    MODE_EXTRA3: definitions.RED_LIGHT,
}

# ──────────────────────────────────────────────────────────────────────────────
# MCU-TOUCH BOOK-KEEPING  (one slot per channel 0-7)
# ──────────────────────────────────────────────────────────────────────────────
TOUCH_DOWN = [False] * 8  # True while NOTE-ON 127 is held
TOUCH_TIMER = [None] * 8  # threading.Timer() objects
RELEASE_MS = 400
POLL_PREFIX = MCU_SYSEX_PREFIX


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

        # ── 11-tick pan ring (still snapped) ─────────────────────────────────────────
        pan_f = float(self.get_pan_func(self.index))  # smoothed
        pan_clamped = max(-64.0, min(64.0, pan_f))
        pan_steps = [-64, -51, -38, -25, -13, 0, 13, 26, 38, 51, 64]
        cur_idx = min(range(len(pan_steps)), key=lambda i: abs(pan_steps[i] - pan_clamped))

        inner_r = radius - 6
        tick_len = 6
        for i, _ in enumerate(pan_steps):
            ang = start_rad + math.radians(280) * i / (len(pan_steps) - 1)
            x1 = xc + inner_r * math.cos(ang)
            y1 = yc + inner_r * math.sin(ang)
            x2 = xc + (inner_r - tick_len) * math.cos(ang)
            y2 = yc + (inner_r - tick_len) * math.sin(ang)
            lit = ((cur_idx == 5 and i == 5) or
                   (cur_idx < 5 and i <= 5 and i >= cur_idx) or
                   (cur_idx > 5 and i >= 5 and i <= cur_idx))
            col = definitions.GREEN if lit else definitions.GRAY_DARK
            ctx.set_source_rgb(*definitions.get_color_rgb_float(col))
            ctx.set_line_width(2)
            ctx.move_to(x1, y1);
            ctx.line_to(x2, y2);
            ctx.stroke()

        # ----- Centered green pan value (now smooth) ---------------------------------
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
        SHIFT+SELECT  : super-fine (0.01 dB)  – good for mastering tweaks
        """
        # base step = ~0.5 dB (= 0.007 in Logic’s 0-1 range around unity)
        base_step = 0.007

        # live modifier keys from the app
        mult = 1.0
        if self.app.shift_held:
            mult = 0.1  # 10× finer
            if self.app.select_held:
                mult = 0.02  # 50× finer (0.01 dB-ish)

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
    _pan_display = [0.0] * 8
    _pan_view = [0.0] * 8
    _last_pan = [None] * 8
    _pan_pred = [64.0] * 8   # start centered
    _name_cache = [""] * 8
    _last_names_print = 0  # throttle debug printing

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
            mute = bool(mm.mute_states[strip_idx % 8])
            solo = bool(mm.solo_states[strip_idx % 8])

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

            # Only repaint when the value really changed (tolerance avoids redraw spam)
            if self._last_pan[i] is None or abs(val - float(self._last_pan[i])) > 0.01:
                self._last_pan[i] = val
                self._pan_view[i] = val
                # Update ring to match the new value
                led = int(((val + 64.0) / 128.0) * 127.0)
                self._set_ring(i, led)
                self.app.display_dirty = True



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

            # Cairo returns (x_bearing, y_bearing, width, height, x_advance, y_advance)
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
        # Refresh everything that depends on mode
        self.update_buttons()
        self.update_encoders()
        self._paint_selector_row()
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def _paint_lower_selector(self):
        """Color the lower row buttons as mode selector."""
        for i, mode in enumerate(LOWER_ROW_MODES):
            btn = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")
            col = MODE_COLORS.get(mode, definitions.GRAY)
            # Selected mode gets its color; others are dim gray
            self.push.buttons.set_button_color(btn, col if mode == self.active_mode else definitions.GRAY)

    def _paint_selector_row(self):
        """
        Repaint the bottom row pads (hardware row=7) after PadMeter runs.
        Selected mode = brighter (WHITE border via dual-color trick not possible,
        so we simply use color vs. dark gray).
        """
        # hardware rows in pad_meter use (row, col), row 0 = top, row 7 = bottom
        bottom_row = 7
        for col, mode in enumerate(LOWER_ROW_MODES):
            pad_id = (bottom_row, col)
            colr = MODE_COLORS.get(mode, definitions.GRAY_DARK)
            if mode == self.active_mode:
                # brighten when selected
                self.push.pads.set_pad_color(pad_id, colr)
            else:
                # dimmed version
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

    # ---------------------------------------------------------------- init/up
    def initialize(self, settings=None):
        """Build default strips and start meter timer."""
        super().initialize(settings) if hasattr(super(), "initialize") else None
        self._pad_meter = PadMeter(self.push)
        self.track_strips = []
        self.current_page = 0
        self.tracks_per_page = 8

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

            # ─────────── new state flag ───────────
            self._playing = mm.transport.get("play", False)
            # ensure we respect the current transport state right away
            self._on_mcu_transport(state=mm.transport)
            # and render one meter frame immediately
            self._on_mcu_meter()

            # instantiate our Push2 meter renderer
            self.pad_meter = PadMeter(self.push)
            self._listeners_added = True

    # ─── transport callback ───────────────────────────────────────────
    def _on_mcu_transport(self, *, state, **_):
        self._playing = bool(state.get("play", False))

        # If Logic just stopped, hard-blank the grid once
        if not self._playing and self.app.is_mode_active(self):
            self._pad_meter.update([0] * 8)  # clear cache + pads
            self.push.pads.set_all_pads_to_color(definitions.BLACK)

    def _on_mcu_pan_text(self, *, channel_idx: int, value, **_):
        # Use the precise value typed in Logic for the green number
        if channel_idx is None:
            return
        bi = channel_idx % 8
        if value is not None:
            self._pan_view[bi] = float(value)   # −64..+63 (integer from Logic LCD)
            # keep the ring driven by pan CC echo (_on_mcu_pan) – no change here
            self.app.display_dirty = True
            self.update_strip_values()

    # --- meters ------------------------------------------------------
    def _on_mcu_meter(self, **_):
        # Only light pads while Track-Control (Mix) mode is ACTIVE.
        if not self.app.is_mode_active(self):
            return

        # Ignore all meter packets unless we’re actually playing
        if not getattr(self, "_playing", False):
            return

        mm = self.app.mcu_manager
        num_banks = len(mm.meter_levels) // 8
        # For each of the 8 pad positions, grab that slot from every bank,
        # mask off the high nibble, and take the max (i.e. whichever bank
        # has a real track there).
        raw = []
        for i in range(8):
            levels = [
                (mm.meter_levels[bank * 8 + i] & 0x0F)
                for bank in range(num_banks)
            ]
            raw.append(max(levels))
        # only pay attention to raw values 5…14
        MIN_RAW = 4
        MAX_RAW = 12

        scaled = []
        for v in raw:
            if v <= MIN_RAW:
                # below or at the floor → totally off
                s = 0
            else:
                # remap (MIN_RAW…MAX_RAW] → [1…127]
                frac = (v - MIN_RAW) / (MAX_RAW - MIN_RAW)
                s = int(frac * 127)  # 0…127
                s = max(1, min(127, s))  # force at least 1
            scaled.append(s)

        # push to PadMeter
        self._pad_meter.update(scaled)

        # debug
        #print(f"[TrackMode] Playing={self._playing}  raw={raw}  scaled={scaled}")

    # ---------------------------------------------------------------- ring helper
    def _set_ring(self, idx: int, value: int):
        """
        Set encoder ring LEDs. Handles multiple push2_python API variants.
        """
        enc = self.push.encoders
        name = self.encoder_names[idx]
        # Clamp to 0..127 just in case
        value = max(0, min(127, int(value)))

        if hasattr(enc, "set_ring_value"):  # modern
            enc.set_ring_value(name, value)
            return
        if hasattr(enc, "set_encoder_ring_value"):  # older
            enc.set_encoder_ring_value(name, value)
            return
        if hasattr(enc, "set_encoder_value"):  # some forks
            enc.set_encoder_value(name, value)
            return
        if hasattr(enc, "set_value"):  # very old (rare)
            enc.set_value(name, value)
            return

        # Last resort: do nothing, but don't crash
        # print("[Push2] No known ring API on encoders object")

    def _on_mcu_pan(self, *, channel_idx: int, value: int, **_):
        if channel_idx is None:
            return
        if channel_idx < self.current_page * 8 or channel_idx >= (self.current_page + 1) * 8:
            return

        bi = channel_idx % 8
        mm = getattr(self.app, "mcu_manager", None)
        # Prefer Logic’s current float value (works for typed “-30”)
        if mm and hasattr(mm, "pan_levels"):
            try:
                val = float(mm.pan_levels[bi])
            except Exception:
                val = float(value)  # fallback
        else:
            val = float(value)

        # Update ring + number from the continuous value
        led_val = int(((val + 64.0) / 128.0) * 127.0)
        self._set_ring(bi, led_val)
        self._pan_view[bi] = val
        self._last_pan[bi] = val

        self.app.display_dirty = True
        self.update_strip_values()


    def set_visible_names(self, names):
        """
        Update track strip names from MCU, ignoring transient scribble-strip
        overlays (e.g., 'Volume', 'Pan') and empty strings. Keeps last good
        names so labels don't flicker while touching controls.
        """
        if not names:
            return False

        # Normalize + quick quality check
        norm = [(n or "").strip() for n in names[:8]]
        non_empty = sum(1 for n in norm if n)
        overlays = sum(1 for n in norm if n and n.lower() in definitions.OVERLAY_TOKENS)

        # Heuristic: if more than 2 entries are known overlays, skip this whole packet
        if overlays > 2:
            return False

        changed = False
        for i in range(min(8, len(norm))):
            n = norm[i]
            if not n:
                # keep last good
                if self._name_cache[i] and self.track_strips[i].name != self._name_cache[i]:
                    self.track_strips[i].name = self._name_cache[i]
                    changed = True
                continue

            # ignore overlays on a per-cell basis
            if n.lower() in definitions.OVERLAY_TOKENS:
                # do not replace the current name with overlay text
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
            return True
        return False

    def _start_meter_poll(self):
        if not getattr(self, "_polling_active", False):
            return
        for bank in range(8):
            msg = MCU_SYSEX_PREFIX + [0x10 + bank]
            self.app.mcu_manager.output_port.send(
                mido.Message('sysex', data=msg)
            )
        # schedule next
        self._meter_timer = threading.Timer(0.1, self._start_meter_poll)
        self._meter_timer.start()

    def activate(self):
        # print("→ Sending meters ON:",
        #       self.app.mcu_manager.output_port,
        #       [hex(b) for b in MCU_METERS_ON])
        # self.app.mcu_manager.output_port.send(
        #     mido.Message('sysex', data=MCU_METERS_ON)
        # )
        self.initialize()
        self.current_page = 0
        # start polling meters
        # self._polling_active = True
        # self._start_meter_poll()
        if hasattr(self.app.mcu_manager, "get_visible_track_names"):
            names = self.app.mcu_manager.get_visible_track_names()
        else:
            names = getattr(self.app.mcu_manager, "track_names", [])[:self.tracks_per_page]

        self.set_visible_names(names)
        print("[TrackMode] Setting track names:", names)
        # Hard-black all 64 pads
        self.push.pads.set_all_pads_to_color(color=definitions.BLACK)
        self.update_encoders()
        self._blank_track_row_buttons()
        self.update_buttons()
        self.update_strip_values()
        # Ensure selector row shows the current mode
        self._paint_selector_row()
        # seed predicted + view from Logic's current pan levels
        mm = getattr(self.app, "mcu_manager", None)
        if mm and hasattr(mm, "pan_levels"):
            for i in range(8):
                v = float(mm.pan_levels[i])
                self._pan_view[i] = v
                self._last_pan[i] = int(v)
                self._set_ring(i, int((v + 64) * 127 / 128))
        if mm and mm.transport.get("play", False):
            # live song → show meters right away
            self._pad_meter.update(
                mm.meter_levels[self.current_page * 8: self.current_page * 8 + 8]
            )
        else:
            # stopped song → keep pads dark
            self._pad_meter.update([0] * 8)

    def deactivate(self):
        # print("→ Sending meters OFF:",
        #       self.app.mcu_manager.output_port,
        #       [hex(b) for b in MCU_METERS_OFF])
        # self.app.mcu_manager.output_port.send(
        #     mido.Message('sysex', data=MCU_METERS_OFF)
        # )
        # stop polling meters
        # self._polling_active = False
        # if hasattr(self, "_meter_timer"):
        #     self._meter_timer.cancel()
        super().deactivate()
        # Run supperclass deactivate to set all used buttons to black
        self.push.pads.set_all_pads_to_color(definitions.BLACK)
        # Also set all pads to black
        self._blank_track_row_buttons()
        self.app.pads_need_update = True

    def on_pad_pressed(self, pad_n, pad_ij, velocity, loop=False, quantize=False, shift=False, select=False,
                       long_press=False, double_press=False):
        # pad_ij is (row, col) where row 7 is bottom per pad_meter usage
        row, col = pad_ij
        if row == 7 and 0 <= col < 8:
            # Bottom row is our selector
            mode = LOWER_ROW_MODES[col]
            self._set_mode(mode)
            return True

        # Anything else: just consume (PadMeter owns the grid painting)
        self.app.pads_need_update = True
        return True

    def on_pad_released(self, pad_n, pad_ij, **_):
        return True

    def update_display(self, ctx, w, h):
        ctx.rectangle(0, 0, w, h)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()
        # Make sure we reflect any external pan changes instantly
        self._sync_pan_from_logic()
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
        # TOP header (per-track MUTE/SOLO halves)
        self._draw_top_mute_solo_header(ctx, w, h)
        # Bottom mode labels
        self._draw_bottom_mode_labels(ctx, w, h)
        self.update_buttons()

    def current_page(self) -> int:
        """
        Always show the same MCU bank that Logic currently shows.
        Each bank is 8 tracks wide.
        """
        mm = getattr(self.app, "mcu_manager", None)
        sel = mm.selected_track_idx if mm else 0
        return (sel or 0) // 8  # 0-based bank number

    def _send_mcu_pan_delta(self, channel: int, delta: int):
        """
        Send MCU V‑Pot relative for PAN on CC 16–23.
        Positive delta => 1..63, Negative delta => 65..127 (65 == -1).
        """
        if delta == 0:
            return
        # clamp magnitude to 63 to avoid huge jumps
        mag = min(63, abs(int(delta)))

        if delta > 0:
            value = mag  # 1..63 (CW)
        else:
            value = 64 + mag  # 65..127 (CCW, 65 == -1)

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

        if mm:
            for i in range(8):
                strip_idx = self.current_page * self.tracks_per_page + i
                solo = mm.solo_states[strip_idx % 8]
                mute = mm.mute_states[strip_idx % 8]

                upper = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
                lower = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")

                # --- TOP ROW: shows either SOLO or MUTE depending on active section ---
                if self.active_mode == MODE_SOLO:
                    self.push.buttons.set_button_color(
                        upper,
                        definitions.YELLOW if solo else definitions.OFF_BTN_COLOR
                    )
                elif self.active_mode == MODE_MUTE:
                    # Use SKYBLUE if you have it; fall back to CYAN otherwise
                    sky = getattr(definitions, "SKYBLUE", getattr(definitions, "CYAN", definitions.BLUE))
                    self.push.buttons.set_button_color(
                        upper,
                        sky if mute else definitions.OFF_BTN_COLOR
                    )
                else:
                    self.push.buttons.set_button_color(upper, definitions.OFF_BTN_COLOR)

                # --- BOTTOM ROW: mode selector colors ---
                mode = LOWER_ROW_MODES[i]
                col = MODE_COLORS.get(mode, definitions.GRAY_DARK)
                self.push.buttons.set_button_color(
                    lower,
                    col if mode == self.active_mode else definitions.GRAY_DARK
                )

    def on_button_pressed_raw(self, btn):
        # 1) LOWER ROW = MODE SELECTORS
        for i in range(8):
            lower_btn = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")
            if btn == lower_btn:
                self._set_mode(LOWER_ROW_MODES[i])
                return True

        # 2) UPPER ROW = TRACK ACTIONS (only when mode requires)
        for i in range(8):
            upper_btn = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")

            if btn == upper_btn:
                if self.active_mode == MODE_SOLO:
                    # SOLO notes 8–15
                    self._tap_mcu_button(8 + i)
                    self.app.buttons_need_update = True
                    return True
                elif self.active_mode == MODE_MUTE:
                    # MUTE notes 16–23
                    self._tap_mcu_button(16 + i)
                    self.app.buttons_need_update = True
                    return True
                else:
                    # Other modes: upper row does nothing (absorb)
                    return True

        # Absorb anything else on these rows
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
        Emulate a Mackie fader with Push 2's endless encoders:

        • Send NOTE-ON 127 once at the start of the gesture (“touch down”)
        • Stream PITCHBEND while the knob moves
        • 400 ms after the last tick, send NOTE-ON 0 (“touch up”)
        """

        mcu = getattr(self.app, "mcu_manager", None)
        port = mcu.output_port if (mcu and mcu.output_port) else getattr(self.app, "midi_out", None)
        if port is None:
            print("[TrackMode] ⚠️  No MIDI port for fader move!")
            return

        # ---------------------------------------------------------------- internal state
        if not hasattr(self, "_touch_state"):
            # one flag + one timer per encoder channel
            self._touch_state = [False] * 8  # False = up, True = down
            self._touch_timer = [None] * 8

        touch_note = 0x68 + channel  # 0x68 … 0x6F  (always on MIDI Ch-1)
        pb_value = int(level * 16383) - 8192  # −8192 … +8191

        # ---------------------------------------------------------------- touch-down
        if not self._touch_state[channel]:
            port.send(mido.Message('note_on', note=touch_note, velocity=127, channel=0))
            self._touch_state[channel] = True
            # print(f"▶ TOUCH DOWN ch{channel}  level={level:.3f}")

        # ---------------------------------------------------------------- main fader data
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
        # solo / mute LEDs or record-arm changed
        # print("[TrackMode] live LED refresh")  # debug proof
        self.update_buttons()
        self.update_strip_values()

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

        # PAN mode: smooth UI + relative delta to Logic
        if self.active_mode == MODE_PAN:
            ch = local_idx
            # optional: ignore null ticks
            if increment == 0:
                return True
            self._pan_pred[ch] = max(0.0, min(127.0, self._pan_pred[ch] + increment))
            self._pan_view[ch] = self._raw_to_signed(self._pan_pred[ch])  # −64..+63 (float)
            self.app.display_dirty = True
            self._send_mcu_pan_delta(ch, 1 if increment > 0 else -1)
            return True

        # Not handled by this mode
        return False


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