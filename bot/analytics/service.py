"""UX analytics service managing counters, user paths, and reporting."""

import csv
from collections import Counter
from datetime import datetime, timezone
import io
import logging
import os
from pathlib import Path
import sqlite3
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple, Union
import zipfile

from bot.analytics.anonymizer import anonymize_user_id
from bot.content import ANALYTICS_DB_PATH, WISHLIST_DB_PATH

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_FLUSH_THRESHOLD_BYTES = 50 * 1024 * 1024  # 50 MB


def parse_memory_threshold_bytes(
    val: Optional[Union[str, int, float]],
    default_bytes: int = DEFAULT_FLUSH_THRESHOLD_BYTES,
) -> int:
    """Parse a memory threshold specification into bytes.

    Accepts values like 50, "50MB", "50M", "50000000", "500KB", "1GB".
    """
    if val is None:
        return default_bytes

    if isinstance(val, (int, float)):
        # If small numeric value <= 10240, treat as megabytes
        if val <= 10240:
            return int(val * 1024 * 1024)
        return int(val)

    s = str(val).strip().upper()
    if not s:
        return default_bytes

    try:
        if s.endswith("GB") or s.endswith("G"):
            num_str = s.rstrip("GB").rstrip("G").strip()
            return int(float(num_str) * 1024 * 1024 * 1024)
        if s.endswith("MB") or s.endswith("M"):
            num_str = s.rstrip("MB").rstrip("M").strip()
            return int(float(num_str) * 1024 * 1024)
        if s.endswith("KB") or s.endswith("K"):
            num_str = s.rstrip("KB").rstrip("K").strip()
            return int(float(num_str) * 1024)
        if s.endswith("B"):
            num_str = s.rstrip("B").strip()
            return int(float(num_str))

        parsed_float = float(s)
        if parsed_float <= 10240:
            return int(parsed_float * 1024 * 1024)
        return int(parsed_float)
    except Exception as e:
        logger.warning(f"Could not parse memory threshold '{val}': {e}. Using default {default_bytes} bytes.")
        return default_bytes


