import asyncio
import contextlib

from app.telegram.bot import TelegramBotService
from app.infra.graceful import shutdown_event, add_signal_handler


async def main():
    add_signal_handler()
    service = TelegramBotService()
    bot_task = asyncio.create_task(service.start())

    await shutdown_event.wait()

    await service.dispose()

    bot_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await bot_task

if __name__ == "__main__":
    asyncio.run(main())
