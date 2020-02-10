#!/usr/bin/python

import asyncio
import pickle
import base64
import evdev
import socket


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


async def read_handler(reader, writer, queue):
    while True:
        data = await reader.readline()
        # print(f"read_handler: {data})")
        if not data:
            for device in ui_devices:
                print(f"Removing {device.name}")
                device.close()
            break
        pickle_object = unpickle_data(data)
        # print(pickle_object)
        if pickle_object[0] == "event":
            if not ui_devices:
                pass
            else:
                ui_devices[pickle_object[1]].write_event(pickle_object[2])
                ui_devices[pickle_object[1]].syn()
        if pickle_object[0] == "devices":
            address = writer.get_extra_info('peername')
            address_dns = socket.gethostbyaddr(address[0])
            ui_devices = []
            for n, device in enumerate(pickle_object[1]):
                cap = device.capabilities()
                del cap[0]
                ui_devices.append(evdev.UInput(cap, name=device.name + f' (via {address_dns[0]})', vendor=device.info.vendor, product=device.info.product))
                print(f"Created UInput device {device.name} (via {address_dns[0]})")
                asyncio.create_task(get_events(ui_devices[n], n, queue))


async def write_handler(writer, queue):
    while True:
        data = await queue.get()
        # print(f"write_handler: {data})")
        if data[0] == "event":
            event = data[2]
            if event.code == evdev.ecodes.UI_FF_UPLOAD:
                try:
                    upload = ui_devices[data[1]].begin_upload(event.value)
                    upload.retval = 0
                    print(f'[upload] effect_id: {upload.effect_id}, type: {upload.effect.type}')
                    ui_devices[data[1]].end_upload(upload)
                except:
                    pass
            elif event.code == evdev.ecodes.UI_FF_ERASE:
                try:
                    erase = ui_devices[data[1]].begin_erase(event.value)
                    print(f'[erase] effect_id {erase.effect_id}')
                    erase.retval = 0
                    ui_devices[data[1]].end_erase(erase)
                except:
                    pass
            # print(await queue.get())
            writer.write(pickle_data(event))
            await writer.drain()


async def server_handle(reader, writer):
    queue = asyncio.Queue()
    task_write = asyncio.create_task(write_handler(writer, queue))
    task_read = asyncio.create_task(read_handler(reader, writer, queue))
    await asyncio.gather(task_read, task_write)


async def main():
    global ui_devices
    server = await asyncio.start_server(server_handle, '0.0.0.0', 8888)
    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')
    async with server:
        await server.serve_forever()


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
