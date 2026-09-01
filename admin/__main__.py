"""CLI entry point for running the Admin web console."""

import argparse
import sys

from admin.app import AdminApp
from admin.config import AdminConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="BookTower Admin Console")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--username", type=str, default="admin", help="Admin login username")
    parser.add_argument("--password", type=str, default="admin", help="Admin login password")

    args = parser.parse_args()

    config = AdminConfig(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
    )

    app = AdminApp(config)
    print(f"🚀 BookTower Admin Console starting on http://{args.host}:{args.port}")
    print(f"🔑 Default credentials: username='{args.username}', password='{args.password}'")

    try:
        app.run(background=False)
    except KeyboardInterrupt:
        print("\nStopping Admin Console...")
        app.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
