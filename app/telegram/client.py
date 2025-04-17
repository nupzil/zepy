import logging
from typing import Optional, Tuple
from telethon import TelegramClient

from app.infra.logger import getLogger
from app.telegram.singleton import settings

logger = getLogger(__name__)

telethon_logger = logging.getLogger("telethon")
telethon_logger.setLevel(logging.INFO)
telethon_logger.addHandler(logging.FileHandler(f"{settings.logs}/telethon.log", mode='a'))

_BOT_SESSION_FILE_NAME = "bot-session"
_CLIENT_SESSION_FILE_NAME = "client-session"


# ("socks5", '127.0.0.1', 7890)

def create_telegram_bot_client(api_id: str, api_hash: str, proxy: Optional[Tuple[str, str, int]]) -> TelegramClient:
    return TelegramClient(_BOT_SESSION_FILE_NAME, api_id=api_id, api_hash=api_hash, proxy=proxy)


def create_telegram_client(api_id: str, api_hash: str, proxy: Optional[Tuple[str, str, int]]) -> TelegramClient:
    return TelegramClient(_CLIENT_SESSION_FILE_NAME, api_id=api_id, api_hash=api_hash, proxy=proxy)
