"""README coverage — required topics and actual CLI wording."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_is_russian_not_a_stub():
    readme = _readme()
    assert "issue #8" not in readme.lower()
    assert "Устранение неполадок" in readme


def test_readme_installs_uv_via_official_script():
    readme = _readme()
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in readme
    assert "Homebrew не требуется" in readme


def test_readme_walks_through_login_and_env():
    readme = _readme()
    assert "login.py" in readme
    assert ".env.example" in readme
    assert "TELEGRAM_API_ID" in readme
    assert "TELEGRAM_API_HASH" in readme
    assert "TELEGRAM_SESSION_STRING" in readme


def test_readme_walks_through_export_launcher_and_cli():
    readme = _readme()
    assert "Экспорт чатов.command" in readme
    assert "uv run export.py" in readme


def test_readme_troubleshooting_covers_required_cases():
    readme = _readme()
    assert "Ничего не найдено. Показан полный список." in readme
    assert "Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH должны быть заданы в .env" in readme
    assert "Telegram ограничил запросы." in readme
    assert "Темы форума:" in readme


def test_readme_quotes_login_and_export_prompts():
    readme = _readme()
    assert "Откройте Telegram → Настройки → Устройства → Подключить устройство" in readme
    assert "Записать строку сессии в .env автоматически? (y/N):" in readme
    assert "Введите часть названия чата для поиска (или Enter — показать все):" in readme
    assert "----- Экспорт истории Telegram -----" in readme
    assert "Downloads/telegram-export" in readme
