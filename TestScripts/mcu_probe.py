#!/usr/bin/env python3
# mcu_probe.py
# -----------------------------------------------------------------------------
# Sniff Mackie Control (MCU) MIDI traffic in both directions.
# Prints human-friendly summaries, optional CSV, and attempts basic Mackie SysEx
# decoding (manufacturer 00 00 66). Tested on Python 3.9 + mido + python-rtmidi.
#
# Quick start (Maschine Mackie template):
#   1) In NI Controller Editor: load the "Mackie Control" template.
#   2) In Logic Pro > Control Surfaces > Setup: add "Mackie Control".
#      - Input:  Maschine Controller Virtual Input
#      - Output: Maschine Controller Virtual Output
#   3) Run:
#      python3 mcu_probe.py --auto maschine
#      (or) python3 mcu_probe.py --in "Maschine Controller Virtual Output" \
#                                 --in "Maschine Controller Virtual Input" \
#                                 --csv mcu_log.csv --log mcu_log.txt
#
# For IAC-based rigs:
#      python3 mcu_probe.py --auto iac
#
# Notes:
# - You can pass multiple --in arguments; we'll open and tag each input port.
# - "Virtual Output" (from controller) == what the controller sends to Logic.
# - "Virtual Input"  (to controller)   == what Logic sends back (LEDs, SysEx).
# -----------------------------------------------------------------------------
import argparse
import csv
import datetime as dt
import mido
import sys
import threading
import time
from typing import List, Optional

# -------- Pretty helpers ------------------------------------------------------
def ts() -> str:
    return dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]

def hex_bytes(data: List[int]) -> str:
    return ' '.join(f'{b:02X}' for b in data)

def rel_from_65_63(value: int) -> Optional[int]:
    """Convert 7-bit relative value (65..127 = inc, 63..1 = dec) to signed delta.
    Returns None if value == 64 (no move)."""
    if value == 64:
        return 0
    if value > 64:
        return value - 64  # +1..+63
    if value < 64:
        return value - 64  # -63..-1
    return None

def describe(msg: mido.Message) -> str:
    """Human-ish one-liner for common MCU-ish messages."""
    if msg.type in ('note_on', 'note_off'):
        vel = getattr(msg, 'velocity', 0)
        return f'{msg.type} ch={msg.channel+1} note={msg.note} vel={vel}'
    if msg.type == 'control_change':
        delta = rel_from_65_63(msg.value)
        if delta:
            return f'cc ch={msg.channel+1} cc={msg.control} val={msg.value} (Δ={delta})'
        return f'cc ch={msg.channel+1} cc={msg.control} val={msg.value}'
    if msg.type in ('pitchwheel', 'pitchbend'):
        # mido uses "pitchwheel"
        val14 = msg.pitch  # -8192..+8191
        return f'pitchbend ch={msg.channel+1} pitch={val14:+d}'
    if msg.type == 'aftertouch':
        return f'aftertouch ch={msg.channel+1} value={msg.value}'
    if msg.type == 'polytouch':
        return f'polytouch ch={msg.channel+1} note={msg.note} value={msg.value}'
    if msg.type == 'sysex':
        return decode_sysex(msg.data)
    return str(msg)

def decode_sysex(data: List[int]) -> str:
    """Best-effort Mackie Control SysEx decoding.
    Format we commonly see: F0 00 00 66 14 <cmd> [payload...] F7
    We don't claim full coverage—prints cmd & payload length/bytes.
    """
    if len(data) >= 5 and data[0:3] == [0x00, 0x00, 0x66]:
        model = data[3] if len(data) > 3 else None
        cmd   = data[4] if len(data) > 4 else None
        payload = data[5:]
        return (f'MACKIE-SYSEX model=0x{model:02X} cmd=0x{cmd:02X} '
                f'len={len(payload)} data=[{hex_bytes(payload)}]')
    # Unknown vendor; just dump
    return f'SYSEX vendor=[{hex_bytes(data[:3])}] data=[{hex_bytes(data[3:])}]'

