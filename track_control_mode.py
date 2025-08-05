import math, mido, threading, time
import definitions, push2_python
from display_utils import show_text
from definitions import pb_to_db, db_to_pb
# ──────────────────────────────────────────────────────────────────────────────
# MCU-TOUCH BOOK-KEEPING  (one slot per channel 0-7)
# ──────────────────────────────────────────────────────────────────────────────
TOUCH_DOWN  = [False] * 8          # True while NOTE-ON 127 is held
TOUCH_TIMER = [None]  * 8          # threading.Timer() objects
RELEASE_MS  = 400
# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _bank(idx: int) -> int:
    """Return the 0-7 index within the current 8-channel MCU bank."""
    return idx % 8


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
        self.get_pan_func    = get_pan_func
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
        db     = TrackControlMode._level_to_db(volume)
        label  = "-∞ dB" if db == float('-inf') else f"{db:+.1f} dB"

        # highlight selected track
        if selected:
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_DARK))
            ctx.rectangle(x, y, col_width, display_h)
            ctx.fill()
            ctx.restore()

        # horizontal centring
        content_x = x + col_width * 0.25
        xc = content_x + radius + 3
        yc = margin_top + name_h + val_h + radius + 5

        show_text(ctx, x_part, margin_top, self.name,
                  height=name_h, font_color=definitions.SKYBLUE)
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

        # ----- NEW: centred green pan value ----------------------------------
        pan_val  = int(max(-64, min(64, self.get_pan_func(self.index))))
        pan_text = f"{pan_val:+d}"
        pan_y    = margin_top + name_h + val_h + meter_h + 5
        show_text(ctx, x_part, pan_y, pan_text, height=18,
                  font_color=definitions.GREEN)

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
            mult = 0.1                   # 10× finer
            if self.app.select_held:
                mult = 0.02              # 50× finer (0.01 dB-ish)

        step = base_step * mult
        new_val = max(
            self.vmin,
            min(self.vmax, self.get_volume_func(self.index) + increment * step),
        )
        self.set_volume_func(self.index, new_val)


