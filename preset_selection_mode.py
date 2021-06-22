import definitions
import mido
import push2_python
import time
import os
import json

from display_utils import show_notification


class PresetSelectionMode(definitions.PyshaMode):

    xor_group = 'pads'
    
    favourtie_presets = {}
    favourtie_presets_filename = 'favourite_presets.json'
    pad_pressing_states = {}
    pad_quick_press_time = 0.400
    current_page = 0

    def initialize(self, settings=None):
        if os.path.exists(self.favourtie_presets_filename):
            self.favourtie_presets = json.load(open(self.favourtie_presets_filename))

    def activate(self):
        self.current_page = 0
        self.update_buttons()
        self.update_pads()

    def new_track_selected(self):
        self.current_page = 0
        self.app.pads_need_update = True
        self.app.buttons_need_update = True
    
    def add_favourite_preset(self, preset_number, bank_number):
        instrument_short_name = self.app.track_selection_mode.get_current_track_instrument_short_name() 
        if instrument_short_name not in self.favourtie_presets:
            self.favourtie_presets[instrument_short_name] = []
        self.favourtie_presets[instrument_short_name].append((preset_number, bank_number))
        json.dump(self.favourtie_presets, open(self.favourtie_presets_filename, 'w'))  # Save to file

    def remove_favourite_preset(self, preset_number, bank_number):
        instrument_short_name = self.app.track_selection_mode.get_current_track_instrument_short_name() 
        if instrument_short_name in self.favourtie_presets:
            self.favourtie_presets[instrument_short_name] = \
                [(fp_preset_number, fp_bank_number) for fp_preset_number, fp_bank_number in self.favourtie_presets[instrument_short_name] 
                if preset_number != fp_preset_number or bank_number != fp_bank_number]
            json.dump(self.favourtie_presets, open(self.favourtie_presets_filename, 'w'))  # Save to file

    def preset_num_in_favourites(self, preset_number, bank_number):
        instrument_short_name = self.app.track_selection_mode.get_current_track_instrument_short_name() 
        if instrument_short_name not in self.favourtie_presets:
            return False
        for fp_preset_number, fp_bank_number in self.favourtie_presets[instrument_short_name]:
            if preset_number == fp_preset_number and bank_number == fp_bank_number:
                return True
        return False

    def get_current_page(self):
        # Returns the current page of presets being displayed in the pad grid
        # page 0 = bank 0, presets 0-63
        # page 1 = bank 0, presets 64-127
        # page 2 = bank 1, presets 0-63
        # page 3 = bank 1, presets 64-127
        # ...
        # The number of total available pages depends on the synth.
        return self.current_page    

    def get_num_banks(self):
        # Returns the number of available banks of the selected instrument
        return self.app.track_selection_mode.get_current_track_info()['n_banks']

    def get_bank_names(self):
        # Returns list of bank names
        return self.app.track_selection_mode.get_current_track_info()['bank_names']

    def get_num_pages(self):
        # Returns the number of available preset pages per instrument (2 per bank)
        return self.get_num_banks() * 2

    def next_page(self):
        if self.current_page < self.get_num_pages() - 1:
            self.current_page += 1
        else:
            self.current_page = self.get_num_pages() - 1
        self.app.pads_need_update = True
        self.app.buttons_need_update = True
        self.notify_status_in_display()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
        else:
            self.current_page = 0
        self.app.pads_need_update = True
        self.app.buttons_need_update = True
        self.notify_status_in_display()

    def has_prev_next_pages(self):
        has_next = False
        has_prev = False
        if self.get_current_page() < self.get_num_pages() - 1:
            has_next = True
        if self.get_current_page() > 0:
            has_prev = True
        return (has_prev, has_next)

    def pad_ij_to_bank_and_preset_num(self, pad_ij):
        preset_num = (self.get_current_page() % 2) * 64 + pad_ij[0] * 8 + pad_ij[1]
        bank_num = self.get_current_page() // 2
        return (preset_num, bank_num)

    def send_select_new_preset(self, preset_num):
        msg = mido.Message('program_change', program=preset_num)  # Should this be 1-indexed?
        self.app.send_midi(msg)

    def send_select_new_bank(self, bank_num):
        # If synth only has 1 bank, don't send bank change messages
        if self.get_num_banks() > 1:
            msg = mido.Message('control_change', control=0, value=bank_num)  # Should this be 1-indexed?
            self.app.send_midi(msg)

    def notify_status_in_display(self):
        bank_number = self.get_current_page() // 2 + 1
        bank_names = self.get_bank_names() 
        if bank_names is not None:
            bank_name = bank_names[bank_number - 1]
        else:
            bank_name = bank_number
        self.app.add_display_notification("Preset selection: bank {0}, presets {1}".format(
            bank_name,
            '1-64' if self.get_current_page() % 2 == 0 else '65-128'
        ))

    def activate(self):
        self.update_pads()
        self.notify_status_in_display()

    def deactivate(self):
        self.app.push.pads.set_all_pads_to_color(color=definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_LEFT, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_RIGHT, definitions.BLACK)

    def update_buttons(self):
        show_prev, show_next = self.has_prev_next_pages()
        if show_prev:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_LEFT, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_LEFT, definitions.BLACK)
        if show_next:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_RIGHT, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_RIGHT, definitions.BLACK)

    def update_pads(self):
        instrument_short_name = self.app.track_selection_mode.get_current_track_instrument_short_name() 
        track_color = self.app.track_selection_mode.get_current_track_color() 
        color_matrix = []
        for i in range(0, 8):
            row_colors = []
            for j in range(0, 8):
                cell_color = track_color
                preset_num, bank_num = self.pad_ij_to_bank_and_preset_num((i, j))
                if not self.preset_num_in_favourites(preset_num, bank_num):
                    cell_color = f'{cell_color}_darker2'  # If preset not in favourites, use a darker version of the track color
                row_colors.append(cell_color)
            color_matrix.append(row_colors)
        self.push.pads.set_pads_color(color_matrix)

    def on_pad_pressed_raw(self, pad_n, pad_ij, velocity):
        self.pad_pressing_states[pad_n] = time.time()  # Store time at which pad_n was pressed
        self.push.pads.set_pad_color(pad_ij, color=definitions.GREEN)
        return True  # Prevent other modes to get this event

    def on_pad_released(self, pad_n, pad_ij, velocity):
        pressing_time = self.pad_pressing_states.get(pad_n, None)
        is_long_press = False
        if pressing_time is None:
            # Consider quick press (this should not happen as self.pad_pressing_states[pad_n] should have been set before)
            pass
        else:
            if time.time() - pressing_time > self.pad_quick_press_time:
                # Consider this is a long press
                is_long_press = True
            self.pad_pressing_states[pad_n] = None  # Reset pressing time to none

        preset_num, bank_num = self.pad_ij_to_bank_and_preset_num(pad_ij)

        if is_long_press:
            # Add/remove preset to favourites, don't send any MIDI
            if not self.preset_num_in_favourites(preset_num, bank_num):
                self.add_favourite_preset(preset_num, bank_num)
            else:
                self.remove_favourite_preset(preset_num, bank_num)
        else:
            # Send midi message to select the bank and preset preset
            self.send_select_new_bank(bank_num)
            self.send_select_new_preset(preset_num)
            bank_names = self.get_bank_names()
            if bank_names is not None:
                bank_name = bank_names[bank_num]
            else:
                bank_name = bank_num + 1
            self.app.add_display_notification("Selected bank {0}, preset {1}".format(
                bank_name,  # Show 1-indexed value
                preset_num + 1  # Show 1-indexed value
            ))
            
        self.app.pads_need_update = True
        return True  # Prevent other modes to get this event

    def on_button_released(self, button_name):
       if button_name in [push2_python.constants.BUTTON_LEFT, push2_python.constants.BUTTON_RIGHT]:
            show_prev, show_next = self.has_prev_next_pages()
            if button_name == push2_python.constants.BUTTON_LEFT and show_prev:
                self.prev_page()
            elif button_name == push2_python.constants.BUTTON_RIGHT and show_next:
                self.next_page()
            return True
