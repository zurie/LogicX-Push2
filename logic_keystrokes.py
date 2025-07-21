import json
from pathlib import Path
from pynput.keyboard import Key, Controller

keyboard = Controller()

DEBUG_LOGS = True

KEY_LOOKUP = {
    'ctrl': Key.ctrl,
    'alt': Key.alt,
    'cmd': Key.cmd,
    'shift': Key.shift,
    'delete': Key.delete,
    'space': Key.space,
    'enter': Key.enter,
    'tab': Key.tab,
    'up': Key.up,
    'down': Key.down,
    'left': Key.left,
    'right': Key.right,
    'escape': Key.esc
}

CONFIG_PATH = Path("push2_keymap.json")
MODIFIER_KEYS = {}
SPECIAL_KEYS = {}
COMMANDS = {}
CONFIG_MTIME = None


def load_config():
    global MODIFIER_KEYS, SPECIAL_KEYS, COMMANDS, CONFIG_MTIME
    if not CONFIG_PATH.exists():
        print(f"[ERROR] Config file not found: {CONFIG_PATH.resolve()}")
        return

    mtime = CONFIG_PATH.stat().st_mtime
    if CONFIG_MTIME is not None and mtime == CONFIG_MTIME:
        return
    CONFIG_MTIME = mtime

    with CONFIG_PATH.open() as f:
        config = json.load(f)

    MODIFIER_KEYS.clear()
    SPECIAL_KEYS.clear()
    COMMANDS.clear()

    for symbol, name in config.get("modifiers", {}).items():
        MODIFIER_KEYS[symbol] = KEY_LOOKUP.get(name.lower())

    for name, mapped in config.get("special_keys", {}).items():
        SPECIAL_KEYS[name.lower()] = KEY_LOOKUP.get(mapped.lower(), mapped)

    COMMANDS.update(config.get("commands", {}))


CHARACTER_ALIASES = {
    "backslash": "\\",
    "slash": "/",
    "pipe": "|",
    "tilde": "~"
}


def press_keybinding(binding):
    load_config()

    if not binding:
        print("[WARN] Empty binding")
        return

    lower = binding.lower()
    if lower in SPECIAL_KEYS:
        key = SPECIAL_KEYS[lower]
        key = CHARACTER_ALIASES.get(key, key)
        keyboard.press(key)
        keyboard.release(key)
        if DEBUG_LOGS:
            print(f"[DEBUG] Pressing special key: {key}")
        return

    modifiers = []
    i = 0
    while i < len(binding) and binding[i] in MODIFIER_KEYS:
        mod = MODIFIER_KEYS[binding[i]]
        if mod:
            modifiers.append(mod)
        i += 1

    key = binding[i:].lower()
    if not key:
        print(f"[WARN] No key after modifiers in: {binding}")
        return

    main_key = SPECIAL_KEYS.get(key, key)
    main_key = CHARACTER_ALIASES.get(main_key, main_key)

    if DEBUG_LOGS:
        print(f"[DEBUG] Pressing modifiers: {[str(m) for m in modifiers]}")
        print(f"[DEBUG] Pressing main key: {main_key}")

    for mod in modifiers:
        keyboard.press(mod)
    keyboard.press(main_key)
    keyboard.release(main_key)
    for mod in reversed(modifiers):
        keyboard.release(mod)


def press_command(osc_path, shift=False, loop=False, quantize=False, select=False):
    load_config()
    key = osc_path
    suffixes = []
    if shift:
        suffixes.append("shift")
    if loop:
        suffixes.append("loop")
    if quantize:
        suffixes.append("quantize")
    if select:
        suffixes.append("select")
    if suffixes:
        key += "_" + "_".join(suffixes)
    binding = COMMANDS.get(key)
    if binding:
        press_keybinding(binding)
    else:
        print(f"[WARN] No keybinding found for: {key}")
