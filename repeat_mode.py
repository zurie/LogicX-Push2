import definitions
import push2_python.constants
import time

from display_utils import show_title, show_value, draw_text_at


class RepeatMode(definitions.LogicMode):
    current_page = 0
    n_pages = 1
    buttons_used = [
        push2_python.constants.BUTTON_1_32T,
        push2_python.constants.BUTTON_1_32,
        push2_python.constants.BUTTON_1_16T,
        push2_python.constants.BUTTON_1_16,
        push2_python.constants.BUTTON_1_8T,
        push2_python.constants.BUTTON_1_8,
        push2_python.constants.BUTTON_1_4T,
        push2_python.constants.BUTTON_1_4
    ]

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
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_32T, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_32, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_16T, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_16, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_8T, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_8, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_4T, definitions.OFF_BTN_COLOR)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_4, definitions.OFF_BTN_COLOR)

    def update_buttons(self):
        if self.current_page == 0:  # Performance settings
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_32T, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_32, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_16T, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_16, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_8T, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_8, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_4T, self.app.track_selection_mode.get_current_track_color())
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_1_4, self.app.track_selection_mode.get_current_track_color())

    def on_button_pressed_raw(self, button_name):

        if self.current_page == 0:  # Performance settings
            if button_name == self.buttons_used[0]:
                self.app.logic_interface.quantize(0, False, False, False, True)
                return True
            elif button_name == self.buttons_used[1]:
                self.app.logic_interface.quantize(1, False, False, False, True)
                return True
            elif button_name == self.buttons_used[2]:
                self.app.logic_interface.quantize(2, False, False, False, True)
                return True
            elif button_name == self.buttons_used[3]:
                self.app.logic_interface.quantize(3, False, False, False, True)
                return True
            elif button_name == self.buttons_used[4]:
                self.app.logic_interface.quantize(4, False, False, False, True)
                return True
            elif button_name == self.buttons_used[5]:
                self.app.logic_interface.quantize(5, False, False, False, True)
                return True
            elif button_name == self.buttons_used[6]:
                self.app.logic_interface.quantize(6, False, False, False, True)
                return True
            elif button_name == self.buttons_used[7]:
                self.app.logic_interface.quantize(7, False, False, False, True)
                return True

    def on_button_released_raw(self, button_name):
        self.set_buttons_to_color(self.buttons_used, definitions.OFF_BTN_COLOR)
        if button_name == self.buttons_used[0]:
            self.app.logic_interface.quantize_off(0)
            return True
        elif button_name == self.buttons_used[1]:
            self.app.logic_interface.quantize_off(1)
            return True
        elif button_name == self.buttons_used[2]:
            self.app.logic_interface.quantize_off(2)
            return True
        elif button_name == self.buttons_used[3]:
            self.app.logic_interface.quantize_off(3)
            return True
        elif button_name == self.buttons_used[4]:
            self.app.logic_interface.quantize_off(4)
            return True
        elif button_name == self.buttons_used[5]:
            self.app.logic_interface.quantize_off(5)
            return True
        elif button_name == self.buttons_used[6]:
            self.app.logic_interface.quantize_off(6)
            return True
        elif button_name == self.buttons_used[7]:
            self.app.logic_interface.quantize_off(7)
            return True
