import asyncio
import evdev
import pickle
import socket


async def server_action(reader, writer):
    while True:
        data_enc = await reader.read(1024)
        data_dec = pickle.loads(data_enc)
        if data_dec[0] == "devices":
            address = writer.get_extra_info('peername')
            address_dns = socket.gethostbyaddr(address[0])
            devices_local = []
            for device in data_dec[1]:
                cap = device.capabilities()
                del cap[0]
                devices_local.append(
                    evdev.UInput(cap, name=device.name + f' (via {address_dns[0]})', vendor=device.info.vendor,
                                 product=device.info.product))
                print(f'"{device.name} (via {address_dns[0]})" created')
        if data_dec[0] == "event":
            if not devices_local:
                pass
            else:
                print(data_dec[2])
                devices_local[data_dec[1]].write_event(data_dec[2])
                devices_local[data_dec[1]].syn()

loop = asyncio.get_event_loop()
coro = asyncio.start_server(server_action, '0.0.0.0', 8888, loop=loop)
server = loop.run_until_complete(coro)

print('Serving on {}'.format(server.sockets[0].getsockname()))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
