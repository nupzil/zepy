import asyncio
import logging
import time
import os
import shutil
import tempfile
from enum import Enum
from telethon.tl import types
from asyncio.tasks import sleep
from types import SimpleNamespace
from telethon import TelegramClient
from rich.progress import Progress
from rich.logging import RichHandler
from dataclasses import dataclass, field
from typing import Callable, TypeAlias, Optional, Union

from app.infra.idgen import idgen
from app.telegram.media_types import MediaTypes
from app.telegram.link_parser import fetch_message_by_link
from app.infra.rich_progress import create_download_progress
from app.telegram.singleton import cache_manager, settings

logger = logging.getLogger("downloadService")


class SilentFilter(logging.Filter):
    def __init__(self, silent: bool):
        super().__init__()
        self.silent = silent

    def filter(self, record):
        return record.levelno >= logging.INFO


_fh2 = RichHandler(rich_tracebacks=True)
_fh3 = logging.FileHandler(f"{settings.logs}/download.log", mode='a')

_fh2.setLevel(logging.DEBUG)
_fh3.setLevel(logging.DEBUG)

logger.addHandler(_fh2)
logger.addHandler(_fh3)
logger.setLevel(logging.DEBUG)


class TaskStatus(Enum):
    pending = 0
    running = 1
    success = 2
    failure = 3

    def is_completion(self) -> bool:
        return self == TaskStatus.failure or self == TaskStatus.success


class DownloadErrorCode(str, Enum):
    ExistInCache = "ExistInCache"
    Unsupported = "UnsupportedMediaType"
    Unknown = "Unknown"
    NotExistMedia = "NotExistMedia"
    NetworkError = "NetworkError"
    AuthError = "AuthError"
    FileSystemError = "FileSystemError"
    RateLimitError = "RateLimitError"


class DownloadException(Exception):
    def __init__(self, error_code: DownloadErrorCode, message: str):
        self.message = message
        self.error_code = error_code
        super().__init__(f"{error_code}: {message}")

    @staticmethod
    def from_error(exception: Exception) -> "DownloadException":
        """将通用异常转换为下载特定异常"""
        if isinstance(exception, DownloadException):
            return exception

        error_message = str(exception)

        # 根据异常类型或消息内容判断错误类型
        if isinstance(exception, ConnectionError) or "connection" in error_message.lower():
            return DownloadException(DownloadErrorCode.NetworkError, f"网络连接错误: {error_message}")
        elif isinstance(exception, PermissionError) or "permission" in error_message.lower():
            return DownloadException(DownloadErrorCode.FileSystemError, f"文件系统权限错误: {error_message}")
        elif "auth" in error_message.lower() or "unauthorized" in error_message.lower():
            return DownloadException(DownloadErrorCode.AuthError, f"认证错误: {error_message}")
        elif "limit" in error_message.lower() or "flood" in error_message.lower():
            return DownloadException(DownloadErrorCode.RateLimitError, f"速率限制错误: {error_message}")
        else:
            return DownloadException(DownloadErrorCode.Unknown, f"未知错误: {error_message}")


TaskID: TypeAlias = str

TaskResult: TypeAlias = str

TaskCallback: TypeAlias = Callable[[Optional[DownloadException], Optional[TaskResult]], None]


@dataclass
class TaskDefinition:
    id: TaskID
    source: Union[types.Message, str]

    result: Optional[TaskResult] = None
    waiter: Optional[asyncio.Future] = None
    exception: Optional[DownloadException] = None
    created_at: float = field(default_factory=time.time)
    status: TaskStatus = field(default=TaskStatus.pending)
    callback: Optional[Callable[[Optional[DownloadException], Optional[TaskResult]], None]] = None


def _next_task_id() -> TaskID:
    return f'_t{idgen.get_next_id()}'


def _is_task_id(task_id: TaskID) -> bool:
    return task_id.startswith("_t")


@dataclass
class ServiceStatus:
    running_count: int
    pending_count: int
    failed_count: int = 0
    completed_count: int = 0


