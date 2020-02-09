#!/usr/bin/python

import asyncio
import pickle
import base64
import evdev
import socket


dev_names = ["SHANWAN PS3 GamePad"]


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


async def get_events(device, n, queue):
    async for event in device.async_read_loop():
        event_list = ["event", n, event]
        queue.put_nowait(event_list)


def unpickle_data(data):
    data = base64.b64decode(data[:-1])
    data = pickle.loads(data)
    return data


def pickle_data(data):
    data = pickle.dumps(data)
    data = base64.b64encode(data) + b'\n'
    return data


async def read_handler(reader, writer):
    while True:
        data = await reader.readline()
        if not data:
            print("Client disconnect, removing devices...")
            for device in devices:
                device.close()
            break
        pickle_object = unpickle_data(data)
        if pickle_object[0] == "event":
            if not devices:
                pass
            else:
                print(pickle_object[2])
                devices[pickle_object[1]].write_event(pickle_object[2])
                devices[pickle_object[1]].syn()
        if pickle_object[0] == "devices":
            address = writer.get_extra_info('peername')
            address_dns = socket.gethostbyaddr(address[0])
            devices = []
            for device in pickle_object[1]:
                cap = device.capabilities()
                del cap[0]
                devices.append(
                    evdev.UInput(cap, name=device.name + f' (via {address_dns[0]})', vendor=device.info.vendor,
                                 product=device.info.product))
                print(f"Created UInput device {device.name} (via {address_dns[0]})")


async def write_handler(writer, queue):
    while True:
        print(await queue.get())
        writer.write(pickle_data(await queue.get()))
        await writer.drain()


async def server_handle(reader, writer):
    queue = asyncio.Queue()
    devices = get_device(dev_names)
    task_write = asyncio.create_task(write_handler(writer, queue))
    task_read = asyncio.create_task(read_handler(reader, writer))
    await asyncio.gather(task_read, task_write, *[get_events(device, n, queue) for n, device in enumerate(devices)])


async def main():
    server = await asyncio.start_server(server_handle, '0.0.0.0', 8888)
    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')
    async with server:
        await server.serve_forever()


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
