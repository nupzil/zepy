from typing import Set
from urllib.parse import urlparse

from app.telegram.singleton import settings


def is_valid_url(url: str) -> bool:
    result = urlparse(url)
    return all([result.scheme, result.netloc])


def get_links_for_configure_or_raise() -> Set[str]:
    urls: Set[str] = set()

    with open(settings.urls_path, 'r') as file:
        for line in file.readlines():
            line = line.strip()
            if not line:
                continue
            if is_valid_url(line):
                urls.add(line)
            else:
                raise ValueError(f"无效的 URL: {line}")

    if len(urls) == 0:
        raise ValueError(f"没有找到 URL ")
    return urls
