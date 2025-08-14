import math, mido, threading, time
import definitions, push2_python
from display_utils import show_text
from definitions import pb_to_db, db_to_pb, MCU_SYSEX_PREFIX, MCU_MODEL_ID, MCU_METERS_ON, MCU_METERS_OFF
from push2_python import constants as P2
from typing import Optional  # put this at the top with imports
from push2_python.constants import ANIMATION_STATIC

# Color helpers (choose safe fallbacks if a name isn't defined in your palette)
_SKY = getattr(definitions, "SKYBLUE", getattr(definitions, "skyblue", getattr(definitions, "CYAN", "cyan")))
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


# 0..7 index within current bank
def _bank(idx: int) -> int:
    return idx % 8


PAD_COLUMNS = [[(row, col) for row in range(8)] for col in range(8)]

# ──────────────────────────────────────────────────────────────────────────────
# Assign translation (MCU official <-> Maschine/Logic observed)
# ──────────────────────────────────────────────────────────────────────────────
_MCU_OFFICIAL = {
    "PAGE_LEFT": 44,
    "PAGE_RIGHT": 45,
    "BANK_LEFT": 46,
    "BANK_RIGHT": 47,
    "TRACK": 48,
    "SEND": 49,
    "PAN": 50,
    "PLUGIN": 51,
    "EQ": 52,
    "INSTRUMENT": 53,
}

_MASCHINE_LOGIC = {
    "TRACK": 40,  # Maschine “In/Out”
    "SEND": 41,  # Maschine “Sends”
    "PAN": 42,
    "PLUGIN": 43,
    "EQ": 44,  # conflicts with official PAGE_LEFT
    "DYNAMICS": 45,  # conflicts with official PAGE_RIGHT (often “DYN”)
    "BANK_LEFT": 46,
    "BANK_RIGHT": 47,
}

_ASSIGN_ALIAS = {
    "TRACK": {_MCU_OFFICIAL["TRACK"], _MASCHINE_LOGIC.get("TRACK", -1)},
    "SEND": {_MCU_OFFICIAL["SEND"], _MASCHINE_LOGIC.get("SEND", -1)},
    "PAN": {_MCU_OFFICIAL["PAN"], _MASCHINE_LOGIC.get("PAN", -1)},
    "PLUGIN": {_MCU_OFFICIAL["PLUGIN"], _MASCHINE_LOGIC.get("PLUGIN", -1)},
    "EQ": {_MCU_OFFICIAL["EQ"], _MASCHINE_LOGIC.get("EQ", -1)},
    "INSTRUMENT": {_MCU_OFFICIAL["INSTRUMENT"], _MASCHINE_LOGIC.get("INSTRUMENT", -1)},
    "BANK_LEFT": {_MCU_OFFICIAL["BANK_LEFT"], _MASCHINE_LOGIC.get("BANK_LEFT", -1)},
    "BANK_RIGHT": {_MCU_OFFICIAL["BANK_RIGHT"], _MASCHINE_LOGIC.get("BANK_RIGHT", -1)},
    "PAGE_LEFT": {_MCU_OFFICIAL["PAGE_LEFT"]},
    "PAGE_RIGHT": {_MCU_OFFICIAL["PAGE_RIGHT"]},
}
for k in list(_ASSIGN_ALIAS.keys()):
    _ASSIGN_ALIAS[k] = {n for n in _ASSIGN_ALIAS[k] if isinstance(n, int) and n >= 0}

_ASSIGN_RAW_TO_ACTION = {}
for action, ids in _ASSIGN_ALIAS.items():
    for i in ids:
        _ASSIGN_RAW_TO_ACTION.setdefault(i, set()).add(action)

_ACTION_TO_OFFICIAL = {name: code for name, code in _MCU_OFFICIAL.items()}


def _resolve_assign_action(raw_id: int, *, page_mode: bool = False) -> Optional[str]:
    actions = _ASSIGN_RAW_TO_ACTION.get(raw_id)
    if not actions:
        return None
    if raw_id == 44:  # EQ vs PAGE_LEFT
        if page_mode and "PAGE_LEFT" in actions:
            return "PAGE_LEFT"
        return "EQ" if "EQ" in actions else next(iter(actions))
    if raw_id == 45:  # DYNAMICS vs PAGE_RIGHT
        if page_mode and "PAGE_RIGHT" in actions:
            return "PAGE_RIGHT"
        return "DYNAMICS" if "DYNAMICS" in actions else next(iter(actions))
    for pref in ("TRACK", "SEND", "PAN", "PLUGIN", "EQ", "INSTRUMENT", "BANK_LEFT", "BANK_RIGHT", "PAGE_LEFT",
                 "PAGE_RIGHT"):
        if pref in actions:
            return pref
    return next(iter(actions))


# ──────────────────────────────────────────────────────────────────────────────
# Modes & labels
# ──────────────────────────────────────────────────────────────────────────────
MODE_VOLUME = "volume"
MODE_PAN = "pan"
MODE_EQ = "eq"
MODE_MUTE = "mute"
MODE_SOLO = "solo"
MODE_VPOT = "vpot"
MODE_EXTRA2 = "extra2"
MODE_EXTRA3 = "extra3"

