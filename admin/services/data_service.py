"""Service for exporting and importing BookTower asset data in zip archives."""

import io
import json
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Sequence, Set, Tuple, Union

from bot.content import ASSETS_PATH

logger = logging.getLogger(__name__)

VALID_COMPONENTS: Tuple[str, ...] = ("map", "participants", "recs", "timetables")
ALLOWED_MAP_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}
IGNORE_FILENAMES: Set[str] = {".ds_store", "thumbs.db", "desktop.ini", "__macosx"}


class AdminDataTransferService:
    """Handles archiving (export) and structure validation & replacement (import) for assets."""

    def __init__(self, assets_path: Optional[str] = None):
        self.assets_path = str(Path(assets_path or ASSETS_PATH).resolve())

    def export_assets_to_zip(
        self,
        output_target: Optional[Union[str, Path, BinaryIO]] = None,
    ) -> Union[str, bytes]:
        """Export all assets into a zip file respecting their original directory structure.

        Args:
            output_target: Optional file path or binary stream. If None, returns zip bytes.

        Returns:
            The output file path (if path provided) or raw bytes of the zip archive.
        """
        os.makedirs(self.assets_path, exist_ok=True)

        if output_target is None:
            buffer = io.BytesIO()
            self._write_assets_to_zip(buffer)
            return buffer.getvalue()

        if isinstance(output_target, (str, Path)):
            out_path = str(Path(output_target).resolve())
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                self._write_assets_to_zip(f)
            return out_path

        # Assume file-like binary stream
        self._write_assets_to_zip(output_target)
        return ""

    def _write_assets_to_zip(self, file_or_buffer: BinaryIO) -> None:
        """Write all assets contents (excluding databases) into a zip archive stream."""
        with zipfile.ZipFile(file_or_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(self.assets_path):
                # Filter out hidden or cache directories, as well as db directory
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d.lower() != "__pycache__"
                    and d.lower() != "db"
                ]
                rel_root = os.path.relpath(root, self.assets_path)
                root_parts = rel_root.split(os.sep) if rel_root != "." else []
                if "db" in [p.lower() for p in root_parts]:
                    continue
                for file in files:
                    if file.startswith(".") or file.lower() in IGNORE_FILENAMES:
                        continue
                    abs_file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_file_path, self.assets_path)
                    # Use forward slashes for zip internal paths
                    zip_arcname = rel_path.replace(os.sep, "/")
                    zf.write(abs_file_path, arcname=zip_arcname)

    def _normalize_components(
        self,
        component: Optional[Union[str, Sequence[str]]] = None,
        components: Optional[Union[str, Sequence[str]]] = None,
    ) -> Optional[List[str]]:
        """Normalize component or components into a list of valid component names or None (representing all)."""
        raw = components if components is not None else component
        if raw is None:
            return None

        if isinstance(raw, str):
            clean = raw.strip().lower()
            if clean in ("all", "*", ""):
                return None
            parts = [p.strip().lower() for p in clean.split(",") if p.strip()]
        elif isinstance(raw, (list, tuple, set)):
            parts = []
            for item in raw:
                if isinstance(item, str):
                    for sub in item.split(","):
                        if sub.strip():
                            parts.append(sub.strip().lower())
                elif item is not None:
                    parts.append(str(item).strip().lower())
        else:
            parts = [str(raw).strip().lower()]

        if not parts or "all" in parts or "*" in parts:
            return None

        for p in parts:
            if p not in VALID_COMPONENTS:
                raise ValueError(
                    f"Неизвестный компонент '{p}'. Допустимые: {', '.join(VALID_COMPONENTS)} или 'all'"
                )

        unique_parts = [c for c in VALID_COMPONENTS if c in parts]
        return unique_parts if unique_parts else None

    def validate_zip_structure(
        self,
        zip_source: Union[str, Path, bytes, BinaryIO],
        component: Optional[Union[str, Sequence[str]]] = None,
        components: Optional[Union[str, Sequence[str]]] = None,
    ) -> Dict[str, Any]:
        """Validate zip archive structure and contents against expected BookTower assets format.

        Args:
            zip_source: Path to zip file, raw bytes, or a binary file-like object.
            component: Optional component filter or list of components.
            components: Optional alias for component filter(s).

        Returns:
            A dict with validation details:
                - 'is_valid': bool
                - 'prefix': str (common prefix stripped, e.g. 'assets/')
                - 'components_found': list of detected components
                - 'files_by_component': dict mapping component name to normalized zip file paths
                - 'target_components': list of target component names or None

        Raises:
            ValueError: If the zip archive is corrupt, insecure, or structure does not match.
        """
        target_components = self._normalize_components(component=component, components=components)

        try:
            if isinstance(zip_source, bytes):
                zf = zipfile.ZipFile(io.BytesIO(zip_source), "r")
            elif isinstance(zip_source, (str, Path)):
                zf = zipfile.ZipFile(str(zip_source), "r")
            else:
                zf = zipfile.ZipFile(zip_source, "r")
        except Exception as e:
            raise ValueError(f"Некорректный ZIP-архив: {e}")

        with zf:
            infolist = zf.infolist()
            if not infolist:
                raise ValueError("ZIP-архив пуст")

            # Collect all normalized non-directory, non-ignored paths
            raw_names: List[str] = []
            for info in infolist:
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/").strip("/")
                parts = name.split("/")
                # Security check for path traversal
                if ".." in parts or any(p.startswith("/") for p in parts):
                    raise ValueError(f"Обнаружен небезопасный путь в архиве: {info.filename}")
                # Skip OS metadata
                if any(p.startswith(".") or p.lower() in IGNORE_FILENAMES or p.lower() == "__macosx" for p in parts):
                    continue
                raw_names.append(name)

            if not raw_names:
                raise ValueError("ZIP-архив не содержит файлов данных")

            # Detect common root directory prefix if present (e.g. 'assets/db/...' or 'booktower/assets/db/...')
            prefix = self._detect_common_prefix(raw_names)
            normalized_files: List[Tuple[str, str]] = []  # (original_zip_name, normalized_rel_name)

            for original_name in raw_names:
                norm = original_name[len(prefix):] if prefix and original_name.startswith(prefix) else original_name
                norm = norm.strip("/")
                if norm:
                    normalized_files.append((original_name, norm))

            # Group files by component
            files_by_comp: Dict[str, List[Tuple[str, str]]] = {c: [] for c in VALID_COMPONENTS}
            unrecognized_files: List[str] = []

            for orig, norm in normalized_files:
                parts = norm.split("/")
                top_dir = parts[0].lower()
                if top_dir in VALID_COMPONENTS:
                    files_by_comp[top_dir].append((orig, norm))
                else:
                    unrecognized_files.append(norm)

            components_found = [c for c, f in files_by_comp.items() if len(f) > 0]

            if not components_found:
                raise ValueError(
                    f"Структура ZIP-архива не соответствует структуре ассетов. "
                    f"Ожидаются разделы: {', '.join(VALID_COMPONENTS)}"
                )

            # If specific component(s) requested, ensure each is present
            if target_components is not None:
                for comp_req in target_components:
                    if comp_req not in components_found or len(files_by_comp[comp_req]) == 0:
                        raise ValueError(
                            f"В архиве отсутствуют файлы для выбранного раздела '{comp_req}'"
                        )
            else:
                # In full import, reject if there are unrecognized root directories or files
                if unrecognized_files:
                    logger.warning("Unrecognized files in asset zip archive: %s", unrecognized_files)

            # Deep format validation of component files
            self._validate_component_contents(zf, files_by_comp, target_components)

            return {
                "is_valid": True,
                "prefix": prefix,
                "components_found": components_found,
                "files_by_component": files_by_comp,
                "target_component": ", ".join(target_components) if target_components else "all",
                "target_components": target_components,
            }

    def _detect_common_prefix(self, file_paths: List[str]) -> str:
        """Detect if all paths are wrapped in a root folder (like 'assets/')."""
        if not file_paths:
            return ""

        first_parts = [p.split("/")[0] for p in file_paths if "/" in p]
        if first_parts and len(first_parts) == len(file_paths):
            common_first = first_parts[0]
            if all(p == common_first for p in first_parts):
                # If the common root is NOT one of the valid components, it's a wrapper directory (e.g. 'assets')
                if common_first.lower() not in VALID_COMPONENTS:
                    return f"{common_first}/"

        return ""

    def _validate_component_contents(
        self,
        zf: zipfile.ZipFile,
        files_by_comp: Dict[str, List[Tuple[str, str]]],
        target_components: Optional[Union[str, Sequence[str]]] = None,
    ) -> None:
        """Inspect contents of JSON / data files in the zip to ensure valid structure."""
        if target_components is None:
            components_to_check = VALID_COMPONENTS
        elif isinstance(target_components, str):
            components_to_check = (target_components,)
        else:
            components_to_check = tuple(target_components)

        for comp in components_to_check:
            comp_files = files_by_comp.get(comp, [])
            if not comp_files:
                continue

            if comp == "recs":
                # Expect recs/recs.json
                recs_found = False
                for orig, norm in comp_files:
                    if norm.lower() == "recs/recs.json" or norm.lower().endswith(".json"):
                        try:
                            content = zf.read(orig).decode("utf-8")
                            data = json.loads(content)
                            if not isinstance(data, dict) or "recs" not in data or not isinstance(data["recs"], list):
                                raise ValueError("Файл recs.json должен содержать JSON-объект со списком 'recs'")
                            recs_found = True
                        except json.JSONDecodeError as e:
                            raise ValueError(f"Ошибка в формате JSON файла {norm}: {e}")
                if not recs_found:
                    raise ValueError("Раздел 'recs' не содержит корректного файла recs.json")

            elif comp == "participants":
                # Expect participants/participants.json
                parts_found = False
                for orig, norm in comp_files:
                    if norm.lower() == "participants/participants.json" or norm.lower().endswith(".json"):
                        try:
                            content = zf.read(orig).decode("utf-8")
                            data = json.loads(content)
                            if not isinstance(data, dict) or "participants" not in data or not isinstance(data["participants"], list):
                                raise ValueError("Файл participants.json должен содержать JSON-объект со списком 'participants'")
                            parts_found = True
                        except json.JSONDecodeError as e:
                            raise ValueError(f"Ошибка в формате JSON файла {norm}: {e}")
                if not parts_found:
                    raise ValueError("Раздел 'participants' не содержит корректного файла participants.json")

            elif comp == "timetables":
                # Expect timetables/*.json
                tt_found = False
                for orig, norm in comp_files:
                    if norm.lower().endswith(".json"):
                        try:
                            content = zf.read(orig).decode("utf-8")
                            data = json.loads(content)
                            if not isinstance(data, dict) or "date" not in data or "events" not in data:
                                raise ValueError(f"Файл {norm} должен содержать поля 'date' и 'events'")
                            tt_found = True
                        except json.JSONDecodeError as e:
                            raise ValueError(f"Ошибка в формате JSON расписания {norm}: {e}")
                if not tt_found:
                    raise ValueError("Раздел 'timetables' не содержит файлов расписаний (.json)")

            elif comp == "map":
                # Expect at least one map file (.png, .jpg, active_map.json, etc.)
                has_valid_map_file = False
                for orig, norm in comp_files:
                    ext = os.path.splitext(norm)[1].lower()
                    fname = os.path.basename(norm).lower()
                    if ext in ALLOWED_MAP_EXTENSIONS or fname in ("active_map.json", "active_map.txt"):
                        has_valid_map_file = True
                        break
                if not has_valid_map_file:
                    raise ValueError("Раздел 'map' не содержит поддерживаемых файлов карты (PNG, JPG, SVG и т.д.)")

    def import_assets_from_zip(
        self,
        zip_source: Union[str, Path, bytes, BinaryIO],
        component: Optional[Union[str, Sequence[str]]] = None,
        components: Optional[Union[str, Sequence[str]]] = None,
    ) -> Dict[str, Any]:
        """Validate and import assets from a zip archive, replacing existing assets.

        Args:
            zip_source: Zip file path, bytes, or file stream.
            component: Target component(s) ('all', 'map', 'participants', 'recs', 'timetables').
            components: Optional alias for component(s).

        Returns:
            A dict with status and summary of imported files.

        Raises:
            ValueError: If structure does not match or validation fails.
        """
        validation = self.validate_zip_structure(zip_source, component=component, components=components)
        target_components = validation["target_components"]
        target_component_str = validation["target_component"]
        files_by_comp = validation["files_by_component"]

        # Re-open zip archive for extraction
        if isinstance(zip_source, bytes):
            zf = zipfile.ZipFile(io.BytesIO(zip_source), "r")
        elif isinstance(zip_source, (str, Path)):
            zf = zipfile.ZipFile(str(zip_source), "r")
        else:
            if hasattr(zip_source, "seek"):
                zip_source.seek(0)
            zf = zipfile.ZipFile(zip_source, "r")

        components_to_replace = target_components if target_components else validation["components_found"]

        with zf:
            with tempfile.TemporaryDirectory() as temp_dir:
                extracted_files_count = 0
                imported_components: List[str] = []

                for comp in components_to_replace:
                    comp_files = files_by_comp.get(comp, [])
                    if not comp_files:
                        continue

                    # Extract to temp dir first
                    temp_comp_dir = os.path.join(temp_dir, comp)
                    os.makedirs(temp_comp_dir, exist_ok=True)

                    for orig_name, norm_name in comp_files:
                        # norm_name is e.g. "timetables/10092026.json"
                        # strip the component folder itself for relative extraction
                        rel_in_comp = norm_name[len(comp):].lstrip("/\\")
                        dest_file_path = os.path.join(temp_comp_dir, rel_in_comp)
                        os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)

                        with open(dest_file_path, "wb") as f_out:
                            f_out.write(zf.read(orig_name))
                        extracted_files_count += 1

                    # Atomically replace target component folder in assets
                    target_comp_dir = os.path.join(self.assets_path, comp)
                    if os.path.exists(target_comp_dir):
                        shutil.rmtree(target_comp_dir)
                    os.makedirs(os.path.dirname(target_comp_dir), exist_ok=True)
                    shutil.copytree(temp_comp_dir, target_comp_dir)
                    imported_components.append(comp)

                logger.info(
                    "Successfully imported %d files into assets (components: %s)",
                    extracted_files_count,
                    imported_components,
                )

                return {
                    "status": "ok",
                    "component": target_component_str or "all",
                    "imported_components": imported_components,
                    "files_count": extracted_files_count,
                }
