import asyncio
import signal


shutdown_event = asyncio.Event()


def add_signal_handler():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)
