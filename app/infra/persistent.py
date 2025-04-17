import abc
import pickledb

from typing import Any, Optional, Callable, TypeVar, Generic

T = TypeVar("T")


class Serializer(Generic[T]):
    def __init__(self, encode: Callable[[T], Any], decode: Callable[[Any], T], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encode = encode
        self.decode = decode


# storage 不能每次都直接读文件，建议是维护一个内存中的 kv 存储，这样可以避免每次都读文件，提高性能
class BasePersistentStorage:
    @abc.abstractmethod
    def get(self, key: str) -> Any:
        """Get the value associated with the given key."""
        pass

    @abc.abstractmethod
    def set(self, key: str, value: Any):
        """Set the value associated with the given key."""
        pass


# 基础的持久化类
class BasePersistent:
    def __init__(self, store: BasePersistentStorage):
        self._store = store


# 内部实现了缓存，但是使用时需要确保 persisted 必定是全局唯一的修改入口，否则缓存可能会不一致
def persisted(key: str, default: T, *, use_cache: bool = True, serializer: Optional[Serializer[T]] = None) -> property:
    attr_name = f"_cache_{key}"

    def getter(self):
        if use_cache:
            if not hasattr(self, attr_name):
                # 第一次访问的时候，从持久化存储中加载
                value = self._store.get(key)
                try:
                    value = serializer.decode(value) if serializer is not None and value is not None else value
                except Exception as e:
                    print(f"Error decoding key '{key}': {e}")
                    value = None
                setattr(self, attr_name, default if value is None else value)
            # 直接返回缓存的值
            return getattr(self, attr_name)

        # 每次都从持久化存储中加载
        value = self._store.get(key)
        try:
            value = serializer.decode(value) if serializer is not None and value is not None else value
        except Exception as e:
            print(f"Error decoding key '{key}': {e}")
            value = None
        return default if value is None else value

    def setter(self, value):
        value_to_store = value
        if serializer is not None:
            try:
                value_to_store = serializer.encode(value)
            except Exception as e:
                print(f"Error encoding value for key '{key}': {e}")
                raise e
        self._store.set(key, value_to_store)
        if use_cache:
            # 更新缓存
            setattr(self, attr_name, value_to_store)

    return property(getter, setter)


# 默认的存储基于 pickle
class DefaultStorage(BasePersistentStorage):
    def __init__(self, storage: pickledb.PickleDB):
        # pickle 是线程安全的
        # 它内部应该是有缓存的，不会每次都读文件
        self._store = storage

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def set(self, key: str, value: Any):
        self._store.set(key, value)
        self._store.dump()


__all__ = ["persisted", "DefaultStorage", "BasePersistent", "BasePersistentStorage", "Serializer"]
