from dataclasses import dataclass
from typing import Optional, Tuple

from app.infra.yml import parse_from
from app.infra.utils import is_empty
from app.infra.path import resolve_path, parse_proxy_link


@dataclass
class Settings:
    # 缓存文件路径（可选）
    cache_file: str

    # 是否开启缓存（可选）
    # - 默认: True
    # - 无论是否开启缓存，都会缓存下载过的文件信息
    # - 如果开启缓存，在下载时会先检查文件是否存在，如果存在则不会下载
    use_cache: bool

    # 代理配置（可选）
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

    # cookie 中的字段 - 必填
    ct0: str

    # cookie 中的字段 - 必填
    auth_token: str

    # 用户名 - 必填
    # twitter 的账号 - @符号后面的部分
    username: str
    # 只下载图片（可选）
    only_image: bool

    # 只下载视频（可选）
    only_video: bool

    @staticmethod
    def create() -> "Settings":
        data = parse_from(path=resolve_path("./configure.yml"))

        proxy_tuple = None
        proxy = data.get("proxy", None)
        if not is_empty(proxy):
            proxy = proxy.strip()
            proxy_tuple = parse_proxy_link(proxy=proxy)

        ct0 = data.get("twitter", {}).get("ct0", None)
        auth_token = data.get("twitter", {}).get("auth_token", None)
        screen_name = data.get("twitter", {}).get("screen_name", None)

        if is_empty(ct0) or is_empty(auth_token) or is_empty(screen_name):
            raise ValueError("ct0 or auth_token or screen_name 存在 None 值")

        return Settings(
            proxy=proxy,
            ct0=ct0.strip(),
            proxy_tuple=proxy_tuple,
            username=screen_name.strip(),
            auth_token=auth_token.strip(),
            max_concurrent=data.get("max_concurrent", 5),
            use_cache=not data.get("cache_disabled", False),
            only_image=data.get("twitter", {}).get("only_image", False),
            only_video=data.get("twitter", {}).get("only_video", False),
            cache_file=resolve_path(data.get("cache_file", "./caches.txt").strip()),
            storage_directory=resolve_path(data.get("storage_directory", "./downloads").strip()),
        )
