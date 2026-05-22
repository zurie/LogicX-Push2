import definitions
import push2_python.constants

from melodic_mode import MelodicMode


class RhythmicMode(MelodicMode):

    rhythmic_notes_matrix = [
        [64, 65, 66, 67, 96, 97, 98, 99],
        [60, 61, 62, 63, 92, 93, 94, 95],
        [56, 57, 58, 59, 88, 89, 90, 91],
        [52, 53, 54, 55, 84, 85, 86, 87],
        [48, 49, 50, 51, 80, 81, 82, 83],
        [44, 45, 46, 47, 76, 77, 78, 79],
        [40, 41, 42, 43, 72, 73, 74, 75],
        [36, 37, 38, 39, 68, 69, 70, 71]
    ]

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.rhythmic_notes_matrix[pad_ij[0]][pad_ij[1]]

    def update_scale_button(self):
        # Rythmic does not have scale buttons
        pass

    def update_octave_buttons(self):
        # Rhythmic does not have octave buttons
        pass

    def _pad_color(self, i, j, midi_note):
        if i >= 4 and j < 4:
            color = self.app.track_selection_mode.get_current_track_color()  # main 4x4 grid
        elif i >= 4 and j >= 4:
            color = definitions.GRAY_LIGHT
        elif i < 4 and j < 4:
            color = definitions.GRAY_LIGHT
        else:
            color = definitions.GRAY_LIGHT
        if self.is_midi_note_being_played(midi_note):
            color = definitions.NOTE_ON_COLOR
        return color

    def on_button_pressed(self, button_name, loop=False, quantize=False, shift=False, select=False, long_press=False, double_press=False):
        if button_name == push2_python.constants.BUTTON_OCTAVE_UP or button_name == push2_python.constants.BUTTON_OCTAVE_DOWN:
            # Don't react to octave up/down buttons as these are not used in rhythm mode
            pass
        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed_raw(button_name)
