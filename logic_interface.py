# logic_interface.py

import definitions
import push2_python
from logic_keystrokes import press_keybinding

tracks_state_fps = 4.0
transport_state_fps = 10.0
bpm_button_names = [
    push2_python.constants.BUTTON_UPPER_ROW_1,
    push2_python.constants.BUTTON_UPPER_ROW_2,
    push2_python.constants.BUTTON_UPPER_ROW_3,
    push2_python.constants.BUTTON_UPPER_ROW_4,
    push2_python.constants.BUTTON_UPPER_ROW_5,
    push2_python.constants.BUTTON_UPPER_ROW_6,
    push2_python.constants.BUTTON_UPPER_ROW_7,
    push2_python.constants.BUTTON_UPPER_ROW_8
]


def to_utf8(utf8):
    return utf8.decode("utf-8")


class LogicInterface(definitions.LogicMode):
    def __init__(self, app):
        self.app = app
        self.last_received_tracks_raw_state = ""
        self.parsed_state = {}

    def update_button(self, value, attribute, button, on_color, off_color):
        is_active = value == 1.0
        setattr(definitions, attribute, is_active)
        self.app.logic_interface.get_buttons_state()
        color = on_color if is_active else off_color
        self.app.push.buttons.set_button_color(button, color)

    def update_stop(self, *values):
        # definitions.isPlaying = 0.0
        definitions.isRecording = 0.0
        self.app.logic_interface.get_buttons_state()

    def update_play_button(self, *values):
        print(f"[Debug] update_play_button received values: {values}")
        value = values[0] if values else 0.0
        self.update_button(value, 'isPlaying', push2_python.constants.BUTTON_PLAY, definitions.GREEN, definitions.LIME)

    def update_metronome_button(self, value):
        self.update_button(value, 'isMetronome', push2_python.constants.BUTTON_METRONOME, definitions.WHITE,
                           definitions.OFF_BTN_COLOR)

    def update_record_button(self, *values):
        definitions.isRecording = 1.0
        value = values[0] if values else 0.0
        self.update_button(value, 'isRecording', push2_python.constants.BUTTON_RECORD, definitions.RED,
                           definitions.GREEN)

    def automate(self):
        press_keybinding('A')

    def repeat(self):
        press_keybinding('^~return')

    def layout(self):
        press_keybinding('L')

    def session(self):
        press_keybinding('E')

    def add_track(self):
        press_keybinding('T')

    def device(self):
        press_keybinding('B')

    def mix(self):
        press_keybinding('X')  # Adjust if wrong

    def browse(self):
        press_keybinding('Y')

    def clip(self):
        press_keybinding('C')

    def fixed_length(self):
        press_keybinding('\\')

    def new(self):
        press_keybinding('~!N')

    def new_next(self):
        press_keybinding('^return')

    def duplicate(self):
        press_keybinding('!D')

    def double_loop(self):
        press_keybinding('2')  # Placeholder

    def double(self):
        press_keybinding('C')  # Placeholder

    def stop_clip(self):
        press_keybinding('V')  # Placeholder

    def mute(self):
        press_keybinding('M')

    def mute_off(self):
        press_keybinding('^#M')

    def solo(self):
        press_keybinding('S')

    def solo_lock(self):
        press_keybinding('^S')

    def undo(self):
        press_keybinding('!Z')

    def redo(self):
        press_keybinding('#!Z')

    def delete(self):
        press_keybinding('delete')

    def pause(self):
        press_keybinding('space')

    def play(self):
        press_keybinding('space')

    def record(self):
        press_keybinding('R')
        # Toggle internal recording state
        definitions.isRecording = not definitions.isRecording

        if definitions.isRecording:
            self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.RED)
        else:
            self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.GREEN)

    def stop(self):
        press_keybinding('space')

    def arrow_keys(self, direction, shift, loop):
        if direction in ['up', 'down', 'left', 'right']:
            if shift and loop:
                if direction == 'right':
                    press_keybinding('#!.')
                elif direction == 'left':
                    press_keybinding('#!,')
            elif shift:
                press_keybinding(f'#{direction}')
            elif loop:
                if direction == 'down':
                    press_keybinding("~'")
                elif direction == 'up':
                    press_keybinding('U')
                else:
                    press_keybinding(direction)
            else:
                press_keybinding(direction)

    def quantize(self, index, quantize, shift, loop, repeat, off):
        quant_map = {
            "1_32T": '7', "1_32": '3', "1_16T": '6', "1_16": '2',
            "1_8T": '5', "1_8": '1', "1_4T": '4', "1_4": '0'
        }
        if index in quant_map:
            press_keybinding(f'~!#^{quant_map[index]}')
        else:
            press_keybinding('Q')

    def metronome_on_off(self):
        press_keybinding('K')  # placeholder if needed

    def get_buttons_state(self):
        metronome_on = definitions.isMetronome
        is_recording = definitions.isRecording

        # Do not overwrite PLAY here; use update_play_button_color instead
        # self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.LIME if not is_playing else definitions.GREEN)

        self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD,
                                               definitions.GREEN if not is_recording else definitions.RED)
        self.app.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME,
                                               definitions.OFF_BTN_COLOR if not metronome_on else definitions.WHITE)
        self.app.midi_cc_mode.update_buttons()
        return definitions.isPlaying, metronome_on, is_recording
