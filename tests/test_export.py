"""Single-thread export — fake gateway, temp directory, no network."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from telegram_parser.export_messages import (
    export_selection,
    format_json_record,
    format_txt_line,
    sanitize_filename,
)
from telegram_parser.gateway import (
    ChatMessage,
    GroupChat,
    Topic,
    media_label_ru,
    message_from_telethon,
)
from telegram_parser.selection import DateRange, Selection


def test_format_txt_line_plain_text():
    msg = ChatMessage(
        id=1,
        sender="Анна",
        date=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        text="Привет, клуб!",
    )

    assert format_txt_line(msg) == "[2026-06-01 14:30] Анна: Привет, клуб!"


def test_format_txt_line_media_placeholder():
    msg = ChatMessage(
        id=2,
        sender="Борис",
        date=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        text="",
        media="[фото]",
    )

    assert format_txt_line(msg) == "[2026-06-01 15:00] Борис: [фото]"


def test_format_txt_line_caption_plus_media():
    msg = ChatMessage(
        id=3,
        sender="Борис",
        date=datetime(2026, 6, 1, 15, 5, tzinfo=timezone.utc),
        text="смотри",
        media="[файл: report.pdf]",
    )

    assert format_txt_line(msg) == "[2026-06-01 15:05] Борис: смотри [файл: report.pdf]"


def test_format_json_record_omits_empty_fields():
    msg = ChatMessage(
        id=10,
        sender="Анна",
        date=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
        text="ok",
    )

    assert format_json_record(msg) == {
        "id": 10,
        "sender": "Анна",
        "date": "2026-06-01T14:30:00+00:00",
        "text": "ok",
    }


def test_format_json_record_includes_media_reply_forward():
    msg = ChatMessage(
        id=11,
        sender="Борис",
        date=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc),
        text="",
        media="[фото]",
        reply_to=10,
        forwarded_from="Канал Новостей",
    )

    assert format_json_record(msg) == {
        "id": 11,
        "sender": "Борис",
        "date": "2026-06-02T09:00:00+00:00",
        "media": "[фото]",
        "reply_to": 10,
        "forwarded": {"from_name": "Канал Новостей"},
    }


def test_sanitize_filename_strips_unsafe_chars():
    assert sanitize_filename('Клуб/книга: "2026"?') == "Клуб_книга_2026"
    assert sanitize_filename("  a\\b  ") == "a_b"


class _FakeGateway:
    def __init__(self, messages):
        self._messages = list(messages)
        self.calls = []

    def list_groups(self):
        return []

    def list_topics(self, chat_id):
        return []

    def iter_messages(self, chat_id, *, start, end, topic_id=None):
        self.calls.append(
            {"chat_id": chat_id, "start": start, "end": end, "topic_id": topic_id}
        )
        return list(self._messages)


def test_export_selection_writes_txt_and_json(tmp_path: Path):
    messages = [
        ChatMessage(
            id=1,
            sender="Анна",
            date=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
            text="Привет",
        ),
        ChatMessage(
            id=2,
            sender="Борис",
            date=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            text="",
            media="[фото]",
            reply_to=1,
        ),
        ChatMessage(
            id=3,
            sender="Анна",
            date=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
            text="ок",
            forwarded_from="Канал",
        ),
    ]
    gateway = _FakeGateway(messages)
    selection = Selection(
        chat=GroupChat(id=100, title='Клуб/книга'),
        topic=None,
        all_topics=False,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 7)),
    )

    [(txt_path, json_path)] = export_selection(selection, gateway, output_dir=tmp_path)

    assert txt_path.name == "Клуб_книга_2026-06-01_2026-06-07.txt"
    assert json_path.name == "Клуб_книга_2026-06-01_2026-06-07.json"
    assert txt_path.read_text(encoding="utf-8") == (
        "[2026-06-01 14:30] Анна: Привет\n"
        "[2026-06-01 15:00] Борис: [фото]\n"
        "[2026-06-01 16:00] Анна: ок\n"
    )
    assert json.loads(json_path.read_text(encoding="utf-8")) == [
        {
            "id": 1,
            "sender": "Анна",
            "date": "2026-06-01T14:30:00+00:00",
            "text": "Привет",
        },
        {
            "id": 2,
            "sender": "Борис",
            "date": "2026-06-01T15:00:00+00:00",
            "media": "[фото]",
            "reply_to": 1,
        },
        {
            "id": 3,
            "sender": "Анна",
            "date": "2026-06-01T16:00:00+00:00",
            "text": "ок",
            "forwarded": {"from_name": "Канал"},
        },
    ]
    assert gateway.calls == [
        {"chat_id": 100, "start": date(2026, 6, 1), "end": date(2026, 6, 7), "topic_id": None}
    ]


def test_export_selection_passes_topic_id(tmp_path: Path):
    gateway = _FakeGateway([])
    selection = Selection(
        chat=GroupChat(id=100, title="Форум", is_forum=True),
        topic=Topic(id=55, title="Книги/раздел"),
        all_topics=False,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 1)),
    )

    [(txt_path, _)] = export_selection(selection, gateway, output_dir=tmp_path)

    assert gateway.calls[0]["topic_id"] == 55
    assert txt_path.name == "Форум_Книги_раздел_2026-06-01_2026-06-01.txt"


class _FloodWaitLike(Exception):
    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(f"wait {seconds}s")


class _FloodThenOkGateway:
    """Raises a flood-wait-like error on first iter_messages, then yields messages."""

    def __init__(self, messages):
        self._messages = list(messages)
        self._fails_left = 1
        self.calls = []

    def list_groups(self):
        return []

    def list_topics(self, chat_id):
        return []

    def iter_messages(self, chat_id, *, start, end, topic_id=None):
        self.calls.append(
            {"chat_id": chat_id, "start": start, "end": end, "topic_id": topic_id}
        )
        if self._fails_left > 0:
            self._fails_left -= 1
            raise _FloodWaitLike(42)
        return list(self._messages)


def test_export_retries_after_flood_wait(tmp_path: Path):
    messages = [
        ChatMessage(
            id=1,
            sender="Анна",
            date=datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc),
            text="после ожидания",
        ),
    ]
    gateway = _FloodThenOkGateway(messages)
    selection = Selection(
        chat=GroupChat(id=100, title="Клуб"),
        topic=None,
        all_topics=False,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 7)),
    )
    sleeps: list[float] = []
    printed: list[str] = []

    [(txt_path, _)] = export_selection(
        selection,
        gateway,
        output_dir=tmp_path,
        print_fn=lambda *args, **_: printed.append(" ".join(str(a) for a in args)),
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )

    assert sleeps == [42]
    assert any("42" in line and "сек" in line for line in printed)
    assert txt_path.read_text(encoding="utf-8") == (
        "[2026-06-01 14:30] Анна: после ожидания\n"
    )
    assert len(gateway.calls) == 2


def test_export_prints_progress_while_fetching(tmp_path: Path):
    messages = [
        ChatMessage(
            id=i,
            sender="Анна",
            date=datetime(2026, 6, 1, 14, i, tzinfo=timezone.utc),
            text=f"m{i}",
        )
        for i in range(1, 6)
    ]
    gateway = _FakeGateway(messages)
    selection = Selection(
        chat=GroupChat(id=100, title="Клуб"),
        topic=None,
        all_topics=False,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 7)),
    )
    printed: list[str] = []

    export_selection(
        selection,
        gateway,
        output_dir=tmp_path,
        print_fn=lambda *args, **_: printed.append(" ".join(str(a) for a in args)),
        sleep_fn=lambda _s: None,
        progress_every=2,
    )

    assert printed == [
        "Загружено 2 сообщений…",
        "Загружено 4 сообщений…",
        "Загружено 5 сообщений…",
    ]


def test_export_all_topics_prints_progress_while_fetching(tmp_path: Path):
    gateway = _FakeForumGateway(
        [Topic(id=10, title="Тема")],
        {
            10: [
                ChatMessage(
                    id=i,
                    sender="Анна",
                    date=datetime(2026, 6, 1, 10, i, tzinfo=timezone.utc),
                    text=f"t{i}",
                )
                for i in range(1, 4)
            ],
        },
    )
    selection = Selection(
        chat=GroupChat(id=100, title="Форум", is_forum=True),
        topic=None,
        all_topics=True,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 7)),
    )
    printed: list[str] = []

    export_selection(
        selection,
        gateway,
        output_dir=tmp_path,
        print_fn=lambda *args, **_: printed.append(" ".join(str(a) for a in args)),
        sleep_fn=lambda _s: None,
        progress_every=2,
    )

    assert printed == [
        "Загружено 2 сообщений…",
        "Загружено 3 сообщений…",
    ]


def test_export_all_topics_retries_after_flood_wait(tmp_path: Path):
    class _FloodForumGateway:
        def __init__(self):
            self._fails_left = 1
            self.calls = []

        def list_groups(self):
            return []

        def list_topics(self, chat_id):
            return [Topic(id=10, title="Тема")]

        def iter_messages(self, chat_id, *, start, end, topic_id=None):
            self.calls.append({"topic_id": topic_id})
            if self._fails_left > 0:
                self._fails_left -= 1
                raise _FloodWaitLike(7)
            return [
                ChatMessage(
                    id=1,
                    sender="Анна",
                    date=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
                    text="ok",
                )
            ]

    gateway = _FloodForumGateway()
    selection = Selection(
        chat=GroupChat(id=100, title="Форум", is_forum=True),
        topic=None,
        all_topics=True,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 7)),
    )
    sleeps: list[float] = []
    printed: list[str] = []

    written = export_selection(
        selection,
        gateway,
        output_dir=tmp_path,
        print_fn=lambda *args, **_: printed.append(" ".join(str(a) for a in args)),
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )

    assert sleeps == [7]
    assert any("7" in line and "сек" in line for line in printed)
    assert len(written) == 1
    assert written[0][0].read_text(encoding="utf-8") == (
        "[2026-06-01 10:00] Анна: ok\n"
    )
    assert len(gateway.calls) == 2


class _FakeForumGateway:
    """Fake forum group: list_topics + per-topic messages."""

    def __init__(self, topics: list[Topic], messages_by_topic: dict[int, list]):
        self._topics = list(topics)
        self._messages_by_topic = {
            tid: list(msgs) for tid, msgs in messages_by_topic.items()
        }
        self.calls = []

    def list_groups(self):
        return []

    def list_topics(self, chat_id):
        self.calls.append({"op": "list_topics", "chat_id": chat_id})
        return list(self._topics)

    def iter_messages(self, chat_id, *, start, end, topic_id=None):
        self.calls.append(
            {
                "op": "iter_messages",
                "chat_id": chat_id,
                "start": start,
                "end": end,
                "topic_id": topic_id,
            }
        )
        return list(self._messages_by_topic.get(topic_id, []))


def test_export_all_topics_writes_per_topic_under_group_subdir(tmp_path: Path):
    topics = [
        Topic(id=10, title="Книги/раздел"),
        Topic(id=20, title="Общее"),
    ]
    gateway = _FakeForumGateway(
        topics,
        {
            10: [
                ChatMessage(
                    id=1,
                    sender="Анна",
                    date=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
                    text="про книги",
                ),
            ],
            20: [
                ChatMessage(
                    id=2,
                    sender="Борис",
                    date=datetime(2026, 6, 2, 11, 0, tzinfo=timezone.utc),
                    text="",
                    media="[фото]",
                ),
            ],
        },
    )
    selection = Selection(
        chat=GroupChat(id=100, title="Форум/клуб", is_forum=True),
        topic=None,
        all_topics=True,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 7)),
    )

    written = export_selection(selection, gateway, output_dir=tmp_path)

    group_dir = tmp_path / "Форум_клуб"
    books_txt = group_dir / "Книги_раздел_2026-06-01_2026-06-07.txt"
    books_json = group_dir / "Книги_раздел_2026-06-01_2026-06-07.json"
    general_txt = group_dir / "Общее_2026-06-01_2026-06-07.txt"
    general_json = group_dir / "Общее_2026-06-01_2026-06-07.json"

    assert written == [
        (books_txt, books_json),
        (general_txt, general_json),
    ]
    assert books_txt.read_text(encoding="utf-8") == (
        "[2026-06-01 10:00] Анна: про книги\n"
    )
    assert json.loads(books_json.read_text(encoding="utf-8")) == [
        {
            "id": 1,
            "sender": "Анна",
            "date": "2026-06-01T10:00:00+00:00",
            "text": "про книги",
        },
    ]
    assert general_txt.read_text(encoding="utf-8") == (
        "[2026-06-02 11:00] Борис: [фото]\n"
    )
    assert json.loads(general_json.read_text(encoding="utf-8")) == [
        {
            "id": 2,
            "sender": "Борис",
            "date": "2026-06-02T11:00:00+00:00",
            "media": "[фото]",
        },
    ]
    assert gateway.calls == [
        {"op": "list_topics", "chat_id": 100},
        {
            "op": "iter_messages",
            "chat_id": 100,
            "start": date(2026, 6, 1),
            "end": date(2026, 6, 7),
            "topic_id": 10,
        },
        {
            "op": "iter_messages",
            "chat_id": 100,
            "start": date(2026, 6, 1),
            "end": date(2026, 6, 7),
            "topic_id": 20,
        },
    ]


def test_export_all_topics_skips_topics_without_messages(tmp_path: Path):
    topics = [
        Topic(id=10, title="Пустая"),
        Topic(id=20, title="С сообщениями"),
        Topic(id=30, title="Тоже пустая"),
    ]
    gateway = _FakeForumGateway(
        topics,
        {
            20: [
                ChatMessage(
                    id=5,
                    sender="Анна",
                    date=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
                    text="есть",
                ),
            ],
        },
    )
    selection = Selection(
        chat=GroupChat(id=100, title="Форум", is_forum=True),
        topic=None,
        all_topics=True,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 7)),
    )

    written = export_selection(selection, gateway, output_dir=tmp_path)

    group_dir = tmp_path / "Форум"
    only_txt = group_dir / "С_сообщениями_2026-06-01_2026-06-07.txt"
    only_json = group_dir / "С_сообщениями_2026-06-01_2026-06-07.json"
    assert written == [(only_txt, only_json)]
    assert only_txt.read_text(encoding="utf-8") == "[2026-06-03 12:00] Анна: есть\n"
    assert not (group_dir / "Пустая_2026-06-01_2026-06-07.txt").exists()
    assert not (group_dir / "Тоже_пустая_2026-06-01_2026-06-07.txt").exists()
    assert [c for c in gateway.calls if c["op"] == "iter_messages"] == [
        {
            "op": "iter_messages",
            "chat_id": 100,
            "start": date(2026, 6, 1),
            "end": date(2026, 6, 7),
            "topic_id": 10,
        },
        {
            "op": "iter_messages",
            "chat_id": 100,
            "start": date(2026, 6, 1),
            "end": date(2026, 6, 7),
            "topic_id": 20,
        },
        {
            "op": "iter_messages",
            "chat_id": 100,
            "start": date(2026, 6, 1),
            "end": date(2026, 6, 7),
            "topic_id": 30,
        },
    ]


def test_media_label_ru_photo_and_document():
    assert media_label_ru(_Msg(photo=object())) == "[фото]"
    assert media_label_ru(_Msg(document=object(), file=_File(name="report.pdf"))) == (
        "[файл: report.pdf]"
    )


def test_message_from_telethon_maps_reply_and_forward():
    msg = _Msg(
        id=7,
        message="hi",
        date=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        sender=_Sender(first_name="Анна"),
        reply_to=_Reply(reply_to_msg_id=3, reply_to_top_id=55),
        fwd_from=_Fwd(from_name="Канал"),
        photo=object(),
    )

    assert message_from_telethon(msg, topic_id=55) == ChatMessage(
        id=7,
        sender="Анна",
        date=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        text="hi",
        media="[фото]",
        reply_to=3,
        forwarded_from="Канал",
    )


def test_message_from_telethon_ignores_forum_topic_root_reply():
    msg = _Msg(
        id=8,
        message="in topic",
        date=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        sender=_Sender(first_name="Анна"),
        reply_to=_Reply(reply_to_msg_id=55, reply_to_top_id=55),
    )

    assert message_from_telethon(msg, topic_id=55).reply_to is None


class _File:
    def __init__(self, name=None):
        self.name = name


class _Sender:
    def __init__(self, first_name="", last_name="", title=None):
        self.first_name = first_name
        self.last_name = last_name
        self.title = title


class _Reply:
    def __init__(self, reply_to_msg_id, reply_to_top_id=None):
        self.reply_to_msg_id = reply_to_msg_id
        self.reply_to_top_id = reply_to_top_id


class _Fwd:
    def __init__(self, from_name=None):
        self.from_name = from_name


class _Msg:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.message = kwargs.get("message")
        self.date = kwargs.get("date", datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.sender = kwargs.get("sender")
        self.reply_to = kwargs.get("reply_to")
        self.fwd_from = kwargs.get("fwd_from")
        self.web_preview = kwargs.get("web_preview")
        self.sticker = kwargs.get("sticker")
        self.photo = kwargs.get("photo")
        self.voice = kwargs.get("voice")
        self.video_note = kwargs.get("video_note")
        self.video = kwargs.get("video")
        self.audio = kwargs.get("audio")
        self.gif = kwargs.get("gif")
        self.document = kwargs.get("document")
        self.contact = kwargs.get("contact")
        self.geo = kwargs.get("geo")
        self.poll = kwargs.get("poll")
        self.media = kwargs.get("media")
        self.file = kwargs.get("file")
