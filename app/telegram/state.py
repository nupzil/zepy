import pickledb

from app.infra.persistent import DefaultStorage, BasePersistent, persisted


# 不是线程安全的
# 因为内部都是同步方法，加同步锁会影响性能，异步锁会导致都是异步的
class AppState(BasePersistent):
    # 持久化的属性
    # 自程序上线以来的数据统计
    lifetime_total_downloads: int = persisted(key="lifetime_total_downloads", default=0)
    lifetime_failed_downloads: int = persisted(key="lifetime_failed_downloads", default=0)
    lifetime_success_downloads: int = persisted(key="lifetime_success_downloads", default=0)

    # 非持久化的属性 (会话统计)
    session_total_downloads: int = 0
    session_failed_downloads: int = 0
    session_success_downloads: int = 0

    def __init__(self, persistent_path: str):
        super().__init__(DefaultStorage(pickledb.load(persistent_path, False)))