class AnalyticsService:
    """Service managing UX metrics collection, storage, in-memory buffering and aggregation."""

    EVENT_INLINE_KEYBOARD = "inline_keyboard_events"
    EVENT_COMMAND = "commands"
    EVENT_UNRECOGNIZED = "unrecognized_messages"

    MENU_INLINE_BUTTON_SPECS = [
        {
            "name": "🏢 План ярмарки",
            "callback": "action_map",
            "aliases": ["action_map", "🏢 План ярмарки", "План ярмарки", "Карта", "map"],
        },
        {
            "name": "📅 Расписание",
            "callback": "action_timetable",
            "aliases": ["action_timetable", "📅 Расписание", "Расписание", "timetable", "timetables"],
        },
        {
            "name": "🎈 Детская программа",
            "callback": "section_children_activity",
            "aliases": ["section_children_activity", "🎈 Детская программа", "Детская программа", "children"],
        },
        {
            "name": "🎨 Мастер-классы",
            "callback": "action_master_classes",
            "aliases": ["action_master_classes", "🎨 Мастер-классы", "Мастер-классы", "masterclasses"],
        },
        {
            "name": "📚 Рекомендации",
            "callback": "action_recommendations",
            "aliases": ["action_recommendations", "📚 Рекомендации", "Рекомендации", "recommendations"],
        },
        {
            "name": "👥 Участники",
            "callback": "action_participants",
            "aliases": ["action_participants", "👥 Участники", "Участники", "participants", "participants_list"],
        },
        {
            "name": "📝 Вишлист",
            "callback": "action_wishlist",
            "aliases": ["action_wishlist", "📝 Вишлист", "Вишлист", "wishlist"],
        },
        {
            "name": "ℹ️ Помощь",
            "callback": "action_help",
            "aliases": ["action_help", "ℹ️ Помощь", "Помощь", "help"],
        },
    ]

    BASIC_TEXT_COMMAND_SPECS = [
        {"command": "/start", "description": "Запуск / Главное меню", "aliases": ["/start", "start"]},
        {"command": "/help", "description": "Помощь", "aliases": ["/help", "help"]},
        {"command": "/map", "description": "План площадки", "aliases": ["/map", "map"]},
        {"command": "/timetables", "description": "Расписание мероприятий", "aliases": ["/timetables", "/timetable", "/schedule", "timetables", "timetable"]},
        {"command": "/children", "description": "Детская программа", "aliases": ["/children", "/children_activity", "/kids", "children"]},
        {"command": "/masterclasses", "description": "Мастер-классы", "aliases": ["/masterclasses", "/masterclass", "/mc", "/master_classes", "masterclasses", "mc"]},
        {"command": "/recommendations", "description": "Рекомендации книг", "aliases": ["/recommendations", "/recs", "recommendations", "recs"]},
        {"command": "/participants", "description": "Участники и стенды", "aliases": ["/participants", "/stands", "/stand", "/vendors", "/vendor", "/part", "participants", "stands"]},
        {"command": "/wishlist", "description": "Вишлист и книги", "aliases": ["/wishlist", "/getlist", "/addbook", "/editbook", "/removebook", "/deletebook", "/isbn", "/addisbn", "wishlist"]},
    ]

    def __init__(
        self,
        db_path: Optional[str] = None,
        wishlist_db_path: Optional[str] = None,
        flush_threshold_bytes: Optional[int] = None,
    ):
        if db_path is None:
            env_db = os.getenv("ANALYTICS_DB_PATH", "assets/db/analytics.db")
            if not os.path.isabs(env_db):
                self.db_path = str((PROJECT_ROOT / env_db).resolve())
            else:
                self.db_path = env_db
        else:
            self.db_path = db_path

        if wishlist_db_path is None:
            env_wdb = os.getenv("WISHLIST_DB_PATH", "assets/db/wishlist.db")
            if not os.path.isabs(env_wdb):
                self.wishlist_db_path = str((PROJECT_ROOT / env_wdb).resolve())
            else:
                self.wishlist_db_path = env_wdb
        else:
            self.wishlist_db_path = wishlist_db_path

        # Threshold configuration
        if flush_threshold_bytes is not None:
            self.flush_threshold_bytes = flush_threshold_bytes
        else:
            env_threshold = (
                os.getenv("ANALYTICS_FLUSH_THRESHOLD_MB")
                or os.getenv("ANALYTICS_MEMORY_THRESHOLD")
                or os.getenv("ANALYTICS_RAM_THRESHOLD")
                or os.getenv("ANALYTICS_FLUSH_THRESHOLD")
            )
            self.flush_threshold_bytes = parse_memory_threshold_bytes(env_threshold)

        # In-memory RAM buffers
        self._lock = threading.Lock()
        self._buffer_events: Dict[str, int] = {
            self.EVENT_INLINE_KEYBOARD: 0,
            self.EVENT_COMMAND: 0,
            self.EVENT_UNRECOGNIZED: 0,
        }
        self._buffer_inline_buttons: Dict[str, int] = {}
        self._buffer_text_commands: Dict[str, int] = {}
        self._buffer_chats: Dict[str, int] = {}
        self._buffer_commands: List[Dict[str, str]] = []
        self._buffer_bytes: int = 0

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection to SQLite database."""
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize analytics database schema for user paths only."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode = WAL;")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ux_user_commands (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        command TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ux_user_commands_uid ON ux_user_commands (user_id, id);")
                # Drop legacy tables if they exist: use DB only for user paths
                cursor.execute("DROP TABLE IF EXISTS ux_event_counters;")
                cursor.execute("DROP TABLE IF EXISTS ux_users;")
                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing analytics database: {e}", exc_info=True)

    def get_buffered_memory_usage(self) -> int:
        """Estimate current memory usage (in bytes) of in-memory analytics data in RAM."""
        with self._lock:
            size = (
                sys.getsizeof(self._buffer_events)
                + sys.getsizeof(self._buffer_inline_buttons)
                + sys.getsizeof(self._buffer_text_commands)
                + sys.getsizeof(self._buffer_chats)
                + sys.getsizeof(self._buffer_commands)
                + self._buffer_bytes
            )
            return size

    def _check_and_flush_if_needed(self) -> None:
        """Flush buffer to database if memory threshold is reached."""
        if self.get_buffered_memory_usage() >= self.flush_threshold_bytes:
            self.flush()

    def flush(self) -> None:
        """Flush buffered in-memory user commands into the SQLite database on disk."""
        with self._lock:
            if self._buffer_commands:
                try:
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        for cmd_entry in self._buffer_commands:
                            cursor.execute(
                                """
                                INSERT INTO ux_user_commands (user_id, command, created_at)
                                VALUES (?, ?, ?);
                                """,
                                (cmd_entry["user_id"], cmd_entry["command"], cmd_entry["created_at"]),
                            )
                        conn.commit()
                    self._buffer_commands.clear()
                except Exception as e:
                    logger.error(f"Error flushing analytics data to database: {e}", exc_info=True)
            self._buffer_bytes = 0

    def record_chat_interaction(self, user_id: str) -> None:
        """Record/increment chat count for anonymized user in RAM buffer."""
        if not user_id:
            return
        with self._lock:
            self._buffer_chats[user_id] = self._buffer_chats.get(user_id, 0) + 1
            self._buffer_bytes += 16
        self._check_and_flush_if_needed()

    def record_inline_keyboard_event(
        self,
        user_id: Optional[str] = None,
        callback_data: Optional[str] = None,
        button_name: Optional[str] = None,
    ) -> None:
        """Record an inline keyboard button click event in RAM."""
        with self._lock:
            self._buffer_events[self.EVENT_INLINE_KEYBOARD] += 1
            self._buffer_bytes += 32
            if callback_data:
                self._buffer_inline_buttons[callback_data] = (
                    self._buffer_inline_buttons.get(callback_data, 0) + 1
                )
                self._buffer_bytes += len(callback_data) + 16
            if button_name and button_name != callback_data:
                self._buffer_inline_buttons[button_name] = (
                    self._buffer_inline_buttons.get(button_name, 0) + 1
                )
                self._buffer_bytes += len(button_name) + 16
        self._check_and_flush_if_needed()

    def record_command(
        self,
        user_id: Optional[str],
        command: str,
    ) -> None:
        """Record command execution and append to user path in DB and buffer."""
        cleaned_cmd = command.strip()
        if not cleaned_cmd:
            return
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self._buffer_events[self.EVENT_COMMAND] += 1
            self._buffer_bytes += len(cleaned_cmd) + 32
            if cleaned_cmd.startswith("/"):
                cmd_norm = cleaned_cmd.split()[0].split("@")[0].lower()
                self._buffer_text_commands[cmd_norm] = (
                    self._buffer_text_commands.get(cmd_norm, 0) + 1
                )
            if user_id:
                # Directly persist user command so ongoing sessions are immediately in DB
                try:
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            INSERT INTO ux_user_commands (user_id, command, created_at)
                            VALUES (?, ?, ?);
                            """,
                            (user_id, cleaned_cmd, now_str),
                        )
                        conn.commit()
                except Exception as e:
                    logger.error(f"Error directly persisting user command: {e}", exc_info=True)
                    self._buffer_commands.append({
                        "user_id": user_id,
                        "command": cleaned_cmd,
                        "created_at": now_str,
                    })
                    self._buffer_bytes += len(user_id) + len(cleaned_cmd) + 64
        self._check_and_flush_if_needed()

    def record_unrecognized_message(
        self,
        user_id: Optional[str] = None,
        message_text: Optional[str] = None,
    ) -> None:
        """Record an unrecognized message event in RAM."""
        with self._lock:
            self._buffer_events[self.EVENT_UNRECOGNIZED] += 1
            self._buffer_bytes += 32
        self._check_and_flush_if_needed()

    def get_event_counts(self) -> Dict[str, int]:
        """Return total counts for each event category."""
        self.flush()
        counts = {
            self.EVENT_INLINE_KEYBOARD: self._buffer_events.get(self.EVENT_INLINE_KEYBOARD, 0),
            self.EVENT_COMMAND: self._buffer_events.get(self.EVENT_COMMAND, 0),
            self.EVENT_UNRECOGNIZED: self._buffer_events.get(self.EVENT_UNRECOGNIZED, 0),
        }
        # Derive counts from DB user commands if DB has more data (e.g. across processes)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT command FROM ux_user_commands;")
                db_commands = 0
                db_unrecognized = 0
                db_inline = 0
                for row in cursor.fetchall():
                    cmd = row["command"]
                    if cmd == "Неожиданный ввод":
                        db_unrecognized += 1
                    elif cmd.startswith("/"):
                        db_commands += 1
                    else:
                        db_inline += 1
                counts[self.EVENT_COMMAND] = max(counts[self.EVENT_COMMAND], db_commands)
                counts[self.EVENT_UNRECOGNIZED] = max(counts[self.EVENT_UNRECOGNIZED], db_unrecognized)
                counts[self.EVENT_INLINE_KEYBOARD] = max(counts[self.EVENT_INLINE_KEYBOARD], db_inline)
        except Exception as e:
            logger.error(f"Error reading event counts: {e}", exc_info=True)
        counts["total_events"] = sum(counts.values())
        return counts

    def get_menu_button_counts(self) -> List[Dict[str, Any]]:
        """Return click counts for each of the basic inline buttons of the menu."""
        self.flush()
        db_command_counts: Dict[str, int] = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT command, COUNT(*) AS cnt FROM ux_user_commands GROUP BY command;")
                for row in cursor.fetchall():
                    db_command_counts[row["command"]] = int(row["cnt"])
        except Exception as e:
            logger.error(f"Error fetching menu button counts from DB: {e}", exc_info=True)

        results: List[Dict[str, Any]] = []
        with self._lock:
            for spec in self.MENU_INLINE_BUTTON_SPECS:
                btn_name = spec["name"]
                callback = spec["callback"]
                aliases = spec.get("aliases", [callback, btn_name])

                # Total from RAM buffer
                buffer_count = 0
                for alias in aliases:
                    buffer_count = max(buffer_count, self._buffer_inline_buttons.get(alias, 0))

                # Total from DB
                db_count = 0
                for alias in aliases:
                    if alias in db_command_counts:
                        db_count += db_command_counts[alias]

                total_count = max(buffer_count, db_count)
                results.append({
                    "button": btn_name,
                    "callback": callback,
                    "count": total_count,
                })

        return results

    def get_menu_buttons_dict(self) -> Dict[str, int]:
        """Return mapping of basic menu button callback to its click count."""
        return {item["callback"]: item["count"] for item in self.get_menu_button_counts()}

    def get_text_command_counts(self) -> List[Dict[str, Any]]:
        """Return execution counts for each of the text commands."""
        self.flush()
        db_command_counts: Dict[str, int] = {}
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT command, COUNT(*) AS cnt FROM ux_user_commands GROUP BY command;")
                for row in cursor.fetchall():
                    db_command_counts[row["command"].lower()] = int(row["cnt"])
        except Exception as e:
            logger.error(f"Error fetching text command counts from DB: {e}", exc_info=True)

        results: List[Dict[str, Any]] = []
        matched_db_commands = set()

        with self._lock:
            for spec in self.BASIC_TEXT_COMMAND_SPECS:
                cmd = spec["command"]
                desc = spec["description"]
                aliases = [a.lower() for a in spec.get("aliases", [cmd])]

                # Total from RAM buffer
                buffer_count = 0
                for alias in aliases:
                    buffer_count = max(buffer_count, self._buffer_text_commands.get(alias, 0))

                # Total from DB
                db_count = 0
                for alias in aliases:
                    if alias in db_command_counts:
                        db_count += db_command_counts[alias]
                        matched_db_commands.add(alias)

                total_count = max(buffer_count, db_count)
                results.append({
                    "command": cmd,
                    "description": desc,
                    "count": total_count,
                })

            # Check if there are other commands in DB or buffer starting with '/'
            other_cmds: Dict[str, int] = {}
            for k, v in self._buffer_text_commands.items():
                if k.startswith("/") and k not in [s["command"] for s in self.BASIC_TEXT_COMMAND_SPECS]:
                    other_cmds[k] = max(other_cmds.get(k, 0), v)
            for k, v in db_command_counts.items():
                if k.startswith("/") and k not in matched_db_commands:
                    other_cmds[k] = max(other_cmds.get(k, 0), v)

            for extra_cmd, cnt in sorted(other_cmds.items()):
                results.append({
                    "command": extra_cmd,
                    "description": "Дополнительная команда",
                    "count": cnt,
                })

        return results

    def get_text_commands_dict(self) -> Dict[str, int]:
        """Return mapping of text command string to its execution count."""
        return {item["command"]: item["count"] for item in self.get_text_command_counts()}

    def get_user_stats(self) -> Dict[str, int]:
        """Return aggregate statistics across users without storing personal data."""
        self.flush()
        total_users = len(self._buffer_chats)
        total_chats = sum(self._buffer_chats.values())
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(DISTINCT user_id) AS db_users FROM ux_user_commands;")
                row = cursor.fetchone()
                if row and row["db_users"]:
                    total_users = max(total_users, int(row["db_users"]))

                cursor.execute(
                    """
                    SELECT COUNT(*) AS start_chats
                    FROM ux_user_commands
                    WHERE command IN ('/start', 'start');
                    """
                )
                start_row = cursor.fetchone()
                if start_row and start_row["start_chats"]:
                    total_chats = max(total_chats, int(start_row["start_chats"]))
                total_chats = max(total_chats, total_users)
        except Exception as e:
            logger.error(f"Error reading user stats: {e}", exc_info=True)
        return {"total_users": total_users, "total_chats": total_chats}

    def get_generalized_user_paths(self, limit: Optional[int] = 50) -> List[Dict[str, Any]]:
        """Return aggregated user command sequences (paths) with occurrence counts."""
        self.flush()
        paths: List[str] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT user_id, command
                    FROM ux_user_commands
                    ORDER BY user_id, id ASC;
                    """
                )
                user_commands: Dict[str, List[str]] = {}
                for row in cursor.fetchall():
                    uid = row["user_id"]
                    cmd = row["command"]
                    if uid not in user_commands:
                        user_commands[uid] = []
                    user_commands[uid].append(cmd)

                for cmds in user_commands.values():
                    current_path: List[str] = []
                    for cmd in cmds:
                        if cmd in ("/start", "start") and current_path:
                            paths.append(" ➔ ".join(current_path))
                            current_path = [cmd]
                        else:
                            current_path.append(cmd)
                    if current_path:
                        paths.append(" ➔ ".join(current_path))
        except Exception as e:
            logger.error(f"Error computing user paths: {e}", exc_info=True)

        if not paths:
            return []

        counter = Counter(paths)
        total_paths = len(paths)
        results = []
        for path_str, count in counter.most_common(limit):
            percentage = round((count / total_paths) * 100, 1) if total_paths > 0 else 0.0
            results.append({
                "path": path_str,
                "count": count,
                "percentage": percentage,
            })
        return results

    def get_wishlist_stats(self, limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """Return aggregate counts of wishlisted books by title and ISBN on demand.

        Never returns individual user wishlists or identifiers.
        """
        if not os.path.exists(self.wishlist_db_path):
            return []

        results = []
        try:
            conn = sqlite3.connect(self.wishlist_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    title,
                    COALESCE(isbn, '') AS isbn,
                    COUNT(*) AS count
                FROM wishlist_books
                GROUP BY title, COALESCE(isbn, '')
                ORDER BY count DESC, title ASC
                LIMIT ?;
                """,
                (limit or 100,),
            )
            for row in cursor.fetchall():
                results.append({
                    "title": row["title"],
                    "isbn": row["isbn"] or "—",
                    "count": int(row["count"]),
                })
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching wishlist statistics: {e}", exc_info=True)

        return results

    def get_full_summary(self) -> Dict[str, Any]:
        """Return a complete UX analytics summary dictionary."""
        self.flush()
        events = self.get_event_counts()
        users = self.get_user_stats()
        paths = self.get_generalized_user_paths()
        wishlist = self.get_wishlist_stats()
        menu_buttons = self.get_menu_button_counts()
        text_commands = self.get_text_command_counts()

        return {
            "events": events,
            "users": users,
            "paths": paths,
            "wishlist": wishlist,
            "menu_buttons": menu_buttons,
            "text_commands": text_commands,
        }

    def get_csv_reports(self) -> Dict[str, str]:
        """Generate individual CSV reports for events, buttons, commands, paths, and wishlist."""
        self.flush()
        summary = self.get_full_summary()
        reports: Dict[str, str] = {}

        # 1. events.csv: Event counters & general activity
        events_out = io.StringIO()
        events_writer = csv.writer(events_out)
        events_writer.writerow(["Event Type", "Count"])
        events_writer.writerow(["Inline Keyboard Clicks", summary["events"].get(self.EVENT_INLINE_KEYBOARD, 0)])
        events_writer.writerow(["Commands Executed", summary["events"].get(self.EVENT_COMMAND, 0)])
        events_writer.writerow(["Unrecognized Messages", summary["events"].get(self.EVENT_UNRECOGNIZED, 0)])
        events_writer.writerow(["Total Events", summary["events"].get("total_events", 0)])
        events_writer.writerow(["Total Unique Users", summary["users"].get("total_users", 0)])
        events_writer.writerow(["Total User Chats", summary["users"].get("total_chats", 0)])
        reports["events.csv"] = events_out.getvalue()

        # 2. buttons.csv: Specific inline menu buttons click counters
        buttons_out = io.StringIO()
        buttons_writer = csv.writer(buttons_out)
        buttons_writer.writerow(["Button Label", "Callback Action", "Clicks Count"])
        for btn in summary["menu_buttons"]:
            buttons_writer.writerow([btn["button"], btn["callback"], btn["count"]])
        reports["buttons.csv"] = buttons_out.getvalue()

        # 3. commands.csv: Text commands execution counters
        commands_out = io.StringIO()
        commands_writer = csv.writer(commands_out)
        commands_writer.writerow(["Command", "Description", "Invocations Count"])
        for cmd in summary["text_commands"]:
            commands_writer.writerow([cmd["command"], cmd["description"], cmd["count"]])
        reports["commands.csv"] = commands_out.getvalue()

        # 4. paths.csv: Generalized user navigation paths
        paths_out = io.StringIO()
        paths_writer = csv.writer(paths_out)
        paths_writer.writerow(["User Path", "User Count", "Percentage (%)"])
        for item in summary["paths"]:
            paths_writer.writerow([item["path"], item["count"], item["percentage"]])
        if not summary["paths"]:
            paths_writer.writerow(["No command sequences recorded yet", 0, 0.0])
        reports["paths.csv"] = paths_out.getvalue()

        # 5. wishlist.csv: Anonymized aggregate wishlist book statistics
        wishlist_out = io.StringIO()
        wishlist_writer = csv.writer(wishlist_out)
        wishlist_writer.writerow(["Book Title", "ISBN", "Wishlist Additions Count"])
        for item in summary["wishlist"]:
            wishlist_writer.writerow([item["title"], item["isbn"], item["count"]])
        if not summary["wishlist"]:
            wishlist_writer.writerow(["No books added to wishlist yet", "—", 0])
        reports["wishlist.csv"] = wishlist_out.getvalue()

        return reports

    def export_zip(
        self,
        output_target: Optional[Union[str, Path, Any]] = None,
    ) -> Union[str, bytes]:
        """Export all UX analytics reports into a zip archive containing separate CSV files.

        Contains:
          - events.csv: Event counters and user overview metrics
          - buttons.csv: Specific inline menu button click counts
          - commands.csv: Text command invocation counts
          - paths.csv: Generalized user paths (command sequences)
          - wishlist.csv: Aggregate wishlist book statistics

        Never includes raw or personal user identifiers.
        """
        reports = self.get_csv_reports()

        def _write_to_zip(stream: Any) -> None:
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as zf:
                for filename, content in reports.items():
                    zf.writestr(filename, content.encode("utf-8-sig"))

        if output_target is None:
            buf = io.BytesIO()
            _write_to_zip(buf)
            return buf.getvalue()

        if isinstance(output_target, (str, Path)):
            out_path = str(Path(output_target).resolve())
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                _write_to_zip(f)
            return out_path

        _write_to_zip(output_target)
        return ""

    def export_csv(self) -> str:
        """Export all aggregated UX data as CSV string without any user IDs."""
        self.flush()
        output = io.StringIO()
        writer = csv.writer(output)

        # Section 1: Overview
        summary = self.get_full_summary()
        writer.writerow(["=== UX Overview Metrics ==="])
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Unique Users", summary["users"]["total_users"]])
        writer.writerow(["Total User Chats", summary["users"]["total_chats"]])
        writer.writerow(["Total Events", summary["events"]["total_events"]])
        writer.writerow([])

        # Section 2: Event Counters
        writer.writerow(["=== Event Counters ==="])
        writer.writerow(["Event Type", "Count"])
        writer.writerow(["Inline Keyboard Clicks", summary["events"].get(self.EVENT_INLINE_KEYBOARD, 0)])
        writer.writerow(["Commands Executed", summary["events"].get(self.EVENT_COMMAND, 0)])
        writer.writerow(["Unrecognized Messages", summary["events"].get(self.EVENT_UNRECOGNIZED, 0)])
        writer.writerow([])

        # Section 3: Basic Menu Inline Buttons Counters
        writer.writerow(["=== Basic Menu Inline Buttons Counters ==="])
        writer.writerow(["Button Label", "Callback Action", "Clicks Count"])
        for btn in summary["menu_buttons"]:
            writer.writerow([btn["button"], btn["callback"], btn["count"]])
        writer.writerow([])

        # Section 4: Text Commands Counters
        writer.writerow(["=== Text Commands Counters ==="])
        writer.writerow(["Command", "Description", "Invocations Count"])
        for cmd in summary["text_commands"]:
            writer.writerow([cmd["command"], cmd["description"], cmd["count"]])
        writer.writerow([])

        # Section 5: Generalized User Paths
        writer.writerow(["=== Generalized User Paths (Command Sequences) ==="])
        writer.writerow(["User Path", "User Count", "Percentage (%)"])
        for item in summary["paths"]:
            writer.writerow([item["path"], item["count"], item["percentage"]])
        if not summary["paths"]:
            writer.writerow(["No command sequences recorded yet", 0, 0.0])
        writer.writerow([])

        # Section 6: Wishlisted Books Summary
        writer.writerow(["=== Wishlisted Books Statistics ==="])
        writer.writerow(["Book Title", "ISBN", "Wishlist Additions Count"])
        for item in summary["wishlist"]:
            writer.writerow([item["title"], item["isbn"], item["count"]])
        if not summary["wishlist"]:
            writer.writerow(["No books added to wishlist yet", "—", 0])

        return output.getvalue()


# Default singleton instance
default_analytics_service = AnalyticsService()
