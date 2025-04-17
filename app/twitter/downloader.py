import os
import logging
import mimetypes
import requests
import rich.logging
from pathlib import Path
from time import sleep
from threading import Lock
from typing import Optional

from app.api.twitter import TwitterAPI
from app.twitter.executor import Downloader
from app.twitter.progress import ProgressManager
from app.twitter.models import UserInfo, MediaInfo, MediaTypes
from app.twitter.singleton import threaded_pool, settings, cache_manager

logger = logging.getLogger(__name__)
fh = rich.logging.RichHandler()
fh.setLevel(logging.DEBUG)
logger.setLevel(logging.DEBUG)
logger.addHandler(fh)


class FakeResponse:
    def __init__(self, total_size, chunk_size):
        self.total_size = total_size
        self.chunk_size = chunk_size
        self._pos = 0

    def iter_content(self, chunk_size=1024):
        while self._pos < self.total_size:
            sleep(0.5)
            chunk = b"x" * min(chunk_size, self.total_size - self._pos)
            self._pos += len(chunk)
            yield chunk


class TwitterLikesMediaDownloader(Downloader):
    # 目前使用的是线程池下载
    lock = Lock()
    api: TwitterAPI
    user_info: UserInfo

    limit: int = 20
    timeout: float = 120.0
    chunk_size: int = 8192

    # 上面的属性都是常量不会修改的
    api_request_count: int = 0
    image_download_count: int = 0
    video_download_count: int = 0

    def __init__(self):
        # 获取下一页数据的 token
        self.cursor: Optional[str] = None
        # 下载失败的数据-目前暂时没有重试机制
        self.failed_list: list[MediaInfo] = []
        self.progress = ProgressManager()
        self.session: requests.Session = requests.Session()
        self.api = TwitterAPI.create(auth_token=settings.auth_token, ct0=settings.ct0)
        logger.debug("TwitterLikesMediaDownloader 初始化完成")

    # 私有方法-暂时使用继承实现导致公开了
    def get_medias(self, count: int) -> Optional[list[MediaInfo]]:
        try:
            with self.lock:
                cursor = self.cursor
                rest_id = self.user_info.rest_id

            logger.debug(f"开始获取媒体数据，count={count}, cursor={cursor[:20] if cursor else None}...")

            count = min(max(1, count), 2)
            result, next_cursor = self.api.get_user_likes_medias(rest_id=rest_id, count=count, cursor=cursor)

            if result:
                self.progress.add_total(len(result))
                logger.debug(f"成功获取 {len(result)} 个媒体数据")
            else:
                logger.debug("未获取到媒体数据")

            with self.lock:
                self.cursor = next_cursor
                self.api_request_count += 1

            return result
        except Exception as e:
            logger.debug(f"[ERROR] get_medias: {e}")
            return None

    # 私有方法-暂时使用继承实现导致公开了
    def download_media(self, media: MediaInfo) -> None:
        media_id = media.id
        logger.debug(f"开始下载媒体 {media_id}, URL: {media.url}")
        try:
            if not MediaTypes.allow_download(media):
                raise ValueError(f"[SKIP] 媒体类型不匹配: {media.original_type}")

            key = f"x-{media.id}"

            # 如果曾经下载过了
            if cache_manager and cache_manager.contains(key):
                raise ValueError(f"[SKIP] 已缓存: {key}")

            save_dir = Path(media.type.storage_dir())
            # 确保目录存在
            save_dir.mkdir(parents=True, exist_ok=True)

            temp = save_dir / f"x-likes-{media.id}{media.extension()}.tmp"

            # 删除下载失败的残余文件
            if temp.exists():
                temp.unlink()
                logger.debug(f"删除残余临时文件: {temp}")

            # 发送请求并获取文件大小
            res = self.session.get(media.url, stream=True, timeout=self.timeout)
            res.raise_for_status()

            # 获取文件总大小
            total_size = int(res.headers.get('content-length', 0))
            if total_size > 0:
                logger.debug(f"媒体 {media_id} 大小: {total_size / 1024:.2f} KB")

            # 下载文件并更新进度
            with open(temp, "wb") as f:
                for chunk in res.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)

            # 处理文件扩展名
            ctype = res.headers.get("Content-Type", "").split(";")[0]
            ext = mimetypes.guess_extension(ctype) or media.extension()
            if ext == ".jpe":
                ext = ".jpg"

            final = save_dir / f"x-likes-{media.id}{ext}"
            logger.debug(f"下载完成，重命名文件: {temp} -> {final}")

            # 下载完成修改文件名
            os.replace(temp, final)
            cache_manager.set(key)

            with self.lock:
                if media.type == MediaTypes.image:
                    self.image_download_count += 1
                elif media.type == MediaTypes.video:
                    self.video_download_count += 1

            self.progress.update()
            logger.debug(f"媒体 {media_id} 下载成功")

        except Exception as e:
            with self.lock:
                self.failed_list.append(media)
            logger.debug(f"[FAIL] {media.id}: {e}")
            self.progress.update(failures=True)

    # 入口方法
    # todo 目前进度条失效-后面再改
    def start(self):
        logger.debug("开始下载Twitter点赞媒体...")
        user_info = self.api.get_user_info(screen_name=settings.username)
        self.user_info = user_info
        self.api_request_count += 1

        logger.debug(f"用户信息: {user_info.name} (@{user_info.screen_name}), ID: {user_info.rest_id}")
        logger.debug(f"下载的文件将存储在：{settings.storage_directory}/{settings.username}")

        self.progress.start()

        # 开始下载
        logger.debug(f"开始下载，限制数量: {self.limit}")
        threaded_pool.start_download(downloader=self, count=self.limit)

        # 停止进度条
        self.progress.close()

        # 线程池生命周期由调用者负责维护
        logger.debug("<<<<<下载完成>>>>>")
        logger.debug(
            f"API请求: {self.api_request_count}, "
            f"图片: {self.image_download_count}, "
            f"视频: {self.video_download_count}, "
            f"失败: {len(self.failed_list)}"
        )

        # 输出失败的媒体ID列表
        if self.failed_list:
            failed_ids = [media.id for media in self.failed_list]
            logger.debug(f"失败的媒体ID: {failed_ids}")
