import definitions
import push2_python

import mido
import time


class MainControlsMode(definitions.PyshaMode):
    pyramid_track_triggering_button_pressing_time = None
    track_triggering_button_pressing_time = None
    record_button_pressing_time = None
    play_button_pressing_time = None
    preset_selection_button_pressing_time = None
    button_quick_press_time = 0.400

    last_tap_tempo_times = []

    toggle_display_button = push2_python.constants.BUTTON_USER
    settings_button = push2_python.constants.BUTTON_SETUP
    scalemode_button = push2_python.constants.BUTTON_SCALE
    melodic_rhythmic_toggle_button = push2_python.constants.BUTTON_NOTE
    pyramid_track_triggering_button = push2_python.constants.BUTTON_ADD_TRACK
    track_triggering_button = push2_python.constants.BUTTON_SESSION
    preset_selection_mode_button = push2_python.constants.BUTTON_ADD_DEVICE
    ddrm_tone_selection_mode_button = push2_python.constants.BUTTON_DEVICE
    shift_button = push2_python.constants.BUTTON_SHIFT
    select_button = push2_python.constants.BUTTON_SELECT
    play_button = push2_python.constants.BUTTON_PLAY
    record_button = push2_python.constants.BUTTON_RECORD
    metronome_button = push2_python.constants.BUTTON_METRONOME
    tap_tempo_button = push2_python.constants.BUTTON_TAP_TEMPO
    fixed_length_button = push2_python.constants.BUTTON_FIXED_LENGTH
    record_automation_button = push2_python.constants.BUTTON_AUTOMATE

    buttons_used = [toggle_display_button, settings_button, scalemode_button, melodic_rhythmic_toggle_button, track_triggering_button,
                    preset_selection_mode_button,
                    ddrm_tone_selection_mode_button, shift_button, select_button, play_button, record_button,
                    metronome_button, fixed_length_button,
                    record_automation_button]

    def activate(self):
        self.update_buttons()

    def update_buttons(self):
        # Shift and select button
        self.set_button_color_if_pressed(self.shift_button, animation=definitions.DEFAULT_ANIMATION)
        self.set_button_color_if_pressed(self.select_button, animation=definitions.DEFAULT_ANIMATION)

        # Note button, to toggle melodic/rhythmic mode
        self.set_button_color(self.melodic_rhythmic_toggle_button)

        # Button to toggle display on/off
        self.set_button_color_if_expression(self.toggle_display_button, self.app.use_push2_display)

        # Settings button, to toggle settings mode
        self.set_button_color_if_expression(self.settings_button, self.app.is_mode_active(self.app.settings_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # # Scale Mode button, to toggle scale mode
        self.set_button_color_if_expression(self.scalemode_button, self.app.is_mode_active(self.app.scalemenu_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # # Track triggering mode
        # self.set_button_color_if_expression(self.pyramid_track_triggering_button,
        #                                     self.app.is_mode_active(self.app.pyramid_track_triggering_mode),
        #                                     animation=definitions.DEFAULT_ANIMATION)
        # Preset selection mode
        self.set_button_color_if_expression(self.preset_selection_mode_button,
                                            self.app.is_mode_active(self.app.preset_selection_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # Mute button, to toggle display on/off
        if self.app.use_push2_display:
            self.push.buttons.set_button_color(self.toggle_display_button, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(self.toggle_display_button, definitions.OFF_BTN_COLOR)

        # DDRM tone selector mode
        if self.app.ddrm_tone_selector_mode.should_be_enabled():
            self.set_button_color_if_expression(self.ddrm_tone_selection_mode_button,
                                                self.app.is_mode_active(self.app.ddrm_tone_selector_mode),
                                                animation=definitions.DEFAULT_ANIMATION)
        else:
            self.set_button_color(self.ddrm_tone_selection_mode_button, definitions.BLACK)

    def on_button_pressed(self, button_name, shift=False, select=False, long_press=False, double_press=False):
        if button_name == self.melodic_rhythmic_toggle_button:
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
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME, definitions.BLACK)
            return True

        # PRESSED button play
        elif button_name == push2_python.constants.BUTTON_PLAY:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.BLACK)
            self.play_button_pressing_time = time.time()
            return True

        # PRESSED button record
        elif button_name == push2_python.constants.BUTTON_RECORD:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.BLACK)
            return True

        elif button_name == self.settings_button:
            self.app.toggle_and_rotate_settings_mode()
            self.app.buttons_need_update = True
            return True

        elif button_name == self.scalemode_button:
            self.app.toggle_and_rotate_scalemenu_mode()
            self.app.buttons_need_update = True
            return True

        elif button_name == self.toggle_display_button:
            self.app.use_push2_display = not self.app.use_push2_display
            if not self.app.use_push2_display:
                self.push.display.send_to_display(self.push.display.prepare_frame(self.push.display.make_black_frame()))
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
        elif button_name == self.ddrm_tone_selection_mode_button:
            if self.app.ddrm_tone_selector_mode.should_be_enabled():
                self.app.toggle_ddrm_tone_selector_mode()
                self.app.buttons_need_update = True
            return True

    def on_button_released_raw(self, button_name):
        if button_name == self.pyramid_track_triggering_button:
            # Decide if short press or long press
            pressing_time = self.pyramid_track_triggering_button_pressing_time
            is_long_press = False
            if pressing_time is None:
                # Consider quick press (this should not happen pressing time should have been set before)
                pass
            else:
                if time.time() - pressing_time > self.button_quick_press_time:
                    # Consider this is a long press
                    is_long_press = True
                self.pyramid_track_triggering_button_pressing_time = None

            if is_long_press:
                # If long press, deactivate track triggering mode, else do nothing
                self.app.unset_pyramid_track_triggering_mode()
                self.app.buttons_need_update = True

            return True

        # RELEASED metronome
        elif button_name == push2_python.constants.BUTTON_METRONOME:
            self.app.shepherd_interface.metronome_on_off()

            return True

        # RELEASED button play
        elif button_name == push2_python.constants.BUTTON_PLAY:
            pressing_time = self.play_button_pressing_time
            is_long_press = False
            if pressing_time is None:
                # Consider quick press (this should not happen pressing time should have been set before)
                pass
            else:
                if time.time() - pressing_time > self.button_quick_press_time:
                    # Consider this is a long press
                    is_long_press = True
                self.play_button_pressing_time = None
                self.app.shepherd_interface.global_play_stop()
            if is_long_press:
                self.app.shepherd_interface.global_pause()
                # self.app.buttons_need_update = True

            return True

        # RELEASED button record
        elif button_name == push2_python.constants.BUTTON_RECORD:
            self.app.shepherd_interface.global_record()

            return True

        elif button_name == self.preset_selection_mode_button:
            # Decide if short press or long press
            pressing_time = self.preset_selection_button_pressing_time
            is_long_press = False
            if pressing_time is None:
                # Consider quick press (this should not happen pressing time should have been set before)
                pass
            else:
                if time.time() - pressing_time > self.button_quick_press_time:
                    # Consider this is a long press
                    is_long_press = True
                self.preset_selection_button_pressing_time = None

            if is_long_press:
                # If long press, deactivate preset selection mode, else do nothing
                self.app.unset_preset_selection_mode()
                self.app.buttons_need_update = True

            return True
