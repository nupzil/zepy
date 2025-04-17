import os
import mimetypes
from enum import Enum
from typing import Optional
from dataclasses import dataclass
from pathlib import PurePosixPath, Path
from urllib.parse import urlparse, unquote

from app.twitter.singleton import settings


@dataclass
class UserInfo:
    name: str
    rest_id: str
    screen_name: str
    media_count: int = 0


@dataclass
class MediaInfo:
    id: str
    # 这个 url 是原始的或者说是可以直接通过其下载的。
    url: str
    type: "MediaTypes"
    original_type: str
    bitrate: Optional[int] = None
    duration: Optional[int] = None
    mimetype: Optional[str] = None

    def extension(self) -> Optional[str]:
        if self.mimetype is not None:
            extension = mimetypes.guess_extension(self.mimetype)
            if extension is not None:
                return extension

        path = unquote(urlparse(self.url).path)

        suffix = PurePosixPath(path).suffix

        return suffix if not suffix else None


class MediaTypes(str, Enum):
    image = "image"
    video = "video"
    other = "other"

    def storage_dir(self):
        base = Path(settings.storage_directory) / settings.username
        match self:
            case MediaTypes.image:
                subdir = 'images'
            case MediaTypes.video:
                subdir = "videos"
            case _:
                subdir = "others"

        full_path = base / subdir
        os.makedirs(full_path, exist_ok=True)
        return str(full_path)

    @staticmethod
    def allow_download(media: MediaInfo) -> bool:
        if media.type == MediaTypes.image and not settings.only_video:
            return True

        if media.type == MediaTypes.video and not settings.only_image:
            return True

        return False

    @staticmethod
    def from_string(typo: str) -> "MediaTypes":
        if typo == "photo":
            return MediaTypes.image
        elif typo == "video":
            return MediaTypes.video
        else:
            return MediaTypes.other
