import argparse
import base64
import pickle
import asyncio
import evdev
import socket


parser = argparse.ArgumentParser(description="evdev-client 0.1")
parser.add_argument("-s", "--server", help="Server address", required=True)
parser.add_argument("-d", "--device-name", help="Device to pass to the server", action="append", required=True)
args = parser.parse_args()
devs = args.device_name
srv = args.server
devices = []


def unpickle_data(data):
    data = base64.b64decode(data[:-1])
    data = pickle.loads(data)
    return data


def pickle_data(data):
    data = pickle.dumps(data)
    data = base64.b64encode(data) + b'\n'
    return data


async def tcp_client():
    reader, writer = await asyncio.open_connection(srv, 8888)
    writer.write(pickle_data(["client_devices", devs]))
    while True:
        try:
            data = unpickle_data(await reader.readline())
        except EOFError:
            print("Connection lost...")
            break
        if data[0] == "srv_dev":
            address = writer.get_extra_info('peername')
            address_dns = socket.gethostbyaddr(address[0])
            device = data[2]
            cap = device.capabilities()
            del cap[0]
            devices.append(evdev.UInput(cap, name=device.name + f' (via {address_dns[0]})', vendor=device.info.vendor,
                                        product=device.info.product))
            print(f"Created UInput device {device.name} (via {srv})")
        if data[0] == "srv_dev_event":
            if not data[0]:
                break
            devices[data[1]].write_event(data[2])


loop = asyncio.get_event_loop()

try:
    loop.run_until_complete(tcp_client())
except KeyboardInterrupt:
    for device in devices:
        print("Removing " + device.name)
        device.close()
    pass

loop.close()
