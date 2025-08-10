#!/usr/bin/env python3
import mido, threading, signal, sys

MODEL_IDS   = (0x10, 0x14)      # support HUI (0x10) & Logic (0x14)
SCAN_CODES  = (0x00, 0x01, 0x13)
ENABLE_METERS = [0x00,0x00,0x66,0x14,0x12,0x00,0x00]
POLL_PREFIX   = [0x00,0x00,0x66,0x14,0x20]

# our inquiry
SERIAL    = [ord(c) for c in "MCUPRO "]
CHALLENGE = [0x10,0x20,0x30,0x40]
INQUIRY   = [0x00,0x00,0x66,0x14,0x01] + SERIAL + CHALLENGE

def compute_response(ch):
    l1,l2,l3,l4 = ch
    return [
        (l1 + (l2^0x0A) - l4)      & 0x7F,
        ((l3>>4) ^ (l1+l4))        & 0x7F,
        (l4 - (l3<<2) ^ (l1|l2))   & 0x7F,
        (l2 - l3 + (0xF0 ^ (l4<<4)))& 0x7F,
        ]

# cleanup
def cleanup(*_):
    try: outp.send(mido.Message('sysex', data=[0x00,0x00,0x66,0x14,0x12,0x00,0x01]))
    except: pass
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# open Logic’s virtual ports
inp  = mido.open_input("Logic Pro Virtual Out")
outp = mido.open_output("Logic Pro Virtual In")
print("▶ Listening on Logic Pro Virtual Out → replying into Virtual In")

# STEP 1: on first scan, send our inquiry once
print("▶ Waiting for initial scan ping…")
while True:
    msg = inp.receive()
    if msg.type!='sysex': continue
    data = list(msg.data)
    if len(data)>=5 and data[0:3]==[0,0,0x66] and data[3] in MODEL_IDS and data[4] in SCAN_CODES:
        print(f"🔍 Scan code=0x{data[4]:02X} from model 0x{data[3]:02X}, sending inquiry")
        outp.send(mido.Message('sysex', data=INQUIRY))
        break

# STEP 2: wait for Logic’s full connect query (with challenge)
print("▶ Waiting for Logic’s full connect-query (0x01/0x13 + 16+ bytes)…")
while True:
    msg = inp.receive()
    if msg.type!='sysex': continue
    d = list(msg.data)
    if len(d)>=16 and d[0:3]==[0,0,0x66] and d[3] in MODEL_IDS and d[4] in (0x01,0x13):
        code = d[4]
        serial   = d[5:12]
        challenge= d[12:16]
        print(f"   🔑 Got full query code=0x{code:02X}, serial={bytes(serial)!r}, challenge={[hex(x) for x in challenge]}")
        # compute and send response (0x02)
        resp = compute_response(challenge)
        reply = [0x00,0x00,0x66,d[3],0x02] + serial + resp
        outp.send(mido.Message('sysex', data=reply))
        print("   ✉️  Sent connect-response (0x02)")
        break

# STEP 3: wait for confirmation (0x03)
print("▶ Waiting for confirmation (0x03)…")
while True:
    msg = inp.receive()
    if msg.type!='sysex': continue
    d = list(msg.data)
    if len(d)>=5 and d[0:3]==[0,0,0x66] and d[3] in MODEL_IDS and d[4]==0x03:
        print("   ✅ Connection confirmed by Logic (0x03).")
        break

# STEP 4: enable meters & poll
print("▶ Enabling meters…")
outp.send(mido.Message('sysex', data=ENABLE_METERS))

def poll():
    for bank in range(8):
        outp.send(mido.Message('sysex', data=POLL_PREFIX+[bank]))
    threading.Timer(0.1, poll).start()

poll()

# STEP 5: print meter dumps
print("▶ Listening for meter dumps…")
while True:
    msg = inp.receive()
    if msg.type=='sysex':
        d = list(msg.data)
        if d[:4]==POLL_PREFIX and len(d)>=5:
            print(f"[Bank {d[4]}] → {d[5:]}")
