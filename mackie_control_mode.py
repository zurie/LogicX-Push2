import math
import time
from typing import Optional

import mido
import push2_python
from push2_python import constants as P2
from push2_python.constants import ANIMATION_STATIC
from mcu_state import MCU_STATE
import definitions
from display_utils import show_text
from ui import create_renderer


# ──────────────────────────────────────────────────────────────────────────────
# Color helpers (use your palette, with safe fallbacks)
# ──────────────────────────────────────────────────────────────────────────────
_SKY = getattr(definitions, "SKYBLUE", getattr(definitions, "CYAN", getattr(definitions, "BLUE", "deepskyblue")))
_YELLOW = getattr(definitions, "YELLOW", "yellow")
_RED = getattr(definitions, "RED", "red")
_GREEN = getattr(definitions, "GREEN", "green")
_OFF = getattr(definitions, "BLACK", "black")
_DARK = getattr(definitions, "GRAY_DARK", "gray")
_WHITE = getattr(definitions, "WHITE", "white")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _row_buttons(row_index: int):
    """Return pad IDs as (row, col) tuples for pads.set_pad_color."""
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


def _bank(idx: int) -> int:
    """Return the 0-7 index within the current 8-channel MCU bank."""
    return idx % 8


# ──────────────────────────────────────────────────────────────────────────────
# Mode constants
# ──────────────────────────────────────────────────────────────────────────────
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
    MODE_VOLUME: getattr(definitions, "GREEN", "green"),
    MODE_MUTE: _SKY,
    MODE_SOLO: _YELLOW,
    MODE_PAN: getattr(definitions, "KARMA", getattr(definitions, "ORANGE", "orange")),
    MODE_VPOT: getattr(definitions, "PINK", "magenta"),
    MODE_EXTRA1: getattr(definitions, "GRAY_DARK", "gray"),
    MODE_EXTRA2: getattr(definitions, "GREEN_LIGHT", getattr(definitions, "GREEN", "green")),
    MODE_EXTRA3: getattr(definitions, "RED_LIGHT", getattr(definitions, "RED", "red")),
}

ROW6_MODE_FUNCTION = "function"  # F1..F8 (MCU 40..47)
ROW6_MODE_CUSTOM = "custom"

# MCU Assignment / Function keys (notes)
MCU_ASSIGN_INOUT = 40
MCU_ASSIGN_SENDS = 41
MCU_ASSIGN_PAN = 42
MCU_ASSIGN_PLUGINS = 43
MCU_ASSIGN_PAGE_LEFT = 44
MCU_ASSIGN_PAGE_RIGHT = 45
MCU_ASSIGN_BANK_LEFT = 46
MCU_ASSIGN_BANK_RIGHT = 47
MCU_ASSIGN_TRACK = 40   # "Track / Volume"
MCU_ASSIGN_FLIP = 50


# ──────────────────────────────────────────────────────────────────────────────
# TrackStrip (GUI-neutral data + utilities used by renderers)
# ──────────────────────────────────────────────────────────────────────────────
class TrackStrip:
    """Simple data object + draw helper for the Legacy GUI."""

    def __init__(
            self,
            app,
            index: int,
            name: str,
            get_color_func,
            get_volume_func,
            set_volume_func,
            get_pan_func,
    ):
        self.app = app
        self.index = index  # absolute 0..63
        self.name = name
        self.get_color_func = get_color_func
        self.get_volume_func = get_volume_func
        self.set_volume_func = set_volume_func
        self.get_pan_func = get_pan_func
        self.vmin = 0.0
        self.vmax = 1.0

    # ------------------------------ LEGACY GUI draw (kept here to avoid import cycles)
    def draw(self, ctx, x_part, selected=False):
        """Legacy arc+ring+labels per-strip UI (unchanged)."""
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
        norm = min(1.0, max(0.0, norm))
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
        xb, yb, tw, th, _, _ = ctx.text_extents(pan_text)
        tx = xc - (tw / 2.0) - xb
        ty = yc - (th / 2.0) - yb
        ctx.move_to(tx, ty)
        ctx.show_text(pan_text)
        ctx.restore()

    # ------------------------------ values
    def update_value(self, increment: int):
        """
        Normal turn   : coarse   (0.5 dB)
        SHIFT held    : fine     (0.05 dB)
        SHIFT+SELECT  : super-fine (0.01 dB)
        """
        base_step = 0.007  # ~0.5 dB around unity
        mult = 1.0
        if getattr(self.app, "shift_held", False):
            mult = 0.1
            if getattr(self.app, "select_held", False):
                mult = 0.02
        step = base_step * mult
        new_val = max(
            self.vmin,
            min(self.vmax, self.get_volume_func(self.index) + increment * step),
        )
        self.set_volume_func(self.index, new_val)


