import math, mido, threading, time
import definitions, push2_python
from display_utils import show_text
from definitions import pb_to_db, db_to_pb
from pad_meter import PadMeter

# ──────────────────────────────────────────────────────────────────────────────
# MCU-TOUCH BOOK-KEEPING  (one slot per channel 0-7)
# ──────────────────────────────────────────────────────────────────────────────
TOUCH_DOWN = [False] * 8  # True while NOTE-ON 127 is held
TOUCH_TIMER = [None] * 8  # threading.Timer() objects
RELEASE_MS = 400


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _bank(idx: int) -> int:
    """Return the 0-7 index within the current 8-channel MCU bank."""
    return idx % 8

PAD_COLUMNS = [[(row, col)          # 0-based, bottom-row = 0
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
        db = TrackControlMode._level_to_db(volume)
        label = "-∞ dB" if db == float('-inf') else f"{db:+.1f} dB"

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

        # ── 11-tick pan ring ──────────────────────────────────────────────
        pan_val = int(max(-64, min(64, self.get_pan_func(self.index))))
        pan_steps = [-64, -51, -38, -25, -13, 0, 13, 26, 38, 51, 64]
        cur_idx = min(range(len(pan_steps)), key=lambda i: abs(pan_steps[i] - pan_val))

        inner_r = radius - 6  # nest inside main arc
        tick_len = 6
        for i, _ in enumerate(pan_steps):
            ang = start_rad + math.radians(280) * i / (len(pan_steps) - 1)
            x1 = xc + inner_r * math.cos(ang)
            y1 = yc + inner_r * math.sin(ang)
            x2 = xc + (inner_r - tick_len) * math.cos(ang)
            y2 = yc + (inner_r - tick_len) * math.sin(ang)

            lit = (
                    (cur_idx == 5 and i == 5) or
                    (cur_idx < 5 and i <= 5 and i >= cur_idx) or  # left fill
                    (cur_idx > 5 and i >= 5 and i <= cur_idx)  # right fill
            )
            col = definitions.GREEN if lit else definitions.GRAY_DARK
            ctx.set_source_rgb(*definitions.get_color_rgb_float(col))
            ctx.set_line_width(2)
            ctx.move_to(x1, y1)
            ctx.line_to(x2, y2)
            ctx.stroke()
        # ----- NEW: centred green pan value ----------------------------------
        pan_val = int(max(-64, min(64, self.get_pan_func(self.index))))
        pan_text = f"{pan_val:+d}"
        pan_y = margin_top + name_h + val_h + meter_h + 5
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
# TrackControlMode
# ──────────────────────────────────────────────────────────────────────────────
class TrackControlMode(definitions.LogicMode):
    xor_group = "pads"

    # ---------------------------------------------------------------- helpers
    def _blank_track_row_buttons(self):
        for btn in self.buttons_used:
            self.push.buttons.set_button_color(btn, definitions.OFF_BTN_COLOR)

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
    def _blank_track_row_buttons(self):
        for btn in self.buttons_used:
            self.push.buttons.set_button_color(btn, definitions.OFF_BTN_COLOR)

    def _tap_mcu_button(self, note_num: int):
        port = self.app.mcu_manager.output_port or getattr(self.app, "midi_out", None)
        if not port: return
        port.send(mido.Message('note_on', note=note_num, velocity=127, channel=0))
        port.send(mido.Message('note_on', note=note_num, velocity=0, channel=0))

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
            mm = getattr(self.app, "mcu_manager", None)
            return mm.pan_levels[_bank(idx)] if mm else 0

        for i in range(64):
            self.track_strips.append(
                TrackStrip(self.app, i, f"Track {i + 1}", get_color, get_volume, set_volume, get_pan)
            )

        # add listeners only once
        mm = getattr(self.app, "mcu_manager", None)
        if mm and not getattr(self, "_listeners_added", False):
            mm.add_listener("pan", self._on_mcu_pan)
            mm.add_listener("track_state", self._on_mcu_track_state)
            mm.add_listener("solo", self._on_mcu_track_state)
            mm.add_listener("mute", self._on_mcu_track_state)
            mm.add_listener("meter", self._on_mcu_meter)

            self._listeners_added = True

    # --- meters ------------------------------------------------------
    def _on_mcu_meter(self, **_):
        # Only light pads while Track-Control (Mix) mode is ACTIVE.
        if not self.app.is_mode_active(self):
            return

        mm    = self.app.mcu_manager
        start = self.current_page * 8          # which 8-track page is visible?
        self._pad_meter.update(mm.meter_levels[start:start + 8])

    # ---------------------------------------------------------------- ring helper
    def _set_ring(self, idx: int, value: int):
        """
        Push 2 encoders have three possible APIs depending on the library
        version.  This helper picks whichever one exists.
        """
        enc = self.push.encoders
        name = self.encoder_names[idx]

        if hasattr(enc, "set_ring_value"):           # push2-python ≥1.2
            enc.set_ring_value(name, value)
        elif hasattr(enc, "set_encoder_ring_value"): # very old push2-python
            enc.set_encoder_ring_value(name, value)
        else:                                        # fallback
            enc.set_value(name, value)

    def _on_mcu_pan(self, *, channel_idx: int, value: int, **_):
        if self.current_page * 8 > channel_idx or channel_idx >= (self.current_page + 1) * 8:
            return  # pan event belongs to another page; ignore
        if channel_idx is None:
            return
        encoder_name = self.encoder_names[channel_idx % 8]
        led_val = int((value + 64) * 127 / 128)
        self._set_ring(channel_idx % 8, led_val)
        self.app.display_dirty = True
        global_idx = self.current_page * 8 + channel_idx
        try:
            strip = self.track_strips[global_idx]
            if strip:
                # force a UI refresh; value is already in mm.pan_levels
                self.update_strip_values()
        except IndexError:
            pass

    def set_visible_names(self, names):
        # names is length-8 list from MCUManager
        for i, nm in enumerate(names):
            self.track_strips[i].name = nm
        self.update_strip_values()

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
        # Hard-black all 64 pads
        self.push.pads.set_all_pads_to_color(color=definitions.BLACK)
        self.update_encoders()
        self._blank_track_row_buttons()
        self.update_buttons()
        self.update_strip_values()
        # ── paint meters immediately, no need to wait for the next event
        mm = getattr(self.app, "mcu_manager", None)
        if mm:
            self._pad_meter.update(mm.meter_levels[self.current_page*8 :
                                                   self.current_page*8+8])

    def deactivate(self):
        # Run supperclass deactivate to set all used buttons to black
        self.push.pads.set_all_pads_to_color(definitions.BLACK)
        super().deactivate()
        # Also set all pads to black
        self._blank_track_row_buttons()
        self.app.pads_need_update = True

    def on_pad_pressed(self, pad_n, pad_ij, velocity, loop=False, quantize=False, shift=False, select=False,
                       long_press=False, double_press=False):
        self.app.pads_need_update = True
        return True

    def on_pad_released(self, pad_n, pad_ij, **_):
        return True

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
        Send a V-Pot delta.  delta ∈ [-63 … +63], 1 step ≈ 1 Logic pan tick.
        """
        if delta == 0:
            return
        cc_num = 16 + channel
        value = delta & 0x7F  # wrap to 7-bit signed
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

                solo_btn = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
                mute_btn = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")

                self.push.buttons.set_button_color(
                    solo_btn, definitions.YELLOW if solo else definitions.OFF_BTN_COLOR
                )
                self.push.buttons.set_button_color(
                    mute_btn, definitions.SKYBLUE if mute else definitions.OFF_BTN_COLOR
                )

    def on_button_pressed_raw(self, btn):
        for i in range(8):
            solo_btn = getattr(push2_python.constants, f"BUTTON_UPPER_ROW_{i + 1}")
            mute_btn = getattr(push2_python.constants, f"BUTTON_LOWER_ROW_{i + 1}")
            if btn == solo_btn:
                self._tap_mcu_button(8 + i)  # SOLO notes 8–15
                self.app.buttons_need_update = True
                return True

            if btn == mute_btn:
                self._tap_mcu_button(16 + i)
                self.app.buttons_need_update = True
                return True
        return btn in self.buttons_used  # absorb anything else on these rows

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
        # self.app.pads_need_update = True
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
