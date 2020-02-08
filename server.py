import asyncio
import evdev
import pickle
import socket
import base64
import threading


def pickle_data(data):
    data = pickle.dumps(data)
    data = base64.b64encode(data) + b'\n'
    return data


async def get_events(queue, devices):
    for device in devices:
        print(f"Writing events from {device.name}")
        async for event in device.async_read_loop():
            if event.type != evdev.ecodes.EV_UINPUT:
                pass
            if event.type == evdev.ecodes.EV_FF:
                queue.put_nowait(event)
            if event.code == evdev.ecodes.UI_FF_UPLOAD:
                try:
                    upload = device.begin_upload(event.value)
                    upload.retval = 0
                    print(f'[upload] effect_id: {upload.effect_id}, type: {upload.effect.type}')
                    device.end_upload(upload)
                except:
                    pass
            elif event.code == evdev.ecodes.UI_FF_ERASE:
                try:
                    erase = device.begin_erase(event.value)
                    print(f'[erase] effect_id {erase.effect_id}')
                    erase.retval = 0
                    device.end_erase(erase)
                except:
                    pass


async def writer_handler(queue, writer):
    while True:
        writer.write(pickle_data(await queue.get()))


async def server_handle(reader, writer):
    queue = asyncio.Queue()
    while True:
        data_enc = await reader.readline()
        if not data_enc:
            print("No more data received, exiting...")
            break
        data_dec = pickle.loads(base64.b64decode(data_enc[:-1]))
        if data_dec[0] == "event":
            if not devices:
                pass
            else:
                # print(data_dec[2])
                devices[data_dec[1]].write_event(data_dec[2])
                devices[data_dec[1]].syn()
        if data_dec[0] == "devices":
            address = writer.get_extra_info('peername')
            address_dns = socket.gethostbyaddr(address[0])
            devices = []
            for device in data_dec[1]:
                cap = device.capabilities()
                del cap[0]
                devices.append(evdev.UInput(cap, name=device.name + f' (via {address_dns[0]})', vendor=device.info.vendor, product=device.info.product))
                print(f'"{device.name} (via {address_dns[0]})" created')
            asyncio.create_task(get_events(queue, devices))
            asyncio.create_task(writer_handler(queue, writer))


loop = asyncio.get_event_loop()
coro = asyncio.start_server(server_handle, '0.0.0.0', 8888, loop=loop)
server = loop.run_until_complete(coro)
print('Waiting for remote devices on {}'.format(server.sockets[0].getsockname()))
try:
    loop.run_forever()
except KeyboardInterrupt:
    print("Ctrl-C detected, exiting...")
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
