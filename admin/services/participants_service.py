"""Service for managing participants data in the admin console."""

import copy
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bot.content import PARTICIPANTS_PATH
from bot.participants.participant import Participant
from bot.participants.service import sort_participant_key

# URL regex matching web URLs with or without protocol (http:// or https://)
URL_REGEX = re.compile(
    r"^(?:https?:\/\/)?"
    r"(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}|localhost|\d{1,3}(?:\.\d{1,3}){3})"
    r"(?::\d{1,5})?"
    r"(?:[/?#]\S*)?$",
    re.IGNORECASE,
)


class AdminParticipantsService:
    """Provides CRUD operations and validation for participants (participants.json)."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or PARTICIPANTS_PATH
        self._staged_data: Optional[Dict[str, Any]] = None
        self._has_pending_changes: bool = False

    def load_data(self) -> Dict[str, Any]:
        """Load participants data from staged in-memory cache or disk."""
        if self._staged_data is not None:
            return copy.deepcopy(self._staged_data)

        if not os.path.exists(self.file_path):
            return {"participants": []}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"participants": []}
            if "participants" not in data or not isinstance(data["participants"], list):
                data["participants"] = []
            return data
        except Exception:
            return {"participants": []}

    def save_data(self, data: Dict[str, Any]) -> None:
        """Stage participants data in-memory without immediately writing to disk."""
        self._staged_data = copy.deepcopy(data)
        self._has_pending_changes = True

    def save_to_disk(self) -> None:
        """Commit staged in-memory data to the JSON asset file on disk."""
        data = self.load_data()
        # Sort participants by stand before saving
        raw_list = data.get("participants", [])
        if isinstance(raw_list, list):
            raw_list.sort(key=sort_participant_key)
            data["participants"] = raw_list

        os.makedirs(os.path.dirname(os.path.abspath(self.file_path)), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        self._staged_data = None
        self._has_pending_changes = False

    commit = save_to_disk

    def discard_changes(self) -> None:
        """Discard in-memory changes and reload original data from disk."""
        self._staged_data = None
        self._has_pending_changes = False

    rollback = discard_changes

    def has_pending_changes(self) -> bool:
        """Return whether there are uncommitted changes."""
        return self._has_pending_changes

    def get_participants(self) -> List[Participant]:
        """Return all participants sorted by stand number."""
        data = self.load_data()
        raw_parts = data.get("participants", [])
        participants = [Participant.from_dict(item) for item in raw_parts if isinstance(item, dict)]
        participants.sort(key=sort_participant_key)
        return participants

    def get_participant_dict_list(self) -> List[Dict[str, Any]]:
        """Return sorted list of participant dictionaries."""
        return [p.to_dict() for p in self.get_participants()]

    def add_participant(
        self,
        name: str,
        stand: str,
        link: str = "",
        description: str = "",
    ) -> None:
        """Add a new participant validating mandatory fields."""
        part_dict = self._validate_and_build_participant(
            name=name,
            stand=stand,
            link=link,
            description=description,
        )

        data = self.load_data()
        raw_parts = data.setdefault("participants", [])
        raw_parts.append(part_dict)
        raw_parts.sort(key=sort_participant_key)
        self.save_data(data)

    def update_participant(
        self,
        participant_index: int,
        name: str,
        stand: str,
        link: str = "",
        description: str = "",
    ) -> None:
        """Update an existing participant at sorted index."""
        part_dict = self._validate_and_build_participant(
            name=name,
            stand=stand,
            link=link,
            description=description,
        )

        data = self.load_data()
        raw_parts = data.get("participants", [])
        raw_parts.sort(key=sort_participant_key)

        if not (0 <= participant_index < len(raw_parts)):
            raise IndexError("Participant index out of range")

        raw_parts[participant_index] = part_dict
        raw_parts.sort(key=sort_participant_key)
        data["participants"] = raw_parts
        self.save_data(data)

    def delete_participant(self, participant_index: int) -> None:
        """Delete a participant by index in sorted list."""
        data = self.load_data()
        raw_parts = data.get("participants", [])
        raw_parts.sort(key=sort_participant_key)

        if not (0 <= participant_index < len(raw_parts)):
            raise IndexError("Participant index out of range")

        raw_parts.pop(participant_index)
        data["participants"] = raw_parts
        self.save_data(data)

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Validate whether the URL has a valid format with or without protocol."""
        if not url:
            return False
        return bool(URL_REGEX.match(url.strip()))

    def _validate_and_build_participant(
        self,
        name: str,
        stand: str,
        link: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        """Validate mandatory fields and return standard dictionary."""
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Field 'name' is mandatory and cannot be empty")

        clean_stand = (stand or "").strip()
        if not clean_stand:
            raise ValueError("Field 'stand' is mandatory and cannot be empty")

        clean_link = (link or "").strip()
        if clean_link and not self._is_valid_url(clean_link):
            raise ValueError("Field 'link' must be a valid URL")

        clean_description = (description or "").strip()

        return {
            "name": clean_name,
            "stand": clean_stand,
            "description": clean_description,
            "link": clean_link,
        }
