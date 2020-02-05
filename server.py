import asyncio
import evdev
import pickle
import socket
import struct


async def read_data(sock):
    lengthbuf = await read(sock, 4)
    length, = struct.unpack('!I', lengthbuf)
    return await read(sock, length)


async def read(sock, count):
    buf = b''
    while count:
        newbuf = await sock.read(count)
        if not newbuf:
            return None
        buf += newbuf
        count -= len(newbuf)
    return buf


async def server_action(reader, writer):
    while True:
        data_enc = await reader.read(1024)
        # data_enc = await read_data(reader)
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
                # devices_local[data_dec[1]].write_event(data_dec[2])
                # devices_local[data_dec[1]].syn()

loop = asyncio.get_event_loop()
coro = asyncio.start_server(server_action, '0.0.0.0', 8888, loop=loop)
server = loop.run_until_complete(coro)

# Serve requests until Ctrl+C is pressed
print('Serving on {}'.format(server.sockets[0].getsockname()))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

# Close the server
server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
