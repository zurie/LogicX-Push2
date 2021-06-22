import definitions
import mido
import push2_python
import time
import math
import json
import os

from definitions import PyshaMode
from display_utils import show_text


NAME_STRING_1 = 'String\n1'
NAME_STRING_2 = 'String\n2'
NAME_STRING_3 = 'String\n3'
NAME_STRING_4 = 'String\n4'
NAME_BRASS_1 = 'Brass\n1'
NAME_BRASS_2 = 'Brass\n2'
NAME_BRASS_3 = 'Brass\n3'
NAME_FLUTE = 'Flute'
NAME_ELECTRIC_PIANO = 'Electric\nPiano'
NAME_BASS = 'Bass'
NAME_CLAVI_1 = 'Clavi-\nChord\n1'
NAME_CLAVI_2 = 'Clavi-\nChord\n2'
NAME_HARPSI_1 = 'Harpsi-\nChord\n1'
NAME_HARPSI_2 = 'Harpsi-\nChord\n2'
NAME_ORGAN_1 = 'Organ\n1'
NAME_ORGAN_2 = 'Organ\n2'
NAME_GUITAR_1 = 'Guitar\n1'
NAME_GUITAR_2 = 'Guitar\n2'
NAME_FUNKY_1 = 'Funky\n1'
NAME_FUNKY_2 = 'Funky\n2'
NAME_FUNKY_3 = 'Funky\n3'
NAME_FUNKY_4 = 'Funky\n4'

DDRM_DEVICE_NAME = "DDRM"

