import definitions
import push2_python

import mido
import time


class MainControlsMode(definitions.LogicMode):
    track_triggering_button_pressing_time = None
    record_button_pressing_time = None
    play_button_pressing_time = None
    preset_selection_button_pressing_time = None
    button_quick_press_time = 0.400

    last_tap_tempo_times = []

    # BUTTONS (TOP LEFT TO BOTTOM LEFT OF PUSH2)

    tap_tempo_button = push2_python.constants.BUTTON_TAP_TEMPO
    metronome_button = push2_python.constants.BUTTON_METRONOME

    delete_button = push2_python.constants.BUTTON_DELETE
    undo_button = push2_python.constants.BUTTON_UNDO

    mute_button = push2_python.constants.BUTTON_MUTE
    solo_button = push2_python.constants.BUTTON_SOLO
    stop_button = push2_python.constants.BUTTON_STOP

    convert_button = push2_python.constants.BUTTON_CONVERT
    double_loop_button = push2_python.constants.BUTTON_DOUBLE_LOOP
    quantize_button = push2_python.constants.BUTTON_QUANTIZE

    duplicate_button = push2_python.constants.BUTTON_DUPLICATE
    new_button = push2_python.constants.BUTTON_NEW

    fixed_length_button = push2_python.constants.BUTTON_FIXED_LENGTH
    automate_button = push2_python.constants.BUTTON_AUTOMATE

    record_button = push2_python.constants.BUTTON_RECORD
    play_button = push2_python.constants.BUTTON_PLAY

    user_button = push2_python.constants.BUTTON_USER
    settings_button = push2_python.constants.BUTTON_SETUP
    scalemode_button = push2_python.constants.BUTTON_SCALE
    note_button = push2_python.constants.BUTTON_NOTE
    track_triggering_button = push2_python.constants.BUTTON_SESSION
    preset_selection_mode_button = push2_python.constants.BUTTON_ADD_DEVICE
    shift_button = push2_python.constants.BUTTON_SHIFT
    select_button = push2_python.constants.BUTTON_SELECT
    record_automation_button = push2_python.constants.BUTTON_AUTOMATE

    up_button = push2_python.constants.BUTTON_UP
    down_button = push2_python.constants.BUTTON_DOWN
    left_button = push2_python.constants.BUTTON_LEFT
    right_button = push2_python.constants.BUTTON_RIGHT

    buttons_used = [
        automate_button,
        convert_button,
        delete_button,
        double_loop_button,
        down_button,
        duplicate_button,
        fixed_length_button,
        left_button,
        # note_button,
        # mute_button,
        metronome_button,
        new_button,
        preset_selection_mode_button,
        quantize_button,
        record_automation_button,
        right_button,
        scalemode_button,
        select_button,
        settings_button,
        shift_button,
        # solo_button,
        stop_button,
        tap_tempo_button,
        # user_button,
        track_triggering_button,
        undo_button,
        up_button,
    ]

    def activate(self):
        self.app.logic_interface.get_buttons_state()
        self.update_buttons()
        self.set_buttons_to_color(self.buttons_used, definitions.OFF_BTN_COLOR)
        self.set_buttons_to_color([self.play_button], definitions.LIME)
        self.set_buttons_to_color([self.record_button], definitions.GREEN)

    def deactivate(self):
        super().deactivate()

    def update_buttons(self):
        # Shift and select button
        self.set_button_color_if_pressed(self.shift_button, animation=definitions.DEFAULT_ANIMATION)
        self.set_button_color_if_pressed(self.select_button, animation=definitions.DEFAULT_ANIMATION)

        # Note button, to toggle melodic/rhythmic mode
        self.set_button_color(self.note_button)

        # self.set_button_color(self.up_button)
        # self.set_button_color(self.down_button)
        # self.set_button_color(self.left_button)
        # self.set_button_color(self.right_button)
        self.set_button_color(self.mute_button)
        self.set_button_color(self.solo_button)

        # Button to toggle display on/off
        self.set_button_color_if_expression(self.user_button, self.app.use_push2_display)

        # Settings button, to toggle settings mode
        self.set_button_color_if_expression(self.settings_button, self.app.is_mode_active(self.app.settings_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # # Scale Mode button, to toggle scale mode
        self.set_button_color_if_expression(self.scalemode_button, self.app.is_mode_active(self.app.scalemenu_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # Preset selection mode
        self.set_button_color_if_expression(self.preset_selection_mode_button,
                                            self.app.is_mode_active(self.app.preset_selection_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # Mute button, to toggle display on/off
        if self.app.use_push2_display:
            self.push.buttons.set_button_color(self.user_button, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(self.user_button, definitions.OFF_BTN_COLOR)

    def on_button_pressed(self, button_name, shift=False, select=False, long_press=False, double_press=False):
        if button_name == self.automate_button:
            self.app.logic_interface.automate()
            return True

        elif button_name == self.note_button:
            self.app.toggle_melodic_rhythmic_slice_modes()
            self.app.pads_need_update = True
            self.app.buttons_need_update = True
            return True

        # PRESSED BUTTON_ADD_TRACK
        elif button_name == push2_python.constants.BUTTON_ADD_TRACK:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_ADD_TRACK, definitions.BLACK)
            return True

        # PRESSED metronome
        elif button_name == push2_python.constants.BUTTON_METRONOME:
            self.app.logic_interface.metronome_on_off()
            return True

        # PLAY
        #
        elif button_name == self.play_button:
            if long_press:
                if not shift:
                    self.app.logic_interface.global_pause()
                else:
                    pass
            else:
                if not shift:
                    self.app.logic_interface.global_play_stop()
                else:
                    pass
            self.app.buttons_need_update = True
            self.app.pads_need_update = True
            return True


        # RECORD
        #
        elif button_name == self.record_button:
            if long_press:
                if not shift:
                    pass
                else:
                    pass
            else:
                if not shift:
                    self.app.logic_interface.global_record()
                else:
                    pass
            self.app.buttons_need_update = True
            self.app.pads_need_update = True
            return True

        elif button_name == self.settings_button:
            self.app.toggle_and_rotate_settings_mode()
            self.app.buttons_need_update = True
            return True

        elif button_name == self.scalemode_button:
            self.app.toggle_and_rotate_scalemenu_mode()
            self.app.buttons_need_update = True
            return True

        # USER BUTTON
        elif button_name == self.user_button:
            if long_press:
                if not shift:
                    pass
                else:
                    self.app.use_push2_display = not self.app.use_push2_display
                    if not self.app.use_push2_display:
                        self.push.display.send_to_display(
                            self.push.display.prepare_frame(self.push.display.make_black_frame()))
                    self.app.buttons_need_update = True
                    return True
            else:
                if not shift:
                    pass
                else:
                    pass
            self.app.buttons_need_update = True
            self.app.pads_need_update = True
            return True

        elif button_name == self.preset_selection_mode_button:
            if self.app.is_mode_active(self.app.preset_selection_mode):
                # If already active, deactivate and set pressing time to None
                self.app.unset_preset_selection_mode()
                self.preset_selection_button_pressing_time = None
            else:
                # Activate preset selection mode and store time button pressed
                self.app.set_preset_selection_mode()
                self.preset_selection_button_pressing_time = time.time()
            self.app.buttons_need_update = True
            return True

        # PRESET SELECTION BUTTON
        elif button_name == self.preset_selection_mode_button:
            if long_press:
                if not shift:
                    pass
                else:
                    self.app.unset_preset_selection_mode()
                    return True
            else:
                if not shift:
                    pass
                else:
                    pass
            self.app.buttons_need_update = True
            self.app.pads_need_update = True
            return True

        # SOLO
        elif button_name == self.solo_button:
            if long_press:
                self.app.logic_interface.global_solo_lock()
                return True
            else:
                self.app.logic_interface.global_solo()
                return True
            self.app.buttons_need_update = True
            return True

        # SOLO
        elif button_name == self.mute_button:
            if long_press:
                self.app.logic_interface.global_mute_off()
                return True
            else:
                self.app.logic_interface.global_mute()
                return True
            self.app.buttons_need_update = True
            return True

        elif button_name == self.preset_selection_mode_button:
            if self.app.is_mode_active(self.app.preset_selection_mode):
                # If already active, deactivate and set pressing time to None
                self.app.unset_preset_selection_mode()
                self.preset_selection_button_pressing_time = None
            else:
                # Activate preset selection mode and store time button pressed
                self.app.set_preset_selection_mode()
                self.preset_selection_button_pressing_time = time.time()
            self.app.buttons_need_update = True
            return True

    def on_button_pressed_raw(self, button_name):

        if button_name == self.automate_button:
            self.push.buttons.set_button_color(self.automate_button, definitions.WHITE)
            return True

        elif button_name == self.left_button:
            self.push.buttons.set_button_color(self.left_button, definitions.WHITE)
            self.app.logic_interface.global_left()
            return True
        elif button_name == self.right_button:
            self.push.buttons.set_button_color(self.right_button, definitions.WHITE)
            self.app.logic_interface.global_right()
            return True
        elif button_name == self.up_button:
            self.push.buttons.set_button_color(self.up_button, definitions.WHITE)
            self.app.logic_interface.global_up()
            return True
        elif button_name == self.down_button:
            self.push.buttons.set_button_color(self.down_button, definitions.WHITE)
            self.app.logic_interface.global_down()
            return True

    def on_button_released_raw(self, button_name):
        self.set_buttons_to_color(self.buttons_used, definitions.OFF_BTN_COLOR)
        return True
