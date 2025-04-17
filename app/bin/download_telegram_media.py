import asyncio
from typing import Optional

from app.telegram.downloader import logger
from app.telegram.singleton import settings
from app.telegram.downloader import DownloadService
from app.telegram.client import create_telegram_client
from app.telegram.input import get_links_for_configure_or_raise


async def submit_task_wrap(downloader: DownloadService, url: str) -> Optional[str]:
    try:
        result = await downloader.submit_async(url)
        logger.debug(f"{url} 下载成功，已存储至 {result}")
        return None
    except Exception as e:
        logger.error(f"{url} 下载失败：{e}", exc_info=True)
        return url


async def bulk_submit_task(downloader: DownloadService, batch_urls: list[str]) -> list[str]:
    tasks = []
    for url in batch_urls:
        tasks.append(asyncio.create_task(submit_task_wrap(downloader, url)))
    results = await asyncio.gather(*tasks)
    return [url for url in results if url is not None]


# 无法复用 Telegram Desktop App 的 session 访问权限是受限的
async def main():
    urls = list(get_links_for_configure_or_raise())
    client = create_telegram_client(settings.api_id, settings.api_hash, proxy=settings.proxy_tuple)
    downloader = DownloadService(client, bot=None, max_concurrent=settings.max_concurrent, silent=False)

    await client.start(phone=settings.phone)

    me = await client.get_me()
    logger.info(f'Logged in as {me.username}')

    # 批量处理 urls，每次最多处理 4 条
    batch_size = 4
    failed_urls = []
    total_urls = len(urls)

    # 所有批次处理完成后，启动下载进度显示
    # todo 目前task如果抛出错误会一直阻塞
    task = asyncio.create_task(downloader.start_with_progress())

    for i in range(0, total_urls, batch_size):
        batch_urls = urls[i:i + batch_size]
        logger.debug(
            f"处理第 {i // batch_size + 1} 批，"
            f"共 {len(batch_urls)} 条链接 ({i + 1}-{min(i + len(batch_urls), total_urls)}/{total_urls})"
        )

        # 提交当前批次的任务
        batch_results = await bulk_submit_task(downloader, batch_urls)

        # 收集失败任务
        if batch_results:
            failed_urls.extend(batch_results)

        logger.debug(f"第 {i // batch_size + 1} 批处理完成")

    # 输出失败统计
    if failed_urls:
        logger.warning(f"共有 {len(failed_urls)} 条链接下载失败")
        for idx, failed_url in enumerate(failed_urls):
            logger.warning(f"失败链接 {idx + 1}: {failed_url}")
    else:
        logger.info("所有链接下载成功")

    await downloader.shutdown()
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