tone_selector_values = {  # (MIDI CC for upper row, MIDI CC for lower row, MIDI value)
    NAME_BASS: [(40, 67, 0),
                (41, 68, 0),
                (42, 69, 55),
                (43, 71, 2),
                (44, 70, 1),
                (45, 72, 0),
                (46, 73, 0),
                (47, 119, 126),
                (48, 75, 34),
                (49, 76, 86),
                (50, 77, 26),
                (51, 78, 74),
                (52, 79, 13),
                (53, 80, 29),
                (54, 81, 71),
                (55, 82, 127),
                (56, 83, 0),
                (57, 84, 28),
                (58, 85, 92),
                (59, 86, 0),
                (60, 87, 41),
                (61, 88, 32),
                (62, 89, 86),
                (63, 90, 67),
                (65, 91, 0),
                (66, 92, 31)],
    NAME_BRASS_1: [(40, 67, 0),
                   (41, 68, 0),
                   (42, 69, 0),
                   (43, 71, 127),
                   (44, 70, 1),
                   (45, 72, 0),
                   (46, 73, 0),
                   (47, 119, 0),
                   (48, 75, 48),
                   (49, 76, 4),
                   (50, 77, 70),
                   (51, 78, 57),
                   (52, 79, 84),
                   (53, 80, 63),
                   (54, 81, 48),
                   (55, 82, 127),
                   (56, 83, 0),
                   (57, 84, 59),
                   (58, 85, 127),
                   (59, 86, 125),
                   (60, 87, 32),
                   (61, 88, 0),
                   (62, 89, 47),
                   (63, 90, 126),
                   (65, 91, 92),
                   (66, 92, 107)],
    NAME_BRASS_2: [(40, 67, 0),
                   (41, 68, 0),
                   (42, 69, 0),
                   (43, 71, 127),
                   (44, 70, 1),
                   (45, 72, 0),
                   (46, 73, 0),
                   (47, 119, 0),
                   (48, 75, 46),
                   (49, 76, 21),
                   (50, 77, 109),
                   (51, 78, 57),
                   (52, 79, 83),
                   (53, 80, 97),
                   (54, 81, 51),
                   (55, 82, 127),
                   (56, 83, 0),
                   (57, 84, 72),
                   (58, 85, 102),
                   (59, 86, 111),
                   (60, 87, 13),
                   (61, 88, 30),
                   (62, 89, 51),
                   (63, 90, 0),
                   (65, 91, 93),
                   (66, 92, 126)],
    NAME_BRASS_3: [(40, 67, 0),
                   (41, 68, 0),
                   (42, 69, 0),
                   (43, 71, 127),
                   (44, 70, 1),
                   (45, 72, 0),
                   (46, 73, 22),
                   (47, 119, 0),
                   (48, 75, 39),
                   (49, 76, 59),
                   (50, 77, 77),
                   (51, 78, 86),
                   (52, 79, 54),
                   (53, 80, 43),
                   (54, 81, 62),
                   (55, 82, 127),
                   (56, 83, 0),
                   (57, 84, 59),
                   (58, 85, 63),
                   (59, 86, 57),
                   (60, 87, 36),
                   (61, 88, 27),
                   (62, 89, 52),
                   (63, 90, 99),
                   (65, 91, 108),
                   (66, 92, 122)],
    NAME_CLAVI_1: [(40, 67, 0),
                   (41, 68, 0),
                   (42, 69, 111),
                   (43, 71, 1),
                   (44, 70, 126),
                   (45, 72, 0),
                   (46, 73, 61),
                   (47, 119, 64),
                   (48, 75, 44),
                   (49, 76, 56),
                   (50, 77, 42),
                   (51, 78, 45),
                   (52, 79, 23),
                   (53, 80, 86),
                   (54, 81, 30),
                   (55, 82, 127),
                   (56, 83, 0),
                   (57, 84, 0),
                   (58, 85, 78),
                   (59, 86, 47),
                   (60, 87, 0),
                   (61, 88, 0),
                   (62, 89, 80),
                   (63, 90, 127),
                   (65, 91, 0),
                   (66, 92, 0)],
    NAME_CLAVI_2: [(40, 67, 0),
                   (41, 68, 0),
                   (42, 69, 126),
                   (43, 71, 0),
                   (44, 70, 1),
                   (45, 72, 0),
                   (46, 73, 19),
                   (47, 119, 0),
                   (48, 75, 23),
                   (49, 76, 42),
                   (50, 77, 0),
                   (51, 78, 127),
                   (52, 79, 14),
                   (53, 80, 62),
                   (54, 81, 58),
                   (55, 82, 127),
                   (56, 83, 0),
                   (57, 84, 0),
                   (58, 85, 63),
                   (59, 86, 49),
                   (60, 87, 31),
                   (61, 88, 0),
                   (62, 89, 67),
                   (63, 90, 127),
                   (65, 91, 0),
                   (66, 92, 0)],
    NAME_ELECTRIC_PIANO: [(40, 67, 0),
                          (41, 68, 0),
                          (42, 69, 53),
                          (43, 71, 0),
                          (44, 70, 126),
                          (45, 72, 0),
                          (46, 73, 0),
                          (47, 119, 0),
                          (48, 75, 35),
                          (49, 76, 19),
                          (50, 77, 75),
                          (51, 78, 76),
                          (52, 79, 0),
                          (53, 80, 63),
                          (54, 81, 56),
                          (55, 82, 126),
                          (56, 83, 0),
                          (57, 84, 0),
                          (58, 85, 65),
                          (59, 86, 65),
                          (60, 87, 64),
                          (61, 88, 0),
                          (62, 89, 53),
                          (63, 90, 126),
                          (65, 91, 0),
                          (66, 92, 121)],
    NAME_FLUTE: [(40, 67, 0),
                 (41, 68, 0),
                 (42, 69, 0),
                 (43, 71, 127),
                 (44, 70, 0),
                 (45, 72, 0),
                 (46, 73, 0),
                 (47, 119, 0),
                 (48, 75, 46),
                 (49, 76, 19),
                 (50, 77, 0),
                 (51, 78, 43),
                 (52, 79, 85),
                 (53, 80, 89),
                 (54, 81, 20),
                 (55, 82, 127),
                 (56, 83, 0),
                 (57, 84, 56),
                 (58, 85, 127),
                 (59, 86, 127),
                 (60, 87, 17),
                 (61, 88, 18),
                 (62, 89, 35),
                 (63, 90, 99),
                 (65, 91, 41),
                 (66, 92, 126)],
    NAME_FUNKY_1: [(40, 67, 62),
                   (41, 68, 20),
                   (42, 69, 89),
                   (43, 71, 0),
                   (44, 70, 0),
                   (45, 72, 0),
                   (46, 73, 18),
                   (47, 119, 126),
                   (48, 75, 19),
                   (49, 76, 126),
                   (50, 77, 126),
                   (51, 78, 86),
                   (52, 79, 0),
                   (53, 80, 16),
                   (54, 81, 56),
                   (55, 82, 126),
                   (56, 83, 0),
                   (57, 84, 20),
                   (58, 85, 127),
                   (59, 86, 126),
                   (60, 87, 0),
                   (61, 88, 35),
                   (62, 89, 126),
                   (63, 90, 126),
                   (65, 91, 126),
                   (66, 92, 126)],
    NAME_FUNKY_2: [(40, 67, 0),
                   (41, 68, 0),
                   (42, 69, 0),
                   (43, 71, 126),
                   (44, 70, 1),
                   (45, 72, 0),
                   (46, 73, 39),
                   (47, 119, 65),
                   (48, 75, 21),
                   (49, 76, 108),
                   (50, 77, 126),
                   (51, 78, 126),
                   (52, 79, 57),
                   (53, 80, 52),
                   (54, 81, 0),
                   (55, 82, 126),
                   (56, 83, 0),
                   (57, 84, 0),
                   (58, 85, 60),
                   (59, 86, 54),
                   (60, 87, 0),
                   (61, 88, 40),
                   (62, 89, 50),
                   (63, 90, 126),
                   (65, 91, 0),
                   (66, 92, 113)],
    NAME_FUNKY_3: [(40, 67, 83),
                   (41, 68, 22),
                   (42, 69, 49),
                   (43, 71, 0),
                   (44, 70, 126),
                   (45, 72, 0),
                   (46, 73, 18),
                   (47, 119, 126),
                   (48, 75, 5),
                   (49, 76, 126),
                   (50, 77, 126),
                   (51, 78, 102),
                   (52, 79, 124),
                   (53, 80, 98),
                   (54, 81, 50),
                   (55, 82, 126),
                   (56, 83, 81),
                   (57, 84, 20),
                   (58, 85, 127),
                   (59, 86, 126),
                   (60, 87, 0),
                   (61, 88, 35),
                   (62, 89, 126),
                   (63, 90, 126),
                   (65, 91, 85),
                   (66, 92, 126)],
    NAME_GUITAR_1: [(40, 67, 0),
                    (41, 68, 0),
                    (42, 69, 80),
                    (43, 71, 1),
                    (44, 70, 127),
                    (45, 72, 0),
                    (46, 73, 52),
                    (47, 119, 63),
                    (48, 75, 66),
                    (49, 76, 73),
                    (50, 77, 56),
                    (51, 78, 42),
                    (52, 79, 17),
                    (53, 80, 42),
                    (54, 81, 46),
                    (55, 82, 126),
                    (56, 83, 0),
                    (57, 84, 0),
                    (58, 85, 70),
                    (59, 86, 28),
                    (60, 87, 43),
                    (61, 88, 14),
                    (62, 89, 50),
                    (63, 90, 126),
                    (65, 91, 14),
                    (66, 92, 126)],
    NAME_GUITAR_2: [(40, 67, 0),
                    (41, 68, 0),
                    (42, 69, 30),
                    (43, 71, 126),
                    (44, 70, 1),
                    (45, 72, 0),
                    (46, 73, 39),
                    (47, 119, 126),
                    (48, 75, 32),
                    (49, 76, 108),
                    (50, 77, 89),
                    (51, 78, 126),
                    (52, 79, 11),
                    (53, 80, 92),
                    (54, 81, 37),
                    (55, 82, 126),
                    (56, 83, 0),
                    (57, 84, 0),
                    (58, 85, 95),
                    (59, 86, 24),
                    (60, 87, 14),
                    (61, 88, 17),
                    (62, 89, 23),
                    (63, 90, 126),
                    (65, 91, 0),
                    (66, 92, 126)],
    NAME_HARPSI_1: [(40, 67, 0),
                    (41, 68, 0),
                    (42, 69, 99),
                    (43, 71, 1),
                    (44, 70, 126),
                    (45, 72, 0),
                    (46, 73, 81),
                    (47, 119, 48),
                    (48, 75, 77),
                    (49, 76, 30),
                    (50, 77, 0),
                    (51, 78, 0),
                    (52, 79, 17),
                    (53, 80, 0),
                    (54, 81, 0),
                    (55, 82, 127),
                    (56, 83, 0),
                    (57, 84, 0),
                    (58, 85, 73),
                    (59, 86, 15),
                    (60, 87, 20),
                    (61, 88, 0),
                    (62, 89, 0),
                    (63, 90, 126),
                    (65, 91, 0),
                    (66, 92, 0)],
    NAME_HARPSI_2: [(40, 67, 0),
                    (41, 68, 0),
                    (42, 69, 100),
                    (43, 71, 2),
                    (44, 70, 126),
                    (45, 72, 0),
                    (46, 73, 64),
                    (47, 119, 0),
                    (48, 75, 79),
                    (49, 76, 0),
                    (50, 77, 0),
                    (51, 78, 0),
                    (52, 79, 13),
                    (53, 80, 0),
                    (54, 81, 0),
                    (55, 82, 127),
                    (56, 83, 0),
                    (57, 84, 0),
                    (58, 85, 75),
                    (59, 86, 3),
                    (60, 87, 0),
                    (61, 88, 31),
                    (62, 89, 0),
                    (63, 90, 53),
                    (65, 91, 0),
                    (66, 92, 0)],
    NAME_ORGAN_1: [(40, 67, 0),
                   (41, 68, 0),
                   (42, 69, 0),
                   (43, 71, 127),
                   (44, 70, 1),
                   (45, 72, 0),
                   (46, 73, 54),
                   (47, 119, 126),
                   (48, 75, 60),
                   (49, 76, 60),
                   (50, 77, 0),
                   (51, 78, 0),
                   (52, 79, 14),
                   (53, 80, 0),
                   (54, 81, 0),
                   (55, 82, 127),
                   (56, 83, 0),
                   (57, 84, 0),
                   (58, 85, 0),
                   (59, 86, 127),
                   (60, 87, 0),
                   (61, 88, 126),
                   (62, 89, 0),
                   (63, 90, 0),
                   (65, 91, 0),
                   (66, 92, 126)],
    NAME_ORGAN_2: [(40, 67, 0),
                   (41, 68, 0),
                   (42, 69, 0),
                   (43, 71, 1),
                   (44, 70, 127),
                   (45, 72, 0),
                   (46, 73, 0),
                   (47, 119, 0),
                   (48, 75, 64),
                   (49, 76, 127),
                   (50, 77, 0),
                   (51, 78, 0),
                   (52, 79, 0),
                   (53, 80, 0),
                   (54, 81, 0),
                   (55, 82, 127),
                   (56, 83, 0),
                   (57, 84, 0),
                   (58, 85, 23),
                   (59, 86, 38),
                   (60, 87, 0),
                   (61, 88, 127),
                   (62, 89, 0),
                   (63, 90, 0),
                   (65, 91, 0),
                   (66, 92, 126)],
    NAME_STRING_1: [(40, 67, 0),
                    (41, 68, 0),
                    (42, 69, 0),
                    (43, 71, 126),
                    (44, 70, 0),
                    (45, 72, 0),
                    (46, 73, 70),
                    (47, 119, 73),
                    (48, 75, 84),
                    (49, 76, 80),
                    (50, 77, 80),
                    (51, 78, 79),
                    (52, 79, 78),
                    (53, 80, 66),
                    (54, 81, 19),
                    (55, 82, 127),
                    (56, 83, 0),
                    (57, 84, 85),
                    (58, 85, 127),
                    (59, 86, 88),
                    (60, 87, 0),
                    (61, 88, 24),
                    (62, 89, 59),
                    (63, 90, 126),
                    (65, 91, 0),
                    (66, 92, 0)],
    NAME_STRING_2: [(40, 67, 0),
                    (41, 68, 0),
                    (42, 69, 0),
                    (43, 71, 127),
                    (44, 70, 2),
                    (45, 72, 0),
                    (46, 73, 57),
                    (47, 119, 0),
                    (48, 75, 126),
                    (49, 76, 0),
                    (50, 77, 0),
                    (51, 78, 0),
                    (52, 79, 0),
                    (53, 80, 0),
                    (54, 81, 0),
                    (55, 82, 127),
                    (56, 83, 0),
                    (57, 84, 35),
                    (58, 85, 127),
                    (59, 86, 127),
                    (60, 87, 34),
                    (61, 88, 0),
                    (62, 89, 0),
                    (63, 90, 37),
                    (65, 91, 0),
                    (66, 92, 126)],
    NAME_STRING_3: [(40, 67, 0),
                    (41, 68, 0),
                    (42, 69, 0),
                    (43, 71, 127),
                    (44, 70, 0),
                    (45, 72, 0),
                    (46, 73, 0),
                    (47, 119, 0),
                    (48, 75, 99),
                    (49, 76, 0),
                    (50, 77, 0),
                    (51, 78, 0),
                    (52, 79, 14),
                    (53, 80, 0),
                    (54, 81, 0),
                    (55, 82, 127),
                    (56, 83, 0),
                    (57, 84, 98),
                    (58, 85, 79),
                    (59, 86, 126),
                    (60, 87, 52),
                    (61, 88, 57),
                    (62, 89, 0),
                    (63, 90, 106),
                    (65, 91, 0),
                    (66, 92, 126)],
    NAME_STRING_4: [(40, 67, 0),
                    (41, 68, 0),
                    (42, 69, 0),
                    (43, 71, 127),
                    (44, 70, 2),
                    (45, 72, 0),
                    (46, 73, 57),
                    (47, 119, 10),
                    (48, 75, 73),
                    (49, 76, 0),
                    (50, 77, 49),
                    (51, 78, 49),
                    (52, 79, 53),
                    (53, 80, 83),
                    (54, 81, 50),
                    (55, 82, 127),
                    (56, 83, 0),
                    (57, 84, 69),
                    (58, 85, 86),
                    (59, 86, 127),
                    (60, 87, 46),
                    (61, 88, 36),
                    (62, 89, 44),
                    (63, 90, 20),
                    (65, 91, 65),
                    (66, 92, 126)]}


