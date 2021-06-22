import definitions
import mido
import push2_python.constants
import time


class MelodicMode(definitions.PyshaMode):

    xor_group = 'pads'

    notes_being_played = []
    root_midi_note = 0  # default redefined in initialize
    scale_pattern = [True, False, True, False, True, True, False, True, False, True, False, True]
    fixed_velocity_mode = False
    use_poly_at = False  # default redefined in initialize
    channel_at_range_start = 401  # default redefined in initialize
    channel_at_range_end = 800  # default redefined in initialize
    poly_at_max_range = 40  # default redefined in initialize
    poly_at_curve_bending = 50  # default redefined in initialize
    latest_channel_at_value = (0, 0)
    latest_poly_at_value = (0, 0)
    latest_velocity_value = (0, 0)
    last_time_at_params_edited = None
    modulation_wheel_mode = False

    lumi_midi_out = None
    last_time_tried_initialize_lumi = 0

    octave_up_button = push2_python.constants.BUTTON_OCTAVE_UP
    octave_down_button = push2_python.constants.BUTTON_OCTAVE_DOWN
    accent_button = push2_python.constants.BUTTON_ACCENT

    buttons_used = [octave_up_button, octave_down_button, accent_button]

    def init_lumi_midi_out(self):
        print('Configuring LUMI notes MIDI out...')
        self.last_time_tried_initialize_lumi = time.time()
        device_name = "LUMI Keys BLOCK"
        try:
            full_name = [name for name in mido.get_output_names() if device_name.lower() in name.lower()][0]
        except IndexError:
            full_name = None

        if full_name is not None:
            try:
                self.lumi_midi_out = mido.open_output(full_name)
                print('Sending notes MIDI in to "{0}"'.format(full_name))
            except IOError:
                print('Could not connect to notes MIDI output port "{0}"\nAvailable device names:'.format(full_name))
        else:
            print('No available device name found for {}'.format(device_name))

    def set_lumi_pressure_mode(self):
        if self.lumi_midi_out is not None:
            if not self.use_poly_at:
                msg = mido.Message('sysex', data=[0x00, 0x21, 0x10, 0x77, 0x27, 0x10, 0x00, 0x24, 0x00, 0x00, 0x00, 0x00, 0x00, 0x64])
            else:
                msg = mido.Message('sysex', data=[0x00, 0x21, 0x10, 0x77, 0x27, 0x10, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04])
            self.lumi_midi_out.send(msg)
   
    def initialize(self, settings=None):
        if settings is not None:
            self.use_poly_at = settings.get('use_poly_at', True)
            self.set_root_midi_note(settings.get('root_midi_note', 64))
            self.channel_at_range_start = settings.get('channel_at_range_start', 401)
            self.channel_at_range_end = settings.get('channel_at_range_end', 800)
            self.poly_at_max_range = settings.get('poly_at_max_range', 40)
            self.poly_at_curve_bending = settings.get('poly_at_curve_bending', 50)
        self.init_lumi_midi_out()

    def get_settings_to_save(self):
        return {
            'use_poly_at': self.use_poly_at,
            'root_midi_note': self.root_midi_note,
            'channel_at_range_start': self.channel_at_range_start,
            'channel_at_range_end': self.channel_at_range_end,
            'poly_at_max_range': self.poly_at_max_range,
            'poly_at_curve_bending': self.poly_at_curve_bending,
        }

    def set_channel_at_range_start(self, value):
        # Parameter in range [401, channel_at_range_end - 1]
        if value < 401:
            value = 401
        elif value >= self.channel_at_range_end:
            value = self.channel_at_range_end - 1
        self.channel_at_range_start = value
        self.last_time_at_params_edited = time.time()

    def set_channel_at_range_end(self, value):
        # Parameter in range [channel_at_range_start + 1, 2000]
        if value <= self.channel_at_range_start:
            value = self.channel_at_range_start + 1
        elif value > 2000:
            value = 2000
        self.channel_at_range_end = value
        self.last_time_at_params_edited = time.time()

    def set_poly_at_max_range(self, value):
        # Parameter in range [0, 127]
        if value < 0:
            value = 0
        elif value > 127:
            value = 127
        self.poly_at_max_range = value
        self.last_time_at_params_edited = time.time()

    def set_poly_at_curve_bending(self, value):
        # Parameter in range [0, 100]
        if value < 0:
            value = 0
        elif value > 100:
            value = 100
        self.poly_at_curve_bending = value
        self.last_time_at_params_edited = time.time()

    def get_poly_at_curve(self):
        pow_curve = [pow(e, 3*self.poly_at_curve_bending/100) for e in [i/self.poly_at_max_range for i in range(0, self.poly_at_max_range)]]
        return [int(127 * pow_curve[i]) if i < self.poly_at_max_range else 127 for i in range(0, 128)]

    def add_note_being_played(self, midi_note, source):
        self.notes_being_played.append({'note': midi_note, 'source': source})

    def remove_note_being_played(self, midi_note, source):
        self.notes_being_played = [note for note in self.notes_being_played if note['note'] != midi_note or note['source'] != source]

    def remove_all_notes_being_played(self):
        self.notes_being_played = []

    def pad_ij_to_midi_note(self, pad_ij):
        return self.root_midi_note + ((7 - pad_ij[0]) * 5 + pad_ij[1])

    def is_midi_note_root_octave(self, midi_note):
        relative_midi_note = (midi_note - self.root_midi_note) % 12
        return relative_midi_note == 0

    def is_black_key_midi_note(self, midi_note):
        relative_midi_note = (midi_note - self.root_midi_note) % 12
        return not self.scale_pattern[relative_midi_note]

    def is_midi_note_being_played(self, midi_note):
        for note in self.notes_being_played:
            if note['note'] == midi_note:
                return True
        return False

    def note_number_to_name(self, note_number):
        semis = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        note_number = int(round(note_number))
        return semis[note_number % 12] + str(note_number//12 - 2)

    def set_root_midi_note(self, note_number):
        self.root_midi_note = note_number
        if self.root_midi_note < 0:
            self.root_midi_note = 0
        elif self.root_midi_note > 127:
            self.root_midi_note = 127

    def activate(self):

        # Configure polyAT and AT
        if self.use_poly_at:
            self.push.pads.set_polyphonic_aftertouch()
        else:
            self.push.pads.set_channel_aftertouch()
        self.push.pads.set_channel_aftertouch_range(range_start=self.channel_at_range_start, range_end=self.channel_at_range_end)
        self.push.pads.set_velocity_curve(velocities=self.get_poly_at_curve())

        self.set_lumi_pressure_mode()

        # Configure touchstrip behaviour
        if self.modulation_wheel_mode:
            self.push.touchstrip.set_modulation_wheel_mode()
        else:
            self.push.touchstrip.set_pitch_bend_mode()

        # Update buttons and pads
        self.update_buttons()
        self.update_pads()

    def deactivate(self):
        # Run supperclass deactivate to set all used buttons to black
        super().deactivate()

    def check_for_delayed_actions(self):
        if self.last_time_at_params_edited is not None and time.time() - self.last_time_at_params_edited > definitions.DELAYED_ACTIONS_APPLY_TIME:
            # Update channel and poly AT parameters
            self.push.pads.set_channel_aftertouch_range(range_start=self.channel_at_range_start, range_end=self.channel_at_range_end)
            self.push.pads.set_velocity_curve(velocities=self.get_poly_at_curve())
            self.last_time_at_params_edited = None

    def on_midi_in(self, msg, source=None):
        # Update the list of notes being currently played so push2 pads can be updated accordingly
        if msg.type == "note_on":
            if msg.velocity == 0:
                self.remove_note_being_played(msg.note, source)
            else:
                self.add_note_being_played(msg.note, source)
        elif msg.type == "note_off":
            self.remove_note_being_played(msg.note, source)
        self.app.pads_need_update = True

    def update_octave_buttons(self):
        self.set_button_color(self.octave_down_button)
        self.set_button_color(self.octave_up_button)

    def update_accent_button(self):
        if self.fixed_velocity_mode:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_ACCENT, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_ACCENT, definitions.WHITE, animation=definitions.DEFAULT_ANIMATION)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_ACCENT, definitions.OFF_BTN_COLOR)

    def update_modulation_wheel_mode_button(self):
        if self.modulation_wheel_mode:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_SHIFT, definitions.BLACK)
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_SHIFT, definitions.WHITE, animation=definitions.DEFAULT_ANIMATION)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_SHIFT, definitions.OFF_BTN_COLOR)

    def update_buttons(self):
        self.update_octave_buttons()
        self.update_modulation_wheel_mode_button()
        self.update_accent_button()

    def update_pads(self):
        color_matrix = []
        for i in range(0, 8):
            row_colors = []
            for j in range(0, 8):
                corresponding_midi_note = self.pad_ij_to_midi_note([i, j])
                cell_color = definitions.WHITE
                if self.is_black_key_midi_note(corresponding_midi_note):
                    cell_color = definitions.BLACK
                if self.is_midi_note_root_octave(corresponding_midi_note):
                    try:
                        cell_color = self.app.track_selection_mode.get_current_track_color()
                    except AttributeError:
                        cell_color = definitions.YELLOW
                if self.is_midi_note_being_played(corresponding_midi_note):
                    cell_color = definitions.NOTE_ON_COLOR

                row_colors.append(cell_color)
            color_matrix.append(row_colors)

        self.push.pads.set_pads_color(color_matrix)

    def on_pad_pressed_raw(self, pad_n, pad_ij, velocity):
        midi_note = self.pad_ij_to_midi_note(pad_ij)
        if midi_note is not None:
            self.latest_velocity_value = (time.time(), velocity)
            if self.app.track_selection_mode.get_current_track_info().get('illuminate_local_notes', True) or self.app.notes_midi_in is None:
                # illuminate_local_notes is used to decide wether a pad/key should be lighted when pressing it. This will probably be the default behaviour,
                # but in synth definitions this can be disabled because we will be receiving back note events at the "notes_midi_in" device and in this
                # case we don't want to light the pad "twice" (or if the note pressed gets processed and another note is actually played we don't want to
                # light the currently presed pad). However, if "notes_midi_in" input is not configured, we do want to liht the pad as we won't have
                # notes info comming from any other source
                self.add_note_being_played(midi_note, 'push')
            msg = mido.Message('note_on', note=midi_note, velocity=velocity if not self.fixed_velocity_mode else 127)
            self.app.send_midi(msg)
            self.update_pads()  # Directly calling update pads method because we want user to feel feedback as quick as possible
            return True

    def on_pad_released_raw(self, pad_n, pad_ij, velocity):
        midi_note = self.pad_ij_to_midi_note(pad_ij)
        if midi_note is not None:
            if self.app.track_selection_mode.get_current_track_info().get('illuminate_local_notes', True) or self.app.notes_midi_in is None:
                # see comment in "on_pad_pressed" above
                self.remove_note_being_played(midi_note, 'push')
            msg = mido.Message('note_off', note=midi_note, velocity=velocity)
            self.app.send_midi(msg)
            self.update_pads()  # Directly calling update pads method because we want user to feel feedback as quick as possible
            return True

    def on_pad_aftertouch(self, pad_n, pad_ij, velocity):
        if pad_n is not None:
            # polyAT mode
            self.latest_poly_at_value = (time.time(), velocity)
            midi_note = self.pad_ij_to_midi_note(pad_ij)
            if midi_note is not None:
                msg = mido.Message('polytouch', note=midi_note, value=velocity)
        else:
            # channel AT mode
            self.latest_channel_at_value = (time.time(), velocity)
            msg = mido.Message('aftertouch', value=velocity)
        self.app.send_midi(msg)
        return True

    def on_touchstrip(self, value):
        if self.modulation_wheel_mode:
            msg = mido.Message('control_change', control=1, value=value)
        else:
            msg = mido.Message('pitchwheel', pitch=value)
        self.app.send_midi(msg)
        return True

    def on_sustain_pedal(self, sustain_on):
        msg = mido.Message('control_change', control=64, value=127 if sustain_on else 0)
        self.app.send_midi(msg)
        return True

    def on_button_released_raw(self, button_name):
        if button_name == push2_python.constants.BUTTON_OCTAVE_UP:
            self.set_root_midi_note(self.root_midi_note + 12)
            self.app.pads_need_update = True
            self.app.add_display_notification("Octave up: from {0} to {1}".format(
                self.note_number_to_name(self.pad_ij_to_midi_note((7, 0))),
                self.note_number_to_name(self.pad_ij_to_midi_note((0, 7))),
            ))
            return True

        elif button_name == self.octave_down_button:
            self.set_root_midi_note(self.root_midi_note - 12)
            self.app.pads_need_update = True
            self.app.add_display_notification("Octave down: from {0} to {1}".format(
                self.note_number_to_name(self.pad_ij_to_midi_note((7, 0))),
                self.note_number_to_name(self.pad_ij_to_midi_note((0, 7))),
            ))
            return True

        elif button_name == push2_python.constants.BUTTON_ACCENT:
            self.fixed_velocity_mode = not self.fixed_velocity_mode
            self.app.buttons_need_update = True
            self.app.pads_need_update = True
            self.app.add_display_notification("Fixed velocity: {0}".format('On' if self.fixed_velocity_mode else 'Off'))
            return True

        elif button_name == push2_python.constants.BUTTON_SHIFT:
            self.modulation_wheel_mode = not self.modulation_wheel_mode
            if self.modulation_wheel_mode:
                self.push.touchstrip.set_modulation_wheel_mode()
            else:
                self.push.touchstrip.set_pitch_bend_mode()
            self.app.buttons_need_update = True
            self.app.add_display_notification("Touchstrip mode: {0}".format('Modulation wheel' if self.modulation_wheel_mode else 'Pitch bend'))
            return True
