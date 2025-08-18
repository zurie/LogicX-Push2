# ui/__init__.py
from .legacy_gui import LegacyGui
from .mackie_gui_v2 import MackieGuiV2


def create_renderer(profile: str, mode) -> "Renderer":
    if profile == "mackie_v2":
        return MackieGuiV2(mode)
    return LegacyGui(mode)  # default
