import re
import asyncio
import logging
import time
import textwrap
from pathlib import Path

from telethon.tl import types
from telethon import events, types

from app.telegram.singleton import settings
from app.telegram.downloader import DownloadService
from app.telegram.client import create_telegram_bot_client, create_telegram_client

# 改进日志配置
logger = logging.getLogger("/bot-service")

_fh2 = logging.StreamHandler()
_fh3 = logging.FileHandler(f"{settings.logs}/bot-service.log", mode='a')
_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

_fh2.setLevel(logging.DEBUG)
_fh3.setLevel(logging.DEBUG)

_fh2.setFormatter(_formatter)
_fh3.setFormatter(_formatter)

logger.addHandler(_fh2)
logger.addHandler(_fh3)
logger.setLevel(logging.DEBUG)


async def start_command(event):
    await event.respond((Path(__file__).parent / "bot-start-command.txt").read_text(encoding='utf-8'))


async def help_command(event):
    await event.respond((Path(__file__).parent / "bot-help-command.txt").read_text(encoding='utf-8'))


class TelegramBotService:
    def __init__(self):
        self.client = create_telegram_client(settings.api_id, settings.api_hash, proxy=settings.proxy_tuple)
        self.bot = create_telegram_bot_client(settings.api_id, settings.api_hash, proxy=settings.proxy_tuple)
        # 必须使用  bot 才能下载用户转发的媒体
        self.downloader = DownloadService(self.client, bot=self.bot, max_concurrent=settings.max_concurrent, silent=False)

        self.media_group_lock = asyncio.Lock()
        self.media_group_timers: dict[int, asyncio.Task] = {}
        self.pending_media_groups: dict[int, list[types.Message]] = {}

    async def start(self):
        # 需要添加 await
        await self.client.start(phone=settings.phone)
        await self.bot.start(bot_token=settings.bot_token)

        self._setup_handlers()

        # 并发等待两个连接
        await asyncio.gather(
            self.downloader.start(),
            self.bot.run_until_disconnected(),
            self.client.run_until_disconnected()
        )

    async def _get_download_status(self, event):
        try:
            status = await self.downloader.status()
            await event.respond(textwrap.dedent(
                f"""
                📊 **下载进度一览**
                
                ▶️ 正在下载: {status.running_count}
                ⏳ 等待队列: {status.pending_count}
                ✅ 下载成功: {status.completed_count}
                ⚠️ 下载失败: {status.failed_count}
                """
            ))
        except Exception as e:
            logger.error(f"查询服务器状态失败: {e}", exc_info=True)
            await event.reply(f"❌ 服务器异常: {e}")

    async def _handle_media_message(self, event):
        message: types.Message = event.message
        if not message.media:
            return
        group_id = message.grouped_id
        if message.grouped_id:
            logger.debug(f"收到媒体组 {group_id} 的一部分 (消息ID: {message.id})")
            # 使用异步锁保护共享数据的访问
            async with self.media_group_lock:
                # 如果是媒体组的一部分
                # 1. 将消息添加到对应的组中
                if group_id not in self.pending_media_groups:
                    self.pending_media_groups[group_id] = []
                self.pending_media_groups[group_id].append(message)

                # 2. 如果该组已存在计时器，取消它（因为收到了新消息，需要重置计时）
                if group_id in self.media_group_timers:
                    logger.debug(f"重置媒体组 {group_id} 的计时器.")
                    self.media_group_timers[group_id].cancel()

            # 3. 安排新的延迟调度任务 (这个任务本身很快完成)
            await self._schedule_media_group_processing(group_id)
        else:
            logger.debug(f"收到单个媒体 (消息ID: {message.id})")
            asyncio.create_task(self._process_single_media(message=message))
            logger.debug(f"已为单个媒体 {message.id} 创建后台处理任务。")

    async def _handle_link_message(self, event) -> None:
        try:
            message = event.message
            telegram_links = re.findall(r"(https?://t\.me/\S+)", message.raw_text)
            if not telegram_links:
                await event.reply("⚠️ 未检测到 Telegram 链接。")
                return
            asyncio.create_task(self._process_telegram_links(message=event.message, links=telegram_links))
        except Exception as e:
            logger.error("下载失败: %s", e, exc_info=True)
            await event.reply(f"❌ 链接下载失败：{e}")

    async def _process_telegram_links(self, message: types.Message, links: list[str]):
        logger.info(f"开始处理 {len(links)} 个链接")
        start_time = time.time()

        # 定义单个链接下载任务
        async def download_link(index, link):
            try:
                logger.debug(f"开始下载链接 ({index}/{len(links)}): {link}")
                result = await self.downloader.submit_async(link)
                logger.info(f"链接 {index}/{len(links)} 下载成功: {result}")
                return index, True, result, None, link
            except Exception as e:
                error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
                logger.error(f"链接 {index}/{len(links)} 下载失败: {e}", exc_info=True)
                return index, False, None, error_msg, link

        # 并发执行所有下载任务
        download_tasks = [download_link(i + 1, link) for i, link in enumerate(links)]
        download_results = await asyncio.gather(*download_tasks)

        # 处理结果
        reply_lines = []
        failed_count = 0
        success_count = 0

        # 按原始顺序整理结果
        sorted_results = sorted(download_results, key=lambda x: x[0])

        for index, is_success, file_path, error_message, url in sorted_results:
            if is_success:
                success_count += 1
                reply_lines.append(f"✅ {url}")
            else:
                failed_count += 1
                reply_lines.append(f"❌ {url} \n⚠️ 错误: {error_message}")

        end_time = time.time()
        download_duration = end_time - start_time

        # 添加摘要信息
        summary = (
            f"📊 链接处理完成: \n"
            f"成功 {success_count}/{len(links)}\n"
            f"失败 {failed_count}/{len(links)}\n"
            f"耗时 {download_duration:.2f} 秒"
        )
        """
        📥 批量下载完成：

        ✅ 成功（3）:
        1. https://t.me/c/xxx1
        2. https://t.me/c/xxx2
        3. https://t.me/c/xxx3

        ❌ 失败（2）:
        1. https://t.me/c/yyy1 - 文件已过期
        2. https://t.me/c/yyy2 - 无法访问私有频道

        ⏱️ 总耗时：12.4 秒
        """
        logger.info(summary)
        reply_lines.append("\n" + summary)

        await self._send_reply(message.peer_id, message.id, reply_text="\n\n".join(reply_lines))

    async def _send_reply(self, peer_id, message_id: int, reply_text: str):
        try:
            logger.debug(f"开始发送消息回复")
            await self.bot.send_message(entity=peer_id, message=reply_text, reply_to=message_id)
            logger.debug(f"消息回复成功")
        except Exception as e:
            logger.error(f"消息回复失败: {e}", exc_info=True)

    async def _schedule_media_group_processing(self, group_id: int, delay: float = 1.5):
        # 创建处理任务
        async def process_group_after_delay():
            try:
                await asyncio.sleep(delay)
                # 延迟结束后，检查 group_id 是否还在 pending_media_groups 中
                messages_to_process = None
                async with self.media_group_lock:
                    if group_id in self.pending_media_groups:
                        messages_to_process = self.pending_media_groups.pop(group_id)  # 取出并删除
                        # 清理计时器字典
                        if group_id in self.media_group_timers:
                            del self.media_group_timers[group_id]

                if messages_to_process:
                    # 对消息按 ID 排序，确保顺序正确
                    messages_to_process.sort(key=lambda m: m.id)
                    await self._process_media_group(group_id, messages_to_process)

            except asyncio.CancelledError:
                # 如果任务被取消（因为收到了同一组的新消息），则不执行任何操作
                logger.debug(f"媒体组 {group_id} 的处理任务被取消/重置.")
            except Exception as e:
                logger.error(f"处理媒体组 {group_id} 延迟任务时发生意外错误: {e}")
                # 确保即使出错也尝试清理
                async with self.media_group_lock:
                    if group_id in self.pending_media_groups:
                        del self.pending_media_groups[group_id]
                    if group_id in self.media_group_timers:
                        del self.media_group_timers[group_id]

        # 创建并存储任务
        delay_task = asyncio.create_task(process_group_after_delay())
        async with self.media_group_lock:
            self.media_group_timers[group_id] = delay_task
        logger.debug(f"已为媒体组 {group_id} 安排处理任务，延迟 {delay} 秒.")

    async def _process_media_group(self, group_id: int, messages: list[types.Message]):
        logger.debug(f"--- 开始处理媒体组 (ID: {group_id}) 包含 {len(messages)} 条消息 ---")
        messages.sort(key=lambda m: m.id)
        first_message = messages[0]  # 用于回复

        start_time = time.time()

        # 定义单个媒体下载任务
        async def download_media(index, media_message):
            try:
                file_path = await self.downloader.submit_async(media_message)
                logger.debug(f"媒体组 {group_id} 的第 {index}/{len(messages)} 个媒体下载成功: {file_path}")
                return index, True, file_path, None
            except Exception as e:
                logger.error(f"媒体组 {group_id} 的第 {index}/{len(messages)} 个媒体下载失败: {e}", exc_info=True)
                return index, False, None, str(e)[:50] + "..."

        # 并发执行所有下载任务
        download_tasks = [download_media(i + 1, msg) for i, msg in enumerate(messages)]
        download_results = await asyncio.gather(*download_tasks)

        # 处理结果
        reply_lines = []
        success_count = 0
        failed_count = 0

        # 按原始顺序整理结果
        sorted_results = sorted(download_results, key=lambda x: x[0])

        for index, is_success, file_path, error_message in sorted_results:
            if is_success:
                success_count += 1
                reply_lines.append(f"✅ 媒体 {index}/{len(messages)} 下载成功")
            else:
                failed_count += 1
                reply_lines.append(f"❌ 媒体 {index}/{len(messages)} 下载失败: {error_message}")

        end_time = time.time()
        download_duration = end_time - start_time

        # 添加摘要信息
        summary = (
            f"📊 媒体相册处理完成: "
            f"成功 {success_count}/{len(messages)}, "
            f"失败 {failed_count}/{len(messages)}, "
            f"耗时 {download_duration:.2f} 秒"
        )
        """
        📷 相册下载完成：

        ✅ 成功（3）:
        1. 项目 1
        2. 项目 2
        3. 项目 3

        ❌ 失败（1）:
        4. 项目 4 - 文件损坏

        ⏱️ 总耗时：12.4 秒
        """
        logger.info(summary)
        reply_lines.append("\n" + summary)

        await self._send_reply(
            peer_id=first_message.peer_id,
            message_id=first_message.id,
            reply_text='\n'.join(reply_lines)
        )

    async def _process_single_media(self, message: types.Message):
        msg_id = message.id
        logger.debug(f"--- 开始处理单个媒体 (消息ID: {msg_id}) ---")

        file_path = None
        start_time = time.time()
        try:
            file_path = await self.downloader.submit_async(message)
            logger.info(f"媒体 {msg_id} 下载成功，存储于: {file_path}")
        except Exception as e:
            logger.error(f"媒体 {msg_id} 下载失败: {e}", exc_info=True)
        finally:
            end_time = time.time()
            download_duration = end_time - start_time
            logger.debug(f"--- 单个媒体 {msg_id} 处理完毕，耗时: {download_duration:.2f} 秒 ---")

        if file_path:
            reply_text = f"✅ 文件下载成功\n⏱️ 耗时: {download_duration:.2f} 秒"
        else:
            reply_text = f"❌ 文件下载失败\n⏱️ 耗时: {download_duration:.2f} 秒"

        await self._send_reply(peer_id=message.peer_id, message_id=message.id, reply_text=reply_text)

    def _setup_handlers(self):
        handlers = [
            (help_command, events.NewMessage(pattern="/help")),
            (start_command, events.NewMessage(pattern="/start")),
            (self._get_download_status, events.NewMessage(pattern="/status")),
            (self._handle_media_message, events.NewMessage()),
            (self._handle_link_message, events.NewMessage(pattern=r"(https?://t\.me/\S+)")),
        ]

        for handler, event in handlers:
            self.bot.add_event_handler(handler, event)

    async def dispose(self):
        await self.downloader.shutdown()
        await self.client.disconnect()
        await self.bot.disconnect()
