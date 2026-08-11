"""Telegram access seam: list groups and forum topics."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Protocol

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


class TelegramGateway(Protocol):
    def list_groups(self) -> list[GroupChat]: ...

    def list_topics(self, chat_id: int) -> list[Topic]: ...


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
