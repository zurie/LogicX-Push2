import time

import definitions
import push2_python.constants

from settings_mode import SettingsMode
from display_utils import show_title, show_value, draw_text_at, show_bigvalue


class ScaleMenuMode(SettingsMode):
    current_page = 0
    n_pages = 1

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
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_7, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_8, definitions.BLACK)

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

        if self.current_page == 0:  # Performance settings
            if button_name == push2_python.constants.BUTTON_UPPER_ROW_1:
                self.app.melodic_mode.set_root_midi_note(self.app.melodic_mode.root_midi_note + 1)
                self.app.pads_need_update = True
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_2:
                self.app.melodic_mode.toggle_scale()
                return True

    def update_display(self, ctx, w, h):

        # Divide display in 8 parts to show different settings
        part_w = w // 2
        part_h = h

        # Draw labels and values
        for i in range(0, 2):
            part_x = i * w // 8
            part_y = 0

            ctx.set_source_rgb(0, 0, 0)  # Draw black background
            ctx.rectangle(part_x - 3, part_y, w, h)  # do x -3 to add some margin between parts
            ctx.fill()

            color = [1.0, 1.0, 1.0]

            if self.current_page == 0:  # Performance settings
                if i == 0:  # Root note
                    if not self.app.is_mode_active(self.app.melodic_mode):
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DISABLED)
                    show_title(ctx, part_x, h, 'ROOT NOTE')
                    show_value(ctx, part_x, h, "{0} ({1})".format(self.app.melodic_mode.note_number_to_name(
                        self.app.melodic_mode.root_midi_note), self.app.melodic_mode.root_midi_note), color)

                elif i == 1:  # SCALE
                    show_title(ctx, part_x, h, 'SCALE')
                    show_bigvalue(ctx, part_x, h, definitions.SCALE_NAME, color)

        # After drawing all labels and values, draw other stuff if required
        if self.current_page == 0:  # Performance settings

            current_time = time.time()
            if current_time - self.app.melodic_mode.latest_channel_at_value[
                0] < 3 and not self.app.melodic_mode.use_poly_at:
                # Lastest channel AT value received less than 3 seconds ago
                draw_text_at(ctx, 3, part_h - 3, f'Latest cAT: {self.app.melodic_mode.latest_channel_at_value[1]}',
                             font_size=20)
            if current_time - self.app.melodic_mode.latest_poly_at_value[0] < 3 and self.app.melodic_mode.use_poly_at:
                # Lastest channel AT value received less than 3 seconds ago
                draw_text_at(ctx, 3, part_h - 3, f'Latest pAT: {self.app.melodic_mode.latest_poly_at_value[1]}',
                             font_size=20)
            if current_time - self.app.melodic_mode.latest_velocity_value[0] < 3:
                # Lastest note on velocity value received less than 3 seconds ago
                draw_text_at(ctx, 3, part_h - 26, f'Latest velocity: {self.app.melodic_mode.latest_velocity_value[1]}',
                             font_size=20)

    def on_encoder_rotated(self, encoder_name, increment):

        self.encoders_state[encoder_name]['last_message_received'] = time.time()

        if self.current_page == 0:  # Performance settings
            if encoder_name == push2_python.constants.ENCODER_TRACK1_ENCODER:
                self.app.melodic_mode.set_root_midi_note(self.app.melodic_mode.root_midi_note + increment)
                self.app.pads_need_update = True  # Using async update method because we don't really need immediate response here

            elif encoder_name == push2_python.constants.ENCODER_TRACK2_ENCODER:
                if increment >= 1:  # Only respond to "big" increments
                    self.app.melodic_mode.toggle_scale()
                elif increment <= -1:
                    self.app.melodic_mode.toggle_scale()

        return True  # Always return True because encoder should not be used in any other mode if this is first active
