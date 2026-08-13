#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"
uv run export.py
status=$?
echo
echo "Нажмите Enter, чтобы закрыть окно."
read -r _ || true
exit "$status"
