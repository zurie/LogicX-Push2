import definitions
import push2_python.constants
import time

from display_utils import show_title, show_value, draw_text_at


class RepeatMode(definitions.LogicMode):
    current_page = 0
    n_pages = 1

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

    ] + quantize_buttons

    def move_to_next_page(self):
        self.app.buttons_need_update = True
        self.current_page += 1
        if self.current_page >= self.n_pages:
            self.current_page = 0
            return True  # Return true because page rotation finished 
        return False

    def activate(self):
        self.current_page = 0
        self.app.logic_interface.repeat()
        self.update_buttons()

    def deactivate(self):
        self.app.logic_interface.repeat()
        self.set_all_repeat_buttons_off()

    def set_all_repeat_buttons_off(self):
        self.set_buttons_to_color(self.quantize_buttons, definitions.OFF_BTN_COLOR)

    def update_buttons(self):
        if self.current_page == 0:  # Performance settings
            self.set_buttons_to_color(self.quantize_buttons, self.app.track_selection_mode.get_current_track_color())

    def on_button_pressed_raw(self, button_name):
        if self.current_page == 0:  # Performance settings
            for button in self.quantize_buttons:
                if button_name == button:
                    self.app.logic_interface.quantize(button, False, False, False, True, False)

    def on_button_released_raw(self, button_name):
        if self.current_page == 0:  # Performance settings
            self.set_buttons_to_color(self.quantize_buttons, definitions.OFF_BTN_COLOR)
            for button in self.quantize_buttons:
                if button_name == button:
                    self.app.logic_interface.quantize(button, False, False, False, False, True)


