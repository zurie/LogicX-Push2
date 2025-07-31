import time

import definitions
import push2_python.constants

from settings_mode import SettingsMode
from display_utils import show_title, show_value, draw_text_at, show_bigvalue


class ScaleMenuMode(SettingsMode):
    current_page = 0
    n_pages = 1
    encoders_state = {}

    def initialize(self, settings=None):
        current_time = time.time()
        for encoder_name in self.push.encoders.available_names:
            self.encoders_state[encoder_name] = {
                'last_message_received': current_time,
            }

    def activate(self):
        self.current_page = 0
        self.update_buttons()

    def deactivate(self):
        self.set_all_upper_row_buttons_off()

    def update_buttons(self):
        if self.current_page == 0:  # Performance settings
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_1, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_2, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_3, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_4, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_5, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_6, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_7, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_8, self.app.track_selection_mode.get_current_track_color())

    def set_all_upper_row_buttons_off(self):
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_1, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_2, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_3, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_4, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_5, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_6, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_7, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_8, definitions.BLACK)

    def on_button_pressed_raw(self, button_name):
        if self.current_page == 0:
            if button_name == push2_python.constants.BUTTON_UPPER_ROW_1:
                self.app.melodic_mode.set_root_midi_note(self.app.melodic_mode.root_midi_note + 1)
                self.app.pads_need_update = True
                return True
        return None

    def on_button_pressed(self, button_name, loop=False, quantize=False, shift=False, select=False, long_press=False, double_press=False):
        if self.current_page == 0:
            if button_name == push2_python.constants.BUTTON_UPPER_ROW_2:
                self.app.toggle_collapse_scale()
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_7:
                self.app.melodic_mode.scaley('dec')
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_8:
                self.app.melodic_mode.scaley('inc')
                return True
        return None

    def update_display(self, ctx, w, h):
        part_h = h

        for i in range(2, 6):
            part_x = i * w // 8
            ctx.set_source_rgb(0, 0, 0)  # Black background
            ctx.rectangle(part_x - 3, 0, w // 8 + 6, h)
            ctx.fill()

        for i in range(2):
            part_x = i * w // 8
            ctx.set_source_rgb(0, 0, 0)
            ctx.rectangle(part_x - 3, 0, w // 8 + 6, h)
            ctx.fill()

            color = [1.0, 1.0, 1.0]
            if self.current_page == 0:
                if i == 0:
                    if not self.app.is_mode_active(self.app.melodic_mode):
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DISABLED)
                    show_title(ctx, part_x, h, 'ROOT NOTE')
                    show_value(ctx, part_x, h, "{0} ({1})".format(
                        self.app.melodic_mode.note_number_to_name(self.app.melodic_mode.root_midi_note),
                        self.app.melodic_mode.root_midi_note), color)

                elif i == 1:
                    show_title(ctx, part_x, h, 'COLLAPSE SCALE')
                    show_bigvalue(ctx, part_x, h, definitions.SCALE_NAME, color)

        for i, label in zip([6, 7], ["<", ">"]):
            part_x = i * w // 8
            ctx.set_source_rgb(0, 0, 0)
            ctx.rectangle(part_x - 3, 0, w // 8 + 6, h)
            ctx.fill()
            draw_text_at(ctx, part_x + 5, h // 2, label, font_size=40)

        current_time = time.time()
        if current_time - self.app.melodic_mode.latest_channel_at_value[0] < 3 and not self.app.melodic_mode.use_poly_at:
            draw_text_at(ctx, 3, part_h - 3, f'Latest cAT: {self.app.melodic_mode.latest_channel_at_value[1]}',
                         font_size=20)
        if current_time - self.app.melodic_mode.latest_poly_at_value[0] < 3 and self.app.melodic_mode.use_poly_at:
            draw_text_at(ctx, 3, part_h - 3, f'Latest pAT: {self.app.melodic_mode.latest_poly_at_value[1]}',
                         font_size=20)
        if current_time - self.app.melodic_mode.latest_velocity_value[0] < 3:
            draw_text_at(ctx, 3, part_h - 26, f'Latest velocity: {self.app.melodic_mode.latest_velocity_value[1]}',
                         font_size=20)

    def on_encoder_rotated(self, encoder_name, increment):
        now = time.time()

        if self.current_page == 0:
            if encoder_name == push2_python.constants.ENCODER_TRACK1_ENCODER:
                self.app.melodic_mode.set_root_midi_note(self.app.melodic_mode.root_midi_note + increment)
                self.app.pads_need_update = True

            elif encoder_name == push2_python.constants.ENCODER_TRACK2_ENCODER:
                last_time = self.encoders_state[encoder_name].get('last_scale_turn_time', 0)
                throttle_delay = 0.05

                if now - last_time < throttle_delay:
                    return True

                self.encoders_state[encoder_name]['last_scale_turn_time'] = now

                if increment > 0:
                    self.app.melodic_mode.scaley('inc')
                elif increment < 0:
                    self.app.melodic_mode.scaley('dec')
                return True

        return True
