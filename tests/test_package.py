"""Smoke test that the package skeleton is importable after `uv sync`."""


def test_package_is_importable():
    import telegram_parser

    assert telegram_parser.__version__
