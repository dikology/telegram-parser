"""Finder .command launchers — run a fake `uv`, no network."""

import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_LAUNCHER = REPO_ROOT / "Экспорт чатов.command"
LOGIN_LAUNCHER = REPO_ROOT / "Вход.command"


def _install_fake_uv(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "uv.log"
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir()
    uv.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os, sys",
                f"log = {str(log)!r}",
                "with open(log, 'w', encoding='utf-8') as f:",
                "    f.write('cwd=' + os.getcwd() + '\\n')",
                "    f.write('args=' + ' '.join(sys.argv[1:]) + '\\n')",
            ]
        )
        + "\n"
    )
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
    return uv, log


def _run_launcher(launcher: Path, tmp_path: Path) -> list[str]:
    uv, log = _install_fake_uv(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    env = os.environ.copy()
    env["PATH"] = f"{uv.parent}{os.pathsep}{env.get('PATH', '')}"
    env["HOME"] = str(tmp_path)

    result = subprocess.run(
        [str(launcher)],
        cwd=elsewhere,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    return log.read_text(encoding="utf-8").splitlines()


def test_export_launcher_runs_export_from_project_dir(tmp_path: Path):
    recorded = _run_launcher(EXPORT_LAUNCHER, tmp_path)
    assert recorded[0] == f"cwd={REPO_ROOT}"
    assert recorded[1] == "args=run export.py"


def test_login_launcher_runs_login_from_project_dir(tmp_path: Path):
    recorded = _run_launcher(LOGIN_LAUNCHER, tmp_path)
    assert recorded[0] == f"cwd={REPO_ROOT}"
    assert recorded[1] == "args=run login.py"


def test_launchers_are_executable():
    for launcher in (EXPORT_LAUNCHER, LOGIN_LAUNCHER):
        assert launcher.stat().st_mode & stat.S_IXUSR, launcher


def test_readme_explains_launchers():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "Экспорт чатов.command" in readme
    assert "Вход.command" in readme
    assert "дважды" in readme.lower()
