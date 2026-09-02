"""Service for managing venue map uploads, past versions, and active map selection."""

from datetime import datetime
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple

from bot.content import MAP_DIR, MAP_PATH


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable units."""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    return f"{size_bytes / (1024 * 1024):.1f} МБ"


class AdminMapService:
    """Provides operations for uploading, versioning, selecting, and serving venue maps."""

    ALLOWED_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}

    def __init__(self, directory_path: Optional[str] = None):
        self.directory_path = directory_path or MAP_DIR
        os.makedirs(self.directory_path, exist_ok=True)
        self._staged_active_map: Optional[str] = None
        self._staged_deletions: Set[str] = set()
        self._has_pending_changes: bool = False

    @classmethod
    def validate_extension(cls, filename: str) -> str:
        """Validate that the file extension is supported."""
        base = os.path.basename(filename.strip())
        _, ext = os.path.splitext(base)
        ext = ext.lower()
        if not ext or ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(f"Неподдерживаемый формат изображения. Допустимые: {', '.join(sorted(cls.ALLOWED_EXTENSIONS))}")
        return ext

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize uploaded filename, keeping extension and safe characters."""
        base = os.path.basename(filename.strip())
        name, ext = os.path.splitext(base)
        ext = ext.lower()

        # Replace non-alphanumeric (except dashes, underscores) with underscore
        clean_name = re.sub(r"[^\w\s\.-]", "_", name, flags=re.UNICODE).strip()
        clean_name = re.sub(r"\s+", "_", clean_name)
        if not clean_name or clean_name.startswith("."):
            clean_name = f"map_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return f"{clean_name}{ext}"

    def _get_active_from_disk(self) -> Optional[str]:
        """Read currently active map filename from active_map.json or fallbacks."""
        meta_file = os.path.join(self.directory_path, "active_map.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    active_name = data.get("active_map")
                    if active_name and isinstance(active_name, str):
                        target_path = os.path.join(self.directory_path, active_name)
                        if os.path.exists(target_path):
                            return active_name
            except Exception:
                pass

        txt_file = os.path.join(self.directory_path, "active_map.txt")
        if os.path.exists(txt_file):
            try:
                with open(txt_file, "r", encoding="utf-8") as f:
                    active_name = f.read().strip()
                    if active_name:
                        target_path = os.path.join(self.directory_path, active_name)
                        if os.path.exists(target_path):
                            return active_name
            except Exception:
                pass

        # Check default map.png
        map_png = os.path.join(self.directory_path, "map.png")
        if os.path.exists(map_png):
            return "map.png"

        # Check any valid image files
        all_images = self._get_all_image_files_on_disk()
        if all_images:
            return all_images[0]

        return None

    def _get_all_image_files_on_disk(self) -> List[str]:
        """List all valid image files on disk sorted by modification time (newest first)."""
        if not os.path.exists(self.directory_path):
            return []

        files = []
        for fname in os.listdir(self.directory_path):
            if fname in ("active_map.json", "active_map.txt"):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in self.ALLOWED_EXTENSIONS:
                fpath = os.path.join(self.directory_path, fname)
                if os.path.isfile(fpath):
                    mtime = os.path.getmtime(fpath)
                    files.append((fname, mtime))

        files.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in files]

    def get_active_map(self) -> Optional[str]:
        """Return the currently active map filename (considering staged changes)."""
        if self._staged_active_map is not None:
            if self._staged_active_map not in self._staged_deletions:
                return self._staged_active_map

        active = self._get_active_from_disk()
        if active and active not in self._staged_deletions:
            return active

        # If disk active was deleted in staging, pick next available
        for fname in self._get_all_image_files_on_disk():
            if fname not in self._staged_deletions:
                return fname

        return None

    def get_active_map_path(self) -> Optional[str]:
        """Return the absolute path to the currently active map file."""
        active = self.get_active_map()
        if not active:
            return None
        return os.path.abspath(os.path.join(self.directory_path, active))

    def list_maps(self) -> List[Dict[str, Any]]:
        """List all available map versions with metadata, active status, and preview links."""
        active_filename = self.get_active_map()
        results = []

        for fname in self._get_all_image_files_on_disk():
            if fname in self._staged_deletions:
                continue

            fpath = os.path.join(self.directory_path, fname)
            stat = os.stat(fpath)
            dt = datetime.fromtimestamp(stat.st_mtime)
            is_active = (fname == active_filename)

            results.append({
                "filename": fname,
                "size_bytes": stat.st_size,
                "formatted_size": _format_file_size(stat.st_size),
                "modified_at": dt.strftime("%d.%m.%Y %H:%M"),
                "timestamp": stat.st_mtime,
                "is_active": is_active,
                "preview_url": f"/map/file/{fname}",
            })

        # Sort so active map is first, followed by newest files
        results.sort(key=lambda x: (not x["is_active"], -x["timestamp"]))
        return results

    def upload_map(
        self,
        filename: str,
        content: bytes,
        set_as_active: bool = True,
    ) -> str:
        """Upload a new map version, save to assets/map directory, and optionally set as active."""
        if not content or len(content) == 0:
            raise ValueError("Файл карты не может быть пустым")

        self.validate_extension(filename)
        clean_name = self.sanitize_filename(filename)

        # Ensure unique filename to prevent accidental overwrite of past versions
        target_path = os.path.join(self.directory_path, clean_name)
        if os.path.exists(target_path):
            stem, ext_part = os.path.splitext(clean_name)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_name = f"{stem}_{timestamp_str}{ext_part}"
            target_path = os.path.join(self.directory_path, clean_name)

        with open(target_path, "wb") as f:
            f.write(content)

        self._staged_deletions.discard(clean_name)

        if set_as_active:
            self.select_map(clean_name)

        return clean_name

    def select_map(self, filename: str) -> None:
        """Select an existing map version from past versions as the active map."""
        clean_name = os.path.basename(filename.strip())
        target_path = os.path.join(self.directory_path, clean_name)

        if not os.path.exists(target_path) or clean_name in self._staged_deletions:
            raise ValueError(f"Файл карты '{clean_name}' не найден среди версий")

        self._staged_active_map = clean_name
        self._has_pending_changes = True

    def delete_map(self, filename: str) -> bool:
        """Delete a past map version (cannot delete currently active map)."""
        clean_name = os.path.basename(filename.strip())
        active_filename = self.get_active_map()

        if clean_name == active_filename:
            raise ValueError("Нельзя удалить активную карту ярмарки")

        target_path = os.path.join(self.directory_path, clean_name)
        if not os.path.exists(target_path):
            raise ValueError(f"Файл карты '{clean_name}' не найден")

        self._staged_deletions.add(clean_name)
        self._has_pending_changes = True
        return True

    def get_map_file_content(self, filename: str) -> Optional[Tuple[bytes, str]]:
        """Safely read map file content and return (bytes, mime_type)."""
        clean_name = os.path.basename(filename.strip())
        target_path = os.path.join(self.directory_path, clean_name)

        if not os.path.exists(target_path) or not os.path.isfile(target_path):
            return None

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(target_path)
        if not mime_type:
            ext = os.path.splitext(clean_name)[1].lower()
            if ext == ".png":
                mime_type = "image/png"
            elif ext in (".jpg", ".jpeg"):
                mime_type = "image/jpeg"
            elif ext == ".webp":
                mime_type = "image/webp"
            elif ext == ".svg":
                mime_type = "image/svg+xml"
            elif ext == ".gif":
                mime_type = "image/gif"
            else:
                mime_type = "application/octet-stream"

        with open(target_path, "rb") as f:
            content = f.read()

        return content, mime_type

    def save_to_disk(self) -> None:
        """Commit staged active map and deletions to disk and invalidate bot map cache."""
        # Process deletions
        for fname in list(self._staged_deletions):
            fpath = os.path.join(self.directory_path, fname)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
        self._staged_deletions.clear()

        # Process active map selection
        active_to_save = self._staged_active_map or self._get_active_from_disk()
        if active_to_save:
            meta_file = os.path.join(self.directory_path, "active_map.json")
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump({"active_map": active_to_save}, f, ensure_ascii=False, indent=2)
                f.write("\n")

        # Invalidate Bot Map Cache
        try:
            from bot.sections.map import Map
            Map.clear_cache()
        except Exception:
            pass

        self._staged_active_map = None
        self._has_pending_changes = False

    commit = save_to_disk

    def discard_changes(self) -> None:
        """Discard in-memory staged active map changes and deletions."""
        self._staged_active_map = None
        self._staged_deletions.clear()
        self._has_pending_changes = False

    rollback = discard_changes

    def has_pending_changes(self) -> bool:
        """Return True if there are uncommitted map changes."""
        return self._has_pending_changes
