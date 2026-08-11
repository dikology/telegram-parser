"""Interactive chat / topic / date-range selection for export."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from telegram_parser.gateway import GroupChat, TelegramGateway, Topic

PrintFn = Callable[..., None]
InputFn = Callable[[str], str]


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date  # inclusive


@dataclass(frozen=True)
class Selection:
    chat: GroupChat
    topic: Topic | None
    all_topics: bool
    date_range: DateRange


def filter_groups_by_search(groups: list[GroupChat], query: str) -> list[GroupChat]:
    needle = query.strip().casefold()
    if not needle:
        return list(groups)
    return [g for g in groups if needle in g.title.casefold()]


def parse_date(text: str) -> date:
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").date()
    except ValueError as exc:
        raise ValueError(f"invalid date: {text!r}") from exc


def resolve_preset_range(preset: str, *, today: date) -> DateRange:
    """Resolve '7' or '30' day presets ending on today (inclusive)."""
    days = int(preset)
    if days < 1:
        raise ValueError(f"invalid preset: {preset!r}")
    return DateRange(start=today - timedelta(days=days - 1), end=today)


def _prompt_choice(
    prompt: str,
    max_n: int,
    *,
    input_fn: InputFn,
    print_fn: PrintFn,
) -> int:
    while True:
        raw = input_fn(prompt).strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= max_n:
                return n
        print_fn(f"Введите число от 1 до {max_n}.")


def _pick_group(
    groups: list[GroupChat],
    *,
    input_fn: InputFn,
    print_fn: PrintFn,
) -> GroupChat:
    query = input_fn(
        "Введите часть названия чата для поиска (или Enter — показать все): "
    )
    matches = filter_groups_by_search(groups, query)
    if not matches:
        print_fn("Ничего не найдено. Показан полный список.")
        matches = list(groups)
    if not matches:
        raise RuntimeError("Нет доступных групп для экспорта.")

    print_fn("\nДоступные группы:")
    for i, group in enumerate(matches, start=1):
        print_fn(f"  {i}) {group.title}")

    index = _prompt_choice("Выберите номер группы: ", len(matches), input_fn=input_fn, print_fn=print_fn)
    return matches[index - 1]


def _pick_topic(
    topics: list[Topic],
    *,
    input_fn: InputFn,
    print_fn: PrintFn,
) -> tuple[Topic | None, bool]:
    print_fn("\nТемы форума:")
    for i, topic in enumerate(topics, start=1):
        print_fn(f"  {i}) {topic.title}")
    all_option = len(topics) + 1
    print_fn(f"  {all_option}) Все темы")

    index = _prompt_choice(
        "Выберите тему: ",
        all_option,
        input_fn=input_fn,
        print_fn=print_fn,
    )
    if index == all_option:
        return None, True
    return topics[index - 1], False


def _pick_date_range(
    *,
    input_fn: InputFn,
    print_fn: PrintFn,
    today: date,
) -> DateRange:
    print_fn("\nПериод экспорта:")
    print_fn("  1) Последние 7 дней")
    print_fn("  2) Последние 30 дней")
    print_fn("  3) Свой диапазон (ДД.ММ.ГГГГ)")

    choice = _prompt_choice("Выберите вариант: ", 3, input_fn=input_fn, print_fn=print_fn)
    if choice == 1:
        return resolve_preset_range("7", today=today)
    if choice == 2:
        return resolve_preset_range("30", today=today)

    while True:
        try:
            start = parse_date(input_fn("Дата начала (ДД.ММ.ГГГГ): "))
            end = parse_date(input_fn("Дата конца (ДД.ММ.ГГГГ): "))
        except ValueError:
            print_fn("Неверный формат даты. Используйте ДД.ММ.ГГГГ.")
            continue
        if end < start:
            print_fn("Дата конца не может быть раньше даты начала.")
            continue
        return DateRange(start=start, end=end)


def _format_confirmation(selection: Selection) -> str:
    if selection.all_topics:
        topic_scope = "все темы"
    elif selection.topic is not None:
        topic_scope = selection.topic.title
    else:
        topic_scope = "без тем (обычная группа)"

    start = selection.date_range.start.strftime("%d.%m.%Y")
    end = selection.date_range.end.strftime("%d.%m.%Y")
    return (
        "\n----- Подтверждение выбора -----\n"
        f"Чат: {selection.chat.title}\n"
        f"Темы: {topic_scope}\n"
        f"Период: {start} — {end} (включительно)\n"
    )


def run_selection(
    gateway: TelegramGateway,
    *,
    input_fn: InputFn = input,
    print_fn: PrintFn = print,
    today: date | None = None,
) -> Selection:
    """Walk the user through chat → topic → date range; print confirmation."""
    if today is None:
        today = date.today()

    groups = gateway.list_groups()
    chat = _pick_group(groups, input_fn=input_fn, print_fn=print_fn)

    topic: Topic | None = None
    all_topics = False
    if chat.is_forum:
        topics = gateway.list_topics(chat.id)
        topic, all_topics = _pick_topic(topics, input_fn=input_fn, print_fn=print_fn)

    date_range = _pick_date_range(input_fn=input_fn, print_fn=print_fn, today=today)
    selection = Selection(
        chat=chat,
        topic=topic,
        all_topics=all_topics,
        date_range=date_range,
    )
    print_fn(_format_confirmation(selection))
    return selection
