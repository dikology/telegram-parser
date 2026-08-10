# Telegram group-chat export toolkit (v1)

> **Status**: not yet filed to the issue tracker. `gh` is not installed/authenticated
> on this machine; file this to GitHub Issues with the `ready-for-agent` label once
> available, then this file can be deleted.

## Problem Statement

A non-technical person wants a copy of the message history from one of their
Telegram group chats for a specific date range (e.g. "everything from our book
club group in June"), readable as plain text and available to reprocess as
structured data. They have a Mac but no development environment, no `git`, and
no experience with Telegram's API. Today the only options are scrolling
manually through the Telegram app, or relying on someone technical to run a
one-off script for them each time.

## Solution

A small, self-contained toolkit — distributed as a GitHub "Download ZIP", unzipped
into a folder, and run from Terminal on a Mac — that lets that person:

1. Log in to their own Telegram account once (QR-code scan, no phone/SMS flow)
   and save an authenticated session locally.
2. Run an interactive, Russian-language menu that walks them through picking
   one group chat (optionally one thread within it, if the group uses forum
   topics), a date range, and exporting the messages to a human-readable `.txt`
   transcript plus a structured `.json` file in their Downloads folder.
3. Re-run exports afterwards by double-clicking a launcher, without opening
   Terminal again.

The toolkit ships with one shared Telegram API application (`api_id`/`api_hash`,
created once by the developer and distributed privately) so the end user never
needs to register anything on `my.telegram.org` — the only account-specific
secret they generate themselves is the session string from the QR login.

## User Stories

1. As a non-technical Mac user, I want step-by-step Russian instructions for
   installing everything needed (uv, which provisions Python itself), so that I
   don't need any prior programming knowledge to get started.
2. As a non-technical Mac user, I want to download the toolkit as a ZIP file
   from GitHub, so that I don't need to know what `git` or `clone` mean.
3. As a recipient of this toolkit, I want to receive a working `api_id`/`api_hash`
   pair from the person who gave me the toolkit, so that I don't have to
   register my own application on my.telegram.org.
4. As a first-time user, I want to log in by scanning a QR code with my phone's
   Telegram app, so that I never have to handle SMS codes or type my phone
   number.
5. As a first-time user, I want the login script to offer to save my session
   string into `.env` for me, so that I don't have to manually edit
   configuration files.
6. As a returning user, I want my saved session to be reused automatically, so
   that I don't have to log in again for every export.
7. As a user with many group chats, I want to type part of a chat's name to
   narrow the list before picking, so that I'm not scrolling through fifty
   numbered options.
8. As a user with only a few group chats, I want to skip the search step and
   see the full numbered list immediately, so that an empty search still works.
9. As a user, I want only groups and supergroups shown in the picker, so that
   channels and private one-on-one chats don't clutter the list.
10. As a user exporting from a group that uses Telegram's forum/topics feature,
    I want to pick a single topic, so that I only get the thread I care about.
11. As a user exporting from a forum-enabled group, I want the option to export
    every topic in that group for the same period in one run, so that I don't
    have to repeat the process per topic.
12. As a user exporting from a group without topics, I want the topic-picking
    step to be skipped entirely, so that plain groups behave simply.
13. As a user, I want to type a date range as `ДД.MM.ГГГГ`, so that the format
    matches how I'd normally write dates.
14. As a user, I want quick presets like "last week" or "last month", so that I
    don't have to type exact dates for common cases.
15. As a user, I want a plain-text transcript where each line shows the time,
    sender name, and message text, so that I can read it like a chat log.
16. As a user, I want a JSON file alongside the transcript with the same
    messages in structured form, so that I (or someone else) can reprocess the
    data programmatically.
17. As a user exporting a forum-enabled group's topics, I want one transcript
    (txt+json) per topic inside a folder named after the group, so that
    threads stay separate and readable rather than interleaved.
18. As a user, I want photos, voice messages, files, and other attachments
    shown as a placeholder (e.g. "[фото]", "[файл: report.pdf]") in the
    transcript, so that I know something was there without waiting for large
    downloads.
19. As a user exporting a long history, I want to see a periodically updating
    count of messages fetched, so that I know the export is progressing and
    hasn't frozen.
20. As a user, I want the tool to handle Telegram's rate-limit ("flood wait")
    responses by waiting and telling me it's waiting, so that I never see a
    raw error or crash because of it.
21. As a returning user, I want a double-clickable launcher for exports, so
    that after the initial setup I never have to open Terminal again.
22. As the developer distributing this toolkit, I want the login flow adapted
    from `telegram-mcp`'s `session_string_generator.py` with a visible
    Apache-2.0 attribution, so that reused code is properly credited.
23. As the developer, I want an Apache-2.0 `LICENSE` file in the repo, so that
    the terms of reuse and redistribution are unambiguous.
24. As the developer, I want `.env` (containing credentials and the session
    string) to stay gitignored, so that I never accidentally commit secrets
    during development.

## Implementation Decisions

- **Repo**: this repo (`telegram-parser`). Package/dependency management via
  `uv` + `pyproject.toml` (mirrors `telegram-mcp`'s setup), so `uv sync` /
  `uv run` provisions Python itself — no separate Python install step in the
  README.
- **Two entry-point scripts**, no unified single-CLI menu combining both
  concerns:
  - `login.py` — one-time interactive QR login. Adapted from
    `telegram-mcp/session_string_generator.py`: keep the QR-login and
    `.env`-writing logic; drop `--phone` flow, `install_guard.py` (PyPI-name
    collision guard, not applicable here), and `client_identity.py` (device-name
    env vars, not needed for a single personal use case). Add a short
    "adapted from chigwell/telegram-mcp (Apache-2.0)" credit comment.
  - `export.py` — interactive Russian-language menu: search/pick chat → (if
    forum-enabled) pick topic or "all topics" → pick date range (typed
    `DD.MM.YYYY` or preset) → export.
- **Telegram access seam**: a thin gateway module wrapping the specific
  Telethon calls needed (list dialogs filtered to groups/supergroups, list
  forum topics via the `entity.forum` flag + `GetForumTopicsRequest`/native
  Telethon 1.44+ equivalent, iterate messages within a date range for a chat or
  topic). All chat-picking, topic-picking, date-parsing, formatting, and
  file-writing logic takes this gateway (or a fake standing in for it) as a
  parameter, so none of that logic touches Telethon directly.
- **Credentials**: single shared `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` pair
  (one Telegram application registered once by the developer, distributed
  out-of-band/privately) plus a per-user `TELEGRAM_SESSION_STRING` generated by
  `login.py`. All three live in `.env` (copied from a checked-in
  `.env.example`), following the same variable names as `telegram-mcp` for
  familiarity. Single account only — no multi-account label support.
- **Chat picker**: prompts for an optional search substring (case-insensitive
  match against chat title); empty input shows the full numbered list of
  groups/supergroups (dialogs where the entity is a `Chat` or a `Channel` with
  `megagroup=True`), excluding channels (`megagroup=False`) and private
  one-on-one dialogs.
- **Topic handling**: only offered when the selected entity has `forum=True`.
  Menu offers each topic by title plus an "all topics" choice. Groups without
  forum topics skip this step entirely and export as a single thread.
- **Date input**: custom range typed as `DD.MM.YYYY` for both start and end,
  parsed to date boundaries; presets for "last 7 days", "last 30 days", and
  "custom range" reduce typing for common cases. End date is inclusive.
- **Export scope**: exactly one group per run (with either one topic or all of
  that group's topics). No cross-group bulk export in v1.
- **Output layout**: rooted at `~/Downloads/telegram-export/`.
  - Plain group (or a single chosen topic): `<chat-name>_<from>_<to>.txt` and
    `.json` directly under the root.
  - "All topics" export of a forum-enabled group:
    `<group-name>/<topic-name>_<from>_<to>.{txt,json}`, one file pair per
    topic, all inside a subfolder named after the group.
  - Chat/topic names are sanitized for filesystem-safety (strip/replace path
    separators and other invalid characters) before being used in paths.
- **Transcript (`.txt`) format**: one line per message,
  `[YYYY-MM-DD HH:MM] Sender Name: message text`, matching the reference
  project's general message-line conventions (media placeholder, reply/forward
  indicators can follow the same spirit as `telegram-mcp`'s
  `format_message_line`, scoped down to what's needed for a readable
  transcript).
- **Structured (`.json`) format**: one record per message mirroring
  `telegram-mcp`'s `message_to_dict` shape (id, sender, date, text, media
  label, reply/forward metadata where present) — omit empty/absent fields
  rather than emitting nulls, for compactness.
- **Media**: never downloaded in v1. Represented as a short placeholder label
  (photo/voice/video/document-with-filename/sticker/etc.), reusing the
  detection logic pattern from `telegram-mcp`'s `get_media_label`.
- **Progress & rate limits**: while iterating messages, print a periodically
  updated count (e.g. "Загружено N сообщений…") rather than a silent hang.
  Telegram flood-wait errors are caught, the required wait time is
  communicated in Russian, the process sleeps, and the fetch resumes
  automatically rather than raising to the user.
- **Repeat-use launcher**: a `.command` file (e.g. `Экспорт чатов.command`)
  that `cd`s into the project directory and runs `uv run export.py`, so that
  after the one-time Terminal-based setup, day-to-day exports are a Finder
  double-click. A second `.command` launcher for `login.py` is reasonable to
  include as well, for re-authenticating later without reopening Terminal
  manually.
- **Licensing**: add an `Apache-2.0` `LICENSE` file at the repo root, matching
  the license of the `telegram-mcp` code being adapted.
- **README**: entirely in Russian, covering: what this tool does, installing
  `uv` (official install script, no Homebrew dependency assumed), running
  `login.py` once, filling in `.env` with the credentials received privately,
  running `export.py` (or the `.command` launcher) for each export, and a
  troubleshooting section (no chats found, invalid credentials, flood wait,
  etc.) mirroring `telegram-mcp`'s troubleshooting section in tone.

## Testing Decisions

- Good tests here assert on **external behavior** — the files that end up on
  disk, the formatted transcript lines, the menu's chat/topic/date-range
  selection outcomes — never on internal call sequences into Telethon.
- **`login.py`**: directly reuse the prior-art pattern from
  `telegram-mcp/tests/test_session_string_generator.py` — fake QR object
  (`_FakeQR`) and fake client (`_FakeClient`) standing in for Telethon,
  `monkeypatch` for `input`/`getpass`/`sys.argv`, asserting on `.env` file
  contents after a run and on retry/2FA/expiry behavior. No real network
  connection in any test.
- **`export.py` and its supporting modules**: introduce a fake gateway
  implementing the same narrow interface as the real Telethon-backed gateway
  (list groups, list topics, iterate messages for a date range) returning
  canned in-memory data. Tests drive the menu/export logic with the fake
  gateway and fake stdin (via `monkeypatch` on `input`, following the same
  pattern as the reference project's tests) and assert on:
  - which chats appear in the picker after a given search substring (groups
    only, channels/DMs excluded).
  - topic-selection behavior for forum vs. non-forum groups, including the
    "all topics" path.
  - date parsing for both typed `DD.MM.YYYY` ranges and each preset.
  - the exact `.txt` line format and `.json` record shape produced from a
    canned set of fake messages (including a media message, a reply, and a
    forwarded message, to exercise the placeholder/metadata logic).
  - output file paths for both the single-thread and per-group/per-topic
    layouts, including filename sanitization of unusual characters.
  - flood-wait handling: fake gateway raises a flood-wait-like exception with
    a `.seconds` value; test injects a fake sleep function and asserts the
    fetch retries and completes rather than propagating the exception.
- No test opens a real Telegram connection, reads a real `.env`, or writes
  outside a temporary directory (`tmp_path` fixture) provided by pytest.

## Out of Scope

- Registering per-user `api_id`/`api_hash` via my.telegram.org — v1 ships one
  shared application pair distributed privately by the developer.
- Phone-number + SMS-code login — QR-only for v1.
- Exporting channels or private one-on-one chats.
- Bulk export across multiple *different* groups in a single run — v1 is
  scoped to one selected group per run (optionally all its topics).
- Downloading media attachments — placeholders only.
- Multi-account support (several saved sessions/labels in one install).
- Windows/Linux setup instructions — Mac only for v1.
- Resuming a single export that was interrupted mid-run by something other
  than a flood wait (e.g. the process being killed) — re-running from scratch
  is acceptable for v1.
- Filing this spec to GitHub Issues — blocked on `gh` being installed and
  authenticated on this machine; see the status note at the top of this file.

## Further Notes

- The shared `api_id`/`api_hash` pair is a deliberate v1 tradeoff: it removes
  the hardest onboarding step for a non-technical recipient, at the cost of
  concentrating Telegram-side rate limits/reputation under one application
  identity shared by everyone who receives this toolkit. Acceptable for
  friends/family-scale distribution; would need revisiting for any wider
  release.
- `telegram-mcp` (`chigwell/telegram-mcp`, Apache-2.0) is the direct source of
  the login flow being adapted, and a strong reference for message
  formatting/sanitization conventions (`message_to_dict`, `get_media_label`,
  `format_message_line`) and forum-topic access
  (`entity.forum`, `GetForumTopicsRequest`) even though none of its MCP-server,
  multi-account, or write-tool functionality is relevant here.
- Once `gh` is available, file this spec as a GitHub issue on
  `dikology/telegram-parser` with the `ready-for-agent` label (per
  `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`), and
  delete this file.
