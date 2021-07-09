from operator import index

import definitions
import push2_python.constants
import os
import json


class HelpMode(definitions.LogicMode):
    help_docs = []
    selected_track = 0

    current_page = 0
    n_pages = 1
    up_button = push2_python.constants.BUTTON_UP
    down_button = push2_python.constants.BUTTON_DOWN
    left_button = push2_python.constants.BUTTON_LEFT
    right_button = push2_python.constants.BUTTON_RIGHT

    buttons_used = [
        up_button,
        down_button,
        left_button,
        right_button
    ]

    def initialize(self, settings=None):
        self.load_help()

    def move_to_next_page(self):
        self.app.buttons_need_update = True
        self.current_page += 1
        if self.current_page >= self.n_pages:
            self.current_page = 0
            return True  # Return true because page rotation finished
        return False

    def activate(self):
        self.current_page = 0
        self.update_buttons()

    def deactivate(self):
        definitions.help_title = definitions.help_hotkey = definitions.help_path = definitions.help_description = definitions.help_color = None
        self.app.help_time = 0

    def update_buttons(self):
        if self.current_page == 0:  # Performance settings
            pass

    def load_help(self):
        if os.path.exists('button_docs.json'):
            help_data = json.load(open('button_docs.json'))
        else:
            help_data = {}

        # Iterating through the json
        # list
        for j, i in enumerate(help_data['help_docs']):
            self.help_docs.append({
                'button': i.get('button'),
                'title': i.get('title'),
                'hotkey': i.get('hotkey'),
                'path': i.get('path'),
                'description': i.get('description'),
            })

    def on_button_pressed_raw(self, button_name):
        if self.current_page == 0:  # Performance settings
            self.show_help(button_name)
            # self.app.add_display_help("{0}".format(self.help_docs[0]['title']))

    def show_help(self, button_name):
        print(button_name)
        for j, i in enumerate(self.help_docs):
            if self.help_docs[j]['button'] == button_name:
                self.app.add_display_help(self.help_docs[j]['title'],
                                          self.help_docs[j]['hotkey'],
                                          self.help_docs[j]['path'],
                                          self.help_docs[j]['description'],
                                          self.app.track_selection_mode.get_current_track_color())
