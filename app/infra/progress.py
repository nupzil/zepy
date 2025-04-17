from typing import Optional
from alive_progress import config_handler, alive_bar

config_handler.set_global(
    length=20,
    spinner='wait',
    title_length=40
)


def create_alive_progress(title: str, total=Optional[int]):
    return alive_bar(total, title=title, bar='classic', spinner='twirls')


__all__ = ["create_alive_progress"]
