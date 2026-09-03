"""CLI entry point for running the Admin web console and data import/export CLI."""

import argparse
from datetime import datetime
import os
import sys
from pathlib import Path
from typing import List, Optional, Union
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

from admin.app import AdminApp
from admin.config import AdminConfig
from admin.services.data_service import AdminDataTransferService, VALID_COMPONENTS


def handle_export(assets_path: str, output_path: Optional[str] = None) -> int:
    """Execute CLI export of assets to a zip archive."""
    service = AdminDataTransferService(assets_path=assets_path)
    default_out = f"booktower_assets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    target = output_path or default_out
    try:
        saved_path = service.export_assets_to_zip(output_target=target)
        print(f"✅ Успешно экспортированы ассеты из '{assets_path}' в архив: {saved_path}")
        return 0
    except Exception as e:
        print(f"❌ Ошибка экспорта данных: {e}", file=sys.stderr)
        return 1


def handle_import(assets_path: str, zip_file: str, component: Optional[Union[str, List[str]]] = None) -> int:
    """Execute CLI import of assets from a zip archive."""
    service = AdminDataTransferService(assets_path=assets_path)
    try:
        result = service.import_assets_from_zip(zip_file, component=component)
        comp_str = (
            f" (разделы: {result['component']})"
            if result.get("component") and result.get("component") != "all"
            else ""
        )
        print(f"✅ Успешно импортированы данные{comp_str} в '{assets_path}'!")
        imported_comps = result.get("imported_components", [])
        if imported_comps:
            print(f"   Импортировано разделов: {len(imported_comps)} ({', '.join(imported_comps)})")
        print(f"   Заменено файлов: {result.get('files_count', 0)}")
        return 0
    except Exception as e:
        print(f"❌ Ошибка импорта данных: {e}", file=sys.stderr)
        return 1


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(description="BookTower Admin Console & Data Management")
    parser.add_argument("--host", type=str, default=None, help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on (default: 8080)")
    parser.add_argument("--auth-db-path", "--authDbPath", dest="auth_db_path", type=str, default=None, help="Path to SQLite auth database")
    parser.add_argument("--assets-path", "--assetsPath", dest="assets_path", type=str, default=None, help="Path to assets directory")
    parser.add_argument("--export", dest="export_file", nargs="?", const="default", default=None, help="Export all assets into a zip archive")
    parser.add_argument("--import", dest="import_file", type=str, default=None, help="Import assets from a zip archive")
    parser.add_argument("--component", "--partial-import", dest="component", nargs="*", default=None, help="Target component(s) for partial import")

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    export_parser = subparsers.add_parser("export", help="Export all assets into a zip archive")
    export_parser.add_argument("output", nargs="?", default=None, help="Output zip file path (default: booktower_assets_export_TIMESTAMP.zip)")
    export_parser.add_argument("--assets-path", "--assetsPath", dest="assets_path", type=str, default=None, help="Path to assets directory")

    import_parser = subparsers.add_parser("import", help="Import assets from a zip archive")
    import_parser.add_argument("zip_file", type=str, help="Path to the zip archive to import")
    import_parser.add_argument("--component", "--partial-import", "-c", dest="component", nargs="*", default=None, help="Target component(s) for partial import")
    import_parser.add_argument("--assets-path", "--assetsPath", dest="assets_path", type=str, default=None, help="Path to assets directory")

    args = parser.parse_args(argv)

    if args.assets_path:
        os.environ["ASSETS_PATH"] = args.assets_path

    env_config = AdminConfig.from_env()
    effective_assets_path = args.assets_path or env_config.assets_path

    # Handle Export CLI (via subcommand or flag)
    if args.subcommand == "export" or args.export_file is not None:
        out_target = getattr(args, "output", None) or (args.export_file if args.export_file != "default" else None)
        exit_code = handle_export(effective_assets_path, output_path=out_target)
        sys.exit(exit_code)
        return

    # Handle Import CLI (via subcommand or flag)
    if args.subcommand == "import" or args.import_file is not None:
        in_file = getattr(args, "zip_file", None) or args.import_file
        comp = args.component
        exit_code = handle_import(effective_assets_path, zip_file=in_file, component=comp)
        sys.exit(exit_code)
        return

    config = AdminConfig(
        host=args.host or env_config.host,
        port=args.port if args.port is not None else env_config.port,
        auth_db_path=args.auth_db_path or env_config.auth_db_path,
        assets_path=effective_assets_path,
        recs_path=env_config.recs_path,
        timetables_path=env_config.timetables_path,
    )

    app = AdminApp(config)
    print(f"🚀 BookTower Admin Console starting on http://{config.host}:{config.port}")
    print(f"🔒 Secure Basic Authentication enabled (database: '{config.auth_db_path}')")

    try:
        app.run(background=False)
    except KeyboardInterrupt:
        print("\nStopping Admin Console...")
        app.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
