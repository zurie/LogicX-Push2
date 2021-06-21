import definitions
import push2_python.constants
import time
import os
import sys
import psutil
import threading
import subprocess

from display_utils import show_title, show_value, draw_text_at


class SettingsMode(definitions.PyshaMode):

    # Pad settings
    # - Root note
    # - Aftertouch mode
    # - Velocity curve
    # - Channel aftertouch range

    # MIDI settings
    # - Midi device IN
    # - Midi channel IN
    # - Midi device OUT
    # - Midi channel OUT
    # - Pyramidi channel
    # - Notes Midi
    # - Rerun MIDI initial configuration

    # About panel
    # - definitions.VERSION info
    # - Save current settings
    #  - FPS

    current_page = 0
    n_pages = 3
    encoders_state = {}
    is_running_sw_update = False

    def move_to_next_page(self):
        self.app.buttons_need_update = True
        self.current_page += 1
        if self.current_page >= self.n_pages:
            self.current_page = 0
            return True  # Return true because page rotation finished 
        return False

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

    def check_for_delayed_actions(self):
        current_time = time.time()
        
        if self.app.midi_in_tmp_device_idx is not None:
            # Means we are in the process of changing the MIDI in device
            if current_time - self.encoders_state[push2_python.constants.ENCODER_TRACK1_ENCODER]['last_message_received'] > definitions.DELAYED_ACTIONS_APPLY_TIME:
                self.app.set_midi_in_device_by_index(self.app.midi_in_tmp_device_idx)
                self.app.midi_in_tmp_device_idx = None
        
        if self.app.midi_out_tmp_device_idx is not None:
            # Means we are in the process of changing the MIDI out device
            if current_time - self.encoders_state[push2_python.constants.ENCODER_TRACK3_ENCODER]['last_message_received'] > definitions.DELAYED_ACTIONS_APPLY_TIME:
                self.app.set_midi_out_device_by_index(self.app.midi_out_tmp_device_idx)
                self.app.midi_out_tmp_device_idx = None

        if self.app.notes_midi_in_tmp_device_idx is not None:
            # Means we are in the process of changing the notes MIDI in device
            if current_time - self.encoders_state[push2_python.constants.ENCODER_TRACK6_ENCODER]['last_message_received'] > definitions.DELAYED_ACTIONS_APPLY_TIME:
                self.app.set_notes_midi_in_device_by_index(self.app.notes_midi_in_tmp_device_idx)
                self.app.notes_midi_in_tmp_device_idx = None

    def set_all_upper_row_buttons_off(self):
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_1, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_2, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_3, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_4, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_5, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_6, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_7, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_8, definitions.OFF_BTN_COLOR)

    def update_buttons(self):
        if self.current_page == 0:  # Performance settings
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_1, definitions.WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_2, definitions.WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_3, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_4, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_5, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_6, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_7, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_8, definitions.OFF_BTN_COLOR)

        elif self.current_page == 1: # MIDI settings
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_1, definitions.WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_2, definitions.WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_3, definitions.WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_4, definitions.WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_5, definitions.WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_6, definitions.WHITE)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_7, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_7, definitions.GREEN, animation=definitions.DEFAULT_ANIMATION)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_8, definitions.OFF_BTN_COLOR)
            
        elif self.current_page == 2:  # About
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_1, definitions.GREEN)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_2, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_3, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_3, definitions.RED, animation=definitions.DEFAULT_ANIMATION)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_4, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_5, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_6, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_7, definitions.OFF_BTN_COLOR)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_UPPER_ROW_8, definitions.OFF_BTN_COLOR)
        
    def update_display(self, ctx, w, h):

        # Divide display in 8 parts to show different settings
        part_w = w // 8
        part_h = h

        # Draw labels and values
        for i in range(0, 8):
            part_x = i * part_w
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

                elif i == 1:  # Poly AT/channel AT
                    show_title(ctx, part_x, h, 'AFTERTOUCH')
                    show_value(ctx, part_x, h, 'polyAT' if self.app.melodic_mode.use_poly_at else 'channel', color)

                elif i == 2:  # Channel AT range start
                    if self.app.melodic_mode.last_time_at_params_edited is not None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DELAYED_ACTIONS)
                    show_title(ctx, part_x, h, 'cAT START')
                    show_value(ctx, part_x, h, self.app.melodic_mode.channel_at_range_start, color)

                elif i == 3:  # Channel AT range end
                    if self.app.melodic_mode.last_time_at_params_edited is not None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DELAYED_ACTIONS)
                    show_title(ctx, part_x, h, 'cAT END')
                    show_value(ctx, part_x, h, self.app.melodic_mode.channel_at_range_end, color)

                elif i == 4:  # Poly AT range
                    if self.app.melodic_mode.last_time_at_params_edited is not None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DELAYED_ACTIONS)
                    show_title(ctx, part_x, h, 'pAT RANGE')
                    show_value(ctx, part_x, h, self.app.melodic_mode.poly_at_max_range, color)

                elif i == 5:  # Poly AT curve
                    if self.app.melodic_mode.last_time_at_params_edited is not None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DELAYED_ACTIONS)
                    show_title(ctx, part_x, h, 'pAT CURVE')
                    show_value(ctx, part_x, h, self.app.melodic_mode.poly_at_curve_bending, color)

            elif self.current_page == 1:  # MIDI settings
                if i == 0:  # MIDI in device
                    if self.app.midi_in_tmp_device_idx is not None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DELAYED_ACTIONS)
                        if self.app.midi_in_tmp_device_idx < 0:
                            name = "None"
                        else:
                            name = "{0} {1}".format(self.app.midi_in_tmp_device_idx + 1, self.app.available_midi_in_device_names[self.app.midi_in_tmp_device_idx])
                    else:
                        if self.app.midi_in is not None:
                            name = "{0} {1}".format(self.app.available_midi_in_device_names.index(self.app.midi_in.name) + 1, self.app.midi_in.name)
                        else:
                            color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DISABLED)
                            name = "None"
                    show_title(ctx, part_x, h, 'IN DEVICE')
                    show_value(ctx, part_x, h, name, color)

                elif i == 1:  # MIDI in channel
                    if self.app.midi_in is None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DISABLED)
                    show_title(ctx, part_x, h, 'IN CH')
                    show_value(ctx, part_x, h, self.app.midi_in_channel + 1 if self.app.midi_in_channel > -1 else "All", color)

                elif i == 2:  # MIDI out device
                    if self.app.midi_out_tmp_device_idx is not None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DELAYED_ACTIONS)
                        if self.app.midi_out_tmp_device_idx < 0:
                            name = "None"
                        else:
                            name = "{0} {1}".format(self.app.midi_out_tmp_device_idx + 1, self.app.available_midi_out_device_names[self.app.midi_out_tmp_device_idx])
                    else:
                        if self.app.midi_out is not None:
                            name = "{0} {1}".format(self.app.available_midi_out_device_names.index(self.app.midi_out.name) + 1, self.app.midi_out.name)
                        else:
                            color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DISABLED)
                            name = "None"
                    show_title(ctx, part_x, h, 'OUT DEVICE')
                    show_value(ctx, part_x, h, name, color)

                elif i == 3:  # MIDI out channel
                    if self.app.midi_out is None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DISABLED)
                    show_title(ctx, part_x, h, 'OUT CH')
                    show_value(ctx, part_x, h, self.app.midi_out_channel + 1 if self.app.midi_out_channel >= 0 else 'TR', color)

                elif i == 4:  # Pyramidi out channel
                    show_title(ctx, part_x, h, 'PYRAMIDI CH')
                    show_value(ctx, part_x, h, self.app.track_selection_mode.pyramidi_channel + 1, color)
                
                elif i == 5:  # Notes MIDI in device
                    if self.app.notes_midi_in_tmp_device_idx is not None:
                        color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DELAYED_ACTIONS)
                        if self.app.notes_midi_in_tmp_device_idx < 0:
                            name = "None"
                        else:
                            name = "{0} {1}".format(self.app.notes_midi_in_tmp_device_idx + 1, self.app.available_midi_in_device_names[self.app.notes_midi_in_tmp_device_idx])
                    else:
                        if self.app.notes_midi_in is not None:
                            name = "{0} {1}".format(self.app.available_midi_in_device_names.index(self.app.notes_midi_in.name) + 1, self.app.notes_midi_in.name)
                        else:
                            color = definitions.get_color_rgb_float(definitions.FONT_COLOR_DISABLED)
                            name = "None"
                    show_title(ctx, part_x, h, 'NOTES IN')
                    show_value(ctx, part_x, h, name, color)

                elif i == 6:  # Re-send MIDI connection established (to push, not MIDI in/out device)
                    show_title(ctx, part_x, h, 'RESET MIDI')

            elif self.current_page == 2:  # About
                if i == 0:  # Save button
                    show_title(ctx, part_x, h, 'SAVE')

                elif i ==1: # definitions.VERSION info
                    show_title(ctx, part_x, h, 'VERSION')
                    show_value(ctx, part_x, h, 'Pysha ' + definitions.VERSION, color)

                elif i == 2:  # Software update
                    show_title(ctx, part_x, h, 'SW UPDATE')
                    if self.is_running_sw_update:
                        show_value(ctx, part_x, h, 'Running... ', color)
                
                elif i == 3:  # FPS indicator
                    show_title(ctx, part_x, h, 'FPS')
                    show_value(ctx, part_x, h, self.app.actual_frame_rate, color)

        # After drawing all labels and values, draw other stuff if required
        if self.current_page == 0:  # Performance settings

            # Draw polyAT velocity curve
            ctx.set_source_rgb(0.6, 0.6, 0.6)
            ctx.set_line_width(1)
            data = self.app.melodic_mode.get_poly_at_curve()
            n = len(data)
            curve_x = 4 * part_w + 3  # Start x point of curve
            curve_y = part_h - 10  # Start y point of curve
            curve_height = 50
            curve_length = part_w * 4 - 6
            ctx.move_to(curve_x, curve_y)
            for i, value in enumerate(data):
                x = curve_x + i * curve_length/n
                y = curve_y - curve_height * value/127
                ctx.line_to(x, y)
            ctx.line_to(x, curve_y)
            ctx.fill()

            current_time = time.time()
            if current_time - self.app.melodic_mode.latest_channel_at_value[0] < 3 and not self.app.melodic_mode.use_poly_at:
                # Lastest channel AT value received less than 3 seconds ago
                draw_text_at(ctx, 3, part_h - 3, f'Latest cAT: {self.app.melodic_mode.latest_channel_at_value[1]}', font_size=20)
            if current_time - self.app.melodic_mode.latest_poly_at_value[0] < 3 and self.app.melodic_mode.use_poly_at:
                # Lastest channel AT value received less than 3 seconds ago
                draw_text_at(ctx, 3, part_h - 3, f'Latest pAT: {self.app.melodic_mode.latest_poly_at_value[1]}', font_size=20)
            if current_time - self.app.melodic_mode.latest_velocity_value[0] < 3:
                # Lastest note on velocity value received less than 3 seconds ago
                draw_text_at(ctx, 3, part_h - 26, f'Latest velocity: {self.app.melodic_mode.latest_velocity_value[1]}', font_size=20)


    def on_encoder_rotated(self, encoder_name, increment):

        self.encoders_state[encoder_name]['last_message_received'] = time.time()

        if self.current_page == 0:  # Performance settings
            if encoder_name == push2_python.constants.ENCODER_TRACK1_ENCODER:
                self.app.melodic_mode.set_root_midi_note(self.app.melodic_mode.root_midi_note + increment)
                self.app.pads_need_update = True  # Using async update method because we don't really need immediate response here

            elif encoder_name == push2_python.constants.ENCODER_TRACK2_ENCODER:
                if increment >= 3:  # Only respond to "big" increments
                    if not self.app.melodic_mode.use_poly_at:
                        self.app.melodic_mode.use_poly_at = True
                        self.app.push.pads.set_polyphonic_aftertouch()
                elif increment <= -3:
                    if self.app.melodic_mode.use_poly_at:
                        self.app.melodic_mode.use_poly_at = False
                        self.app.push.pads.set_channel_aftertouch()
                self.app.melodic_mode.set_lumi_pressure_mode()

            elif encoder_name == push2_python.constants.ENCODER_TRACK3_ENCODER:
                self.app.melodic_mode.set_channel_at_range_start(self.app.melodic_mode.channel_at_range_start + increment)

            elif encoder_name == push2_python.constants.ENCODER_TRACK4_ENCODER:
                self.app.melodic_mode.set_channel_at_range_end(self.app.melodic_mode.channel_at_range_end + increment)
                
            elif encoder_name == push2_python.constants.ENCODER_TRACK5_ENCODER:
                self.app.melodic_mode.set_poly_at_max_range(self.app.melodic_mode.poly_at_max_range + increment)

            elif encoder_name == push2_python.constants.ENCODER_TRACK6_ENCODER:
                self.app.melodic_mode.set_poly_at_curve_bending(self.app.melodic_mode.poly_at_curve_bending + increment)

        elif self.current_page == 1:  # MIDI settings
            if encoder_name == push2_python.constants.ENCODER_TRACK1_ENCODER:
                if self.app.midi_in_tmp_device_idx is None:
                    if self.app.midi_in is not None:
                        self.app.midi_in_tmp_device_idx = self.app.available_midi_in_device_names.index(self.app.midi_in.name)
                    else:
                        self.app.midi_in_tmp_device_idx = -1
                self.app.midi_in_tmp_device_idx += increment
                if self.app.midi_in_tmp_device_idx >= len(self.app.available_midi_in_device_names):
                    self.app.midi_in_tmp_device_idx = len(self.app.available_midi_in_device_names) - 1
                elif self.app.midi_in_tmp_device_idx < -1:
                    self.app.midi_in_tmp_device_idx = -1  # Will use -1 for "None"

            elif encoder_name == push2_python.constants.ENCODER_TRACK2_ENCODER:
                self.app.set_midi_in_channel(self.app.midi_in_channel + increment, wrap=False)

            elif encoder_name == push2_python.constants.ENCODER_TRACK3_ENCODER:
                if self.app.midi_out_tmp_device_idx is None:
                    if self.app.midi_out is not None:
                        self.app.midi_out_tmp_device_idx = self.app.available_midi_out_device_names.index(self.app.midi_out.name)
                    else:
                        self.app.midi_out_tmp_device_idx = -1
                self.app.midi_out_tmp_device_idx += increment
                if self.app.midi_out_tmp_device_idx >= len(self.app.available_midi_out_device_names):
                    self.app.midi_out_tmp_device_idx = len(self.app.available_midi_out_device_names) - 1
                elif self.app.midi_out_tmp_device_idx < -1:
                    self.app.midi_out_tmp_device_idx = -1  # Will use -1 for "None"

            elif encoder_name == push2_python.constants.ENCODER_TRACK4_ENCODER:
                self.app.set_midi_out_channel(self.app.midi_out_channel + increment, wrap=False)

            elif encoder_name == push2_python.constants.ENCODER_TRACK5_ENCODER:
                self.app.track_selection_mode.set_pyramidi_channel(self.app.track_selection_mode.pyramidi_channel + increment, wrap=False)

            elif encoder_name == push2_python.constants.ENCODER_TRACK6_ENCODER:
                if self.app.notes_midi_in_tmp_device_idx is None:
                    if self.app.notes_midi_in is not None:
                        self.app.notes_midi_in_tmp_device_idx = self.app.available_midi_in_device_names.index(self.app.notes_midi_in.name)
                    else:
                        self.app.notes_midi_in_tmp_device_idx = -1
                self.app.notes_midi_in_tmp_device_idx += increment
                if self.app.notes_midi_in_tmp_device_idx >= len(self.app.available_midi_in_device_names):
                    self.app.notes_midi_in_tmp_device_idx = len(self.app.available_midi_in_device_names) - 1
                elif self.app.notes_midi_in_tmp_device_idx < -1:
                    self.app.notes_midi_in_tmp_device_idx = -1  # Will use -1 for "None"

        elif self.current_page == 2:  # About
            pass

        return True  # Always return True because encoder should not be used in any other mode if this is first active

    def on_button_pressed(self, button_name):

        if self.current_page == 0:  # Performance settings
            if button_name == push2_python.constants.BUTTON_UPPER_ROW_1:
                self.app.melodic_mode.set_root_midi_note(self.app.melodic_mode.root_midi_note + 1)
                self.app.pads_need_update = True
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_2:
                self.app.melodic_mode.use_poly_at = not self.app.melodic_mode.use_poly_at
                if self.app.melodic_mode.use_poly_at:
                    self.app.push.pads.set_polyphonic_aftertouch()
                else:
                    self.app.push.pads.set_channel_aftertouch()
                self.app.melodic_mode.set_lumi_pressure_mode()
                return True

        elif self.current_page == 1:  # MIDI settings
            if button_name == push2_python.constants.BUTTON_UPPER_ROW_1:
                if self.app.midi_in_tmp_device_idx is None:
                    if self.app.midi_in is not None:
                        self.app.midi_in_tmp_device_idx = self.app.available_midi_in_device_names.index(self.app.midi_in.name)
                    else:
                        self.app.midi_in_tmp_device_idx = -1
                self.app.midi_in_tmp_device_idx += 1
                # Make index position wrap
                if self.app.midi_in_tmp_device_idx >= len(self.app.available_midi_in_device_names):
                    self.app.midi_in_tmp_device_idx = -1  # Will use -1 for "None"
                elif self.app.midi_in_tmp_device_idx < -1:
                    self.app.midi_in_tmp_device_idx = len(self.app.available_midi_in_device_names) - 1
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_2:
                self.app.set_midi_in_channel(self.app.midi_in_channel + 1, wrap=True)
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_3:
                if self.app.midi_out_tmp_device_idx is None:
                    if self.app.midi_out is not None:
                        self.app.midi_out_tmp_device_idx = self.app.available_midi_out_device_names.index(self.app.midi_out.name)
                    else:
                        self.app.midi_out_tmp_device_idx = -1
                self.app.midi_out_tmp_device_idx += 1
                # Make index position wrap
                if self.app.midi_out_tmp_device_idx >= len(self.app.available_midi_out_device_names):
                    self.app.midi_out_tmp_device_idx = -1  # Will use -1 for "None"
                elif self.app.midi_out_tmp_device_idx < -1:
                    self.app.midi_out_tmp_device_idx = len(self.app.available_midi_out_device_names) - 1
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_4:
                self.app.set_midi_out_channel(self.app.midi_out_channel + 1, wrap=True)
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_5:
                self.app.track_selection_mode.set_pyramidi_channel(self.app.track_selection_mode.pyramidi_channel + 1, wrap=False)
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_6:
                if self.app.notes_midi_in_tmp_device_idx is None:
                    if self.app.notes_midi_in is not None:
                        self.app.notes_midi_in_tmp_device_idx = self.app.available_midi_in_device_names.index(self.app.notes_midi_in.name)
                    else:
                        self.app.notes_midi_in_tmp_device_idx = -1
                self.app.notes_midi_in_tmp_device_idx += 1
                # Make index position wrap
                if self.app.notes_midi_in_tmp_device_idx >= len(self.app.available_midi_in_device_names):
                    self.app.notes_midi_in_tmp_device_idx = -1  # Will use -1 for "None"
                elif self.app.notes_midi_in_tmp_device_idx < -1:
                    self.app.notes_midi_in_tmp_device_idx = len(self.app.available_midi_in_device_names) - 1
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_7:
                self.app.on_midi_push_connection_established()
                return True

        elif self.current_page == 2:  # About
            if button_name == push2_python.constants.BUTTON_UPPER_ROW_1:
                # Save current settings
                self.app.save_current_settings_to_file()
                return True

            elif button_name == push2_python.constants.BUTTON_UPPER_ROW_3:
                # Run software update code
                self.is_running_sw_update = True
                run_sw_update()
                return True


def restart_program():
    """Restarts the current program, with file objects and descriptors cleanup
       Source: https://stackoverflow.com/questions/11329917/restart-python-script-from-within-itself
    """
    try:
        p = psutil.Process(os.getpid())
        for handler in p.get_open_files() + p.connections():
            os.close(handler.fd)
    except Exception as e:
        print(e)
    python = sys.executable
    os.execl(python, python, *sys.argv)


def run_sw_update():
    """Runs "git pull" in the current directory to retrieve latest code, then restart process"""
    print('Running SW update...')
    print('- installing dependencies')
    os.system('pip3 install -r requirements.txt --no-cache')
    print('- pulling from repository')
    os.system('git pull')
    print('- restarting process')
    restart_program()
