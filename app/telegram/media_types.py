import os
from typing import  Optional
from pathlib import Path
from enum import Enum, auto
from telethon.tl.custom.message import Message

from app.twitter.singleton import settings


class MediaTypes(Enum):
    # 图像与视频类
    PHOTO = auto()  # 普通图片
    VIDEO = auto()  # 普通视频
    ANIMATION = auto()  # 动图 (GIF)
    VIDEO_NOTE = auto()  # 圆形视频

    # 音频类
    AUDIO = auto()  # 音乐（带标签的音频）
    VOICE = auto()  # 语音消息（.ogg）

    # 文件类
    DOCUMENT = auto()  # 普通文件（PDF/ZIP/图片/视频等以“文件”形式发送）

    UNKNOWN = auto()  # 无法识别的媒体类型

    def is_supported(self) -> bool:
        return self != MediaTypes.UNKNOWN

    def storage_dir(self) -> str:
        base = Path(settings.storage_directory) / "telegram"
        match self:
            case MediaTypes.PHOTO:
                subdir = 'images'
            case MediaTypes.VIDEO:
                subdir = "videos"
            case MediaTypes.ANIMATION:
                subdir = "gifs"
            case MediaTypes.AUDIO | MediaTypes.VOICE:
                subdir = "audios"
            case MediaTypes.UNKNOWN:
                subdir = "unknown"
            case _:
                subdir = "documents"

        full_path = base / subdir
        os.makedirs(full_path, exist_ok=True)
        return str(full_path)

    @staticmethod
    def get_media_if(message: Message) -> Optional[str]:
        media = message.media
        if not media:
            return None
        if hasattr(media, 'photo'):  # 如果是图片
            return media.photo.id
        elif hasattr(media, 'document'):  # 如果是文档（文件）
            return media.document.id
        elif hasattr(media, 'video'):  # 如果是视频
            return media.video.id
        elif hasattr(media, 'audio'):  # 如果是音频
            return media.audio.id
        elif hasattr(media, 'voice'):  # 如果是语音
            return media.voice.id
        elif hasattr(media, 'gif'):  # 如果是语音
            return media.gif.id
        elif hasattr(media, 'video_note'):  # 如果是语音
            return media.video_note.id
        else:
            return None


    @staticmethod
    def from_message(message: Message) -> "MediaTypes":
        if message.photo:
            return MediaTypes.PHOTO
        if message.video:
            return MediaTypes.VIDEO
        if message.gif:
            return MediaTypes.ANIMATION
        if message.video_note:
            return MediaTypes.VIDEO_NOTE
        if message.audio:
            return MediaTypes.AUDIO
        if message.voice:
            return MediaTypes.VOICE
        if message.document:
            return MediaTypes.DOCUMENT
        return MediaTypes.UNKNOWN
