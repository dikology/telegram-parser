#!/usr/bin/env python3
# Adapted from chigwell/telegram-mcp (Apache-2.0).
"""
Генератор строки сессии Telegram по QR-коду для telegram-parser.

Запуск:
    uv run login.py

Нужны TELEGRAM_API_ID и TELEGRAM_API_HASH в .env (см. .env.example).
После успеха предлагает записать TELEGRAM_SESSION_STRING в .env.
"""

import asyncio
import getpass
import io
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import errors
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

# How many times the QR code is regenerated after expiry before giving up.
_QR_MAX_REFRESHES = 10

load_dotenv()


def _render_qr(qr) -> None:
    import qrcode

    print("\n----- Вход по QR-коду -----\n")

    qr_obj = qrcode.QRCode(border=1)
    qr_obj.add_data(qr.url)
    qr_obj.make(fit=True)
    f = io.StringIO()
    qr_obj.print_ascii(out=f, invert=True)
    print(f.getvalue())

    print("Отсканируйте QR-код выше в приложении Telegram:")
    print("  Откройте Telegram → Настройки → Устройства → Подключить устройство\n")
    print(f"Или откройте эту ссылку на устройстве, где вы уже вошли:\n  {qr.url}\n")
    print(f"Истекает в: {qr.expires.strftime('%H:%M:%S')}")
    print("Ожидаем сканирования...")


def _seconds_until_expiry(qr) -> float:
    """Seconds left before this QR token expires, with a small safety margin."""
    expires = qr.expires
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    remaining = (expires - datetime.now(timezone.utc)).total_seconds()
    return max(1.0, remaining - 1.0)


def _qr_login(client: TelegramClient) -> None:
    qr = client.qr_login()
    _render_qr(qr)

    for _ in range(_QR_MAX_REFRESHES):
        try:
            client.loop.run_until_complete(qr.wait(timeout=_seconds_until_expiry(qr)))
            return
        except asyncio.TimeoutError:
            client.loop.run_until_complete(qr.recreate())
            print("\nQR-код истёк, вот новый.")
            _render_qr(qr)
        except errors.SessionPasswordNeededError:
            while True:
                pw = getpass.getpass(
                    "\nВключена двухфакторная аутентификация. Введите пароль: "
                )
                try:
                    client.sign_in(password=pw)
                    return
                except errors.PasswordHashInvalidError:
                    print("Неверный пароль, попробуйте ещё раз.")

    print("\nQR-код истёк слишком много раз. Запустите вход снова.")
    client.disconnect()
    sys.exit(1)


def _write_session_to_env(session_string: str) -> None:
    with open(".env", "r") as file:
        env_contents = file.readlines()

    session_string_line_found = False
    for i, line in enumerate(env_contents):
        if line.startswith("TELEGRAM_SESSION_STRING="):
            env_contents[i] = f"TELEGRAM_SESSION_STRING={session_string}\n"
            session_string_line_found = True
            break

    if not session_string_line_found:
        env_contents.append(f"TELEGRAM_SESSION_STRING={session_string}\n")

    with open(".env", "w") as file:
        file.writelines(env_contents)


def main() -> None:
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть заданы в .env")
        print("Скопируйте .env.example в .env и заполните значения, которые вам передали.")
        sys.exit(1)

    try:
        api_id = int(api_id)
    except ValueError:
        print("Ошибка: TELEGRAM_API_ID должен быть целым числом")
        sys.exit(1)

    print("\n----- Генератор строки сессии Telegram -----\n")
    print("Этот скрипт создаст строку сессии для вашего аккаунта Telegram.")
    print("Её можно записать в файл .env.")
    print(
        "\nВаши данные НЕ отправляются ни на какой сервер и используются только для входа на этом компьютере.\n"
    )

    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        client.connect()

        if not client.is_user_authorized():
            _qr_login(client)

        session_string = StringSession.save(client.session)

        print("\nВход выполнен успешно!")
        print("\n----- Ваша строка сессии -----")
        print(f"\n{session_string}\n")
        print("Добавьте её в .env как:")
        print(f"TELEGRAM_SESSION_STRING={session_string}")
        print("\nВАЖНО: никому не показывайте эту строку!")

        try:
            choice = input(
                "\nЗаписать строку сессии в .env автоматически? (y/N): "
            )
        except EOFError:
            choice = "n"
        if choice.lower() == "y":
            try:
                _write_session_to_env(session_string)
                print("\nФайл .env обновлён.")
            except Exception as e:
                print(f"\nОшибка при обновлении .env: {e}")
                print("Добавьте строку сессии в .env вручную.")

        client.disconnect()

    except Exception as e:
        print(f"\nОшибка: {e}")
        print("Не удалось создать строку сессии. Попробуйте ещё раз.")
        sys.exit(1)


if __name__ == "__main__":
    main()
