from typing import Optional, Union


def is_empty(value: Optional[Union[str, int]]) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, int):
        return value == 0
    return False
