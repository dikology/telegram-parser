"""Telegram access seam: list groups and forum topics."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Iterator, Protocol

from telethon.sync import TelegramClient
from telethon.tl.tlobject import TLObject, TLRequest

# Adapted from chigwell/telegram-mcp (Apache-2.0) — GetForumTopicsRequest
# is still missing from Telethon's generated TL layer.


class GetForumTopicsRequest(TLRequest):
    """Raw request for channels.getForumTopics (not shipped in Telethon yet)."""

    CONSTRUCTOR_ID = 0x0DE560D1
    SUBCLASS_OF_ID = 0x0

    def __init__(self, channel, offset_date, offset_id, offset_topic, limit, q=None):
        self.channel = channel
        self.q = q
        self.offset_date = offset_date
        self.offset_id = offset_id
        self.offset_topic = offset_topic
        self.limit = limit

    async def resolve(self, client, utils):
        self.channel = utils.get_input_channel(await client.get_input_entity(self.channel))

    def to_dict(self):
        return {
            "_": "GetForumTopicsRequest",
            "channel": (
                self.channel.to_dict() if isinstance(self.channel, TLObject) else self.channel
            ),
            "q": self.q,
            "offset_date": self.offset_date,
            "offset_id": self.offset_id,
            "offset_topic": self.offset_topic,
            "limit": self.limit,
        }

    def _bytes(self):
        flags = 0 if self.q is None or self.q is False else 1
        return b"".join(
            (
                struct.pack("<I", self.CONSTRUCTOR_ID),
                struct.pack("<I", flags),
                self.channel._bytes(),
                b"" if self.q is None or self.q is False else self.serialize_bytes(self.q),
                struct.pack("<i", self.offset_date),
                struct.pack("<i", self.offset_id),
                struct.pack("<i", self.offset_topic),
                struct.pack("<i", self.limit),
            )
        )


@dataclass(frozen=True)
class GroupChat:
    id: int
    title: str
    is_forum: bool = False


@dataclass(frozen=True)
class Topic:
    id: int
    title: str


@dataclass(frozen=True)
class ChatMessage:
    id: int
    sender: str
    date: datetime
    text: str = ""
    media: str | None = None
    reply_to: int | None = None
    forwarded_from: str | None = None


class TelegramGateway(Protocol):
    def list_groups(self) -> list[GroupChat]: ...

    def list_topics(self, chat_id: int) -> list[Topic]: ...

    def iter_messages(
        self,
        chat_id: int,
        *,
        start: date,
        end: date,
        topic_id: int | None = None,
    ) -> Iterable[ChatMessage]: ...


def entity_to_group(entity) -> GroupChat | None:
    """Map a Telethon dialog entity to GroupChat, or None if not a group/supergroup."""
    title = getattr(entity, "title", None)
    if title is None:
        return None
    if getattr(entity, "broadcast", False) and not getattr(entity, "megagroup", False):
        return None
    if getattr(entity, "megagroup", False) or not hasattr(entity, "broadcast"):
        return GroupChat(
            id=int(entity.id),
            title=str(title),
            is_forum=bool(getattr(entity, "forum", False)),
        )
    return None


def media_label_ru(msg) -> str | None:
    """Russian media placeholder; never downloads. Adapted from telegram-mcp get_media_label."""
    try:
        if getattr(msg, "web_preview", None) is not None:
            return None
        sticker = getattr(msg, "sticker", None)
        if sticker is not None:
            alt = ""
            for attr in getattr(sticker, "attributes", []) or []:
                a = getattr(attr, "alt", None)
                if a:
                    alt = a
                    break
            return f"[стикер{(' ' + alt) if alt else ''}]"
        if getattr(msg, "photo", None) is not None:
            return "[фото]"
        if getattr(msg, "voice", None) is not None:
            return "[голосовое]"
        if getattr(msg, "video_note", None) is not None:
            return "[видеосообщение]"
        if getattr(msg, "video", None) is not None:
            return "[видео]"
        if getattr(msg, "audio", None) is not None:
            return "[аудио]"
        if getattr(msg, "gif", None) is not None:
            return "[gif]"
        if getattr(msg, "document", None) is not None:
            name = None
            f = getattr(msg, "file", None)
            if f is not None:
                name = getattr(f, "name", None)
            return f"[файл: {name}]" if name else "[файл]"
        if getattr(msg, "contact", None) is not None:
            return "[контакт]"
        if getattr(msg, "geo", None) is not None:
            return "[геолокация]"
        if getattr(msg, "poll", None) is not None:
            return "[опрос]"
        if getattr(msg, "media", None) is not None:
            return "[медиа]"
        return None
    except Exception:
        return None


def _sender_name(msg) -> str:
    sender = getattr(msg, "sender", None)
    if sender is None:
        return "Unknown"
    title = getattr(sender, "title", None)
    if title:
        return str(title)
    first = getattr(sender, "first_name", "") or ""
    last = getattr(sender, "last_name", "") or ""
    full = f"{first} {last}".strip()
    return full or "Unknown"


def _user_reply_to_id(msg, topic_id: int | None = None) -> int | None:
    """Real reply target, ignoring forum-topic root linkage."""
    reply = getattr(msg, "reply_to", None)
    if reply is None:
        return None
    reply_to_id = getattr(reply, "reply_to_msg_id", None)
    if reply_to_id is None:
        return None
    top_id = getattr(reply, "reply_to_top_id", None)
    if top_id is not None and reply_to_id == top_id:
        return None
    if topic_id is not None and reply_to_id == topic_id:
        return None
    return int(reply_to_id)


def _forwarded_from_name(msg) -> str | None:
    fwd = getattr(msg, "fwd_from", None)
    if fwd is None:
        return None
    name = getattr(fwd, "from_name", None)
    if name:
        return str(name)
    forward = getattr(msg, "forward", None)
    if forward is None:
        return None
    chat = getattr(forward, "chat", None)
    if chat is not None:
        title = getattr(chat, "title", None)
        if title:
            return str(title)
        first = getattr(chat, "first_name", "") or ""
        last = getattr(chat, "last_name", "") or ""
        full = f"{first} {last}".strip()
        if full:
            return full
    sender = getattr(forward, "sender", None)
    if sender is not None:
        first = getattr(sender, "first_name", "") or ""
        last = getattr(sender, "last_name", "") or ""
        full = f"{first} {last}".strip()
        if full:
            return full
    return None


def message_from_telethon(msg, *, topic_id: int | None = None) -> ChatMessage:
    text = getattr(msg, "message", None) or ""
    reply_to = _user_reply_to_id(msg, topic_id=topic_id)
    forwarded_from = _forwarded_from_name(msg)
    return ChatMessage(
        id=int(msg.id),
        sender=_sender_name(msg),
        date=msg.date,
        text=str(text) if text else "",
        media=media_label_ru(msg),
        reply_to=reply_to,
        forwarded_from=forwarded_from,
    )


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TelethonGateway:
    """Telethon-backed adapter for the Telegram gateway seam."""

    def __init__(self, client: TelegramClient):
        self._client = client

    def list_groups(self) -> list[GroupChat]:
        groups: list[GroupChat] = []
        for dialog in self._client.iter_dialogs():
            mapped = entity_to_group(dialog.entity)
            if mapped is None:
                continue
            # Prefer dialog.id so later get_entity/calls accept the peer id Telethon uses.
            groups.append(
                GroupChat(id=dialog.id, title=mapped.title, is_forum=mapped.is_forum)
            )
        return groups

    def list_topics(self, chat_id: int) -> list[Topic]:
        entity = self._client.get_entity(chat_id)
        result = self._client(
            GetForumTopicsRequest(
                channel=entity,
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100,
                q=None,
            )
        )
        topics = getattr(result, "topics", None) or []
        out: list[Topic] = []
        for topic in topics:
            title = getattr(topic, "title", None) or "(без названия)"
            out.append(Topic(id=int(topic.id), title=str(title)))
        return out

    def iter_messages(
        self,
        chat_id: int,
        *,
        start: date,
        end: date,
        topic_id: int | None = None,
    ) -> Iterator[ChatMessage]:
        entity = self._client.get_entity(chat_id)
        # offset_date is exclusive upper bound when iterating newest→oldest.
        offset_date = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        start_bound = datetime.combine(start, time.min, tzinfo=timezone.utc)

        kwargs = {"offset_date": offset_date}
        if topic_id is not None:
            kwargs["reply_to"] = topic_id

        collected: list[ChatMessage] = []
        for msg in self._client.iter_messages(entity, **kwargs):
            msg_date = _as_utc(msg.date)
            if msg_date < start_bound:
                break
            collected.append(message_from_telethon(msg, topic_id=topic_id))

        collected.reverse()  # chronological for the transcript
        yield from collected
