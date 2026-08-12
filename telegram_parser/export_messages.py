"""Format and write single-thread chat exports (.txt + .json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from telegram_parser.gateway import ChatMessage, TelegramGateway, Topic
from telegram_parser.selection import Selection

_UNSAFE_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    cleaned = _UNSAFE_FILENAME.sub("_", name.strip())
    cleaned = re.sub(r"[\s_]+", "_", cleaned).strip("._")
    return cleaned or "chat"


def format_txt_line(msg: ChatMessage) -> str:
    stamp = msg.date.strftime("%Y-%m-%d %H:%M")
    body_parts: list[str] = []
    if msg.text:
        body_parts.append(msg.text)
    if msg.media:
        body_parts.append(msg.media)
    body = " ".join(body_parts)
    return f"[{stamp}] {msg.sender}: {body}"


def format_json_record(msg: ChatMessage) -> dict:
    record: dict = {
        "id": msg.id,
        "sender": msg.sender,
        "date": msg.date.isoformat(),
    }
    if msg.text:
        record["text"] = msg.text
    if msg.media:
        record["media"] = msg.media
    if msg.reply_to is not None:
        record["reply_to"] = msg.reply_to
    if msg.forwarded_from:
        record["forwarded"] = {"from_name": msg.forwarded_from}
    return record


def export_paths(selection: Selection, output_dir: Path) -> tuple[Path, Path]:
    chat_name = sanitize_filename(selection.chat.title)
    start = selection.date_range.start.isoformat()
    end = selection.date_range.end.isoformat()
    if selection.topic is not None:
        topic_name = sanitize_filename(selection.topic.title)
        stem = f"{chat_name}_{topic_name}_{start}_{end}"
    else:
        stem = f"{chat_name}_{start}_{end}"
    return output_dir / f"{stem}.txt", output_dir / f"{stem}.json"


def all_topics_export_paths(
    selection: Selection,
    topic: Topic,
    output_dir: Path,
) -> tuple[Path, Path]:
    group_dir = output_dir / sanitize_filename(selection.chat.title)
    topic_name = sanitize_filename(topic.title)
    start = selection.date_range.start.isoformat()
    end = selection.date_range.end.isoformat()
    stem = f"{topic_name}_{start}_{end}"
    return group_dir / f"{stem}.txt", group_dir / f"{stem}.json"


def _write_thread_files(
    messages: list[ChatMessage],
    txt_path: Path,
    json_path: Path,
) -> None:
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(
        "".join(format_txt_line(msg) + "\n" for msg in messages),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            [format_json_record(msg) for msg in messages],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def export_selection(
    selection: Selection,
    gateway: TelegramGateway,
    *,
    output_dir: Path,
) -> list[tuple[Path, Path]]:
    """Write .txt + .json for a plain group, one topic, or all forum topics."""
    if selection.all_topics:
        return _export_all_topics(selection, gateway, output_dir=output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    topic_id = selection.topic.id if selection.topic is not None else None
    messages = list(
        gateway.iter_messages(
            selection.chat.id,
            start=selection.date_range.start,
            end=selection.date_range.end,
            topic_id=topic_id,
        )
    )

    txt_path, json_path = export_paths(selection, output_dir)
    _write_thread_files(messages, txt_path, json_path)
    return [(txt_path, json_path)]


def _export_all_topics(
    selection: Selection,
    gateway: TelegramGateway,
    *,
    output_dir: Path,
) -> list[tuple[Path, Path]]:
    written: list[tuple[Path, Path]] = []
    for topic in gateway.list_topics(selection.chat.id):
        messages = list(
            gateway.iter_messages(
                selection.chat.id,
                start=selection.date_range.start,
                end=selection.date_range.end,
                topic_id=topic.id,
            )
        )
        if not messages:
            continue
        txt_path, json_path = all_topics_export_paths(selection, topic, output_dir)
        _write_thread_files(messages, txt_path, json_path)
        written.append((txt_path, json_path))
    return written
