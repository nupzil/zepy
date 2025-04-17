import os
import yaml
from typing import Any

from app.infra.path import resolve_path


def parse_from(path: str) -> dict[str: Any]:
    with open(resolve_path(link=path), 'r') as file:
        data: dict[str: Any] = yaml.safe_load(file)
    return data
