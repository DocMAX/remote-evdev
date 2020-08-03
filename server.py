import base64
import pickle
import asyncio
import evdev


def unpickle_data(data):
    data = base64.b64decode(data[:-1])
    data = pickle.loads(data)
    return data


def pickle_data(data):
    data = pickle.dumps(data)
    data = base64.b64encode(data) + b'\n'
    return data


async def get_dev_events(device, n, queue):
    async for event in device.async_read_loop():
        event_list = ["srv_dev_event", n, event]
        queue.put_nowait(event_list)


async def read_loop(reader, writer, queue, task_write_loop):
    get_event_tasks = []
    while True:
        try:
            data = unpickle_data(await reader.readline())
        except EOFError:
            for path in paths:
                print("Unexporting " + path)
            break
        if data[0] == "client_devices":
            paths = data[1]
            for path in data[1]:
                print("Exporting " + path)
            for n, path in enumerate(data[1]):
                device = evdev.InputDevice(path)
                queue.put_nowait(pickle_data(["srv_device", device]))
                get_event_tasks.append(asyncio.create_task(get_dev_events(device, n, queue), name="Device" + str(n)))


async def write_loop(reader, writer, queue):
    while True:
        data = await queue.get()
        writer.write(data)


async def server_handler(reader, writer):
    queue = asyncio.Queue()
    task_write_loop = asyncio.create_task(write_loop(reader, writer, queue))
    task_read_loop = asyncio.create_task(read_loop(reader, writer, queue, task_write_loop))
    await asyncio.gather(task_write_loop, task_read_loop)


def main():
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(server_handler, '0.0.0.0', 8888)
    server = loop.run_until_complete(coro)
    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Caught keyboard interrupt. Canceling tasks...")
    finally:
        for task in asyncio.all_tasks():
            task.cancel()


if __name__ == "__main__":
    main()