# ──────────────────────────────────────────────────────────────────────────────
# TrackControlMode
# ──────────────────────────────────────────────────────────────────────────────
class TrackControlMode(definitions.LogicMode):
    @staticmethod
    def _level_to_db(level: float) -> float:
        # level is kept 0…1   →   pb is 0…16383
        return pb_to_db(int(level * 16383))

    @staticmethod
    def _db_to_level(db: float) -> float:
        return db_to_pb(db) / 16383.0

    current_page = 0
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

    # ---------------------------------------------------------------- init/up
    def initialize(self, settings=None):
        """Build 64 default strips wired to MCU-manager fader state (8-bank safe)."""
        self.track_strips = []
        self.current_page = 0
        self.tracks_per_page = 8

        def get_color(idx):
            if hasattr(self.app, "mcu_manager"):
                return (
                    definitions.GREEN
                    if self.app.mcu_manager.select_states[_bank(idx)]
                    else definitions.GRAY_LIGHT
                )
            return definitions.GRAY_LIGHT

        def get_volume(idx):
            if hasattr(self.app, "mcu_manager"):
                return self.app.mcu_manager.fader_levels[_bank(idx)]
            return 0.0

        def set_volume(idx, val):
            if hasattr(self.app, "mcu_manager"):
                bank_idx = _bank(idx)
                self.app.mcu_manager.fader_levels[bank_idx] = val
                self.app.mcu_manager.emit_event("fader", channel_idx=bank_idx, level=val)

        # NEW ────────────────────────────────────────────────────────────
        def get_pan(idx):
            mm = getattr(self.app, "mcu_manager", None)
            if mm and hasattr(mm, "pan_levels"):
                return mm.pan_levels[_bank(idx)]
            return 0

        for i in range(64):
            name = f"Track {i + 1}"
            self.track_strips.append(
                TrackStrip(self.app, i, name, get_color, get_volume, set_volume, get_pan)
            )

        # OPTIONAL: register for realtime pan events if the manager emits them
        mm = getattr(self.app, "mcu_manager", None)
        if mm and hasattr(mm, "add_listener"):
            mm.add_listener("pan", self._on_mcu_pan)

    # ----------------------------- MCU pan event (optional but snappy)
    def _on_mcu_pan(self, *, channel_idx: int, value: int, **_):
        if channel_idx is None:
            return
        global_idx = self.current_page * 8 + channel_idx
        try:
            strip = self.track_strips[global_idx]
            if strip:
                # force a UI refresh; value is already in mm.pan_levels
                self.update_strip_values()
        except IndexError:
            pass

    # -------------------------------------------------------------- navigation
    def move_to_next_page(self):
        self.app.buttons_need_update = True
        self.current_page += 1
        if self.current_page >= self.n_pages:
            self.current_page = 0
            return True
        return False

    def activate(self):
        self.initialize()
        self.current_page = 0

        if hasattr(self.app.mcu_manager, "get_visible_track_names"):
            names = self.app.mcu_manager.get_visible_track_names()
        else:
            names = getattr(self.app.mcu_manager, "track_names", [])[:self.tracks_per_page]
        for idx, nm in enumerate(names):
            if nm:
                self.track_strips[idx].name = nm
        print("[TrackMode] Setting track names:", names)

        self.update_buttons()
        self.update_encoders()
        self.update_strip_values()

    def deactivate(self):
        for row in range(4):
            for col in range(8):
                btn = self.get_pad_button(col, row)
                if btn:
                    self.push.buttons.set_button_color(btn, definitions.BLACK)

    # ------------------------------------------------------- Push UI refreshes
    def update_buttons(self):
        for i in range(self.tracks_per_page):
            try:
                strip = self.track_strips[self.current_page * self.tracks_per_page + i]
                c = strip.get_color_func(strip.index)
                if c not in definitions.COLORS_NAMES:
                    c = definitions.GRAY_LIGHT
            except IndexError:
                c = definitions.BLACK

            btn = self.get_pad_button(i, 0)
            if btn:
                self.push.buttons.set_button_color(btn, c)

    def update_display(self, ctx, w, h):
        ctx.rectangle(0, 0, w, h)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()

        start = self.current_page * self.tracks_per_page
        selected_idx = getattr(self.app.mcu_manager, "selected_track_idx", None)

        for i in range(self.tracks_per_page):
            strip_idx = start + i
            if strip_idx < len(self.track_strips):
                self.track_strips[strip_idx].draw(
                    ctx, i, selected=(strip_idx == selected_idx)
                )

    def update_strip_values(self):
        if hasattr(self.app, "update_push2_display"):
            self.app.update_push2_display()
        elif hasattr(self.app, "request_push2_display_update"):
            self.app.request_push2_display_update()
        elif hasattr(self.push, "update_display"):
            self.push.update_display()

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
    def on_button_pressed_raw(self, button_name):
        for col in range(self.tracks_per_page):
            if button_name == self.get_pad_button(col, 0):
                print(f"[TrackControlMode] Pressed Track Pad {col}")
                return True
        return False

    # ───────────────────────────────────────────────────────────────────── MIDI
    def _send_mcu_fader_move(self, channel: int, level: float):
        """
        Emulate a Mackie fader with Push 2's endless encoders:

        • Send NOTE-ON 127 once at the start of the gesture (“touch down”)
        • Stream PITCHBEND while the knob moves
        • 400 ms after the last tick, send NOTE-ON 0 (“touch up”)
        """

        mcu  = getattr(self.app, "mcu_manager", None)
        port = mcu.output_port if (mcu and mcu.output_port) else getattr(self.app, "midi_out", None)
        if port is None:
            print("[TrackMode] ⚠️  No MIDI port for fader move!")
            return

        # ---------------------------------------------------------------- internal state
        if not hasattr(self, "_touch_state"):
            # one flag + one timer per encoder channel
            self._touch_state  = [False] * 8      # False = up, True = down
            self._touch_timer  = [None]  * 8

        touch_note = 0x68 + channel                  # 0x68 … 0x6F  (always on MIDI Ch-1)
        pb_value   = int(level * 16383) - 8192       # −8192 … +8191

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

    def on_encoder_rotated(self, encoder_name, increment):
        if encoder_name not in self.encoder_names:
            return False

        local_idx = self.encoder_names.index(encoder_name)  # 0-7 within page
        strip_idx = self.current_page * self.tracks_per_page + local_idx
        if strip_idx >= len(self.track_strips):
            return False

        # 1) update internal value + GUI
        self.track_strips[strip_idx].update_value(increment)

        # 2) read the new level (already bank-safe)
        level = self.app.mcu_manager.fader_levels[local_idx]

        # 3) send Mackie fader move
        self._send_mcu_fader_move(local_idx, level)

        # 4) flag Push redraws
        self.app.buttons_need_update = True
        self.app.pads_need_update = True
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
