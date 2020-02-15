#!/usr/bin/python

import asyncio
import pickle
import base64
import evdev
import socket


def unpickle_data(data):
    data = base64.b64decode(data[:-1])
    data = pickle.loads(data)
    return data


def pickle_data(data):
    data = pickle.dumps(data)
    data = base64.b64encode(data) + b'\n'
    return data


async def get_own_events(device, n, queue):
    # print("get_own_events start")
    async for event in device.async_read_loop():
        event_list = ["server_event", n, event]
        queue.put_nowait(event_list)
    # print("get_own_events stop")


async def read_client_loop(reader, writer, queue, task_write_loop):
    # print("read_client_loop start")
    while True:
        data = await reader.readline()
        if not data:
            writer.close()
            for device in ui_devices:
                print(f"Removing {device.name}")
                try:
                    device.close()
                except OSError:
                    pass
            ui_devices.clear()
            for task in get_event_tasks:
                task.cancel()
            task_write_loop.cancel()
            break
        if data:
            queue.put_nowait(unpickle_data(data))
    # print("read_client_loop stop")


async def write_loop(reader, writer, queue):
    # print("write_loop start")
    while True:
        data = await queue.get()
        if not data:
            break
        if data[0] == "server_event":
            event = data[2]
            if event.code == evdev.ecodes.UI_FF_UPLOAD:
                upload = ui_devices[data[1]].begin_upload(event.value)
                upload.retval = 0
                print(f'[upload] effect_id: {upload.effect_id}, type: {upload.effect.type}')
                ui_devices[data[1]].end_upload(upload)
            elif event.code == evdev.ecodes.UI_FF_ERASE:
                erase = ui_devices[data[1]].begin_erase(event.value)
                print(f'[erase] effect_id {erase.effect_id}')
                erase.retval = 0
                ui_devices[data[1]].end_erase(erase)
            writer.write(pickle_data(event))
            await writer.drain()
        if data[0] == "client_event":
            if not ui_devices:
                pass
            else:
                ui_devices[data[1]].write_event(data[2])
                ui_devices[data[1]].syn()
        if data[0] == "client_devices":
            address = writer.get_extra_info('peername')
            address_dns = socket.gethostbyaddr(address[0])
            for n, device in enumerate(data[1]):
                cap = device.capabilities()
                del cap[0]
                ui_devices.append(
                    evdev.UInput(cap, name=device.name + f' (via {address_dns[0]})', vendor=device.info.vendor,
                                 product=device.info.product))
                print(f"Created UInput device {device.name} (via {address_dns[0]})")
                get_event_tasks.append(asyncio.create_task(get_own_events(device, n, queue), name="Device" + str(n)))
    # print("write_loop stop")


async def server_handler(reader, writer):
    queue = asyncio.Queue()
    task_write_loop = asyncio.create_task(write_loop(reader, writer, queue))
    task_read_client_loop = asyncio.create_task(read_client_loop(reader, writer, queue, task_write_loop))
    await asyncio.gather(task_write_loop, task_read_client_loop)


ui_devices = []
get_event_tasks = []
loop = asyncio.get_event_loop()
coro = asyncio.start_server(server_handler, '0.0.0.0', 8888)
server = loop.run_until_complete(coro)
addr = server.sockets[0].getsockname()
print(f'Serving on {addr}')

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
