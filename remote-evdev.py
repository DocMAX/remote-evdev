import argparse
import asyncio
import evdev
import json
import socket
import re
import pickle

from evdev import categorize


def try_int(s):
    try:
        return int(s)
    except ValueError:
        return s


def alphanum_key(s):
    return [try_int(c) for c in re.split('([0-9]+)', s)]


def get_devices():
    devices_by_name = {}
    for path in evdev.list_devices():
        device = evdev.InputDevice(path)
        devices_by_name[device.name] = device

    devices = []
    for name in args.device:
        try:
            devices.append(devices_by_name[name])
        except KeyError:
            print("Device \"" + name + "\" does not exist! Aborting...")
            exit()
    return devices


async def do_forward_device(socket, device):
    async for event in device.async_read_loop():
        socket.send(pickle.dumps(event))
        # socket.socket.send(pickle.dumps(event))


async def forward_device(socket, device):
    await do_forward_device(socket, device)


async def forward_device_server(connection, device):
    while True:
        data = connection.recv(1024)
        if data:
            event = pickle.loads(data)
            # print(event)
            device.write_event(event)
            device.syn()


async def print_events(device):
    print("XXXXXXXXXXXXXXXX")
    async for event in device.async_read_loop():
        print(categorize(event))

        if event.type != evdev.ecodes.EV_UINPUT:
            pass

        if event.code == evdev.ecodes.UI_FF_UPLOAD:
            upload = device.begin_upload(event.value)
            upload.retval = 0

            print(f'[upload] effect_id: {upload.effect_id}, type: {upload.effect.type}')
            device.end_upload(upload)

        elif event.code == evdev.ecodes.UI_FF_ERASE:
            erase = device.begin_erase(event.value)
            print(f'[erase] effect_id {erase.effect_id}')

            erase.retval = 0
            device.end_erase(erase)


async def run_forward_client(socket, devices):
    tasks = []
    for device in devices:
        tasks.append(asyncio.create_task(forward_device(socket, device)))
    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)


async def run_forward_server(socket, devices):
    tasks = []
    for device in devices:
        tasks.append(asyncio.create_task(forward_device_server(socket, device)))
        tasks.append(asyncio.create_task(print_events(device)))
    await asyncio.wait(*tasks, return_when=asyncio.FIRST_COMPLETED)


parser = argparse.ArgumentParser(description="Remote evdev Tool 0.1")
parser.add_argument("-l", "--list-devices", help="List available input dev", action="store_true")
parser.add_argument("-c", "--client", help="Run in client mode")
parser.add_argument("-s", "--server", help="Run in server mode", action="store_true")
parser.add_argument("-d", "--device", help="Device to pass to the server", action="append")
args = parser.parse_args()

if args.list_devices:
    print("Listing local devices")
    evdev_list = evdev.list_devices()
    evdev_list.sort(key=alphanum_key)
    for path in evdev_list:
        device = evdev.InputDevice(path)
        print('{} = {}'.format(device.path, device.name))

if args.client:
    devices = get_devices()
    print("Running in client mode, exporting device to server")
    remote_ip = args.client
    remote_port = 20001
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    s.connect((remote_ip, remote_port))
    s.send(pickle.dumps(devices))
    asyncio.run(run_forward_client(s, devices))

if args.server:
    print("Running in server mode, listening for devices")
    local_ip = "0.0.0.0"
    local_port = 20001
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
    s.bind((local_ip, local_port))
    s.listen(1)
    while True:
        connection, address = s.accept()
        devices_remote = pickle.loads(connection.recv(1024))
        devices_local = []
        for device in devices_remote:
            cap = device.capabilities()
            del cap[0]
            devices_local.append(evdev.UInput(cap, name=device.name + f' (via {address[0]})', vendor=device.info.vendor,
                                              product=device.info.product))
            print(f'"{device.name} (via {address[0]})" created')
        asyncio.run(run_forward_server(connection, devices_local))
