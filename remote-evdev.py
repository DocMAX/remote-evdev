import argparse
import asyncio
import evdev
import json
import socket
import re
import pickle


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
    for event in devices[0].read_loop():
        s.send(pickle.dumps(event))

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
            devices_local.append(evdev.UInput(cap, name=device.name + f' (via {address[0]})', vendor=device.info.vendor, product=device.info.product))
            print(f'"{device.name} (via {address[0]})" created')
        while True:
            data = connection.recv(1024)
            if data:
                event = pickle.loads(data)
                print(event)
                devices_local[0].write_event(event)
                devices_local[0].syn()
