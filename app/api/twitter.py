import json
import pydash

from typing import Optional, Tuple
from dataclasses import dataclass
from twitter_openapi_python_generated import models
from twitter_openapi_python import (
    TwitterOpenapiPython,
    TwitterOpenapiPythonClient
)
from twitter_openapi_python.models import (
    UserApiUtilsData,
    TweetApiUtilsData,
    TimelineApiUtilsResponse
)

from app.infra.logger import getLogger
from app.twitter.models import UserInfo, MediaInfo, MediaTypes

logger = getLogger(__name__)


@dataclass
class TwitterAPI:
    api: TwitterOpenapiPythonClient

    def get_user_info(self, screen_name: str) -> UserInfo:
        res = self.api.get_user_api().get_user_by_screen_name(screen_name=screen_name)
        data: UserApiUtilsData = res.data

        return UserInfo(
            name=data.user.legacy.name,
            rest_id=data.user.rest_id,
            screen_name=data.user.legacy.screen_name,
            media_count=data.user.legacy.media_count,
        )

    def get_user_likes_medias(self, rest_id: str, count: int = 20, cursor: Optional[str] = None) -> Tuple[list[MediaInfo], str]:
        res = self.api.get_tweet_api().get_likes(user_id=rest_id, count=count, cursor=cursor)
        data: TimelineApiUtilsResponse[TweetApiUtilsData] = res.data

        next_cursor = data.cursor.bottom.value if data.cursor.bottom is not None else None

        result: list[MediaInfo] = []

        for itemValue in data.data:
            medias = extract_media(tweet=itemValue.tweet)
            result.extend(medias)

        return result, next_cursor

    def get_user_medias(self, rest_id: str, count: int = 20, cursor: Optional[str] = None) -> Tuple[list[MediaInfo], str]:
        res = self.api.get_tweet_api().get_user_media(user_id=rest_id, count=count, cursor=cursor)
        data: TimelineApiUtilsResponse[TweetApiUtilsData] = res.data

        next_cursor = data.cursor.bottom.to_str() if data.cursor.bottom is not None else None

        result: list[MediaInfo] = []

        for itemValue in data.data:
            medias = extract_media(tweet=itemValue.tweet)
            result.extend(medias)

        return result, next_cursor

    @staticmethod
    def create(auth_token: str, ct0: str) -> "TwitterAPI":
        client = TwitterOpenapiPython()
        # 这个库cookies正确的应该不是这样传的，但是这样传也能拿到数据
        x = client.get_client_from_cookies(cookies={
            "ct0": ct0,
            "auth_token": auth_token,
        })
        return TwitterAPI(api=x)


def extract_media(tweet: models.Tweet) -> list[MediaInfo]:
    result = []
    medias = pydash.get(tweet, "legacy.extended_entities.media") or pydash.get(tweet, "legacy.entities.media") or []
    for m in medias:
        mtype = pydash.get(m, "type")
        media_key = pydash.get(m, "media_key") or pydash.get(m, "id_str") or str(pydash.get(m, "id"))

        if mtype not in ["image", "video", "photo"]:
            continue

        base = {
            "type": mtype,
            "key": media_key,
        }

        if mtype == "photo":
            url = pydash.get(m, "media_url_https") or pydash.get(m, "media_url")
            if not url:
                logger.debug("Skip media: missing image URL | key=%s type=%s", media_key, mtype)
                continue

            # 确保是高清图
            base["url"] = url + "?name=orig"

        elif mtype in {"video", "animated_gif"}:
            variants = pydash.get(m, "video_info.variants", [])
            mp4s = [v for v in variants if v.content_type == "video/mp4"]
            best: models.MediaVideoInfoVariant = max(mp4s, key=lambda v: v.bitrate or -1, default=None)

            if not best:
                logger.debug("Skip media: no usable mp4 variant | key=%s type=%s", media_key, mtype)
                debug_keys = ["media_key", "type", "media_url", "video_info"]
                logger.debug("Media skipped: raw=%s", json.dumps(pydash.pick(m, debug_keys), ensure_ascii=False))
                continue

            base["url"] = best.url
            base["mimetype"] = best.content_type
            base["bitrate"] = best.bitrate or None
            base["duration"] = pydash.get(m, "video_info.duration_millis")

        result.append(MediaInfo(
            id=media_key,
            url=base.get("url"),
            original_type=mtype,
            type=MediaTypes.from_string(mtype),
            bitrate=base.get("bitrate") or None,
            mimetype=base.get("mimetype") or None,
            duration=base.get("duration") or None,
        ))

    return result
