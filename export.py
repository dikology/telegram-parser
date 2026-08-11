#!/usr/bin/env python3
"""Interactive Telegram group-chat export (single-thread .txt + .json)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from telegram_parser.export_messages import export_selection
from telegram_parser.gateway import TelethonGateway
from telegram_parser.selection import run_selection

load_dotenv()

DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "telegram-export"


def _connect_client() -> TelegramClient:
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session = os.getenv("TELEGRAM_SESSION_STRING")

    if not api_id or not api_hash:
        print("Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть заданы в .env")
        print("Скопируйте .env.example в .env и заполните значения.")
        sys.exit(1)
    if not session:
        print("Ошибка: TELEGRAM_SESSION_STRING не задан в .env")
        print("Сначала выполните: uv run login.py")
        sys.exit(1)

    try:
        api_id = int(api_id)
    except ValueError:
        print("Ошибка: TELEGRAM_API_ID должен быть целым числом")
        sys.exit(1)

    client = TelegramClient(StringSession(session), api_id, api_hash)
    client.connect()
    if not client.is_user_authorized():
        print("Сессия недействительна. Выполните снова: uv run login.py")
        client.disconnect()
        sys.exit(1)
    return client


def main() -> None:
    print("\n----- Экспорт истории Telegram -----\n")
    print("Выберите группу, тему (если есть) и период.\n")

    client = _connect_client()
    try:
        gateway = TelethonGateway(client)
        selection = run_selection(gateway)
        try:
            txt_path, json_path = export_selection(
                selection,
                gateway,
                output_dir=DEFAULT_OUTPUT_DIR,
            )
        except ValueError as exc:
            print(f"Ошибка: {exc}")
            print("Выберите одну тему или обычную группу без форума.")
            sys.exit(1)
        print(f"Готово.\n  {txt_path}\n  {json_path}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
