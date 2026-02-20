from __future__ import annotations

from .app import DashboardApp
from .config import load_config


def main() -> None:
    config = load_config()
    app = DashboardApp(config)
    app.run()


if __name__ == "__main__":
    main()
