import definitions
import push2_python.constants

from melodic_mode import MelodicMode


class SliceNotesMode(MelodicMode):

    start_note = 0
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

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.start_note + 8 * (7 - pad_ij[0]) + pad_ij[1]

    def update_scale_button(self):
        # Rhythmic does not have scale buttons
        pass

    def update_pads(self):
        color_matrix = []
        for i in range(0, 8):
            row_colors = []
            for j in range(0, 8):
                corresponding_midi_note = self.pad_ij_to_midi_note([i, j])
                midi_16_note_groups_idx = corresponding_midi_note // 16
                #cell_color = self.color_groups[midi_16_note_groups_idx]
                if midi_16_note_groups_idx % 2 == 0:
                    cell_color = self.app.track_selection_mode.get_current_track_color()
                else:
                    cell_color = definitions.WHITE
                if self.is_midi_note_being_played(corresponding_midi_note):
                    cell_color = definitions.NOTE_ON_COLOR
                row_colors.append(cell_color)
            color_matrix.append(row_colors)

        self.push.pads.set_pads_color(color_matrix)

    def on_button_pressed(self, button_name, shift=False, select=False, long_press=False, double_press=False):
        if button_name == push2_python.constants.BUTTON_OCTAVE_UP:
            self.start_note += 16
            if self.start_note > 128 - 16 * 4:
                self.start_note = 128 - 16 * 4
            self.app.pads_need_update = True
            self.app.add_display_notification("MIDI notes range: {0} to {1}".format(
                self.pad_ij_to_midi_note((7, 0)),
                self.pad_ij_to_midi_note((0, 7)),
            ))
            return True

        elif button_name == push2_python.constants.BUTTON_OCTAVE_DOWN:
            self.start_note -= 16
            if self.start_note < 0:
                self.start_note = 0
            self.app.pads_need_update = True
            self.app.add_display_notification("MIDI notes range: {0} to {1}".format(
                self.pad_ij_to_midi_note((7, 0)),
                self.pad_ij_to_midi_note((0, 7)),
            ))
            return True

        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed(button_name, shift, select, long_press, double_press)
