"""Interactive command-line interface for approving admin registrations."""

import argparse
import sys
from typing import Optional

from admin.auth.authenticator import AdminAuthenticator
from admin.config import AdminConfig


def interactive_approval(auth: AdminAuthenticator) -> int:
    """Interactively review pending registrations one by one."""
    pending = auth.list_pending_users()
    if not pending:
        print("No pending admin registrations found.")
        return 0

    print(f"Pending registrations to review ({len(pending)}):")
    for user in pending:
        username = user["username"]
        created_at = user.get("created_at", "N/A")
        try:
            choice = input(
                f"\nUser: '{username}' (Registered: {created_at})\nApprove this user? [y/N]: "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return 1

        if choice in ("y", "yes"):
            auth.approve_user(username)
            print(f"User '{username}' approved.")
        else:
            auth.reject_user(username)
            print(f"User '{username}' not approved and removed from database.")

    print("\nReview complete.")
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Admin registration approval tool")
    parser.add_argument("--db-path", type=str, default=None, help="Path to SQLite auth database")
    parser.add_argument(
        "-c",
        "--clear",
        action="store_true",
        help="Clear all non-approved (pending) registrations at once",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("clear", help="Clear all non-approved registrations at once")

    args = parser.parse_args(argv)

    config = AdminConfig.from_env()
    auth = AdminAuthenticator(config=config, db_path=args.db_path)

    if args.clear or args.command == "clear":
        count = auth.clear_pending_users()
        print(f"Cleared {count} non-approved user registration(s).")
        return 0

    return interactive_approval(auth)


if __name__ == "__main__":
    sys.exit(main())