# todo Downloader 负责调度执行，不负责实现
class DownloadService:
    def __init__(self, client: TelegramClient, bot: Optional[TelegramClient], max_concurrent: int = 8, silent=False):
        # 任务队列锁
        self._lock = asyncio.Lock()
        # 最大并发数
        self._max_concurrent: int = max_concurrent
        # 转发给 bot 的媒体需要使用 bot 身份下载，否则比较麻烦
        self._bot: TelegramClient = bot
        # 链接需要使用 user 身份下载
        self._client: TelegramClient = client
        # 关闭信号
        self._shutdown: asyncio.Event = asyncio.Event()
        # 任务列表-包含任务组中的任务
        self._tasks: dict[TaskID, TaskDefinition] = {}
        # asyncio 队列
        self._task_queue: asyncio.Queue[TaskID] = asyncio.Queue()
        # 进度条
        self._progress: Optional[Progress] = None
        # 文件是否下载中或下载过
        # 这个主要是因为并发下载时 cache_manager 无法判断文件正在下载中
        self._cache: Set[str] = set()

        # 统计信息
        self._failed_count: int = 0
        self._completed_count: int = 0

        if silent:
            _fh2.addFilter(SilentFilter(silent=True))

        logger.debug(f"下载服务初始化: 最大并发数={max_concurrent}, 静默模式={silent}")

    async def status(self) -> ServiceStatus:
        async with self._lock:
            pending_count = sum(1 for task in self._tasks.values() if task.status == TaskStatus.pending)
            running_count = sum(1 for task in self._tasks.values() if task.status == TaskStatus.running)
            return ServiceStatus(
                pending_count=pending_count,
                running_count=running_count,
                failed_count=self._failed_count,
                completed_count=self._completed_count
            )

    def submit(self, source: Union[types.Message, str], callback: Optional[TaskCallback] = None) -> TaskID:
        task_id = _next_task_id()
        asyncio.create_task(self._submit(task_id=task_id, source=source, callback=callback))
        logger.debug(f"提交任务(异步): ID={task_id}")
        return task_id

    async def submit_async(self, source: Union[types.Message, str]) -> asyncio.Future[TaskResult]:
        task_id = _next_task_id()
        logger.debug(f"提交任务(同步): ID={task_id}")
        return await self._submit(task_id=task_id, source=source)

    async def _submit(
            self, task_id: TaskID, source: Union[types.Message, str], callback: Optional[TaskCallback] = None
    ) -> asyncio.Future[TaskResult]:
        if self._shutdown.is_set():
            logger.warning(f"任务提交失败: ID={task_id}, 服务已关闭")
            raise RuntimeError("DownloadService is shutdown")

        waiter = asyncio.Future()
        async with self._lock:
            self._tasks[task_id] = TaskDefinition(id=task_id, source=source, waiter=waiter, callback=callback)

        logger.debug(f"任务已加入队列: ID={task_id}, 当前队列长度={self._task_queue.qsize() + 1}")
        await self._task_queue.put(task_id)
        return await waiter

    async def wait(self, task_id: TaskID) -> TaskResult:
        async with self._lock:
            if task_id not in self._tasks:
                logger.error(f"获取任务 waiter 失败: ID={task_id}, 任务不存在")
                raise ValueError(f"not found task by id {task_id}")

            waiter = self._tasks[task_id].waiter

        if waiter is None:
            logger.error(f"获取任务 waiter 失败: ID={task_id}, waiter 为空")
            raise ValueError(f"waiter is None for task {task_id}")

        logger.debug(f"获取任务 waiter 成功: ID={task_id}")
        return await waiter

    async def _worker(self):
        worker_id = idgen.get_next_id()
        logger.debug(f"工作协程启动: ID={worker_id}")

        try:
            while not self._shutdown.is_set():
                try:
                    task_id = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                    start_time = time.time()
                    logger.debug(f"工作协程接收任务: 协程ID={worker_id}, 任务ID={task_id}")

                    await self._run_task(task_id)

                    elapsed = time.time() - start_time
                    logger.debug(f"工作协程完成任务: 协程ID={worker_id}, 任务ID={task_id}, 耗时={elapsed:.2f}秒")
                    self._task_queue.task_done()

                except asyncio.TimeoutError:
                    # 超时只是为了定期检查关闭信号
                    continue
                except Exception as e:
                    logger.error(f"工作协程异常: 协程ID={worker_id}, 错误={str(e)}")
        except asyncio.CancelledError:
            logger.debug(f"工作协程被取消: ID={worker_id}")
        except Exception as e:
            logger.error(f"工作协程意外终止: ID={worker_id}, 错误={str(e)}")
        finally:
            logger.debug(f"工作协程退出: ID={worker_id}")

    async def _run_task(self, task_id: TaskID):
        task = None
        start_time = time.time()

        try:
            async with self._lock:
                if task_id not in self._tasks:
                    logger.warning(f"任务不存在: ID={task_id}")
                    return

                task = self._tasks[task_id]
                task.status = TaskStatus.running

            if isinstance(task.source, str) and task.source in self._cache:
                logger.warning(f"同样的任务正在下载或曾经下载过: ID={task_id}, 源={task.source}")
                error = DownloadException(DownloadErrorCode.ExistInCache, f"同样的任务正在下载或曾经下载过: {task.source}")
                await self._handle_task_completion(task, result=None, error=error)
                return

            source_desc = task.source if isinstance(task.source, str) else f"Message(id={task.source.id})"
            logger.debug(f"开始执行任务: ID={task_id}, 源={source_desc}")

            result = await self._download_media(task.source)

            elapsed = time.time() - start_time
            logger.debug(f"任务成功完成: ID={task_id}, 结果路径={result}, 耗时={elapsed:.2f}秒")

            await self._handle_task_completion(task, result=result, error=None)

        except Exception as e:
            elapsed = time.time() - start_time
            error = DownloadException.from_error(e)
            logger.error(f"任务执行失败: ID={task_id}, 错误={error}, 耗时={elapsed:.2f}秒")

            if task:
                await self._handle_task_completion(task, result=None, error=error)

    async def _handle_task_completion(self, task: TaskDefinition, result: Optional[str], error: Optional[Exception]):
        async with self._lock:
            if error is not None:
                task.exception = error if isinstance(error, DownloadException) else DownloadException.from_error(error)
                task.status = TaskStatus.failure
                self._failed_count += 1
            else:
                task.result = result
                task.status = TaskStatus.success
                self._completed_count += 1

            elapsed = time.time() - task.created_at
            if task.id in self._tasks:
                del self._tasks[task.id]

        logger.debug(f"处理任务完成: ID={task.id}, 状态={task.status.name}, 总耗时={elapsed:.2f}秒")

        if task.waiter is not None:
            if error is not None:
                task.waiter.set_exception(error)
                logger.debug(f"设置任务异常结果: ID={task.id}, 异常={error}")
            else:
                task.waiter.set_result(result)
                logger.debug(f"设置任务成功结果: ID={task.id}, 结果={result}")

        if task.callback is not None:
            try:
                task.callback(error, result)
                logger.debug(f"执行任务回调: ID={task.id}")
            except Exception as e:
                logger.error(f"回调执行错误: ID={task.id}, 错误={e}")

    async def start(self):
        logger.info(f"下载服务启动: 最大并发数={self._max_concurrent}")
        # 重新打开标记
        self._shutdown.clear()

        # 创建协程工作者
        workers = [asyncio.create_task(self._worker()) for _ in range(self._max_concurrent)]
        logger.debug(f"已创建{len(workers)}个工作线程")

        # 等待关机信号
        await self._shutdown.wait()
        logger.info("下载服务收到关闭信号")

        # 等待剩余任务完成
        if not self._task_queue.empty():
            logger.info(f"等待剩余{self._task_queue.qsize()}个任务完成")
            try:
                # 设置超时，防止永久阻塞
                await asyncio.wait_for(self._task_queue.join(), timeout=300)  # 5分钟超时
                logger.info("所有队列任务已完成")
            except asyncio.TimeoutError:
                logger.warning("等待任务完成超时，强制关闭")

        # 通知所有 worker 退出
        logger.debug("取消所有工作线程")
        for worker in workers:
            worker.cancel()

        # 等待所有 worker 退出
        await asyncio.gather(*workers, return_exceptions=True)
        logger.info("下载服务已关闭")

    async def shutdown(self, wait_for_tasks=True, timeout=300):
        logger.info(f"下载服务关闭中... 等待任务完成: {wait_for_tasks}, 超时: {timeout}秒")

        # 设置关闭标志，阻止新任务提交
        self._shutdown.set()

        if not wait_for_tasks:
            # 如果不等待任务完成，清空队列
            while not self._task_queue.empty():
                try:
                    self._task_queue.get_nowait()
                    self._task_queue.task_done()
                except asyncio.QueueEmpty:
                    break
            logger.info("已清空任务队列，不等待任务完成")

    async def start_with_progress(self):
        logger.info("下载服务启动(带进度条)")
        self._progress = create_download_progress()
        with self._progress:
            await self.start()

    # 底层的下载方法
    async def _download_media(self, source: Union[types.Message, str]) -> TaskResult:
        """下载媒体文件并返回保存路径"""
        start_time = time.time()
        message = source

        if isinstance(source, str):
            logger.info(f"解析Telegram链接: {source}")
            message: types.Message = await fetch_message_by_link(client=self._client, link=source)
            logger.debug(f"链接解析完成: {source} -> Message(id={message.id if message else 'None'})")

        if message is None or not message.media:
            error_msg = f"消息不包含媒体或链接无效: {source}"
            logger.warning(error_msg)
            raise DownloadException(DownloadErrorCode.NotExistMedia, error_msg)

        media_type = MediaTypes.from_message(message)
        media_id = MediaTypes.get_media_if(message) or message.id
        cache_key = f"t-{media_id}"

        logger.info(f"处理媒体: ID={media_id}, 类型={media_type}, 缓存键={cache_key}")

        if not media_type.is_supported():
            error_msg = f"不支持的媒体类型: ID={media_id}, 类型={media_type}"
            logger.warning(error_msg)
            raise DownloadException(DownloadErrorCode.Unsupported, error_msg)

        if message.media and getattr(message.media, "ttl_seconds", None):
            error_msg = "这是阅后即焚媒体，不能下载"
            logger.warning(error_msg)
            raise DownloadException(DownloadErrorCode.Unsupported, error_msg)

        if settings.use_cache and cache_manager.contains(cache_key):
            logger.info(f"媒体已存在于缓存中: {cache_key}")
            raise DownloadException(DownloadErrorCode.ExistInCache, f"媒体已存在于缓存中: {cache_key}")

        # 控制下载速度
        await sleep(0.5)

        storage_dir = media_type.storage_dir()
        logger.info(f"开始下载媒体: ID={media_id}, 存储目录={storage_dir}")

        state = SimpleNamespace(total_bytes=0, downloaded_bytes=0, pid=None, last_log_time=time.time())

        if self._progress:
            state.pid = self._progress.add_task(description=f"{media_type.name}_{media_id}", total=None)
            logger.debug(f"创建进度条任务: ID={state.pid}, 描述={media_type.name}_{media_id}")

        def progress_callback(num: int, total: int):
            state.total_bytes = total
            state.downloaded_bytes = num

            if self._progress:
                self._progress.update(state.pid, completed=num, total=total)

        try:
            with tempfile.TemporaryDirectory() as tempdir:
                fn = self._client.download_media if isinstance(source, str) else self._bot.download_media

                downloaded_path = await fn(message, tempdir, progress_callback=progress_callback)
                if not downloaded_path or not os.path.exists(downloaded_path) or os.path.getsize(downloaded_path) == 0:
                    raise DownloadException(DownloadErrorCode.Unknown, "Download failed or created empty file")

                # fix: 修复媒体文件覆盖的问题（同一组或同一个相册的媒体其文件名可能是相同的）
                # 原始文件路径可能重复，需加唯一标识
                _, file_extension = os.path.splitext(downloaded_path)

                # 使用媒体 ID 构造唯一的缓存 key
                new_filename = f"{cache_key}{file_extension}"

                # 最终文件路径避免覆盖
                file_path = os.path.join(storage_dir, new_filename)

                # 拷贝或移动文件
                shutil.move(downloaded_path, file_path)

            elapsed = time.time() - start_time

            if self._progress:
                self._progress.update(state.pid, completed=state.total_bytes, total=state.total_bytes)

            cache_manager.set(cache_key)

            speed = state.total_bytes / elapsed / 1024 if elapsed > 0 else 0
            logger.info(
                f"媒体下载成功: ID={media_id}, 文件路径={file_path}, "
                f"大小={state.total_bytes / 1024 / 1024:.2f}MB, "
                f"耗时={elapsed:.2f}秒, "
                f"平均速度={speed:.2f}KB/s"
            )
            return file_path

        except Exception as e:
            logger.info(e)
            elapsed = time.time() - start_time
            if self._progress:
                self._progress.update(state.pid, failed=True)

            logger.error(
                f"媒体下载失败: ID={media_id}, 错误={str(e)}, "
                f"已下载={state.downloaded_bytes / 1024 / 1024:.2f}MB, "
                f"耗时={elapsed:.2f}秒",
            )
            raise DownloadException.from_error(e)
