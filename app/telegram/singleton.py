from app.infra.cache import CacheManager
from app.telegram.configure import Settings
from app.telegram.state import AppState

# 这里是全局公用的配置
settings = Settings.create()

# 全局状态
appState = AppState(persistent_path=settings.outputs+'/state.txt')

# 全局缓存器
cache_manager = CacheManager(cache_file=settings.cache_file)
