#!/usr/bin/python

import asyncio
import pickle
import base64
import evdev
import sys
import socket
import argparse


parser = argparse.ArgumentParser(description="Remote evdev tool 0.1")
parser.add_argument("-s", "--server", help="Server address", required=True)
parser.add_argument("-d", "--device-name", help="Device to pass to the server", action="append", required=True)
args = parser.parse_args()
dev_names = args.device_name
srv = args.server
# dev_names = ["Logitech Logitech RumblePad 2 USB", "Microsoft Microsoft SideWinder Precision Pro (USB)"]


def get_device(dev_name):
    devices_by_name = {}
    for path in evdev.list_devices():
        device = evdev.InputDevice(path)
        devices_by_name[device.name] = device
    devices = []
    for name in dev_name:
        try:
            devices.append(devices_by_name[name])
        except KeyError:
            print("Device \"" + name + "\" does not exist! Aborting...")
            exit()
    return devices


def unpickle_data(data):
    data = base64.b64decode(data[:-1])
    data = pickle.loads(data)
    return data


def pickle_data(data):
    data = pickle.dumps(data)
    data = base64.b64encode(data) + b'\n'
    return data


async def get_own_events(device, n, queue):
    async for event in device.async_read_loop():
        event_list = ["client_event", n, event]
        queue.put_nowait(event_list)


async def read_server_loop(reader, queue):
    while True:
        data = await reader.readline()
        if not data:
            print("Disconnect")
            sys.exit()
        queue.put_nowait(unpickle_data(data))


async def write_handler(writer, queue):
    while True:
        data = await queue.get()
        if data[0] == "server_event":
            rumble = evdev.ff.Rumble(strong_magnitude=0x0000, weak_magnitude=0xffff)
            effect_type = evdev.ff.EffectType(ff_rumble_effect=rumble)
            duration_ms = 1000

            effect = evdev.ff.Effect(
                evdev.ecodes.FF_RUMBLE, -1, 0,
                evdev.ff.Trigger(0, 0),
                evdev.ff.Replay(duration_ms, 0),
                evdev.ff.EffectType(ff_rumble_effect=rumble)
            )

            repeat_count = 1
            effect_id = devices[data[1]].upload_effect(effect)
            devices[data[1]].write(evdev.ecodes.EV_FF, effect_id, repeat_count)
            await asyncio.sleep(1)
            devices[data[1]].erase_effect(effect_id)
        writer.write(pickle_data(data))
        await writer.drain()


async def client_handler():
    queue = asyncio.Queue()
    try:
        reader, writer = await asyncio.open_connection(srv, 8888)
        address = writer.get_extra_info('peername')
        address_dns = socket.gethostbyaddr(address[0])
        print(f"Connected to {address_dns[0]}")
    except ConnectionRefusedError:
        print("Connection refused")
        sys.exit()
    writer.write(pickle_data(device_list))
    task_read = asyncio.create_task(read_server_loop(reader, queue))
    task_write = asyncio.create_task(write_handler(writer, queue))
    await asyncio.gather(task_read, task_write, *[get_own_events(device, n, queue) for n, device in enumerate(devices)])

devices = get_device(dev_names)
device_list = ["client_devices", devices]

try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client_handler())
except (KeyboardInterrupt, ConnectionRefusedError):
    pass
