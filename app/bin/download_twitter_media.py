from app.infra.logger import getLogger
from app.twitter.singleton import threaded_pool
from app.twitter.downloader import TwitterLikesMediaDownloader

logger = getLogger(__name__)

if __name__ == '__main__':
    TwitterLikesMediaDownloader().start()

    threaded_pool.shutdown()
