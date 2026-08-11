#!/usr/bin/env python3
# Adapted from chigwell/telegram-mcp (Apache-2.0).
"""
QR-only Telegram session string generator for telegram-parser.

Usage:
    uv run login.py

Requires TELEGRAM_API_ID and TELEGRAM_API_HASH in .env (see .env.example).
On success, offers to write TELEGRAM_SESSION_STRING into .env.
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

    print("\n----- QR Code Login -----\n")

    qr_obj = qrcode.QRCode(border=1)
    qr_obj.add_data(qr.url)
    qr_obj.make(fit=True)
    f = io.StringIO()
    qr_obj.print_ascii(out=f, invert=True)
    print(f.getvalue())

    print("Scan the QR code above with your Telegram app:")
    print("  Open Telegram > Settings > Devices > Link Desktop Device\n")
    print(f"Or open this link on a device where you're logged in:\n  {qr.url}\n")
    print(f"Expires at: {qr.expires.strftime('%H:%M:%S')}")
    print("Waiting for you to scan...")


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
            print("\nQR code expired, here is a fresh one.")
            _render_qr(qr)
        except errors.SessionPasswordNeededError:
            while True:
                pw = getpass.getpass(
                    "\nTwo-factor authentication enabled. Please enter your password: "
                )
                try:
                    client.sign_in(password=pw)
                    return
                except errors.PasswordHashInvalidError:
                    print("Invalid password, please try again.")

    print("\nQR code expired too many times. Please run the generator again.")
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
        print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env file")
        print("Create an .env file with your credentials from https://my.telegram.org/apps")
        sys.exit(1)

    try:
        api_id = int(api_id)
    except ValueError:
        print("Error: TELEGRAM_API_ID must be an integer")
        sys.exit(1)

    print("\n----- Telegram Session String Generator -----\n")
    print("This script will generate a session string for your Telegram account.")
    print("The generated session string can be added to your .env file.")
    print(
        "\nYour credentials will NOT be stored on any server and are only used for local authentication.\n"
    )

    try:
        client = TelegramClient(StringSession(), api_id, api_hash)
        client.connect()

        if not client.is_user_authorized():
            _qr_login(client)

        session_string = StringSession.save(client.session)

        print("\nAuthentication successful!")
        print("\n----- Your Session String -----")
        print(f"\n{session_string}\n")
        print("Add this to your .env file as:")
        print(f"TELEGRAM_SESSION_STRING={session_string}")
        print("\nIMPORTANT: Keep this string private and never share it with anyone!")

        try:
            choice = input(
                "\nWould you like to automatically update your .env file with this session string? (y/N): "
            )
        except EOFError:
            choice = "n"
        if choice.lower() == "y":
            try:
                _write_session_to_env(session_string)
                print("\n.env file updated successfully!")
            except Exception as e:
                print(f"\nError updating .env file: {e}")
                print("Please manually add the session string to your .env file.")

        client.disconnect()

    except Exception as e:
        print(f"\nError: {e}")
        print("Failed to generate session string. Please try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
