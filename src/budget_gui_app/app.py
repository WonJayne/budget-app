"""Application entry point."""

from __future__ import annotations

from .ui.main import main


if __name__ in {"__main__", "__mp_main__"}:
    main()