# -------- Logging sink --------------------------------------------------------
class Sink:
    def __init__(self, csv_path: Optional[str], log_path: Optional[str]):
        self.csv_path = csv_path
        self.log_path = log_path
        self.csv_lock = threading.Lock()
        self.txt_lock = threading.Lock()
        self.csv_file = None
        self.csv_writer = None
        if csv_path:
            self.csv_file = open(csv_path, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(['time', 'port', 'direction', 'raw_type', 'channel', 'data', 'pretty'])
        if log_path:
            # Truncate
            open(log_path, 'w').close()

    def write(self, port_name: str, direction: str, msg: mido.Message):
        t = ts()
        # Pretty
        pretty = describe(msg)
        # Raw "data" string
        raw_dict = msg.dict()
        channel = raw_dict.get('channel', None)
        # Compose raw data repr
        if msg.type == 'sysex':
            raw_data = f'F0 {hex_bytes(msg.data)} F7'
        else:
            raw_data = raw_dict

        line = f'[{t}] {direction:<6} {port_name} :: {pretty}'
        with self.txt_lock:
            if self.log_path:
                with open(self.log_path, 'a') as f:
                    f.write(line + '\n')
        print(line)

        if self.csv_writer:
            with self.csv_lock:
                self.csv_writer.writerow([t, port_name, direction, msg.type, channel, str(raw_data), pretty])

    def close(self):
        if self.csv_file:
            self.csv_file.close()

# -------- Port selection ------------------------------------------------------
def auto_select(kind: str) -> List[str]:
    """Return a good default list of input ports to open depending on rig.
    kind in {"maschine","iac"}."""
    names = mido.get_input_names()
    wanted: List[str] = []
    if kind.lower() == 'maschine':
        for s in names:
            if 'Maschine' in s and ('Virtual Input' in s or 'Virtual Output' in s):
                wanted.append(s)
    elif kind.lower() == 'iac':
        for s in names:
            if 'IAC Driver LogicMCU' in s:
                wanted.append(s)
    return wanted

# -------- Worker --------------------------------------------------------------
def listen(port_name: str, sink: Sink):
    # Heuristic: treat "Virtual Output" as controller->DAW (OUT of controller),
    #            "Virtual Input"  as DAW->controller (IN to controller).
    if 'Virtual Output' in port_name or port_name.endswith('_Out'):
        direction = 'CTRL→DAW'
    elif 'Virtual Input' in port_name or port_name.endswith('_In'):
        direction = 'DAW→CTRL'
    else:
        direction = 'IN'
    try:
        with mido.open_input(port_name) as port:
            for msg in port:
                sink.write(port_name, direction, msg)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'!! Error opening/reading "{port_name}": {e}', file=sys.stderr)

# -------- Main ----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description='Sniff Mackie Control MIDI traffic.')
    ap.add_argument('--in', dest='ins', action='append', default=[],
                    help='Input port to sniff (can be passed multiple times).')
    ap.add_argument('--auto', choices=['maschine', 'iac'],
                    help='Auto-select typical ports for Maschine or IAC rigs.')
    ap.add_argument('--csv', help='Write CSV log to this path.')
    ap.add_argument('--log', help='Write plain-text log to this path.')
    args = ap.parse_args()

    ins: List[str] = list(args.ins)

    if args.auto and not ins:
        ins = auto_select(args.auto)

    if not ins:
        print('No input ports selected. Use --auto maschine|iac or --in "Port Name"')
        print('\nAvailable inputs:')
        for name in mido.get_input_names():
            print('  -', name)
        sys.exit(1)

    sink = Sink(csv_path=args.csv, log_path=args.log)
    print('Listening on:')
    for p in ins:
        print('  -', p)
    print('Press Ctrl+C to stop.\n')

    threads = []
    for p in ins:
        t = threading.Thread(target=listen, args=(p, sink), daemon=True)
        t.start()
        threads.append(t)

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        sink.close()

if __name__ == '__main__':
    main()