class DDRMToneSelectorMode(PyshaMode):

    upper_row_button_names = [
        push2_python.constants.BUTTON_UPPER_ROW_1,
        push2_python.constants.BUTTON_UPPER_ROW_2,
        push2_python.constants.BUTTON_UPPER_ROW_3,
        push2_python.constants.BUTTON_UPPER_ROW_4,
        push2_python.constants.BUTTON_UPPER_ROW_5,
        push2_python.constants.BUTTON_UPPER_ROW_6,
        push2_python.constants.BUTTON_UPPER_ROW_7,
        push2_python.constants.BUTTON_UPPER_ROW_8
    ]

    lower_row_button_names = [
        push2_python.constants.BUTTON_LOWER_ROW_1,
        push2_python.constants.BUTTON_LOWER_ROW_2,
        push2_python.constants.BUTTON_LOWER_ROW_3,
        push2_python.constants.BUTTON_LOWER_ROW_4,
        push2_python.constants.BUTTON_LOWER_ROW_5,
        push2_python.constants.BUTTON_LOWER_ROW_6,
        push2_python.constants.BUTTON_LOWER_ROW_7,
        push2_python.constants.BUTTON_LOWER_ROW_8
    ]

    button_left = push2_python.constants.BUTTON_PAGE_LEFT
    button_right = push2_python.constants.BUTTON_PAGE_RIGHT

    used_buttons = upper_row_button_names + lower_row_button_names + [button_left, button_right]

    upper_row_names = [
        NAME_STRING_1,
        NAME_STRING_3,
        NAME_BRASS_1,
        NAME_FLUTE,
        NAME_ELECTRIC_PIANO,
        NAME_CLAVI_1,
        NAME_HARPSI_1,
        NAME_ORGAN_1,
        NAME_GUITAR_1,
        NAME_FUNKY_1,
        NAME_FUNKY_3,
    ]

    lower_row_names = [
        NAME_STRING_2,
        NAME_STRING_4,
        NAME_BRASS_2,
        NAME_BRASS_3,
        NAME_BASS,
        NAME_CLAVI_2,
        NAME_HARPSI_2,
        NAME_ORGAN_2,
        NAME_GUITAR_2,
        NAME_FUNKY_2,
        #NAME_FUNKY_4
    ]

    colors = {
        NAME_STRING_1: definitions.YELLOW,
        NAME_STRING_3: definitions.YELLOW,
        NAME_BRASS_1: definitions.RED,
        NAME_FLUTE: definitions.WHITE,
        NAME_ELECTRIC_PIANO: definitions.YELLOW,
        NAME_CLAVI_1: definitions.YELLOW,
        NAME_HARPSI_1: definitions.YELLOW,
        NAME_ORGAN_1: definitions.WHITE,
        NAME_GUITAR_1: definitions.YELLOW,
        NAME_FUNKY_1: definitions.GREEN,
        NAME_FUNKY_3: definitions.GREEN,
        NAME_STRING_2: definitions.YELLOW,
        NAME_STRING_4: definitions.YELLOW,
        NAME_BRASS_2: definitions.RED,
        NAME_BRASS_3: definitions.RED,
        NAME_BASS: definitions.WHITE,
        NAME_CLAVI_2: definitions.YELLOW,
        NAME_HARPSI_2: definitions.YELLOW,
        NAME_ORGAN_2: definitions.WHITE,
        NAME_GUITAR_2: definitions.YELLOW,
        NAME_FUNKY_2: definitions.GREEN,
        NAME_FUNKY_4: definitions.GREEN
    }

    font_colors = {
        definitions.YELLOW: definitions.BLACK,
        definitions.RED: definitions.WHITE,
        definitions.WHITE: definitions.BLACK,
        definitions.GREEN: definitions.WHITE
    }

    page_n = 0
    upper_row_selected = ''
    lower_row_selected = ''
    inter_message_message_min_time_ms = 4  # ms wait time after each message to DDRM
    send_messages_double = False  # This is a workaround for a DDRM bug that will ignore single CC messages. We'll send 2 messages in a row for the same control with slightly different values

    def should_be_enabled(self):
        return self.app.track_selection_mode.get_current_track_instrument_short_name() == DDRM_DEVICE_NAME

    def get_should_show_next_prev(self):
        show_prev = self.page_n == 1
        show_next = self.page_n == 0
        return show_prev, show_next

    def send_lower_row(self):
        if self.lower_row_selected in tone_selector_values:
            for _, midi_cc, midi_val in tone_selector_values[self.lower_row_selected]:
                if self.send_messages_double:
                    values_to_send = [(midi_val + 1) % 128, midi_val]
                else:
                    values_to_send = [midi_val]
                for val in values_to_send:
                    msg = mido.Message('control_change', control=midi_cc, value=val)  # Should we subtract 1 from midi_cc because mido being 0-indexed?
                    self.app.send_midi(msg)
                    if self.inter_message_message_min_time_ms:
                        time.sleep(self.inter_message_message_min_time_ms*1.0/1000)

    def send_upper_row(self):
        if self.upper_row_selected in tone_selector_values:
            for midi_cc, _, midi_val in tone_selector_values[self.upper_row_selected]:
                if self.send_messages_double:
                    values_to_send = [(midi_val + 1) % 128, midi_val]
                else:
                    values_to_send = [midi_val]
                for val in values_to_send:
                    msg = mido.Message('control_change', control=midi_cc, value=val)  # Should we subtract 1 from midi_cc because mido being 0-indexed?
                    self.app.send_midi(msg)
                    if self.inter_message_message_min_time_ms:
                        time.sleep(self.inter_message_message_min_time_ms*1.0/1000)

    def activate(self):
        self.update_buttons()

    def update_buttons(self):
        for count, name in enumerate(self.upper_row_button_names):
            try:
                tone_name = self.upper_row_names[count + self.page_n * 8]
                self.push.buttons.set_button_color(name, self.colors[tone_name])
            except IndexError:
                self.push.buttons.set_button_color(name, definitions.OFF_BTN_COLOR)

        for count, name in enumerate(self.lower_row_button_names):
            try:
                tone_name = self.lower_row_names[count + self.page_n * 8]
                self.push.buttons.set_button_color(name, self.colors[tone_name])
            except IndexError:
                self.push.buttons.set_button_color(name, definitions.OFF_BTN_COLOR)

        show_prev, show_next = self.get_should_show_next_prev()
        self.set_button_color_if_expression(self.button_left, show_prev, definitions.WHITE)
        self.set_button_color_if_expression(self.button_right, show_next, definitions.WHITE)

    def update_display(self, ctx, w, h):
        if not self.app.is_mode_active(self.app.settings_mode):
            # If settings mode is active, don't draw the upper parts of the screen because settings page will
            # "cover them"
            start = self.page_n * 8

            # Draw upper row
            for i, name in enumerate(self.upper_row_names[start:][:8]):
                font_color = self.font_colors[self.colors[name]]
                if name == self.upper_row_selected:
                    background_color = self.colors[name]
                else:
                    background_color = self.colors[name] + '_darker1'
                height = 80
                top_offset = 0
                show_text(ctx, i, top_offset, name.upper(), height=height, font_color=font_color, background_color=background_color,
                          font_size_percentage=0.2, center_vertically=True, center_horizontally=True, rectangle_padding=1)

            # Draw lower row
            for i, name in enumerate(self.lower_row_names[start:][:8]):
                if name != NAME_FUNKY_4:
                    font_color = self.font_colors[self.colors[name]]
                    if name == self.lower_row_selected:
                        background_color = self.colors[name]
                    else:
                        background_color = self.colors[name] + '_darker1'
                    height = 80
                    top_offset = 80
                    show_text(ctx, i, top_offset, name.upper(), height=height,
                              font_color=font_color, background_color=background_color, font_size_percentage=0.2, center_vertically=True, center_horizontally=True, rectangle_padding=1)

    def on_button_pressed(self, button_name, shift=False, select=False, long_press=False, double_press=False):
        if button_name in self.upper_row_button_names:
            start = self.page_n * 8
            button_idx = self.upper_row_button_names.index(button_name)
            try:
                self.upper_row_selected = self.upper_row_names[button_idx + start]
                self.send_upper_row()
            except IndexError:
                # Do nothing because the button has no assigned tone
                pass
            return True

        elif button_name in self.lower_row_button_names:
            start = self.page_n * 8
            button_idx = self.lower_row_button_names.index(button_name)
            try:
                self.lower_row_selected = self.lower_row_names[button_idx + start]
                self.send_lower_row()
            except IndexError:
                # Do nothing because the button has no assigned tone
                pass
            return True

        elif button_name in [self.button_left, self.button_right]:
            show_prev, show_next = self.get_should_show_next_prev()
            if button_name == self.button_left and show_prev:
                self.page_n = 0
            elif button_name == self.button_right and show_next:
                self.page_n = 1
            return True
