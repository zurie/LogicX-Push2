import definitions
import mido
import push2_python
import time
import math
import os
import json


class TrackState(object):

    track_num = 0
    has_content = False
    is_playing = False

    def __init__(self, track_num=0):
        self.track_num = track_num


class TrackTriggeringMode(definitions.PyshaMode):

    xor_group = 'pads'

    scene_trigger_buttons = [
        push2_python.constants.BUTTON_1_32T,
        push2_python.constants.BUTTON_1_32,
        push2_python.constants.BUTTON_1_16T,
        push2_python.constants.BUTTON_1_16,
        push2_python.constants.BUTTON_1_8T,
        push2_python.constants.BUTTON_1_8,
        push2_python.constants.BUTTON_1_4T,
        push2_python.constants.BUTTON_1_4
    ]
    
    clear_clip_button_being_pressed = False
    clear_clip_button = push2_python.constants.BUTTON_MASTER

    double_clip_button_being_pressed = False
    double_clip_button = push2_python.constants.BUTTON_DOUBLE_LOOP

    def pad_ij_to_track_num(self, pad_ij):
        return pad_ij[0] * 8 + pad_ij[1]

    def activate(self):
        self.clear_clip_button_being_pressed = False
        self.double_clip_button_being_pressed = False
        self.update_buttons()
        self.update_pads()

    def new_track_selected(self):
        self.clear_clip_button_being_pressed = False
        self.double_clip_button_being_pressed = False
        self.app.pads_need_update = True
        self.app.buttons_need_update = True

    def deactivate(self):
        for button_name in self.scene_trigger_buttons:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)
        self.app.push.pads.set_all_pads_to_color(color=definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME, definitions.BLACK)
        self.push.buttons.set_button_color(push2_python.constants.BUTTON_DUPLICATE, definitions.BLACK)
        self.push.buttons.set_button_color(self.clear_clip_button, definitions.BLACK)
        self.push.buttons.set_button_color(self.double_clip_button, definitions.BLACK)

    def update_buttons(self):
        for i, button_name in enumerate(self.scene_trigger_buttons):
            if self.app.shepherd_interface.get_selected_scene() == i:
                self.push.buttons.set_button_color(button_name, definitions.GREEN)
            else:
                self.push.buttons.set_button_color(button_name, definitions.WHITE)
        
        if not self.clear_clip_button_being_pressed:
            self.push.buttons.set_button_color(self.clear_clip_button, definitions.OFF_BTN_COLOR)
        else:
            self.push.buttons.set_button_color(self.clear_clip_button, definitions.BLACK)
            self.push.buttons.set_button_color(self.clear_clip_button, definitions.WHITE, animation=definitions.DEFAULT_ANIMATION)

        is_playing, metronome_on, is_recording = self.app.shepherd_interface.get_buttons_state()
        # self.push.buttons.set_button_color(push2_python.constants.BUTTON_PLAY, definitions.WHITE if not is_playing else definitions.GREEN)
        # self.push.buttons.set_button_color(push2_python.constants.BUTTON_RECORD, definitions.WHITE if not is_recording else definitions.RED)
        # self.push.buttons.set_button_color(push2_python.constants.BUTTON_METRONOME, definitions.BLACK if not metronome_on else definitions.WHITE)

        self.push.buttons.set_button_color(push2_python.constants.BUTTON_DUPLICATE, definitions.WHITE)
        
        self.push.buttons.set_button_color(self.double_clip_button, definitions.WHITE)

    def update_pads(self):
        # Update pads according to track state
        color_matrix = []
        for i in range(0, 8):
            row_colors = []
            for j in range(0, 8):
                state = self.app.shepherd_interface.get_clip_state(j, i)

                if 'E' in state:
                    cell_color = definitions.BLACK
                else:
                    cell_color = definitions.WHITE

                if 'p' in state:
                    cell_color = definitions.GREEN

                if 'c' in state or 'C' in state:
                    cell_color = definitions.YELLOW

                if 'w' in state or 'W' in state:
                    cell_color = definitions.ORANGE

                if 'r' in state:
                    cell_color = definitions.RED

                row_colors.append(cell_color)
            color_matrix.append(row_colors)
        self.push.pads.set_pads_color(color_matrix)

    def on_button_pressed_raw(self, button_name):
        if button_name in self.scene_trigger_buttons:
            triggered_scene_row = self.scene_trigger_buttons.index(button_name)
            self.app.shepherd_interface.scene_play(triggered_scene_row)
            self.app.pads_need_update = True
            return True  # Prevent other modes to get this event

        elif button_name == self.clear_clip_button:
            self.clear_clip_button_being_pressed = True
            return True  # Prevent other modes to get this event

        elif button_name == self.double_clip_button:
            self.double_clip_button_being_pressed = True
            return True  # Prevent other modes to get this event
        
        elif button_name == push2_python.constants.BUTTON_PLAY:
            self.app.shepherd_interface.global_play_stop()
            return True # Prevent other modes to get this event
            
        elif button_name == push2_python.constants.BUTTON_RECORD:
            self.app.shepherd_interface.global_record()
            return True  # Prevent other modes to get this event

        elif button_name == push2_python.constants.BUTTON_METRONOME:
            self.app.shepherd_interface.metronome_on_off()
            return True  # Prevent other modes to get this event

        elif button_name == push2_python.constants.BUTTON_DUPLICATE:
            self.app.shepherd_interface.scene_duplicate(self.app.shepherd_interface.get_selected_scene())
            return True  # Prevent other modes to get this event

    def on_button_released_raw(self, button_name):
        if button_name == self.clear_clip_button:
            self.clear_clip_button_being_pressed = False
            return True  # Prevent other modes to get this event
        elif button_name == self.double_clip_button:
            self.double_clip_button_being_pressed = False
            return True  # Prevent other modes to get this event

    def on_encoder_rotated(self, encoder_name, increment):
        if encoder_name == push2_python.constants.ENCODER_TEMPO_ENCODER:
            new_bpm = int(self.app.shepherd_interface.get_bpm()) + increment * 2
            self.app.shepherd_interface.set_bpm(new_bpm)
            return True  # Prevent other modes to get this event

    def on_pad_pressed_raw(self, pad_n, pad_ij, velocity):

        if not self.clear_clip_button_being_pressed and not self.double_clip_button_being_pressed:
            # Send clip play/stop in shepherd
            self.app.shepherd_interface.clip_play_stop(pad_ij[1], pad_ij[0])
        else:
            if self.clear_clip_button_being_pressed:
                # Send clip clear in shepherd
                self.app.shepherd_interface.clip_clear(pad_ij[1], pad_ij[0])
            elif self.double_clip_button_being_pressed:
                # Send clip double in shepherd
                self.app.shepherd_interface.clip_double(pad_ij[1], pad_ij[0])
