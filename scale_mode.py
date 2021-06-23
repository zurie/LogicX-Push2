import mido

import definitions
import push2_python.constants

import melodic_mode
from melodic_mode import MelodicMode


class ChromaticMode(MelodicMode):
    scale = definitions.Minor
    start_note = 0

    octave_up_button = push2_python.constants.BUTTON_OCTAVE_UP
    octave_down_button = push2_python.constants.BUTTON_OCTAVE_DOWN
    accent_button = push2_python.constants.BUTTON_ACCENT
    scale_button = push2_python.constants.BUTTON_SCALE

    buttons_used = [octave_up_button, octave_down_button, accent_button, scale_button]
    color_groups = [
        definitions.GREEN,
        definitions.YELLOW,
        definitions.ORANGE,
        definitions.RED,
        definitions.PINK,
        definitions.PURPLE,
        definitions.CYAN,
        definitions.BLUE
    ]

    def update_scale_button(self):
        self.set_button_color_if_expression(self.scale_button, self.fixed_velocity_mode,
                                            animation=definitions.DEFAULT_ANIMATION)

    def update_buttons(self):
        self.update_octave_buttons()
        self.update_scale_button()

    def get_settings_to_save(self):
        return {}

    # def pad_ij_to_midi_note(self, pad_ij):
    #     return self.start_note + 8 * (7 - pad_ij[0]) + pad_ij[1]

    def pad_ij_to_midi_note(self, pad_ij):
        return self.root_midi_note + ((7 - pad_ij[0]) * 5 + pad_ij[1])

    def is_black_key_midi_note(self, midi_note):
        relative_midi_note = (midi_note - self.root_midi_note) % 12
        return not self.scale[relative_midi_note]

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

    def on_pad_released_raw(self, pad_n, pad_ij, velocity):
        midi_note = self.pad_ij_to_midi_note(pad_ij)
        if midi_note is not None:
            if self.app.track_selection_mode.get_current_track_info().get('illuminate_local_notes', True) or self.app.notes_midi_in is None:
                # see comment in "on_pad_pressed" above
                self.remove_note_being_played(midi_note, 'push')
            msg = mido.Message('note_off', note=midi_note, velocity=velocity)
            self.app.send_midi(msg)
            self.app.add_display_notification("Padded Presed: {0}".format(midi_note))
            self.update_pads()  # Directly calling update pads method because we want user to feel feedback as quick as possible
            return True

    def on_button_pressed(self, button_name, shift=False, select=False, long_press=False, double_press=False):
        if button_name == push2_python.constants.BUTTON_SCALE:
            self.toggle_scale()
            return True

        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed(button_name, shift, select, long_press, double_press)

    def toggle_scale(self):

        if self.scale == definitions.Minor:
            self.scale = definitions.Dorian
            s = 'Dorian'
            self.update_pads()

        elif self.scale == definitions.Dorian:
            self.scale = definitions.Mixolydian
            s = 'Mixolydian'
            self.update_pads()

        elif self.scale == definitions.Mixolydian:
            self.scale = definitions.Major
            s = 'Major'
            self.update_pads()

        elif self.scale == definitions.Major:
            self.scale = definitions.Lydian
            s = 'Lydian'
            self.update_pads()

        elif self.scale == definitions.Lydian:
            self.scale = definitions.Phrygian
            s = 'Phrygian'
            self.update_pads()

        elif self.scale == definitions.Phrygian:
            self.scale = definitions.Locrian
            s = 'Locrian'
            self.update_pads()

        elif self.scale == definitions.Locrian:
            self.scale = definitions.Diminished
            s = 'Diminished'
            self.update_pads()

        elif self.scale == definitions.Diminished:
            self.scale = definitions.Whole_half
            s = 'Whole_half'
            self.update_pads()

        elif self.scale == definitions.Whole_half:
            self.scale = definitions.Whole_Tone
            s = 'Whole_Tone'
            self.update_pads()

        elif self.scale == definitions.Whole_Tone:
            self.scale = definitions.Minor_Blues
            s = 'Minor_Blues'
            self.update_pads()

        elif self.scale == definitions.Minor_Blues:
            self.scale = definitions.Minor_Pentatonic
            s = 'Minor_Pentatonic'
            self.update_pads()

        elif self.scale == definitions.Minor_Pentatonic:
            self.scale = definitions.Major_Pentatonic
            s = 'Major_Pentatonic'
            self.update_pads()

        elif self.scale == definitions.Major_Pentatonic:
            self.scale = definitions.Harmonic_Minor
            s = 'Harmonic_Minor'
            self.update_pads()

        elif self.scale == definitions.Harmonic_Minor:
            self.scale = definitions.Melodic_Minor
            s = 'Melodic_Minor'
            self.update_pads()

        elif self.scale == definitions.Melodic_Minor:
            self.scale = definitions.Super_Locrian
            s = 'Super_Locrian'
            self.update_pads()

        elif self.scale == definitions.Super_Locrian:
            self.scale = definitions.Bhairav
            s = 'Bhairav'
            self.update_pads()

        elif self.scale == definitions.Bhairav:
            self.scale = definitions.Hungarian_Minor
            s = 'Hungarian_Minor'
            self.update_pads()

        elif self.scale == definitions.Hungarian_Minor:
            self.scale = definitions.Minor_Gypsy
            s = 'Minor_Gypsy'
            self.update_pads()

        elif self.scale == definitions.Minor_Gypsy:
            self.scale = definitions.Hirojoshi
            s = 'Hirojoshi'
            self.update_pads()

        elif self.scale == definitions.Hirojoshi:
            self.scale = definitions.In_Sen
            s = 'In_Sen'
            self.update_pads()

        elif self.scale == definitions.In_Sen:
            self.scale = definitions.Iwato
            s = 'Iwato'
            self.update_pads()

        elif self.scale == definitions.Iwato:
            self.scale = definitions.Kumoi
            s = 'Kumoi'
            self.update_pads()

        elif self.scale == definitions.Kumoi:
            self.scale = definitions.Pelog
            s = 'Pelog'
            self.update_pads()

        elif self.scale == definitions.Pelog:
            self.scale = definitions.Spanish
            s = 'Spanish'
            self.update_pads()

        elif self.scale == definitions.Spanish:
            self.scale = definitions.Minor
            s = 'Minor'
            self.update_pads()

        self.app.add_display_notification("{0} {1} Scale".format(self.note_number_to_name(self.root_midi_note), s))
        return True
