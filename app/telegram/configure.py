from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from app.infra.path import resolve_path, parse_proxy_link
from app.infra.utils import is_empty
from app.infra.yml import parse_from


@dataclass
class Settings:
    # 缓存文件路径
    # - 默认: 在当前目录下创建 caches.txt 文件
    cache_file: str

    # 是否开启缓存
    # - 默认: True
    # - 无论是否开启缓存，都会缓存下载过的文件信息
    # - 如果开启缓存，在下载时会先检查文件是否存在，如果存在则不会下载
    use_cache: bool

    # 代理配置
    # - 默认: None
    # - 格式：https://ip:port
    # 目前使用的 twitter api 客户端不支持代理，使用系统代理吧
    proxy: Optional[str]

    # 元组形式 [scheme, hostname, port]
    proxy_tuple: Optional[Tuple[str, str, int]]

    # 可同时下载的文件数（可选）
    # - 默认: 8
    # - 最小: 2
    # - 最大: 12
    max_concurrent: int

    # 下载的媒体文件的存储目录（可选）
    # - 默认: 在当前目录下创建 downloads 文件夹
    # - 如果目录不存在，会自动创建，目录的路径需要是绝对路径或者是相对于 README.md 所在目录的路径
    storage_directory: str

    # Telegram 需要登录的账号的手机号 国际号码形式
    phone: str

    # Telegram API ID
    api_id: str

    # Telegram API Hash
    api_hash: str

    # Telegram Bot Token
    bot_token: str

    # 存储 Telegram 链接的文件路径
    urls_path: str

    # 一些文件输出目录
    logs: str = resolve_path("./logs")
    outputs: str = resolve_path("./outputs")

    @staticmethod
    def create() -> "Settings":
        data = parse_from(path=resolve_path("./configure.yml"))

        Path(Settings.logs).mkdir(parents=True, exist_ok=True)
        Path(Settings.outputs).mkdir(parents=True, exist_ok=True)

        proxy_tuple = None
        proxy = data.get("proxy", None)
        if not is_empty(proxy):
            proxy = proxy.strip()
            proxy_tuple = parse_proxy_link(proxy=proxy)

        phone = data.get("telegram", {}).get("phone", None)
        api_id = data.get("telegram", {}).get("api_id", None)
        api_hash = data.get("telegram", {}).get("api_hash", None)
        bot_token = data.get("telegram", {}).get("bot_token", None)
        urls_path = data.get("telegram", {}).get("urls_path", None)

        if any(is_empty(x) for x in [phone, api_id, api_hash, bot_token, urls_path]):
            raise ValueError("telegram 配置不全")

        return Settings(
            proxy=proxy,
            proxy_tuple=proxy_tuple,
            phone=phone,
            api_id=api_id,
            api_hash=api_hash.strip(),
            bot_token=bot_token.strip(),
            urls_path=resolve_path(urls_path.strip()),
            max_concurrent=data.get("max_concurrent", 8),
            use_cache=not data.get("cache_disabled", False),
            cache_file=resolve_path(data.get("cache_file", "./caches.txt").strip()),
            storage_directory=resolve_path(data.get("storage_directory", "./downloads").strip()),
        )
