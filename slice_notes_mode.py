import definitions
import push2_python.constants

from melodic_mode import MelodicMode


class SliceNotesMode(MelodicMode):

    color_groups = [
        definitions.RED,
        definitions.ORANGE,
        definitions.TANGERINE,
        definitions.YELLOW,
        definitions.GREEN,
        definitions.BLUE,
        definitions.PINK,
        definitions.PURPLE
    ]
    start_note = 0

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.start_note + 8 * (7 - pad_ij[0]) + pad_ij[1]

    def _pad_color(self, i, j, midi_note):
        color = self.app.track_selection_mode.get_current_track_color() if (midi_note // 16) % 2 == 0 else definitions.WHITE
        if self.is_midi_note_being_played(midi_note):
            color = definitions.NOTE_ON_COLOR
        return color

    def on_button_pressed(self, button_name, loop=False, quantize=False, shift=False, select=False, long_press=False, double_press=False):
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