# ──────────────────────────────────────────────────────────────────────────────
# MackieControlMode (core logic + handlers; rendering is delegated to UI files)
# ──────────────────────────────────────────────────────────────────────────────
class MackieControlMode(definitions.LogicMode):
    xor_group = "pads"
    # Expose constants to renderers (so they can use self.mode.<…>)
    LOWER_ROW_MODES = LOWER_ROW_MODES
    MODE_LABELS     = MODE_LABELS
    MODE_COLORS     = MODE_COLORS
    # === Mode state (class/shared) ============================================
    active_mode = MODE_VOLUME  # default
    _polling_active = False
    _volume_submode = 0
    _submodes = {
        MODE_VOLUME: 0,
        MODE_PAN: 0,
    }
    _startup_submodes_loaded = False

    # Pad brightness policy: OFF = dimmed gray, ON = full
    _PAD_OFF_COLOR = _DARK

    # Pan state: green number (−64..+63) & ring 0..11
    _pan_view = [0.0] * 8
    _pan_ring = [6] * 8
    _last_pan = [None] * 8

    _fired_inout_once = False
    _name_cache = [""] * 8
    _last_names_print = 0  # throttle debug printing
    _last_grid_snapshot = None

    ROW6_DEFAULT_MODE = getattr(definitions, "MIX_ROW6_MODE", ROW6_MODE_FUNCTION)
    if ROW6_DEFAULT_MODE not in (ROW6_MODE_FUNCTION, ROW6_MODE_CUSTOM):
        ROW6_DEFAULT_MODE = ROW6_MODE_FUNCTION
    ROW6_CUSTOM_NOTES = getattr(definitions, "MIX_ROW6_CUSTOM_NOTES", None)

    # Buttons used by this mode
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
        # page keys
        push2_python.constants.BUTTON_PAGE_LEFT,
        push2_python.constants.BUTTON_PAGE_RIGHT,
        push2_python.constants.BUTTON_MASTER
    ]

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
    def __init__(self, app, settings=None):
        super().__init__(app, settings)
        self.renderer = None
        self._pad_color_cache = {}
        self.row6_mode = self.ROW6_DEFAULT_MODE
        self.row6_custom_notes = self.ROW6_CUSTOM_NOTES

    # ================================ GUI-agnostic helpers consumed by renderers
    def _upper_row_label_and_color(self):
        """Returns (label, color) for the 8 upper per-channel buttons, based on active_mode."""
        if self.active_mode == MODE_SOLO:
            return ("SOLO", definitions.YELLOW)
        if self.active_mode == MODE_MUTE:
            return ("MUTE", getattr(definitions, "SKYBLUE", getattr(definitions, "CYAN", definitions.SKYBLUE)))
        # In VOL / PAN / VPOT (and others), upper buttons act as SELECT
        return ("SELECT", definitions.GRAY_LIGHT)

    def _lcd_accept(self, top56: str, bot56: str) -> bool:
        """
        Debounce host overlay flashes (e.g. 'Volume', 'Pan', long params).
        Accept new text if:
          1) It's identical to last drawn, or
          2) It has stayed the same for MC_DEBUG_DEBOUNCE_MS, or
          3) It doesn't look like an overlay token burst.
        """
        debounce_ms = int(getattr(definitions, "MC_DEBUG_DEBOUNCE_MS", 80))
        now = time.time()

        if not hasattr(self, "_lcd_last"):
            self._lcd_last = {"top": "", "bot": "", "since": now}

        last = self._lcd_last
        same = (top56 == last["top"] and bot56 == last["bot"])
        if same:
            last["since"] = now
            return True

        tokens = getattr(definitions, "OVERLAY_TOKENS", set())

        def looks_overlay(s: str) -> bool:
            t = s.strip()
            if not t:
                return False
            if t.lower() in tokens:
                return True
            return (len(t) <= 6 and s.count(" ") >= 40)

        if looks_overlay(top56) or looks_overlay(bot56):
            if (now - last["since"]) * 1000.0 < debounce_ms:
                return False

        last["top"], last["bot"], last["since"] = top56, bot56, now
        return True

    # ================================ MCU send helpers
    def _tap_mcu_button(self, note_num: int):
        self._tap(note_num)

    def _send_assignment(self, note: int):
        self._tap(note)
        # Hint your detector if present (optional)
        mm = getattr(self.app, "mcu_manager", None)
        if mm and hasattr(mm, "mode_detector") and callable(
                getattr(mm.mode_detector, "notify_assignment_pressed", None)):
            try:
                mm.mode_detector.notify_assignment_pressed(int(note))
            except Exception:
                pass

    def _tap(self, note_num: int):
        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if not port:
            return
        # Mackie style: ON 127 then OFF 0
        port.send(mido.Message('note_on', note=note_num, velocity=127, channel=0))
        port.send(mido.Message('note_on', note=note_num, velocity=0, channel=0))

    @staticmethod
    def _level_to_db(level: float) -> float:
        return definitions.pb_to_db(int(level * 16383))

    @staticmethod
    def _db_to_level(db: float) -> float:
        return definitions.db_to_pb(db) / 16383.0

    # ================================ State syncs
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
                val = float(mm.pan_levels[i])  # continuous from Logic
            except Exception:
                continue

            if self._last_pan[i] is None or abs(val - float(self._last_pan[i])) > 0.01:
                self._last_pan[i] = val
                self._pan_view[i] = val
                # Update ring to match the new value (0..127 for Push ring)
                led = int(((val + 64.0) / 128.0) * 127.0)
                self._set_ring(i, led)
                self.app.display_dirty = True

    # ================================ Push LEDs and pads
    def _set_pad_color(self, pad_id, color):
        # Cache to skip redundant calls across floods
        prev = self._pad_color_cache.get(pad_id)
        if prev == color:
            return
        self._pad_color_cache[pad_id] = color
        self.push.pads.set_pad_color(
            pad_id,
            color,
            animation=ANIMATION_STATIC,
            optimize_num_messages=True
        )

    def _blank_upper_row_buttons(self):
        for i in range(8):
            upper = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
            self.app._set_button_color_cached(upper, definitions.OFF_BTN_COLOR)

    def _blank_buttons_used(self):
        for btn in self.buttons_used:
            self.app._set_button_color_cached(btn, definitions.OFF_BTN_COLOR)

    # ================================ Row-6 (F-keys or custom)
    def set_row6_mode(self, mode: str, custom_notes=None):
        if mode not in (ROW6_MODE_FUNCTION, ROW6_MODE_CUSTOM):
            return
        self.row6_mode = mode
        if custom_notes is not None:
            self.row6_custom_notes = custom_notes
        self._render_mix_grid("set_row6_mode")

    def _paint_row6(self, to_set):
        row_idx = 6
        pads = _row_buttons(row_idx)

        if self.row6_mode == ROW6_MODE_FUNCTION:
            col = getattr(definitions, "GRAY_LIGHT", "gray")
            for pad_id in pads:
                to_set.append((pad_id, col))
            return

        if self.row6_mode == ROW6_MODE_CUSTOM:
            col_on = getattr(definitions, "ORANGE", "orange")
            col_off = _DARK
            notes = self.row6_custom_notes or []
            for i, pad_id in enumerate(pads):
                has_binding = (i < len(notes) and notes[i] is not None)
                to_set.append((pad_id, col_on if has_binding else col_off))
            return

        for pad_id in pads:
            to_set.append((pad_id, _DARK))

    # ================================ Mode switching
    def _set_mode(self, mode: str):
        if mode not in MODE_LABELS:
            return
        self.active_mode = mode

        if mode == MODE_VOLUME:
            self._send_assignment(MCU_ASSIGN_INOUT)
            MackieControlMode._volume_submode = self._submodes.get(MODE_VOLUME, 0)
        elif mode == MODE_PAN:
            self._send_assignment(MCU_ASSIGN_PAN)
            MackieControlMode._pan_submode = self._submodes.get(MODE_PAN, 0)

        self.update_buttons()
        self.update_encoders()
        self._paint_selector_row()
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def _paint_selector_row(self):
        bottom_row = 7
        for col, mode in enumerate(LOWER_ROW_MODES):
            pad_id = (bottom_row, col)
            colr = MODE_COLORS.get(mode, definitions.GRAY_DARK)
            self.push.pads.set_pad_color(
                pad_id,
                colr if mode == self.active_mode else definitions.GRAY_DARK
            )

    # ================================ Grid + meters (rows 0..3)
    def activate_mix_mode(self):
        self._render_mix_grid("activate_mix_mode")

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
        top = base + 8

        mute_states = getattr(mcu, "mute_states", []) or []
        solo_states = getattr(mcu, "solo_states", []) or []
        rec_states = getattr(mcu, "recarm_states", []) or []

        def _state(arr, abs_idx):
            try:
                return bool(arr[abs_idx]) if 0 <= abs_idx < len(arr) else False
            except Exception:
                return False

        sel_rel = -1
        sel_abs = getattr(mcu, "selected_track_idx", None)
        if isinstance(sel_abs, (int, float)):
            sel_abs = int(sel_abs)
            if base <= sel_abs < top:
                sel_rel = sel_abs - base

        m_row = tuple(_state(mute_states, base + i) for i in range(8))
        s_row = tuple(_state(solo_states, base + i) for i in range(8))
        r_row = tuple(_state(rec_states, base + i) for i in range(8))
        snapshot = (base, sel_rel, m_row, s_row, r_row)

        if snapshot == getattr(self, "_last_grid_snapshot", None):
            return
        self._last_grid_snapshot = snapshot

        row_select = _row_buttons(0)
        row_mute = _row_buttons(1)
        row_solo = _row_buttons(2)
        row_rec = _row_buttons(3)

        to_set = []

        for row in (row_select, row_mute, row_solo, row_rec):
            for pad_id in row:
                to_set.append((pad_id, _DARK))

        if 0 <= sel_rel < 8:
            to_set.append((row_select[sel_rel], _GREEN))

        for i in range(8):
            abs_idx = base + i
            if m_row[i]:
                to_set.append((row_mute[i], _SKY))
            if s_row[i]:
                to_set.append((row_solo[i], _YELLOW))
            if r_row[i]:
                to_set.append((row_rec[i], _RED))

        self._paint_row6(to_set)
        self._apply_pad_colors(to_set)
        self.app.pads_need_update = True

    def on_mcu_state_changed(self):
        self._render_mix_grid("mcu state changed")

    # ================================ Mode lifecycle
    def initialize(self, settings=None):
        super().initialize(settings) if hasattr(super(), "initialize") else None

        # renderer
        self._install_renderer()

        # state
        self.track_strips = []
        self.current_page = 0
        self.tracks_per_page = 8

        self._pan_view = [0.0] * 8
        self._pan_ring = [6] * 8
        self._last_pan = [None] * 8

        self._build_track_strips()
        self._attach_mcu_listeners_once()

    def _install_renderer(self):
        profile = getattr(self.app, "gui_profile", "legacy")
        self.renderer = create_renderer(profile, self)

    def swap_renderer(self, profile: str):
        self.renderer = create_renderer(profile, self)
        if hasattr(self, "request_full_redraw"):
            self.request_full_redraw()
        else:
            self.app.display_dirty = True

    def _build_track_strips(self):
        if self.track_strips:
            return

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
                bi = _bank(idx)
                mm.fader_levels[bi] = val
                mm.emit_event("fader", channel_idx=bi, level=val)

        def get_pan(idx):
            return float(self._pan_view[_bank(idx)])

        for i in range(64):
            self.track_strips.append(
                TrackStrip(self.app, i, f"Track {i + 1}", get_color, get_volume, set_volume, get_pan)
            )

    def _attach_mcu_listeners_once(self):
        mm = getattr(self.app, "mcu_manager", None)
        if not mm or getattr(self, "_listeners_added", False):
            return
        mm.add_listener("pan", self._on_mcu_pan)
        mm.add_listener("transport", self._on_mcu_transport)
        mm.add_listener("track_state", self._on_mcu_track_state)
        mm.add_listener("solo", self._on_mcu_track_state)
        mm.add_listener("mute", self._on_mcu_track_state)
        mm.add_listener("meter", self._on_mcu_meter)
        mm.add_listener("pan_text", self._on_mcu_pan_text)
        self._playing = mm.transport.get("play", False)
        self._on_mcu_transport(state=mm.transport)
        self._on_mcu_meter()
        self._listeners_added = True

    # ================================ Render entry (delegates to renderer)
    def update_display(self, ctx, w, h):
        if self.renderer is None:
            self._install_renderer()
        self.renderer.on_resize(w, h)
        self.renderer.render(ctx, w, h)

    # ================================ Misc plumbing used by renderers
    def _apply_pad_colors(self, pairs):
        for pad_id, col in pairs:
            self._set_pad_color(pad_id, col)

    def _on_mcu_transport(self, *, state, **_):
        self._playing = bool(state.get("play", False))
        if self.app.is_mode_active(self):
            self._render_mix_grid("on transport")
            self.app.pads_need_update = True

    def _on_mcu_pan_text(self, *, channel_idx: int, value, **_):
        if channel_idx is None:
            return
        bi = channel_idx % 8
        if value is not None:
            self._pan_view[bi] = float(value)  # −64..+63
            self.app.display_dirty = True
            self.update_strip_values()
            try:
                pan_i = int(round(float(value)))
            except Exception:
                pan_i = 0
                self._scribble_set(bi, bottom=f"{pan_i:+d}")

    def on_mcu_pan_echo(self, ch: int, ring_pos: int):
        if ch is None or not (0 <= ch < 8):
            return
        rp = max(0, min(11, int(ring_pos)))
        self._pan_ring[ch] = rp
        self._set_ring(ch, int(rp * 127 / 11))
        self.app.display_dirty = True

    def _on_mcu_meter(self, **_):
        if not self.app.is_mode_active(self):
            return
        if not getattr(self, "_playing", False):
            return
        mm = self.app.mcu_manager
        if not mm or len(mm.meter_levels) < 8:
            return
        # (Pad meters optional / omitted)

    def _set_ring(self, idx: int, value: int):
        enc = self.push.encoders
        name = self.encoder_names[idx]
        value = max(0, min(127, int(value)))
        if hasattr(enc, "set_ring_value"):
            enc.set_ring_value(name, value); return
        if hasattr(enc, "set_encoder_ring_value"):
            enc.set_encoder_ring_value(name, value); return
        if hasattr(enc, "set_encoder_value"):
            enc.set_encoder_value(name, value); return
        if hasattr(enc, "set_value"):
            enc.set_value(name, value); return

    def _now(self):
        return time.time()

    def _init_tx_coalesce(self):
        if not hasattr(self, "_vpot_last_ts"):
            self._vpot_last_ts = [0.0] * 8
            self._vpot_pending = [0] * 8
        if not hasattr(self, "_pb_last_ts"):
            self._pb_last_ts = [0.0] * 8
            self._pb_pending = [None] * 8

    def _flush_pending_vpot(self, hz: int = 125):
        self._init_tx_coalesce()
        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if port is None:
            return
        now = time.time()
        budget = 1.0 / float(hz)
        for ch in range(8):
            pend = int(self._vpot_pending[ch])
            if pend == 0:
                continue
            if (now - self._vpot_last_ts[ch]) < budget:
                continue
            mag = min(63, abs(pend))
            val = (mag if pend > 0 else 64 + mag)  # MCU rel format
            cc_num = 16 + ch
            port.send(mido.Message('control_change', control=cc_num, value=val, channel=0))
            self._vpot_pending[ch] = pend - (mag if pend > 0 else -mag)
            self._vpot_last_ts[ch] = now

    def _on_mcu_pan(self, *, channel_idx: int, value: int, **_):
        if channel_idx is None:
            return
        if channel_idx < self.current_page * self.tracks_per_page or channel_idx >= (
                self.current_page + 1) * self.tracks_per_page:
            return
        bi = channel_idx % 8
        now = time.time()
        if not hasattr(self, "_last_pan_tick"):
            self._last_pan_tick = [0.0] * 8
        if (now - self._last_pan_tick[bi]) < (1.0 / 60.0):
            return
        self._last_pan_tick[bi] = now
        try:
            val = float(value)
        except Exception:
            val = float(self._pan_view[bi]) if 0 <= bi < len(self._pan_view) else 0.0
        led = int(((val + 64.0) / 128.0) * 127.0)
        self._set_ring(bi, led)
        self._pan_view[bi] = val
        self._last_pan[bi] = val
        self.app.display_dirty = True

    def set_visible_names(self, names):
        if not names:
            return False
        norm = [(n or "").strip() for n in names[:8]]
        if tuple(norm) == getattr(self, "_last_names_tuple", None):
            return False
        self._last_names_tuple = tuple(norm)
        overlays = sum(1 for n in norm if n and n.lower() in definitions.OVERLAY_TOKENS)
        if overlays > 2:
            return False
        changed = False
        for i in range(min(8, len(norm))):
            n = norm[i]
            if not n:
                if self._name_cache[i] and self.track_strips[i].name != self._name_cache[i]:
                    self.track_strips[i].name = self._name_cache[i]; changed = True
                continue
            if n.lower() in definitions.OVERLAY_TOKENS:
                if self._name_cache[i] and self.track_strips[i].name != self._name_cache[i]:
                    self.track_strips[i].name = self._name_cache[i]; changed = True
                continue
            if n != self.track_strips[i].name:
                self.track_strips[i].name = n
                self._name_cache[i] = n
                changed = True
        if changed:
            self.update_strip_values()
            if hasattr(self, "_scribble_refresh_titles_for_visible_bank"):
                self._scribble_refresh_titles_for_visible_bank()
        return changed

    # ================================ Navigation / lifecycle
    def move_to_next_page(self):
        self.app.buttons_need_update = True
        self.current_page += 1
        if self.current_page >= self.n_pages:
            self.current_page = 0
        self._last_grid_snapshot = None
        self._render_mix_grid("page change")
        return True

    def activate(self):
        self.initialize()
        self._pad_color_cache = {}
        self.current_page = 0
        self._last_grid_snapshot = None
        self.push.pads.reset_current_pads_state()
        # keep MASTER LED in sync with host-driven FLIP changes
        try:
            MCU_STATE().subscribe(self._on_mcu_state_flip)
        except Exception:
            pass
        if not MackieControlMode._fired_inout_once:
            self._send_assignment(MCU_ASSIGN_INOUT)  # note 40
            MackieControlMode._fired_inout_once = True

        names = (self.app.mcu_manager.get_visible_track_names()
                 if hasattr(self.app.mcu_manager, "get_visible_track_names")
                 else getattr(self.app.mcu_manager, "track_names", [])[:self.tracks_per_page])
        self.set_visible_names(names)

        # Seed pan views and rings from MCU cache immediately
        mm = getattr(self.app, "mcu_manager", None)
        if mm and hasattr(mm, "pan_levels"):
            for i in range(8):
                v = float(mm.pan_levels[i])
                self._pan_view[i] = v
                self._last_pan[i] = v
                self._set_ring(i, int((v + 64) * 127 / 128))

        self._sync_pan_from_logic()
        self.update_strip_values()

        self.push.pads.set_all_pads_to_color(
            color=definitions.BLACK,
            animation=ANIMATION_STATIC,
            animation_end_color='black'
        )
        self.update_encoders()
        self._blank_buttons_used()
        self.update_buttons()
        self._paint_selector_row()
        self._render_mix_grid("activate")

    def deactivate(self):
        super().deactivate()
        self._pad_color_cache = {}
        self.push.pads.set_all_pads_to_color(
            color=definitions.BLACK,
            animation=ANIMATION_STATIC,
            animation_end_color='black'
        )
        self._blank_buttons_used()
        try:
            MCU_STATE().unsubscribe(self._on_mcu_state_flip)
        except Exception:
            pass
        self.app.pads_need_update = True

    # ---- MCU state callback: refresh MASTER LED when FLIP changes ----
    def _on_mcu_state_flip(self, snapshot=None):
        try:
            # whatever your redraw path is—this flags a button refresh
            self.app.buttons_need_update = True
        except Exception:
            pass

    # ================================ Small helpers
    def get_current_page(self) -> int:
        mm = getattr(self.app, "mcu_manager", None)
        sel = mm.selected_track_idx if mm else 0
        return (sel or 0) // 8

    def _send_mcu_pan_delta(self, channel: int, delta: int):
        if not delta:
            return
        self._init_tx_coalesce()
        ch = 0 if channel is None else int(channel)
        if ch < 0 or ch > 7:
            return
        self._vpot_pending[ch] += int(delta)

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

    # ================================ Inputs
    def update_buttons(self):
        mm = getattr(self.app, "mcu_manager", None)
        self._blank_buttons_used()
        # --- MASTER reflects FLIP state ---
        try:
            flip_on = bool(MCU_STATE().flip())
        except Exception:
            flip_on = False
        on_color  = getattr(definitions, "WHITE", "white")
        off_color = getattr(definitions, "GRAY_DARK", "gray")
        try:
            self.push.buttons.set_button_color(P2.BUTTON_MASTER, on_color if flip_on else off_color)
        except Exception:
            pass
        if not mm:
            return

        for i in range(8):
            strip_idx = self.current_page * self.tracks_per_page + i
            solo = bool(mm.solo_states[strip_idx]) if strip_idx < len(mm.solo_states) else False
            mute = bool(mm.mute_states[strip_idx]) if strip_idx < len(mm.mute_states) else False

            upper = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
            lower = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")

            if self.active_mode == MODE_SOLO:
                self.push.buttons.set_button_color(upper, definitions.YELLOW if solo else definitions.OFF_BTN_COLOR)
            elif self.active_mode == MODE_MUTE:
                self.push.buttons.set_button_color(upper, _SKY if mute else definitions.OFF_BTN_COLOR)
            elif self.active_mode in (MODE_VOLUME, MODE_PAN, MODE_VPOT):
                selected_idx = getattr(mm, "selected_track_idx", None)
                self.push.buttons.set_button_color(
                    upper,
                    definitions.GRAY_LIGHT if selected_idx == strip_idx else definitions.OFF_BTN_COLOR
                )
            else:
                self.push.buttons.set_button_color(upper, definitions.OFF_BTN_COLOR)

            mode = LOWER_ROW_MODES[i]
            col = MODE_COLORS.get(mode, definitions.GRAY_DARK)
            self.push.buttons.set_button_color(lower, col if mode == self.active_mode else definitions.GRAY_DARK)

        try:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_LEFT, _WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_RIGHT, _WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_32T, definitions.GREEN)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_32, definitions.SKYBLUE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_16T, definitions.YELLOW)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_16, definitions.RED)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_MIX, _WHITE)
        except Exception:
            pass

    def on_button_pressed_raw(self, btn):
        # MASTER => toggle FLIP
        if btn == P2.BUTTON_MASTER:
            try:
                # Uses your existing Mackie helper + constant (FLIP = 50)
                self._tap_mcu_button(MCU_ASSIGN_FLIP)
            except Exception:
                pass
            return True
        # PAGE < / >  (Shift = Page, no shift = Bank)
        if btn in (push2_python.constants.BUTTON_PAGE_LEFT, push2_python.constants.BUTTON_PAGE_RIGHT):
            shift = bool(getattr(self.app, "shift_held", False))
            if shift:
                self._tap_mcu_button(MCU_ASSIGN_PAGE_LEFT if btn == push2_python.constants.BUTTON_PAGE_LEFT else MCU_ASSIGN_PAGE_RIGHT)
            else:
                self._tap_mcu_button(MCU_ASSIGN_BANK_LEFT if btn == push2_python.constants.BUTTON_PAGE_LEFT else MCU_ASSIGN_BANK_RIGHT)
            return True

        # LOWER ROW = MODE SELECTORS
        for i in range(8):
            lower_btn = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")
            if btn == lower_btn:
                wanted_mode = LOWER_ROW_MODES[i]

                if wanted_mode == MODE_VOLUME:
                    if self.active_mode == MODE_VOLUME:
                        self._tap_mcu_button(MCU_ASSIGN_FLIP)  # FLIP
                        if hasattr(self.app, "_btn_color_cache"):
                            self.app._btn_color_cache.clear()
                        self._paint_selector_row()
                        self.update_buttons()
                        self.update_encoders()
                        self.app.pads_need_update = True
                        self.app.buttons_need_update = True
                        return True
                    else:
                        self._set_mode(MODE_VOLUME)
                        return True

                if wanted_mode == MODE_PAN:
                    if self.active_mode == MODE_PAN:
                        self._send_assignment(MCU_ASSIGN_PAN)
                        self._submodes[MODE_PAN] = 0 if self._submodes.get(MODE_PAN, 0) else 1
                        if hasattr(self.app, "_btn_color_cache"):
                            self.app._btn_color_cache.clear()
                        self._paint_selector_row()
                        self.update_buttons()
                        self.update_encoders()
                        self.app.pads_need_update = True
                        self.app.buttons_need_update = True
                        return True
                    else:
                        self._set_mode(MODE_PAN)
                        return True

                self._set_mode(wanted_mode)
                return True

        # UPPER ROW = TRACK ACTIONS (mode-dependent)
        for i in range(8):
            upper_btn = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
            if btn == upper_btn:
                if self.active_mode == MODE_SOLO:
                    mm = self.app.mcu_manager
                    if mm and mm.selected_track_idx is None:
                        mm.selected_track_idx = self.current_page * self.tracks_per_page + i
                    self._tap_mcu_button(8 + i)  # SOLO
                    self.app.buttons_need_update = True
                    return True

                elif self.active_mode == MODE_MUTE:
                    mm = self.app.mcu_manager
                    if mm and mm.selected_track_idx is None:
                        mm.selected_track_idx = self.current_page * self.tracks_per_page + i
                    self._tap_mcu_button(16 + i)  # MUTE
                    self.app.buttons_need_update = True
                    return True

                elif self.active_mode in (MODE_VOLUME, MODE_PAN, MODE_VPOT):
                    mm = self.app.mcu_manager
                    if mm:
                        abs_idx = self.current_page * self.tracks_per_page + i
                        mm.selected_track_idx = abs_idx
                    self._tap_mcu_button(24 + i)  # SELECT
                    self._render_mix_grid("on button pressed raw")
                    self.app.buttons_need_update = True
                    return True

        return btn in self.buttons_used

    def on_button_pressed(self, button_name, **_):
        return button_name in self.buttons_used

    def on_button_released(self, button_name):
        return button_name in self.buttons_used

    def on_button_released_raw(self, button_name):
        return button_name in self.buttons_used

    # ================================ Encoders & PB/VPOT I/O
    def _send_mcu_fader_move(self, channel: int, level: float):
        self._init_tx_coalesce()
        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if port is None:
            return
        level = max(0.0, min(1.0, float(level)))
        pb_val = int(level * 16383) - 8192  # −8192..+8191
        now = self._now()
        ch = max(0, min(7, int(channel)))

        if (now - self._pb_last_ts[ch]) >= (1.0 / 120.0):
            self._pb_pending[ch] = None
            self._pb_last_ts[ch] = now
            port.send(mido.Message('pitchwheel', pitch=pb_val, channel=ch))
        else:
            self._pb_pending[ch] = pb_val

    def _flush_pending_tx(self):
        self._init_tx_coalesce()
        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if port is None:
            return
        now = self._now()

        # Pitchbend flush
        for ch in range(8):
            if self._pb_pending[ch] is not None and (now - self._pb_last_ts[ch]) >= (1.0 / 120.0):
                port.send(mido.Message('pitchwheel', pitch=int(self._pb_pending[ch]), channel=ch))
                self._pb_pending[ch] = None
                self._pb_last_ts[ch] = now

        # VPOT flush
        for ch in range(8):
            pend = int(self._vpot_pending[ch])
            if pend != 0 and (now - self._vpot_last_ts[ch]) >= (1.0 / 125.0):
                mag = min(63, abs(pend))
                val = (mag if pend > 0 else 64 + mag)  # MCU rel
                cc_num = 16 + ch
                port.send(mido.Message('control_change', control=cc_num, value=val, channel=0))
                self._vpot_pending[ch] = 0
                self._vpot_last_ts[ch] = now

    def set_bank_levels(self, levels):
        for ch, val in enumerate(levels[:8]):
            self.app.mcu_manager.fader_levels[ch] = val
            self._send_mcu_fader_move(ch, val)
        self.update_encoders()
        self.update_strip_values()

    def _on_mcu_track_state(self, **_):
        if not self.app.is_mode_active(self):
            return
        self.update_buttons()
        self.update_strip_values()
        self._render_mix_grid("on mcu track state")
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def on_encoder_rotated(self, encoder_name, increment):
        """
        Handle Push encoders:
          • VOL / SOLO / MUTE → faders (coarse/fine per modifiers)
          • VOL (detail submode=B) → Enc1=selected VOL (absolute), Enc2=selected PAN (relative)
          • PAN → per-strip PAN (relative)
        Also keeps the v2 GUI focus overlay alive while turning.
        """
        # Guard: is this one of the 8 track encoders?
        if encoder_name not in self.encoder_names:
            return False

        local_idx = self.encoder_names.index(encoder_name)   # 0..7 within current bank page
        strip_idx = (self.current_page * self.tracks_per_page) + local_idx
        if strip_idx >= len(self.track_strips):
            return False

        # Keep v2 overlay alive while turning (if renderer supports it)
        if getattr(self, "renderer", None) and hasattr(self.renderer, "poke_focus"):
            try:
                # Default: focus the physical encoder's strip
                focus_ch = local_idx

                # Special-case: Volume detail submode (Enc1/Enc2 act on the SELECTED strip)
                if self.active_mode == MODE_VOLUME and getattr(MackieControlMode, "_volume_submode", 0) == 1:
                    mm = getattr(self.app, "mcu_manager", None)
                    if mm:
                        if mm.selected_track_idx is None:
                            mm.selected_track_idx = self.current_page * self.tracks_per_page
                        focus_ch = (mm.selected_track_idx % 8)

                self.renderer.poke_focus(int(focus_ch))
            except Exception:
                pass

        # --- VOLUME / SOLO / MUTE: encoders move faders ---------------------------
        if self.active_mode in (MODE_VOLUME, MODE_SOLO, MODE_MUTE):

            # Detail submode (B): Enc1 → selected VOL, Enc2 → selected PAN (relative)
            if self.active_mode == MODE_VOLUME and getattr(MackieControlMode, "_volume_submode", 0) == 1:
                mm = getattr(self.app, "mcu_manager", None)
                if mm:
                    if mm.selected_track_idx is None:
                        mm.selected_track_idx = self.current_page * self.tracks_per_page

                    selected_abs = int(mm.selected_track_idx)
                    selected_local = selected_abs % 8

                    # Enc1: selected track volume (absolute)
                    if local_idx == 0:
                        sel_strip_idx = selected_idx
                        if 0 <= selected_abs < len(self.track_strips):
                            self.track_strips[selected_abs].update_value(increment)
                            level = float(mm.fader_levels[selected_local])
                            self._send_mcu_fader_move(selected_local, level)
                            # NEW: scribble for selected column
                            db = MackieControlMode._level_to_db(level)
                            label = "-∞ dB" if db == float("-inf") else f"{db:+.1f} dB"
                            self._scribble_set(local_sel, bottom=label)
                        return True

                    # Enc2: selected track pan (relative)
                    if local_idx == 1:
                        if increment != 0:
                            self._send_mcu_pan_delta(selected_local, 1 if increment > 0 else -1)
                        return True

                    # Enc3..Enc8: no-ops in detail submode
                    return True

            # Normal: each encoder controls its own strip's fader
            self.track_strips[strip_idx].update_value(increment)
            mm = getattr(self.app, "mcu_manager", None)
            if mm:
                level = float(mm.fader_levels[local_idx])
                self._send_mcu_fader_move(local_idx, level)
            # NEW: fast scribble bottom for this column (dB readout)
            db = MackieControlMode._level_to_db(level)
            label = "-∞ dB" if db == float("-inf") else f"{db:+.1f} dB"
            self._scribble_set(local_idx, bottom=label)
            return True

        # --- PAN mode: send relative deltas; Logic echo updates rings/values ------
        if self.active_mode == MODE_PAN:
            if increment != 0:
                self._send_mcu_pan_delta(local_idx, 1 if increment > 0 else -1)
            return True

        # Other modes not handled here
        return False

    def _scribble_set(self, ch: int, *, top=None, bottom=None):
        """Fast path: patch a single 7-char cell (title/value) in the V2 renderer."""
        r = getattr(self, "renderer", None)
        if r and hasattr(r, "update_scribble_cell") and 0 <= ch < 8:
            r.update_scribble_cell(ch, top=top, bottom=bottom)
            self.app.display_dirty = True  # nudge a frame

    def _scribble_refresh_titles_for_visible_bank(self):
        base = (getattr(self, "current_page", 0) or 0) * getattr(self, "tracks_per_page", 8)
        for i in range(8):
            name = ""
            idx = base + i
            try:
                name = (self.track_strips[idx].name or "")[:7]
            except Exception:
                pass
            self._scribble_set(i, top=name)

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

        # Row 6 = F-keys or custom
        if row == 6 and 0 <= col < 8:
            port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
            if port is None:
                return True
            if self.row6_mode == ROW6_MODE_FUNCTION:
                note = 40 + col  # F1..F8
                port.send(mido.Message('note_on', note=note, velocity=127, channel=0))
                port.send(mido.Message('note_on', note=note, velocity=0, channel=0))
                self._set_pad_color((row, col), getattr(definitions, "GRAY_LIGHT", "gray"))
                # optional notify
                if 40 <= note <= 43:
                    mm = getattr(self.app, "mcu_manager", None)
                    if mm and hasattr(mm, "mode_detector"):
                        try:
                            mm.mode_detector.notify_assignment_pressed(note)
                        except Exception:
                            pass
                return True
            if self.row6_mode == ROW6_MODE_CUSTOM:
                notes = self.row6_custom_notes or []
                if col < len(notes) and notes[col] is not None:
                    note = int(notes[col])
                    port.send(mido.Message('note_on', note=note, velocity=127, channel=0))
                    port.send(mido.Message('note_on', note=note, velocity=0, channel=0))
                    self._set_pad_color((row, col), getattr(definitions, "GRAY_LIGHT", "gray"))
                return True

        # Rows 0..3 = SELECT/MUTE/SOLO/REC (MCU)
        note_num = _mcu_note_for(row, col)
        if note_num is None:
            return True

        mcu = getattr(self.app, "mcu_manager", None)

        if row == 0:  # SELECT (optimistic local update)
            base = self._visible_base()
            if mcu:
                mcu.selected_track_idx = base + col
            self._render_mix_grid("on pad pressed")
            self._set_pad_color((row, col), _GREEN)

        elif row == 1:
            self._set_pad_color((row, col), _SKY)
        elif row == 2:
            self._set_pad_color((row, col), _YELLOW)
        elif row == 3:
            self._set_pad_color((row, col), _RED)

        if mcu:
            port = mcu.output_port or getattr(self.app, "midi_out", None)
            if port:
                port.send(mido.Message('note_on', note=note_num, velocity=127, channel=0))
                port.send(mido.Message('note_on', note=note_num, velocity=0, channel=0))
        return True

    def on_pad_released(self, pad_n, pad_ij, **_):
        row, col = pad_ij
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
        try:
            # existing MCU touch-on code...
            if encoder_name not in self.encoder_names:
                return False
            ch = self.encoder_names.index(encoder_name)  # 0..7

            # NEW: tell the renderer which strip is focused
            if getattr(self, "renderer", None) and hasattr(self.renderer, "on_strip_touch"):
                self.renderer.on_strip_touch(ch)  # starts the TTL overlay
                self.app.display_dirty = True

            # existing: send MCU touch note-on
            port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
            if port:
                touch_note = 0x68 + ch
                port.send(mido.Message('note_on', note=touch_note, velocity=127, channel=0))
            return True
        except Exception:
            return False

    def on_encoder_released(self, encoder_name):
        """
        Send MCU fader-touch OFF, flush any throttled PB/VPOT,
        and clear the v2 GUI focus overlay for the appropriate strip.
        """
        try:
            if encoder_name not in self.encoder_names:
                return False

            local_idx = self.encoder_names.index(encoder_name)  # 0..7

            # Compute which strip the overlay was targeting:
            #  • Normal: the same local_idx
            #  • Volume detail submode: Enc1/Enc2 target the SELECTED strip (not the physical one)
            target_local = local_idx
            if self.active_mode == MODE_VOLUME and getattr(MackieControlMode, "_volume_submode", 0) == 1:
                if local_idx in (0, 1):
                    mm = getattr(self.app, "mcu_manager", None)
                    if mm and mm.selected_track_idx is not None:
                        target_local = int(mm.selected_track_idx) % 8

            # Clear the v2 renderer overlay if available
            if getattr(self, "renderer", None) and hasattr(self.renderer, "on_strip_release"):
                try:
                    self.renderer.on_strip_release(int(target_local))
                    self.app.display_dirty = True
                except Exception:
                    pass

            # Force-send any pending throttled PB/VPOT updates for this channel
            if hasattr(self, "_flush_pending_tx"):
                try:
                    # zero the per-channel budget so a flush can happen immediately
                    if hasattr(self, "_pb_last_ts"):
                        self._pb_last_ts[local_idx] = 0.0
                    if hasattr(self, "_vpot_last_ts"):
                        self._vpot_last_ts[local_idx] = 0.0
                except Exception:
                    pass
                self._flush_pending_tx()

            # Send MCU fader touch OFF
            if not hasattr(self, "_touch_state"):
                self._touch_state = [False] * 8

            port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
            if port:
                touch_note = 0x68 + local_idx  # MCU touch notes 0x68–0x6F
                port.send(mido.Message('note_on', note=touch_note, velocity=0, channel=0))
                self._touch_state[local_idx] = False

            return True

        except Exception:
            return False

    # ================================ Misc
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
        return float(raw) - 64.0

    @staticmethod
    def _signed_to_raw(signed: float) -> float:
        return max(0.0, min(127.0, signed + 64.0))
