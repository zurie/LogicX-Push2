#!/usr/bin/env python3
import mido
import threading
import time
import signal
import sys

# ——— CONFIG ——————————————————————————————————————————————————————————————
VPORT_NAME = "Python Mackie"   # Virtual port name; select this in Logic’s Control Surfaces Setup
MODEL_ID   = 0x14              # Logic’s device ID from your SysEx dumps

# ——— SysEx meter commands ———————————————————————————————————————————————————
ENABLE_METERS  = [0x00, 0x00, 0x66, MODEL_ID, 0x12, 0x00, 0x00]
DISABLE_METERS = [0x00, 0x00, 0x66, MODEL_ID, 0x12, 0x00, 0x01]
POLL_PREFIX    = [0x00, 0x00, 0x66, MODEL_ID, 0x20]  # + bank number 0–7

# ——— Mackie inquiry details —————————————————————————————————————————————————
SERIAL    = [ord(c) for c in "MCUPRO "]   # 7-byte ID Logic recognizes
CHALLENGE = [0x10, 0x20, 0x30, 0x40]       # arbitrary 4-byte challenge
INQUIRY   = [0x00, 0x00, 0x66, MODEL_ID, 0x01] + SERIAL + CHALLENGE

# ——— Globals for port & rescan timer —————————————————————————————————————————
vport = None
_rescan_timer = None

# ——— Graceful cleanup —————————————————————————————————————————————————————
def cleanup_and_exit(*_):
    try:
        vport.send(mido.Message('sysex', data=DISABLE_METERS))
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup_and_exit)
signal.signal(signal.SIGTERM, cleanup_and_exit)

# ——— Mackie challenge→response algorithm ———————————————————————————————————
def compute_response(ch):
    l1, l2, l3, l4 = ch
    return [
        (l1 + (l2 ^ 0x0A) - l4)      & 0x7F,
        ((l3 >> 4) ^ (l1 + l4))      & 0x7F,
        (l4 - (l3 << 2) ^ (l1 | l2)) & 0x7F,
        (l2 - l3 + (0xF0 ^ (l4 << 4)))& 0x7F,
        ]

def build_connect_reply(serial, chal):
    return [0x00, 0x00, 0x66, MODEL_ID, 0x02] + serial + compute_response(chal)

# ——— Meter polling helper —————————————————————————————————————————————
def start_meter_polling():
    def poll():
        for bank in range(8):
            vport.send(mido.Message('sysex', data=POLL_PREFIX + [bank]))
        threading.Timer(0.1, poll).start()
    poll()

# ——— Rescan surface every 10s during handshake —————————————————————————————————
def rescan_surface():
    global vport, _rescan_timer
    print("▶ Rescanning Python Mackie surface…")
    try:
        vport.close()
    except:
        pass
    time.sleep(0.5)
    vport = mido.open_ioport(VPORT_NAME, virtual=True)
    print("✅ Virtual port re-created")
    print("▶ Sending Mackie inquiry again…")
    vport.send(mido.Message('sysex', data=INQUIRY))
    # schedule next rescan in 10 seconds
    _rescan_timer = threading.Timer(10, rescan_surface)
    _rescan_timer.start()

# ——— Main script ———————————————————————————————————————————————————————
def main():
    global vport, _rescan_timer

    # set Mido to RTMidi backend
    mido.set_backend('mido.backends.rtmidi')

    # create virtual port
    vport = mido.open_ioport(VPORT_NAME, virtual=True)
    print(f"✅ Virtual port created: {VPORT_NAME!r}")
    print("▶ In Logic Pro: add a Mackie Control surface and set both Input and Output to 'Python Mackie', then restart Logic.")

    # send first inquiry
    print(f"▶ Sending Mackie inquiry: serial={bytes(SERIAL)!r}, challenge={[hex(x) for x in CHALLENGE]}")
    vport.send(mido.Message('sysex', data=INQUIRY))

    # start periodic rescans
    _rescan_timer = threading.Timer(10, rescan_surface)
    _rescan_timer.start()

    # ——— 1) Mackie Control Handshake —————————————————————————————————————
    print("▶ Waiting for Logic’s connect-query…")
    while True:
        msg = vport.receive()
        if msg.type != 'sysex' or len(msg.data) < 16:
            continue
        d = list(msg.data)
        if d[0:3] != [0, 0, 0x66] or d[3] != MODEL_ID:
            continue

        code = d[4]
        if code in (0x01, 0x13):
            serial = d[5:12]
            chal   = d[12:16]
            print(f"   🔑 Query 0x{code:02X}, serial={bytes(serial)!r}, chal={[hex(x) for x in chal]}")
            reply = build_connect_reply(serial, chal)
            vport.send(mido.Message('sysex', data=reply))
            print("   ✉️  Sent connect reply")
            continue

        if code == 0x03:
            print("   ✅ Connection confirmed by Logic.")
            break

    # cancel rescans now that handshake is done
    _rescan_timer.cancel()

    # ——— 2) Enable meters & start polling —————————————————————————————————————
    print("▶ Enabling meters…")
    vport.send(mido.Message('sysex', data=ENABLE_METERS))
    start_meter_polling()

    # ——— 3) Listen for full-bank meter dumps —————————————————————————————————
    print("▶ Listening for meter dumps… (Ctrl-C to quit)")
    while True:
        msg = vport.receive()
        if msg.type == 'sysex':
            d = list(msg.data)
            if d[0:4] == POLL_PREFIX and len(d) >= 5:
                bank   = d[4]
                levels = d[5:]
                print(f"[Bank {bank}] → {levels}")

if __name__ == "__main__":
    main()
