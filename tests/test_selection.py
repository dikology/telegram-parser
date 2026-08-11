"""Selection flow tests — fake gateway, no Telegram network."""

from datetime import date
from types import SimpleNamespace

import pytest

from telegram_parser.gateway import GroupChat, Topic, entity_to_group
from telegram_parser.selection import (
    DateRange,
    Selection,
    filter_groups_by_search,
    parse_date,
    resolve_preset_range,
    run_selection,
)


class _FakeGateway:
    def __init__(self, groups, topics_by_chat=None):
        self._groups = list(groups)
        self._topics_by_chat = topics_by_chat or {}

    def list_groups(self):
        return list(self._groups)

    def list_topics(self, chat_id):
        return list(self._topics_by_chat.get(chat_id, []))


BOOK = GroupChat(id=1, title="Книжный клуб")
WORK = GroupChat(id=2, title="Work Chat")
FORUM = GroupChat(id=3, title="Семейный форум", is_forum=True)


def test_entity_to_group_keeps_basic_group():
    entity = SimpleNamespace(id=10, title="Книжный клуб")

    assert entity_to_group(entity) == GroupChat(id=10, title="Книжный клуб", is_forum=False)


def test_entity_to_group_keeps_megagroup_and_forum_flag():
    entity = SimpleNamespace(
        id=20, title="Форум", megagroup=True, broadcast=False, forum=True
    )

    assert entity_to_group(entity) == GroupChat(id=20, title="Форум", is_forum=True)


def test_entity_to_group_excludes_broadcast_channel():
    entity = SimpleNamespace(id=30, title="Новости", megagroup=False, broadcast=True)

    assert entity_to_group(entity) is None


def test_entity_to_group_excludes_private_dm():
    entity = SimpleNamespace(id=40, first_name="Иван", last_name="Петров")

    assert entity_to_group(entity) is None


def test_search_filters_groups_case_insensitive():
    groups = [BOOK, WORK, FORUM]

    assert filter_groups_by_search(groups, "книж") == [BOOK]
    assert filter_groups_by_search(groups, "CHAT") == [WORK]


def test_empty_search_returns_all_groups():
    groups = [BOOK, WORK, FORUM]

    assert filter_groups_by_search(groups, "") == groups
    assert filter_groups_by_search(groups, "   ") == groups


def test_parse_date_typed_dd_mm_yyyy():
    assert parse_date("01.06.2026") == date(2026, 6, 1)
    assert parse_date("11.08.2026") == date(2026, 8, 11)


def test_parse_date_rejects_invalid():
    with pytest.raises(ValueError):
        parse_date("2026-06-01")
    with pytest.raises(ValueError):
        parse_date("32.01.2026")


def test_preset_last_7_days_inclusive():
    today = date(2026, 8, 11)

    assert resolve_preset_range("7", today=today) == DateRange(
        start=date(2026, 8, 5), end=today
    )


def test_preset_last_30_days_inclusive():
    today = date(2026, 8, 11)

    assert resolve_preset_range("30", today=today) == DateRange(
        start=date(2026, 7, 13), end=today
    )


def _run(gateway, answers, today=date(2026, 8, 11)):
    answers_iter = iter(answers)
    output: list[str] = []

    def fake_input(prompt=""):
        output.append(prompt)
        return next(answers_iter)

    def fake_print(*args, **kwargs):
        output.append(" ".join(str(a) for a in args))

    selection = run_selection(
        gateway,
        input_fn=fake_input,
        print_fn=fake_print,
        today=today,
    )
    return selection, output


def test_non_forum_group_skips_topic_step():
    gateway = _FakeGateway([BOOK, WORK])
    # empty search → pick 1 (BOOK) → preset 1 (last 7 days)
    selection, output = _run(gateway, ["", "1", "1"])

    assert selection == Selection(
        chat=BOOK,
        topic=None,
        all_topics=False,
        date_range=DateRange(start=date(2026, 8, 5), end=date(2026, 8, 11)),
    )
    joined = "\n".join(output)
    assert "Выберите тему" not in joined


def test_forum_group_can_pick_single_topic():
    topics = [Topic(id=101, title="Общее"), Topic(id=102, title="Книги")]
    gateway = _FakeGateway([FORUM], topics_by_chat={FORUM.id: topics})
    # empty search → pick 1 → topic 2 → last 30 days
    selection, _ = _run(gateway, ["", "1", "2", "2"])

    assert selection == Selection(
        chat=FORUM,
        topic=topics[1],
        all_topics=False,
        date_range=DateRange(start=date(2026, 7, 13), end=date(2026, 8, 11)),
    )


def test_forum_group_can_pick_all_topics():
    topics = [Topic(id=101, title="Общее"), Topic(id=102, title="Книги")]
    gateway = _FakeGateway([FORUM], topics_by_chat={FORUM.id: topics})
    # empty search → pick 1 → all topics (option after topics) → custom range
    selection, _ = _run(
        gateway,
        ["", "1", "3", "3", "01.06.2026", "15.06.2026"],
    )

    assert selection == Selection(
        chat=FORUM,
        topic=None,
        all_topics=True,
        date_range=DateRange(start=date(2026, 6, 1), end=date(2026, 6, 15)),
    )


def test_search_narrows_group_picker():
    gateway = _FakeGateway([BOOK, WORK, FORUM])
    selection, output = _run(gateway, ["work", "1", "1"])

    assert selection.chat == WORK
    joined = "\n".join(output)
    assert "Work Chat" in joined
    assert "Книжный клуб" not in joined


def test_selection_prints_confirmation():
    gateway = _FakeGateway([BOOK])
    _, output = _run(gateway, ["", "1", "1"])

    joined = "\n".join(output)
    assert "Книжный клуб" in joined
    assert "без тем" in joined
    assert "05.08.2026" in joined
    assert "11.08.2026" in joined


def test_forum_empty_topics_still_offers_all_topics():
    gateway = _FakeGateway([FORUM], topics_by_chat={FORUM.id: []})
    # empty search → pick forum → only option is "Все темы" (1) → last 7 days
    selection, output = _run(gateway, ["", "1", "1", "1"])

    assert selection.all_topics is True
    assert selection.topic is None
    joined = "\n".join(output)
    assert "Выберите тему" in joined
    assert "Все темы" in joined
    assert "все темы" in joined
