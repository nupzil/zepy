import time
from typing import Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, wait

from app.infra.logger import getLogger

logger = getLogger(__name__)


class Downloader:
    # - 不能抛出错误
    # - 需要自己维护下一页，使用方只需要调用
    # - 抛出错误时返回 None，没有数据时返回空 list
    def get_medias(self, count: int) -> Optional[list[Any]]:
        raise NotImplementedError("Subclasses must implement get_medias")

    # - 不能抛出错误
    # - 需要是线程安全的
    # - 自己维护重试之类的机制。
    def download_media(self, media: Any) -> None:
        raise NotImplementedError("Subclasses must implement download_media")


class ThreadedExecutor:

    def __init__(self, max_workers: int):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def start_download(self, downloader: Downloader, count: int):
        count = min(max(count, 1), 50)

        while True:
            # 这个方法不能抛出错误，只能返回 None，这里不做捕获，需要实现方自己注意
            items = downloader.get_medias(count=count)
            if items is None or len(items) == 0:
                # 不输出日志免得干扰外部的进度条
                break

            # 提交下载任务
            futures = [self.executor.submit(downloader.download_media, media) for media in items]

            # 等待所以任务完成
            wait(futures)

            # 稍微等待一下
            time.sleep(0.5)

    # 提交一批任务并等待执行完毕
    def submit_tasks(self, handler: Callable[[Any], None], args: list[Any]) -> None:
        # 提交任务
        futures = [self.executor.submit(handler, arg) for arg in args]

        # 等待所以任务完成
        wait(futures)

        # 稍微等待一下
        time.sleep(0.5)

    # 清理资源
    def shutdown(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=False)
