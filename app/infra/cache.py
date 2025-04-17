import os
from typing import Set
from threading import RLock


# twitter 的媒体的 key 带有 x- 前缀
# telegram 的媒体的 key 带有 t- 前缀

class CacheManager:
    def __init__(self, cache_file: str):
        self._cache_file = cache_file
        self._lock = RLock()
        self._makedirs()
        self._cache = self._load_from_file()

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._cache

    def set(self, content: str):
        with self._lock:
            if content in self._cache:
                return
            self._cache.add(content)
            self._sync_to_file(content=content)

    def _makedirs(self):
        if os.path.exists(self._cache_file):
            if not os.path.isfile(self._cache_file):
                raise FileExistsError(f"文件 {self._cache_file} 存在且不是文件")
        else:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)

    def _sync_to_file(self, content: str):
        # 追加的方式写入文件
        with open(self._cache_file, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    def _load_from_file(self) -> Set[str]:
        result = set()
        if not os.path.exists(self._cache_file):
            return result

        with open(self._cache_file, "r", encoding="utf-8") as f:
            for line in f.readlines():
                trimmed = line.strip()
                if trimmed:
                    result.add(trimmed)
        return result
