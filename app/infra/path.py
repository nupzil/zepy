from pathlib import Path
from typing import Tuple, Optional
from urllib.parse import urlparse


def resolve_path(link: str) -> str:
    link = link.strip()
    link_path = Path(link)

    if not link_path.is_absolute():
        cwd = Path.cwd()
        # base_path = cwd.parent
        return str((cwd / link_path).resolve())

    return str(link_path.resolve())


def parse_proxy_link(proxy: str) -> Optional[Tuple[str, str, int]]:
    if proxy is not None:
        parsed = urlparse(proxy.strip())
        if parsed.scheme and parsed.hostname and parsed.port:
            return parsed.scheme, parsed.hostname, parsed.port
        else:
            raise ValueError("代理配置无效，格式应为 '协议::/主机:端口'")
    return None