SUB_ALL = "all"
SUB_SINGLE = "single"
EQ_PAGE_1 = 1
EQ_PAGE_2 = 2

MODE_LABELS = {
    MODE_VOLUME: "VOL",
    MODE_PAN: "PAN",
    MODE_EQ: "EQ",
    MODE_MUTE: "MUTE",
    MODE_SOLO: "SOLO",
    MODE_VPOT: "VPOT",
    MODE_EXTRA2: "X2",
    MODE_EXTRA3: "X3",
}

LOWER_ROW_MODES = [
    MODE_VOLUME, MODE_MUTE, MODE_SOLO, MODE_PAN,
    MODE_VPOT, MODE_EQ, MODE_EXTRA2, MODE_EXTRA3,
]

MODE_COLORS = {
    "volume": getattr(definitions, "GREEN", "green"),
    "pan": getattr(definitions, "KARMA", getattr(definitions, "ORANGE", "orange")),
    "eq": getattr(definitions, "ORANGE", "orange"),
    "mute": _SKY,
    "solo": _YELLOW,
    "vpot": getattr(definitions, "PINK", "pink"),
    "extra2": getattr(definitions, "GREEN_LIGHT", getattr(definitions, "GREEN", "green")),
    "extra3": getattr(definitions, "RED_LIGHT", getattr(definitions, "RED", "red")),
}

# PAN submodes
PAN_SUBMODE_TRACK = "track"
PAN_SUBMODE_CSTRIP = "cstrip"

MCU_ASSIGN_PAGE_LEFT = 44
MCU_ASSIGN_PAGE_RIGHT = 45
MCU_ASSIGN_BANK_LEFT = 46
MCU_ASSIGN_BANK_RIGHT = 47
MCU_ASSIGN_TRACK = 48
MCU_ASSIGN_SENDS = 49
MCU_ASSIGN_PAN = 50
MCU_ASSIGN_PLUGINS = 51
MCU_ASSIGN_EQ = 52
MCU_ASSIGN_INSTRUMENT = 53

# Alias so existing code that refers to “INOUT” keeps working:
MCU_ASSIGN_INOUT = MCU_ASSIGN_TRACK

