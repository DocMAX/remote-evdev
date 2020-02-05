import argparse
import asyncio
import pickle
import functions

parser = argparse.ArgumentParser(description="Remote evdev tool 0.1")
parser.add_argument("-s", "--server", help="Server address", required=True)
parser.add_argument("-d", "--device-name", help="Device to pass to the server", action="append", required=True)
args = parser.parse_args()
devices = functions.get_devices(args)


async def get_data_dev(writer, n, device):
    async for event in device.async_read_loop():
        event_list = ["event", n, event]
        print(event_list[2])
        data = pickle.dumps(event_list)
        writer.write(data)


async def client_action():
    reader, writer = await asyncio.open_connection(args.server, 8888)
    device_list = ["devices", devices]
    # await send_data(writer, device_list)
    writer.write(pickle.dumps(device_list))
    await asyncio.gather(*[get_data_dev(writer, n, device) for n, device in enumerate(devices)])

loop = asyncio.get_event_loop()
loop.run_until_complete(client_action())
loop.close()

