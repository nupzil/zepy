import threading

class TaskIdGenerator:
    """线程安全的任务ID生成器单例类"""
    _instance = None
    _lock = threading.Lock()
    _counter = 0
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def get_next_id(self) -> int:
        """获取下一个任务ID"""
        with self._lock:
            self._counter += 1
            return self._counter

# 全局单例实例
idgen = TaskIdGenerator()
