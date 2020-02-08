import evdev

device = evdev.InputDevice("/dev/input/event20")
for event in device.read_loop():
    print(event)
