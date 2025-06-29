import definitions
import push2_python
import time


class MainControlsMode(definitions.LogicMode):
    preset_selection_button_pressing_time = None

    last_tap_tempo_times = []

    # BUTTONS (TOP RIGHT TO BOTTOM RIGHT OF PUSH2)
    add_track_button = push2_python.constants.BUTTON_ADD_TRACK
    device_button = push2_python.constants.BUTTON_DEVICE
    mix_button = push2_python.constants.BUTTON_MIX
    browse_button = push2_python.constants.BUTTON_BROWSE
    clip_button = push2_python.constants.BUTTON_CLIP
    repeat_button = push2_python.constants.BUTTON_REPEAT
    layout_button = push2_python.constants.BUTTON_LAYOUT
    session_button = push2_python.constants.BUTTON_SESSION
    # BUTTONS (TOP LEFT TO BOTTOM LEFT OF PUSH2)

    tap_tempo_button = push2_python.constants.BUTTON_TAP_TEMPO
    metronome_button = push2_python.constants.BUTTON_METRONOME

    delete_button = push2_python.constants.BUTTON_DELETE
    undo_button = push2_python.constants.BUTTON_UNDO

    mute_button = push2_python.constants.BUTTON_MUTE
    solo_button = push2_python.constants.BUTTON_SOLO
    stop_clip_button = push2_python.constants.BUTTON_STOP

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

    arrow_buttons = [
        push2_python.constants.BUTTON_UP,
        push2_python.constants.BUTTON_DOWN,
        push2_python.constants.BUTTON_LEFT,
        push2_python.constants.BUTTON_RIGHT
    ]
    up_button = push2_python.constants.BUTTON_UP
    down_button = push2_python.constants.BUTTON_DOWN
    left_button = push2_python.constants.BUTTON_LEFT
    right_button = push2_python.constants.BUTTON_RIGHT

    quantize_buttons = [
        push2_python.constants.BUTTON_1_32T,
        push2_python.constants.BUTTON_1_32,
        push2_python.constants.BUTTON_1_16T,
        push2_python.constants.BUTTON_1_16,
        push2_python.constants.BUTTON_1_8T,
        push2_python.constants.BUTTON_1_8,
        push2_python.constants.BUTTON_1_4T,
        push2_python.constants.BUTTON_1_4
    ]
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
                       mute_button,
                       metronome_button,
                       new_button,
                       preset_selection_mode_button,
                       quantize_button,
                       record_automation_button,
                       right_button,
                       # scalemode_button,
                       select_button,
                       settings_button,
                       shift_button,
                       solo_button,
                       stop_clip_button,
                       tap_tempo_button,
                       user_button,
                       track_triggering_button,
                       undo_button,
                       up_button,
                       add_track_button,
                       device_button,
                       mix_button,
                       browse_button,
                       clip_button,
                       repeat_button,
                       layout_button,
                       session_button

                   ] + quantize_buttons

    def activate(self):
        self.app.logic_interface.get_buttons_state()
        self.update_buttons()
        self.set_buttons_to_color(self.buttons_used, definitions.OFF_BTN_COLOR)
        self.set_buttons_to_color([self.record_button], definitions.GREEN)

    def deactivate(self):
        super().deactivate()

    def update_buttons(self):
        # Shift and select button
        self.set_button_color_if_pressed(self.shift_button, animation=definitions.DEFAULT_ANIMATION)
        self.set_button_color_if_pressed(self.select_button, animation=definitions.DEFAULT_ANIMATION)
        self.set_button_color_if_pressed(self.quantize_button, animation=definitions.DEFAULT_ANIMATION)
        self.set_button_color_if_pressed(self.double_loop_button, animation=definitions.DEFAULT_ANIMATION)

        # Note button, to toggle melodic/rhythmic mode
        self.set_button_color(self.note_button)
        #
        # # Button to toggle display on/off
        # self.set_button_color_if_expression(self.user_button, self.app.use_push2_display)

        # User button, to toggle HELP mode
        self.set_button_color_if_expression(self.user_button, self.app.is_mode_active(self.app.help_mode),
                                            animation=definitions.DEFAULT_ANIMATION)
        # Settings button, to toggle settings mode
        self.set_button_color_if_expression(self.settings_button, self.app.is_mode_active(self.app.settings_mode),
                                            animation=definitions.DEFAULT_ANIMATION)
        # # REPEAT Mode button, to toggle repeat
        self.set_button_color_if_expression(self.repeat_button, self.app.is_mode_active(self.app.repeat_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # Preset selection mode
        # # Scale Mode button, to toggle scale mode
        self.set_button_color_if_expression(self.scalemode_button, self.app.is_mode_active(self.app.scalemenu_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # Preset selection mode
        self.set_button_color_if_expression(self.preset_selection_mode_button,
                                            self.app.is_mode_active(self.app.preset_selection_mode),
                                            animation=definitions.DEFAULT_ANIMATION)

        # # user button, to toggle display on/off
        # if self.app.use_push2_display:
        #     self.push.buttons.set_button_color(self.user_button, definitions.OFF_BTN_COLOR)
        # else:
        #     self.push.buttons.set_button_color(self.user_button, definitions.WHITE)

    def on_button_pressed(self, button_name, loop=False, quantize=False, shift=False, select=False, long_press=False,
                          double_press=False):
        if button_name == self.user_button:
            self.app.toggle_and_rotate_help_mode()
            self.app.buttons_need_update = True
            return True

        if not self.app.is_mode_active(self.app.help_mode):

            if button_name == self.automate_button:
                self.app.logic_interface.automate()
                return True

            elif button_name == self.duplicate_button:
                self.app.logic_interface.duplicate()
                return True

            elif button_name == self.double_loop_button:
                self.app.logic_interface.double()
                return True
            elif button_name == self.convert_button:
                self.app.logic_interface.convert()
                return True

            elif button_name == self.fixed_length_button:
                self.app.logic_interface.fixed_length()
                return True

            elif button_name == self.new_button:
                if long_press:
                    self.app.logic_interface.new_next()
                else:
                    self.app.logic_interface.new()
                return True

            elif button_name == self.delete_button:
                if long_press:
                    self.app.logic_interface.delete()
                else:
                    self.app.logic_interface.delete()
                return True

            elif button_name == self.undo_button:
                if long_press:
                    self.app.logic_interface.redo()
                else:
                    self.app.logic_interface.undo()
                return True

            elif button_name == self.note_button:
                self.app.toggle_melodic_rhythmic_slice_modes()
                self.app.pads_need_update = True
                self.app.buttons_need_update = True
                return True

            # PRESSED BUTTON_MASTER
            elif button_name == push2_python.constants.BUTTON_MASTER:
                self.push.buttons.set_button_color(push2_python.constants.BUTTON_MASTER, definitions.BLACK)
                return True

            # PRESSED metronome
            elif button_name == push2_python.constants.BUTTON_METRONOME:
                self.app.logic_interface.metronome_on_off()
                return True

            # PLAY
            #
            elif button_name == self.play_button:
                if long_press:
                    # self.app.logic_interface.stop()
                    if not shift:
                        self.app.logic_interface.pause()
                    else:
                        self.app.logic_interface.stop()
                        pass
                else:
                    if not shift:
                        self.app.logic_interface.play()
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
                        self.app.logic_interface.record()
                    else:
                        pass
                self.app.buttons_need_update = True
                self.app.pads_need_update = True
                return True

            elif button_name == self.settings_button:
                self.app.toggle_and_rotate_settings_mode()
                self.app.buttons_need_update = True
                return True

            elif button_name == self.repeat_button:
                self.app.toggle_and_rotate_repeat_mode()
                self.app.buttons_need_update = True
                return True

            elif button_name == self.scalemode_button:
                self.app.toggle_and_rotate_scalemenu_mode()
                self.app.buttons_need_update = True
                return True

            # # USER BUTTON
            # elif button_name == self.user_button:
            #     if long_press:
            #         if not shift:
            #             pass
            #         else:
            #             self.app.use_push2_display = not self.app.use_push2_display
            #             if not self.app.use_push2_display:
            #                 self.push.display.send_to_display(
            #                     self.push.display.prepare_frame(self.push.display.make_black_frame()))
            #             self.app.buttons_need_update = True
            #             return True
            #     else:
            #         if not shift:
            #             pass
            #         else:
            #             pass
            #     self.app.buttons_need_update = True
            #     self.app.pads_need_update = True
            #     return True

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
                else:
                    if not shift:
                        pass
                    else:
                        pass
                self.app.buttons_need_update = True
                self.app.pads_need_update = True
                return True

            elif button_name == self.stop_clip_button:
                self.app.logic_interface.stop_clip()
                return True
            elif button_name == self.device_button:
                self.app.logic_interface.device()
                return True
            elif button_name == self.mix_button:
                self.app.logic_interface.mix()
                return True
            elif button_name == self.browse_button:
                self.app.logic_interface.browse()
                return True
            elif button_name == self.add_track_button:
                self.app.logic_interface.add_track()
                return True
            elif button_name == self.clip_button:
                self.app.logic_interface.clip()
                return True
            elif button_name == self.repeat_button:
                if long_press:
                    self.app.logic_interface.repeat_off()
                else:
                    self.app.logic_interface.repeat()
                return True
            elif button_name == self.layout_button:
                self.app.logic_interface.layout()
                return True
            elif button_name == self.session_button:
                self.app.logic_interface.session()
                return True

            # SOLO
            elif button_name == self.solo_button:
                if long_press:
                    self.app.logic_interface.solo_lock()
                else:
                    self.app.logic_interface.solo()
                self.app.buttons_need_update = True
                return True

            # MUTE
            elif button_name == self.mute_button:
                if long_press:
                    self.app.logic_interface.mute_off()
                else:
                    self.app.logic_interface.mute()
                self.app.buttons_need_update = True
                return True

            elif button_name == self.up_button:
                if not self.app.is_mode_active(self.app.help_mode):
                    self.app.logic_interface.arrow_keys('up', True if shift else False, True if loop else False)
                    return True
            elif button_name == self.down_button:
                self.app.logic_interface.arrow_keys('down', True if shift else False, True if loop else False)
                return True
            elif button_name == self.left_button:
                self.app.logic_interface.arrow_keys('left', True if shift else False, True if loop else False)
                return True
            elif button_name == self.right_button:
                self.app.logic_interface.arrow_keys('right', True if shift else False, True if loop else False)
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

            for button in self.quantize_buttons:
                if button_name == button:
                    self.app.logic_interface.quantize(button_name, True if quantize else False, True if shift else False, True if loop else False, False, False)

    def on_button_pressed_raw(self, button_name):
        if button_name == self.user_button:
            self.push.buttons.set_button_color(self.user_button, definitions.WHITE)
            return True
        # Avoid forcing PLAY/RECORD/METRONOME to white
        if button_name not in [self.play_button, self.record_button, self.metronome_button]:
            self.push.buttons.set_button_color(button_name, definitions.WHITE)
            return True
        return None

    def on_button_released_raw(self, button_name):
        self.set_buttons_to_color(self.buttons_used, definitions.OFF_BTN_COLOR)