# Transport/edit block (you already had these)
MCU_CHANNEL_LEFT = 70
MCU_CHANNEL_RIGHT = 71
MCU_BANK_LEFT = 68
MCU_BANK_RIGHT = 69


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
    _PAD_OFF_COLOR = _DARK  # GRAY_DARK from your palette
    _PAD_OFF_BRIGHT = 1.0  # tweak: 0.35..0.6 depending on taste
    _PAD_ON_BRIGHT = 1.0
    # Pan state: view is the green number (−64..+63), ring is 0..11 from Logic echo
    _pan_view = [0.0] * 8
    _pan_ring = [6] * 8
    _last_pan = [None] * 8

    _name_cache = [""] * 8
    _last_names_print = 0  # throttle debug printing
    _last_grid_snapshot = None
    _pan_submode: Optional[str] = None
    _last_assignment: Optional[str] = None

    buttons_used = [
        push2_python.constants.BUTTON_UPPER_ROW_1,
        push2_python.constants.BUTTON_UPPER_ROW_2,
        push2_python.constants.BUTTON_UPPER_ROW_3,
        push2_python.constants.BUTTON_UPPER_ROW_4,
        push2_python.constants.BUTTON_UPPER_ROW_5,
        push2_python.constants.BUTTON_UPPER_ROW_6,
        push2_python.constants.BUTTON_UPPER_ROW_7,
        push2_python.constants.BUTTON_UPPER_ROW_8,
        push2_python.constants.BUTTON_LOWER_ROW_1,
        push2_python.constants.BUTTON_LOWER_ROW_2,
        push2_python.constants.BUTTON_LOWER_ROW_3,
        push2_python.constants.BUTTON_LOWER_ROW_4,
        push2_python.constants.BUTTON_LOWER_ROW_5,
        push2_python.constants.BUTTON_LOWER_ROW_6,
        push2_python.constants.BUTTON_LOWER_ROW_7,
        push2_python.constants.BUTTON_LOWER_ROW_8,
        push2_python.constants.BUTTON_PAGE_LEFT,
        push2_python.constants.BUTTON_PAGE_RIGHT,
        P2.BUTTON_UP, P2.BUTTON_DOWN, P2.BUTTON_LEFT, P2.BUTTON_RIGHT,
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
    # def _draw_top_mute_solo_header(self, ctx, w, h):
    #     mm = getattr(self.app, "mcu_manager", None)
    #     if not mm:
    #         return
    #
    #     header_h = 22
    #     y = 0
    #     col_w = w / 8.0
    #
    #     sky = getattr(definitions, "SKYBLUE", getattr(definitions, "CYAN", definitions.BLUE))
    #     yellow = definitions.YELLOW
    #
    #     for i in range(8):
    #         strip_idx = self.current_page * self.tracks_per_page + i
    #         mute = bool(mm.mute_states[strip_idx]) if strip_idx < len(mm.mute_states) else False
    #         solo = bool(mm.solo_states[strip_idx]) if strip_idx < len(mm.solo_states) else False
    #
    #         x = int(i * col_w)
    #         half = int(col_w / 2)
    #
    #         # Left half = MUTE
    #         mute_bg = sky if mute else definitions.BLACK
    #         mute_fg = definitions.BLACK if mute else sky
    #
    #         ctx.save()
    #         ctx.set_source_rgb(*definitions.get_color_rgb_float(mute_bg))
    #         ctx.rectangle(x, y, half, header_h)
    #         ctx.fill()
    #         ctx.restore()
    #
    #         ctx.save()
    #         ctx.set_source_rgb(*definitions.get_color_rgb_float(mute_fg))
    #         ctx.select_font_face("Helvetica", 0, 0)
    #         ctx.set_font_size(11)
    #         label = "MUTE"
    #         xb, yb, tw, th, xadv, yadv = ctx.text_extents(label)
    #         tx = x + (half - tw) / 2.0 - xb
    #         ty = y + (header_h - th) / 2.0 - yb
    #         ctx.move_to(tx, ty)
    #         ctx.show_text(label)
    #         ctx.restore()
    #
    #         # Right half = SOLO
    #         solo_bg = yellow if solo else definitions.BLACK
    #         solo_fg = definitions.BLACK if solo else yellow
    #
    #         ctx.save()
    #         ctx.set_source_rgb(*definitions.get_color_rgb_float(solo_bg))
    #         ctx.rectangle(x + half, y, half, header_h)
    #         ctx.fill()
    #         ctx.restore()
    #
    #         ctx.save()
    #         ctx.set_source_rgb(*definitions.get_color_rgb_float(solo_fg))
    #         ctx.select_font_face("Helvetica", 0, 0)
    #         ctx.set_font_size(11)
    #         label = "SOLO"
    #         xb, yb, tw, th, xadv, yadv = ctx.text_extents(label)
    #         tx = x + half + (half - tw) / 2.0 - xb
    #         ty = y + (header_h - th) / 2.0 - yb
    #         ctx.move_to(tx, ty)
    #         ctx.show_text(label)
    #         ctx.restore()

    @staticmethod
    def _level_to_db(level: float) -> float:
        return pb_to_db(int(level * 16383))

    @staticmethod
    def _db_to_level(db: float) -> float:
        return db_to_pb(db) / 16383.0

    def _upper_row_label_and_color(self):
        """Returns (label, color) for the 8 upper per-channel buttons, based on active_mode."""
        if self.active_mode == MODE_SOLO:
            return ("SOLO", definitions.YELLOW)
        if self.active_mode == MODE_MUTE:
            return ("MUTE", getattr(definitions, "SKYBLUE", getattr(definitions, "CYAN", definitions.SKYBLUE)))
        # In VOL / PAN / VPOT (and others), upper buttons act as SELECT
        return ("SELECT", definitions.GRAY_LIGHT)

    def _draw_top_button_labels(self, ctx, w, h):
        """
        Draw a compact bar at the very top labeling what the *upper row buttons* do,
        mirroring the style of the bottom mode bar. It shows the same label over each column
        (e.g., SELECT, MUTE, or SOLO), with action color.
        """
        label, col = self._upper_row_label_and_color()

        header_h = 18
        y = 0
        col_w = w / 8.0
        corner = 5

        for i in range(8):
            x = int(i * col_w) + 1
            width = int(col_w) - 2

            # pill
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

            # text
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.BLACK))
            ctx.select_font_face("Helvetica", 0, 0)
            ctx.set_font_size(11)
            xb, yb, tw, th, xadv, yadv = ctx.text_extents(label)
            tx = x + (width - tw) / 2.0 - xb
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
        # page keys
        push2_python.constants.BUTTON_PAGE_LEFT,
        push2_python.constants.BUTTON_PAGE_RIGHT,
        P2.BUTTON_UP, P2.BUTTON_DOWN, P2.BUTTON_LEFT, P2.BUTTON_RIGHT,

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

    # ──────────────────────────────────────────────────────────────────────────
    # Rendering & state (unchanged logic; trimmed where possible for brevity)
    # ──────────────────────────────────────────────────────────────────────────
    def _set_pad_color(self, pad_id, color):
        # pad_id = (row, col)
        # STATIC avoids the pre-black frame
        self.push.pads.set_pad_color(
            pad_id,
            color,
            animation=ANIMATION_STATIC,
            optimize_num_messages=True
        )

    def _send_assignment(self, note_or_alias):
        """
        Tap a Mackie 'Assign' key in Logic.
        Accepts either a numeric note (44..53) or a string alias like 'PAN', 'EQ', 'PAGE_LEFT'.
        Always sends the official MCU note to Logic.
        """
        alias_map = {
            "PAGE_LEFT": MCU_ASSIGN_PAGE_LEFT,
            "PAGE_RIGHT": MCU_ASSIGN_PAGE_RIGHT,
            "BANK_LEFT": MCU_ASSIGN_BANK_LEFT,
            "BANK_RIGHT": MCU_ASSIGN_BANK_RIGHT,
            "TRACK": MCU_ASSIGN_TRACK,
            "INOUT": MCU_ASSIGN_INOUT,  # alias to TRACK
            "SEND": MCU_ASSIGN_SENDS,
            "SENDS": MCU_ASSIGN_SENDS,
            "PAN": MCU_ASSIGN_PAN,
            "PLUGIN": MCU_ASSIGN_PLUGINS,
            "PLUGINS": MCU_ASSIGN_PLUGINS,
            "EQ": MCU_ASSIGN_EQ,
            "INSTRUMENT": MCU_ASSIGN_INSTRUMENT,
        }

        # Normalize
        if isinstance(note_or_alias, str):
            key = note_or_alias.strip().upper()
            note = alias_map.get(key)
            if note is None:
                return
        else:
            try:
                note = int(note_or_alias)
            except Exception:
                return

        # Only pageable views should be eager; leave TRACK out so we don’t churn on startup
        always_retap = {MCU_ASSIGN_PAN, MCU_ASSIGN_SENDS, MCU_ASSIGN_PLUGINS, MCU_ASSIGN_EQ}

        if note in always_retap or getattr(self, "_last_assignment", None) != note:
            self._tap_mcu_button(note)
            self._last_assignment = note

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

    def _set_mode(self, mode: str):
        if mode not in MODE_LABELS:
            return

        same = (mode == self.active_mode)

        # Toggle substates
        if mode == MODE_VOLUME and same:
            self._substate[MODE_VOLUME] = SUB_SINGLE if self._substate[MODE_VOLUME] == SUB_ALL else SUB_ALL

        # PAN submode toggles are LOCAL ONLY (never re-tap host on second press)
        if mode == MODE_PAN:
            if same:
                self._pan_submode = (
                    PAN_SUBMODE_CSTRIP if self._pan_submode == PAN_SUBMODE_TRACK else PAN_SUBMODE_TRACK
                )
                self._clear_all_fader_touches()
            else:
                self._pan_submode = PAN_SUBMODE_TRACK  # first entry default

        if mode == MODE_EQ and same:
            self._substate[MODE_EQ] = EQ_PAGE_2 if self._substate[MODE_EQ] == EQ_PAGE_1 else EQ_PAGE_1

        # Commit the new active mode
        prev_mode = self.active_mode
        self.active_mode = mode

        # === Host assignment ONLY on first entry to a mode ===
        if not same:
            if mode == MODE_PAN:
                self._send_assignment("PAN")
                self._clear_all_fader_touches()
            elif mode == MODE_VOLUME:
                self._send_assignment("TRACK")
            elif mode == MODE_EQ:
                self._send_assignment("EQ")

        # Apply ring styles for this mode (so PAN never shows arc)
        self._apply_ring_styles_for_mode()

        # On‑screen feedback
        if hasattr(self, "add_display_notification"):
            if mode == MODE_PAN:
                self.add_display_notification(
                    f"PAN • {'Channel' if self._pan_submode == PAN_SUBMODE_CSTRIP else 'Tracks'}"
                )
            else:
                sub = self._substate.get(self.active_mode)
                self.add_display_notification(f"{self.active_mode.upper()} / {sub if isinstance(sub, str) else sub}")

        # Refresh UI and state
        self.update_buttons()
        self.update_encoders()
        self._paint_selector_row()
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def _apply_ring_styles_for_mode(self):
        """
        Ensure encoder rings use the right style for the current mode:
          - VOLUME: arc
          - PAN:    ticks_center (bipolar)
          - EQ:     don't change (Logic VPOT echo owns them)
        """
        if self.active_mode == MODE_EQ:
            return  # let Logic drive via VPOT echo

        style = "arc" if self.active_mode == MODE_VOLUME else "ticks_center"
        if not hasattr(self, "_current_ring_style_mode") or self._current_ring_style_mode != self.active_mode:
            for i in range(8):
                self._set_ring_style(i, style)
            self._current_ring_style_mode = self.active_mode

    def _set_ring_ticks_only(self, idx: int, led_val: int, *, bipolar: bool = True):
        """
        Paint encoder ring as ticks-only (no arc fill).
        For PAN we want a centered, bipolar tick (64 = center).
        'led_val' is 0..127 like _set_ring.
        """
        try:
            enc = self.push.encoders
            name = self.encoder_names[idx]

            # If your push2 lib supports styles, prefer them:
            if hasattr(enc, "set_ring_style"):
                enc.set_ring_style(name, "ticks_center" if bipolar else "ticks")
                enc.set_ring_value(name, led_val)
                return

            # Fallback: if your _set_ring accepts flags, route through it:
            if hasattr(self, "_set_ring"):
                # many codebases accept kwargs like show_arc / ticks_only; try them defensively
                try:
                    self._set_ring(idx, led_val, show_arc=False, ticks_only=True, bipolar=bipolar)
                    return
                except TypeError:
                    pass

            # Last resort: call _set_ring and rely on your painter to check self._force_ticks_only flag
            self._force_ticks_only = True
            self._set_ring(idx, led_val)
            self._force_ticks_only = False

        except Exception:
            # never crash UI over ring paint
            pass

    def _detect_pan_submode_from_lcd(self):
        return getattr(self, "_pan_submode", PAN_SUBMODE_TRACK)

    def _draw_assignment_crumb(self, ctx, w, h):
        if self.active_mode != MODE_PAN:
            return
        crumb = "PAN • Channel" if self._pan_submode == PAN_SUBMODE_CSTRIP else "PAN • Tracks"
        ctx.save()
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.select_font_face("Helvetica", 0, 0)
        ctx.set_font_size(11)
        xb, yb, tw, th, xadv, yadv = ctx.text_extents(crumb)
        # top-right with a little padding
        pad = 6
        tx = w - tw - pad - xb
        ty = pad - yb
        ctx.move_to(tx, ty)
        ctx.show_text(crumb)
        ctx.restore()

    def _set_pan_submode(self, new_mode: Optional[str], cause: str = ""):
        if new_mode and new_mode != getattr(self, "_pan_submode", None):
            self._pan_submode = new_mode
            # reflect immediately: dim rings if needed and refresh UI
            self.update_encoders()
            self.app.display_dirty = True

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
        if msg:
            print(f"[MCP RENDERMIX] From: {msg}")
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
            if _state(mute_states, abs_idx):
                to_set.append((row_mute[i], _SKY))
            if _state(solo_states, abs_idx):
                to_set.append((row_solo[i], _YELLOW))
            if _state(rec_states, abs_idx):
                to_set.append((row_rec[i], _RED))

        self._apply_pad_colors(to_set)
        self.app.pads_need_update = True

    def on_mcu_state_changed(self):
        self._render_mix_grid("mcu state changed")

    def initialize(self, settings=None):
        """Build default strips and start meter timer."""
        super().initialize(settings) if hasattr(super(), "initialize") else None
        # self._pad_meter = PadMeter(self.push)
        self.track_strips = []
        self.current_page = 0
        self.tracks_per_page = 8
        # self.current_mode = getattr(self, "current_mode", MODE_PAN)
        # reset pan state
        self._pan_view = [0.0] * 8
        self._pan_ring = [6] * 8
        self._last_pan = [None] * 8

        self.active_mode = getattr(self, "active_mode", MODE_VOLUME)
        self._substate = {MODE_PAN: SUB_ALL, MODE_VOLUME: SUB_ALL, MODE_EQ: EQ_PAGE_1}
        if hasattr(self, "add_display_notification"):
            self.add_display_notification(f"Mode: {self.active_mode.upper()} / {self._substate[self.active_mode]}")

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

        mm = getattr(self.app, "mcu_manager", None)
        if mm and not getattr(self, "_listeners_added", False):
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

            # self.pad_meter = PadMeter(self.push)
            self._listeners_added = True
        if hasattr(mm, "on_vpot_display"):
            mm.on_vpot_display = self.on_mcu_pan_echo  # reuse same ring handler (0..11 → 0..127)

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
            self._pan_view[bi] = float(value)
            self.app.display_dirty = True
            self.update_strip_values()

    def on_mcu_pan_echo(self, ch: int, ring_pos: int):
        if ch is None or not (0 <= ch < 8):
            return
        rp = max(0, min(11, int(ring_pos)))
        self._pan_ring[ch] = rp
        if self.active_mode == MODE_PAN:
            self._set_ring_style(ch, "ticks_center")
        self._set_ring(ch, int(rp * 127 / 11))
        self.app.display_dirty = True

    def _on_mcu_meter(self, **_):
        if not self.app.is_mode_active(self) or not getattr(self, "_playing", False):
            return
        mm = self.app.mcu_manager
        if not mm or len(mm.meter_levels) < 8:
            return
        num_banks = max(1, len(mm.meter_levels) // 8)
        raw = []
        for i in range(8):
            levels = [(mm.meter_levels[bank * 8 + i] & 0x0F) for bank in range(num_banks) if
                      (bank * 8 + i) < len(mm.meter_levels)]
            raw.append(max(levels) if levels else 0)
        MIN_RAW = 4
        MAX_RAW = 12
        _ = [max(1, min(127, int(((v - MIN_RAW) / (MAX_RAW - MIN_RAW)) * 127))) if v > MIN_RAW else 0 for v in raw]
        # (meter-to-pad rendering handled elsewhere in your project)

    def initialize_mix_defaults(self):
        """Call once when entering Mix/Mackie mode to avoid startup desync."""
        self._substate = {MODE_PAN: SUB_ALL, MODE_VOLUME: SUB_ALL, MODE_EQ: EQ_PAGE_1}
        self._pan_submode = PAN_SUBMODE_TRACK
        self.active_mode = MODE_VOLUME
        self._last_assignment = None
        self._clear_all_fader_touches()
        self._send_assignment("TRACK")
        self._apply_ring_styles_for_mode()

        # --- Anti‑flip nudge (idempotent) ---
        # Briefly poke PAN then TRACK so Logic rebinds VPOTs to pan and faders to volume.
        # This is safe and ends in TRACK, without relying on LCD heuristics.
        try:
            self._tap_mcu_button(MCU_ASSIGN_PAN)  # VPOTs → pan
            self._tap_mcu_button(MCU_ASSIGN_TRACK)  # Faders → volume (final state)
            self._last_assignment = MCU_ASSIGN_TRACK
        except Exception:
            pass

    def _set_ring(self, idx: int, value: int):
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

    def _set_ring_style(self, idx: int, style: str):
        """
        Best-effort ring style setter.
        Common styles you'll want:
          - "arc" (volume-style fill)
          - "ticks_center" (bipolar pan tick; center = 64)
          - "ticks" (unipolar tick)
        """
        enc = self.push.encoders
        name = self.encoder_names[idx]

        # Preferred: modern push2_python exposes set_ring_style(...)
        if hasattr(enc, "set_ring_style"):
            enc.set_ring_style(name, style)
            return

        # Legacy variants some forks expose
        if hasattr(enc, "set_encoder_ring_style"):
            enc.set_encoder_ring_style(name, style)
            return

        # Fallback: stash locally so if your painter checks this, it can honor it.
        # (No crash if nothing consumes it.)
        if not hasattr(self, "_ring_style"):
            self._ring_style = {}
        self._ring_style[name] = style

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
        # In Volume focus, keep only enc2 showing pan; redraw via update_encoders
        if self.active_mode == MODE_VOLUME and self._substate.get(MODE_VOLUME) == SUB_SINGLE:
            self._pan_view[bi] = float(value)
            self._last_pan[bi] = float(value)
            self.update_encoders()
            self.app.display_dirty = True
            return
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

        # Call our own initializer (sets TRACK once, sets ring styles, clears touches)
        self.initialize_mix_defaults()

        # Names
        if hasattr(self.app.mcu_manager, "get_visible_track_names"):
            names = self.app.mcu_manager.get_visible_track_names()
        else:
            names = getattr(self.app.mcu_manager, "track_names", [])[:self.tracks_per_page]
        self.set_visible_names(names)
        print("[TrackMode] Setting track names:", names)

        # Seed pan cache & paint once
        if hasattr(self.app, "mcu_manager"):
            pans = self.app.mcu_manager.get_visible_pan_values()
            if hasattr(self, "set_strip_pan"):
                for i, pan in enumerate(pans):
                    try:
                        self.set_strip_pan(i, int(pan))
                    except Exception:
                        pass
            if hasattr(self, "update_strip_values"):
                self.update_strip_values()

        self._sync_pan_from_logic()
        self.update_strip_values()

        self.push.pads.set_all_pads_to_color(
            color=definitions.BLACK,
            animation=ANIMATION_STATIC,
            animation_end_color='black'
        )

        # Paint hardware & UI
        self._apply_ring_styles_for_mode()
        self.update_encoders()
        self._blank_track_row_buttons()
        self.update_buttons()
        self._paint_selector_row()
        self._render_mix_grid("activate")

        # IMPORTANT: do NOT re‑tap assignment here. The initializer already sent TRACK.

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

        # reflect external value changes (safe), but DO NOT alter submode
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

        self._draw_top_button_labels(ctx, w, h)
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

        Extra guard: before sending the VPOT delta, explicitly send fader‑touch OFF
        for this channel so Logic never animates volume faders while in PAN.
        """
        if delta == 0:
            return

        # SAFETY: ensure any fader‑touch is OFF for this channel
        try:
            port = self.app.mcu_manager.output_port or getattr(self.app, "midi_out", None)
        except Exception:
            port = None
        if port:
            # MCU fader touch notes 0x68–0x6F for channels 0..7
            touch_note = 0x68 + max(0, min(7, int(channel)))
            # Send OFF unconditionally (cheap, prevents stale GUI touch)
            port.send(mido.Message('note_on', note=touch_note, velocity=0, channel=0))

        # Now send the VPOT relative delta (standard MCU)
        mag = min(63, abs(int(delta)))
        value = mag if delta > 0 else 64 + mag
        cc_num = 16 + channel
        if port:
            port.send(mido.Message('control_change', control=cc_num, value=value, channel=0))

    def _clear_all_fader_touches(self):
        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if not port:
            return
        for ch in range(8):
            port.send(mido.Message('note_on', note=0x68 + ch, velocity=0, channel=0))
        # if you track state:
        self._touch_state = [False] * 8

    def update_strip_values(self):
        self.app.display_dirty = True

    def update_encoders(self):
        """
        Paint Push 2 encoder rings to reflect current mode/submode.
        - VOL (SUB_SINGLE): Enc1=Volume (selected track), Enc2=Pan (selected track), Enc3..8=idle.
        - VOL (SUB_ALL):    Enc1..8 = 8 visible track volumes.
        - PAN:               Rings mirror current pan view (or are zeroed in CStrip for Enc2..8).
        - EQ:                Let Logic drive the rings via official VPOT ring echo; we don't paint here.
        """
        self._apply_ring_styles_for_mode()
        encoders = self.push.encoders
        mm = getattr(self.app, "mcu_manager", None)

        # EQ: don't touch rings; Logic's ring echo (on_vpot_display) owns them
        if self.active_mode == MODE_EQ:
            self.app.display_dirty = True
            return

        # ---------------------------
        # VOL focus (single channel)
        # ---------------------------
        if self.active_mode == MODE_VOLUME and self._substate.get(MODE_VOLUME) == SUB_SINGLE:
            if mm and mm.selected_track_idx is None:
                mm.selected_track_idx = (self.current_page or 0) * 8

            sel_rel = None
            if mm and mm.selected_track_idx is not None:
                sel_rel = int(mm.selected_track_idx) % 8

            vol_lin = 0.0
            if mm and sel_rel is not None and 0 <= sel_rel < len(mm.fader_levels):
                try:
                    vol_lin = float(mm.fader_levels[sel_rel])
                except Exception:
                    vol_lin = 0.0
            self._set_ring(0, int(max(0.0, min(1.0, vol_lin)) * 127))

            pan = 0.0
            if mm and sel_rel is not None and hasattr(mm, "pan_levels") and 0 <= sel_rel < len(mm.pan_levels):
                try:
                    pan = float(mm.pan_levels[sel_rel])
                except Exception:
                    pan = 0.0
            self._set_ring(1, int(((max(-64.0, min(63.0, pan)) + 64.0) / 128.0) * 127.0))

            for i in range(2, 8):
                self._set_ring(i, 0)
            self.app.display_dirty = True
            return

        # ---------------------------
        # PAN mode
        # ---------------------------
        # --- PAN mode ---
        if self.active_mode == MODE_PAN:
            self._sync_pan_from_logic()

            if self._pan_submode == PAN_SUBMODE_CSTRIP:
                sel_rel = None
                mm = getattr(self.app, "mcu_manager", None)
                if mm and mm.selected_track_idx is not None:
                    sel_rel = int(mm.selected_track_idx) % 8

                pan = 0.0
                if mm and sel_rel is not None and hasattr(mm, "pan_levels") and 0 <= sel_rel < len(mm.pan_levels):
                    try:
                        pan = float(mm.pan_levels[sel_rel])
                    except Exception:
                        pan = 0.0

                led_val = int(((max(-64.0, min(63.0, pan)) + 64.0) / 128.0) * 127.0)
                self._set_ring_ticks_only(0, led_val, bipolar=True)
                for i in range(1, 8):
                    self._set_ring_ticks_only(i, 0, bipolar=True)

                self.app.display_dirty = True
                return

            # Track‑pan view: 8 pans on 8 rings (ticks only)
            for i in range(self.tracks_per_page):
                try:
                    val = float(self._pan_view[i])
                except Exception:
                    val = 0.0
                led_val = int(((max(-64.0, min(63.0, val)) + 64.0) / 128.0) * 127.0)
                self._set_ring_ticks_only(i, led_val, bipolar=True)

            self.app.display_dirty = True
            return

        # ---------------------------
        # VOL 8‑track view
        # ---------------------------
        if self.active_mode == MODE_VOLUME:
            base = self.current_page * self.tracks_per_page
            for i in range(self.tracks_per_page):
                try:
                    lv = float(self.app.mcu_manager.fader_levels[i])
                except Exception:
                    lv = 0.0
                self._set_ring(i, int(max(0.0, min(1.0, lv)) * 127))
            self.app.display_dirty = True
            return

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
        try:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_LEFT, definitions.GRAY_LIGHT)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_RIGHT, definitions.GRAY_LIGHT)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_RIGHT, definitions.GRAY_LIGHT)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_LEFT, definitions.GRAY_LIGHT)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UP, definitions.GRAY_LIGHT)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_DOWN, definitions.GRAY_LIGHT)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_32T, definitions.GREEN)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_32, definitions.SKYBLUE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_16T, definitions.YELLOW)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_16, definitions.RED)

        except Exception:
            pass

    def on_button_pressed_raw(self, btn):
        mm = getattr(self.app, "mcu_manager", None)

        # === 1) D‑PAD → MCU Cursor (96..99) ===
        if btn in (P2.BUTTON_LEFT, P2.BUTTON_RIGHT, P2.BUTTON_UP, P2.BUTTON_DOWN):
            if not mm:
                return True
            if btn == P2.BUTTON_LEFT:
                mm.cursor_left()
            elif btn == P2.BUTTON_RIGHT:
                mm.cursor_right()
            elif btn == P2.BUTTON_UP:
                mm.cursor_up()
            elif btn == P2.BUTTON_DOWN:
                mm.cursor_down()
            return True

        # === 2) Touch-strip PAGE < > (your “channel/bank” nav) ===
        if btn in (push2_python.constants.BUTTON_PAGE_LEFT, push2_python.constants.BUTTON_PAGE_RIGHT):
            shift = bool(getattr(self.app, "shift_held", False))
            if shift:
                # Shift+Page = BANK < >
                self._send_assignment("BANK_LEFT" if btn == push2_python.constants.BUTTON_PAGE_LEFT else "BANK_RIGHT")
            else:
                # In pageable contexts use true PAGE < >; otherwise fall back to EQ/PAN shortcuts
                page_mode = (self.active_mode == MODE_EQ) or (self._pan_submode == PAN_SUBMODE_CSTRIP)
                if page_mode:
                    self._send_assignment(
                        "PAGE_LEFT" if btn == push2_python.constants.BUTTON_PAGE_LEFT else "PAGE_RIGHT")
                else:
                    self._send_assignment("EQ" if btn == push2_python.constants.BUTTON_PAGE_LEFT else "PAN")
            return True

        # === 3) LOWER ROW = MODE SELECTORS ===
        for i in range(8):
            lower_btn = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")
            if btn == lower_btn:
                self._set_mode(LOWER_ROW_MODES[i])
                return True

        # === 4) UPPER ROW = TRACK ACTIONS (SELECT/MUTE/SOLO) ===
        for i in range(8):
            upper_btn = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
            if btn == upper_btn:
                if self.active_mode == MODE_SOLO:
                    if mm and mm.selected_track_idx is None:
                        mm.selected_track_idx = self.current_page * self.tracks_per_page + i
                    self._tap_mcu_button(8 + i)  # SOLO 8..15
                    self.app.buttons_need_update = True
                    return True

                elif self.active_mode == MODE_MUTE:
                    if mm and mm.selected_track_idx is None:
                        mm.selected_track_idx = self.current_page * self.tracks_per_page + i
                    self._tap_mcu_button(16 + i)  # MUTE 16..23
                    self.app.buttons_need_update = True
                    return True

                elif self.active_mode in (MODE_VOLUME, MODE_PAN, MODE_VPOT):
                    # In these modes, upper row = SELECT for that strip
                    if mm:
                        abs_idx = self.current_page * self.tracks_per_page + i
                        mm.selected_track_idx = abs_idx
                    self._tap_mcu_button(24 + i)  # SELECT 24..31
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
        self._render_mix_grid("on mcu track state")  # render LAST
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def on_encoder_rotated(self, encoder_name, increment):
        if encoder_name not in self.encoder_names:
            return False

        local_idx = self.encoder_names.index(encoder_name)  # 0..7 in visible bank
        strip_idx = self.current_page * self.tracks_per_page + local_idx
        if strip_idx >= len(self.track_strips):
            return False

        # --- PAN mode ---
        if self.active_mode == MODE_PAN:
            mm = getattr(self.app, "mcu_manager", None)

            # Channel‑Strip PAN: only encoder 1 (index 0) is live and targets the SELECTED track
            if self._pan_submode == PAN_SUBMODE_CSTRIP:
                if local_idx != 0:
                    return True
                if not mm or mm.selected_track_idx is None:
                    return True
                sel_rel = int(mm.selected_track_idx) % 8
                if increment != 0:
                    self._send_mcu_pan_delta(sel_rel, 1 if increment > 0 else -1)
                return True

            # Track PAN: encoders map 1:1 to visible channels
            if increment != 0:
                self._send_mcu_pan_delta(local_idx, 1 if increment > 0 else -1)
            return True

        # --- VOLUME mode ---
        if self.active_mode == MODE_VOLUME:
            mm = self.app.mcu_manager

            # Focus submode: enc1=Volume, enc2=Pan for the selected track
            if self._substate.get(MODE_VOLUME) == SUB_SINGLE:
                if not mm or mm.selected_track_idx is None:
                    return True
                sel_rel = int(mm.selected_track_idx) % 8

                if local_idx == 0:
                    # Volume (selected track)
                    self.track_strips[mm.selected_track_idx].update_value(increment)
                    level = mm.fader_levels[sel_rel]
                    self._send_mcu_fader_move(sel_rel, level)
                    return True

                if local_idx == 1:
                    # Pan (selected track)
                    if increment != 0:
                        self._send_mcu_pan_delta(sel_rel, 1 if increment > 0 else -1)
                    return True

                return True

            # 8‑track submode: encoders 1–8 → faders 1–8
            self.track_strips[strip_idx].update_value(increment)
            level = self.app.mcu_manager.fader_levels[local_idx]
            self._send_mcu_fader_move(local_idx, level)
            return True

        # --- EQ: 8 encoders live on both pages ---
        if self.active_mode == MODE_EQ:
            if increment != 0:
                self._send_mcu_vpot_delta(local_idx, 1 if increment > 0 else -1)
            return True

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
            self._render_mix_grid("on pad pressed")  # show green immediately
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
        if encoder_name not in self.encoder_names:
            return False
        ch = self.encoder_names.index(encoder_name)
        if not hasattr(self, "_touch_state"):
            self._touch_state = [False] * 8
        if self._touch_state[ch]:
            return True

        is_fader = False
        if self.active_mode == MODE_VOLUME:
            if self._substate.get(MODE_VOLUME) == SUB_ALL:
                is_fader = True
            else:
                is_fader = (ch == 0)  # only enc1 in single-channel volume mode

        if not is_fader:
            return True

        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if port:
            port.send(mido.Message('note_on', note=0x68 + ch, velocity=127, channel=0))
            self._touch_state[ch] = True
        return True

    def on_encoder_released(self, encoder_name):
        if encoder_name not in self.encoder_names:
            return False
        ch = self.encoder_names.index(encoder_name)
        if not hasattr(self, "_touch_state") or not self._touch_state[ch]:
            return True
        port = getattr(self.app.mcu_manager, "output_port", None) or getattr(self.app, "midi_out", None)
        if port:
            port.send(mido.Message('note_on', note=0x68 + ch, velocity=0, channel=0))
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
