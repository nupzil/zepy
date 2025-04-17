import logging
from rich.logging import RichHandler

# 默认日志级别
_default_level = logging.INFO
#
# 创建并配置基础日志记录器
_logger = logging.getLogger("app")

# 创建一个日志处理器，输出到控制台
# _console_handler = RichHandler(rich_tracebacks=True)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(_default_level)

# 创建一个日志格式器，包含trace_id
_formatter = logging.Formatter('%(name)-15s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
_console_handler.setFormatter(_formatter)

# 设置默认日志级别
_logger.setLevel(_default_level)

# 添加处理器到日志记录器
_logger.addHandler(_console_handler)

# 禁用传播，避免重复日志
_logger.propagate = False


# 设置根日志级别
def set_level(level: str):
    _logger.setLevel(level)
    _console_handler.setLevel(level)


# 获取日志记录器 - 需要传递 __name__ 参数
def getLogger(module_name: str):
    return logging.getLogger(f'app.{module_name}')
