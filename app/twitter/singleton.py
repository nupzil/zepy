from app.infra.cache import CacheManager
from app.twitter.configure import Settings
from app.twitter.executor import ThreadedExecutor

# 这里是全局公用的配置
settings = Settings.create()

# 全局缓存器
cache_manager = CacheManager(cache_file=settings.cache_file)

# 全局线程池
threaded_pool = ThreadedExecutor(max_workers=settings.max_concurrent)
