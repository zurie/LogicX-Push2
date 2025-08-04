import definitions
import push2_python
import math
from display_utils import show_text
import mido

class TrackStrip:
    def __init__(self, index, name, get_color_func, get_volume_func, set_volume_func):
        self.index = index
        self.name = name
        self.get_color_func = get_color_func
        self.get_volume_func = get_volume_func
        self.set_volume_func = set_volume_func
        self.vmin = 0.0
        self.vmax = 1.0

    def draw(self, ctx, x_part, selected=False):
        margin_top = 25
        name_height = 20
        val_height = 30
        height = 55
        radius = height / 2

        display_w = push2_python.constants.DISPLAY_LINE_PIXELS
        display_h = push2_python.constants.DISPLAY_N_LINES
        col_width = display_w // 8
        x = int(col_width * x_part)
        y = 0  # top

        color = self.get_color_func(self.index)
        volume = self.get_volume_func(self.index)
        label = f"{int(volume * 100)}%"

        # -- HIGHLIGHT ENTIRE COLUMN IF SELECTED --
        if selected:
            ctx.save()
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_DARK))  # or BLUE etc
            ctx.rectangle(x, y, col_width, display_h)
            ctx.fill()
            ctx.restore()

        # Now, offset content a bit horizontally for visual balance
        content_x = x + col_width * 0.25
        xc = content_x + radius + 3
        yc = margin_top + name_height + val_height + radius + 5

        show_text(ctx, x_part, margin_top, self.name, height=name_height, font_color=definitions.SKYBLUE)
        show_text(ctx, x_part, margin_top + name_height, label, height=val_height, font_color=color)

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



    def update_value(self, increment):
        step = 0.01
        new_val = max(self.vmin,
                      min(self.vmax, self.get_volume_func(self.index) + increment * step))
        self.set_volume_func(self.index, new_val)


class TrackControlMode(definitions.LogicMode):
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

    def initialize(self, settings=None):
        """Build 64 default strips wired to MCU manager fader state."""
        self.track_strips = []
        self.current_page = 0
        self.tracks_per_page = 8

        def get_color(idx):
            if hasattr(self.app, "mcu_manager"):
                return definitions.GREEN if self.app.mcu_manager.select_states[idx] else definitions.GRAY_LIGHT
            return definitions.GRAY_LIGHT

        def get_volume(idx):
            if hasattr(self.app, "mcu_manager"):
                return self.app.mcu_manager.fader_levels[idx]
            return 0.0

        def set_volume(idx, val):
            if hasattr(self.app, "mcu_manager"):
                self.app.mcu_manager.fader_levels[idx] = val
                self.app.mcu_manager.emit_event("fader", channel_idx=idx, level=val)

        for i in range(64):
            name = f"Track {i + 1}"
            self.track_strips.append(
                TrackStrip(i, name, get_color, get_volume, set_volume)
            )

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
        # clear all 4×8 pads
        for row in range(4):
            for col in range(8):
                btn = self.get_pad_button(col, row)
                if btn:
                    self.push.buttons.set_button_color(btn, definitions.BLACK)

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
        # clear screen
        ctx.rectangle(0, 0, w, h)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()

        start = self.current_page * self.tracks_per_page
        selected_idx = None
        if hasattr(self.app, "mcu_manager") and hasattr(self.app.mcu_manager, "selected_track_idx"):
            selected_idx = self.app.mcu_manager.selected_track_idx

        for i in range(self.tracks_per_page):
            try:
                strip_idx = start + i
                # highlight if this strip is the selected track
                is_selected = (strip_idx == selected_idx)
                self.track_strips[strip_idx].draw(ctx, i, selected=is_selected)
            except IndexError:
                pass



    def update_strip_values(self):
        """
        Trigger a redraw of the current visible strips—typically by causing
        the Push 2 display to repaint with latest track values.
        """
        # Try app-level request first
        if hasattr(self.app, "update_push2_display"):
            self.app.update_push2_display()
        elif hasattr(self.app, "request_push2_display_update"):
            self.app.request_push2_display_update()
        elif hasattr(self.push, "update_display"):
            self.push.update_display()
        else:
            print("[WARN] No display update function found for Push2")

    def update_encoders(self):
        """
        Update all 8 encoder LED rings to reflect the current volume value
        for each visible track strip.
        """
        for i in range(self.tracks_per_page):
            strip_idx = self.current_page * self.tracks_per_page + i
            if strip_idx >= len(self.track_strips):
                continue
            strip = self.track_strips[strip_idx]
            value = strip.get_volume_func(strip.index)
            led_val = int(value * 127)
            encoder_name = self.encoder_names[i]

            # Find the correct method to set encoder ring
            encoders = self.push.encoders
            if hasattr(encoders, 'set_ring_value'):
                encoders.set_ring_value(encoder_name, led_val)
            elif hasattr(encoders, 'set_encoder_ring_value'):
                encoders.set_encoder_ring_value(encoder_name, led_val)
            elif hasattr(encoders, 'set_value'):
                encoders.set_value(encoder_name, led_val)
            else:
                print("[ERROR] No method found to set encoder ring value in Push2Encoders")


    def on_button_pressed_raw(self, button_name):
        for col in range(self.tracks_per_page):
            if button_name == self.get_pad_button(col, 0):
                print(f"[TrackControlMode] Pressed Track Pad {col}")
                return True
        return False

    def on_encoder_rotated(self, encoder_name, increment):
        """
        Turn encoder 1–8 into Mackie‐Control faders 1–8 (Pitch Bend on channels 0–7)
        and send exclusively over the MCU port so Logic updates.
        """
        if encoder_name not in self.encoder_names:
            return False

        idx = self.encoder_names.index(encoder_name)        # 0–7
        track_idx = self.current_page * self.tracks_per_page + idx
        if track_idx >= len(self.track_strips):
            return False

        # 1) locally update Push GUI
        self.track_strips[track_idx].update_value(increment)

        # read the new 0.0–1.0 level from your MCU state:
        level = self.app.mcu_manager.fader_levels[idx]
        # convert to 14-bit 0…16383 signed (Mackie uses –8192…+8191)
        pb = int(level * 16383) - 8192
        msg = mido.Message(
            "pitchwheel",
            pitch=pb,
            channel=idx    # MIDI channels 0–7 map to Logic tracks 1–8
        )

        # 3) send *only* on the MCU output port (where Logic is listening)
        mcu = getattr(self.app, "mcu_manager", None)
        if mcu and getattr(mcu, "output_port", None):
            mcu.output_port.send(msg)
        else:
            # fallback if MCU isn’t up yet
            self.app.midi_out.send(msg)

        # 4) force an immediate Push redraw
        self.app.buttons_need_update = True
        self.app.pads_need_update    = True
        return True


    @property
    def total_pages(self):
        return max(1, math.ceil(len(self.track_strips) / self.tracks_per_page))

    def get_pad_button(self, col, row):
        try:
            return getattr(push2_python.constants, f"BUTTON_ROW_{row}_COL_{col}")
        except AttributeError:
            return None
