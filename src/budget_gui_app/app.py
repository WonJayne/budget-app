"""Application entry point."""

from __future__ import annotations

from .ui.main import build_ui


def main() -> None:
    build_ui()


if __name__ in {"__main__", "__mp_main__"}:
    main()
