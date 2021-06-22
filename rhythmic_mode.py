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

    def update_octave_buttons(self):
        # Rhythmic does not have octave buttons
        pass

    def update_pads(self):
        color_matrix = []
        for i in range(0, 8):
            row_colors = []
            for j in range(0, 8):
                corresponding_midi_note = self.pad_ij_to_midi_note([i, j])
                cell_color = definitions.BLACK
                if i >= 4 and j < 4:
                    # This is the main 4x4 grid
                    cell_color = self.app.track_selection_mode.get_current_track_color()
                elif i >= 4 and j >= 4:
                    cell_color = definitions.GRAY_LIGHT
                elif i < 4 and j < 4:
                    cell_color = definitions.GRAY_LIGHT
                elif i < 4 and j >= 4:
                    cell_color = definitions.GRAY_LIGHT
                if self.is_midi_note_being_played(corresponding_midi_note):
                    cell_color = definitions.NOTE_ON_COLOR

                row_colors.append(cell_color)
            color_matrix.append(row_colors)

        self.push.pads.set_pads_color(color_matrix)

    def on_button_pressed_raw(self, button_name):
        if button_name == push2_python.constants.BUTTON_OCTAVE_UP or button_name == push2_python.constants.BUTTON_OCTAVE_DOWN:
            # Don't react to octave up/down buttons as these are not used in rhythm mode
            pass
        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed_raw(button_name)
