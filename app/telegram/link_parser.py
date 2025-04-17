from typing import Optional
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
from telethon import TelegramClient, types


@dataclass
class TelegramLinkInfo:
    is_private: bool = False
    peer_id: Optional[str] = None
    thread_id: Optional[int] = None
    message_id: Optional[int] = None
    comment_id: Optional[int] = None

    async def resolve_message(self, client: TelegramClient) -> Optional[types.Message]:
        if not self.peer_id or not self.message_id:
            return None
        """
        官方文档说明了私有链接 peer_id 必定是频道或超级组 ID
        - https://core.telegram.org/api/links#message-links
        - https://core.telegram.org/api/bots/ids
        目前支持几种链接：
        - t.me/<username>/<id>
        - t.me/c/<channel>/<id>
        - t.me/<username>/<thread_id>/<id>
        - t.me/c/<channel>/<thread_id>/<id>
        - t.me/<username>/<id>?comment=<comment>
        - t.me/c/<channel>/<id>?comment=<comment>
        - t.me/<username>/<id>?thread=<thread_id>
        - t.me/c/<channel>/<id>?thread=<thread_id>
        """
        peer_id = self.peer_id
        message_id = int(self.comment_id or self.message_id)
        if self.is_private:
            peer_id = int(peer_id)
            peer_id = -(1000000000000 + peer_id)

        try:
            input_peer = await client.get_input_entity(peer_id)
            if self.comment_id:
                main_msg: types.Message = await client.get_messages(input_peer, ids=int(self.message_id))
                if not (main_msg and main_msg.replies and main_msg.replies.channel_id):
                    print(f"Error resolving comment message")
                    return None
                discussion_peer = await client.get_entity(types.PeerChannel(main_msg.replies.channel_id))
                return await client.get_messages(discussion_peer, ids=int(self.comment_id))
            return await client.get_messages(input_peer, ids=message_id)
        except Exception as e:
            print(f"Error resolving message: {e}")
            return None


class InvalidTelegramLinkError(ValueError):
    pass


def parse_telegram_link(link: str) -> TelegramLinkInfo:
    link = link.strip()
    if not link.startswith("https://t.me/"):
        raise InvalidTelegramLinkError("Invalid Telegram link format: must start with https://t.me/")
    """
    - https://core.telegram.org/api/links#message-links
    - https://core.telegram.org/api/bots/ids
    1. 群组/频道
     - https://t.me/c/channel_id/msg_id
     - https://t.me/username/msg_id
    2. 群组/频道-评论信息
     - https://t.me/c/channel_id/msg_id?comment=reply_id
     - https://t.me/username/msg_id?comment=reply_id
    3. 群组/频道-主题信息
     - https://t.me/username/msg_id?thread=root_id
     - https://t.me/c/channel_id/msg_id?thread=root_id
     - https://t.me/username/root_id/msg_id
     - https://t.me/c/channel_id/root_id/msg_id
    """
    try:
        parsed_url = urlparse(link)
        query_params = parse_qs(parsed_url.query)
        path_parts = [p for p in parsed_url.path.split('/') if p]

        thread_id_str = query_params.get('thread', [None])[0]
        comment_id_str = query_params.get('comment', [None])[0]

        thread_id = int(thread_id_str) if thread_id_str and thread_id_str.isdigit() else None
        comment_id = int(comment_id_str) if comment_id_str and comment_id_str.isdigit() else None

        is_private = False
        if path_parts and path_parts[0] == 'c':
            is_private = True
            path_parts = path_parts[1:]

        link_info = None
        num_parts = len(path_parts)
        if num_parts == 2 and thread_id is not None and path_parts[1].isdigit():
            link_info = TelegramLinkInfo(
                peer_id=path_parts[0],
                message_id=int(path_parts[1]),
                thread_id=thread_id,
                is_private=is_private
            )
        elif num_parts == 2 and path_parts[1].isdigit():
            link_info = TelegramLinkInfo(
                peer_id=path_parts[0],
                message_id=int(path_parts[1]),
                comment_id=comment_id,
                thread_id=thread_id,
                is_private=is_private
            )
        elif num_parts == 3 and path_parts[1].isdigit() and path_parts[2].isdigit():
            link_info = TelegramLinkInfo(
                peer_id=path_parts[0],
                message_id=int(path_parts[2]),
                thread_id=int(path_parts[1]),
                is_private=is_private
            )

        if not link_info:
            raise InvalidTelegramLinkError(f"Unsupported Telegram link format: {link}")
        return link_info
    except ValueError:
        raise InvalidTelegramLinkError(f"Invalid integer format in link: {link}")
    except Exception as e:
        raise InvalidTelegramLinkError(f"Error parsing Telegram link '{link}': {e}")


async def fetch_message_by_link(client: TelegramClient, link: str) -> types.Message:
    link_info = parse_telegram_link(link=link)
    message = await link_info.resolve_message(client)
    if not message:
        raise InvalidTelegramLinkError(f"Could not resolve message for link: {link}")
    return message


__all__ = [
    "TelegramLinkInfo",
    "InvalidTelegramLinkError",
    "parse_telegram_link",
    "fetch_message_by_link",
]
