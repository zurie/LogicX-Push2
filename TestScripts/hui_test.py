import mido
import time

# Adjust these port names to match your IAC bus setup
MIDI_IN_PORT = "IAC Driver LogicMCU"
MIDI_OUT_PORT = "IAC Driver LogicMCU"

# Mackie Control Universal (MCU) SysEx constants
MCU_SYSEX_PREFIX = [0x00, 0x00, 0x66, 0x14]
CMD_ID_REQUEST    = 0x01  # Logic requests identity
CMD_ID_RESPONSE   = 0x02  # Surface responds identity
CMD_ENABLE_METERS = 0x03  # Enable meter updates
CMD_METER_DUMP    = 0x04  # Meter data from Logic


def send_sysex(data_bytes, output):
    """
    Send a raw SysEx message built from prefix plus data_bytes.
    """
    msg = mido.Message('sysex', data=MCU_SYSEX_PREFIX + data_bytes)
    output.send(msg)


def parse_meter_message(data):
    """
    Parse incoming SysEx for meter dump (CMD_METER_DUMP).
    Returns list of 8 levels (0-127) or None.
    """
    if len(data) >= 13 and data[4] == CMD_METER_DUMP:
        return list(data[5:13])
    return None


def main():
    print(f"Opening MIDI ports: in='{MIDI_IN_PORT}', out='{MIDI_OUT_PORT}'")
    with mido.open_input(MIDI_IN_PORT) as inport, \
            mido.open_output(MIDI_OUT_PORT) as outport:

        print("Waiting for Logic MCU identity request...")
        # Listen until Logic asks for identity
        for msg in inport:
            if msg.type == 'sysex' and msg.data[:5] == MCU_SYSEX_PREFIX + [CMD_ID_REQUEST]:
                print("Received identity request from Logic. Responding...")
                # Respond with identity handshake
                send_sysex([CMD_ID_RESPONSE, 0x00], outport)
                time.sleep(0.05)
                # Request meter updates
                send_sysex([CMD_ENABLE_METERS, 0x00], outport)
                print("Enabled MCU meter streaming.")
                break

        print("Listening for meter dumps... (Ctrl+C to exit)")
        try:
            for msg in inport:
                if msg.type == 'sysex':
                    levels = parse_meter_message(msg.data)
                    if levels:
                        print(f"Meter banks 1-8 levels: {levels}")
        except KeyboardInterrupt:
            print("Exiting...")

if __name__ == '__main__':
    main()
