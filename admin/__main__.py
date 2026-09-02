"""CLI entry point for running the Admin web console."""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from admin.app import AdminApp
from admin.config import AdminConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="BookTower Admin Console")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--auth-db-path", type=str, default=None, help="Path to SQLite auth database")

    args = parser.parse_args()
    env_config = AdminConfig.from_env()

    config = AdminConfig(
        host=args.host,
        port=args.port,
        auth_db_path=args.auth_db_path or env_config.auth_db_path,
        assets_path=env_config.assets_path,
        recs_path=env_config.recs_path,
        timetables_path=env_config.timetables_path,
    )

    app = AdminApp(config)
    print(f"🚀 BookTower Admin Console starting on http://{args.host}:{args.port}")
    print(f"🔒 Secure Basic Authentication enabled (database: '{config.auth_db_path}')")

    try:
        app.run(background=False)
    except KeyboardInterrupt:
        print("\nStopping Admin Console...")
        app.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
