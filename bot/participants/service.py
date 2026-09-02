"""Service for loading and querying participants from JSON asset files."""

import json
import os
from typing import Any, List, Optional

from bot.content import PARTICIPANTS_PATH
from bot.participants.participant import Participant


def sort_participant_key(participant: Any) -> tuple:
    """Sort key helper: purely numeric stands come first in numeric order, followed by alphanumeric stands."""
    if hasattr(participant, "stand"):
        stand_val = participant.stand
        name_val = participant.name
    elif isinstance(participant, dict):
        stand_val = participant.get("stand", "")
        name_val = participant.get("name", "")
    else:
        stand_val = str(participant)
        name_val = ""

    stand_str = str(stand_val).strip()
    name_str = str(name_val).strip().lower()

    try:
        num = int(stand_str)
        return (0, num, stand_str.lower(), name_str)
    except (ValueError, TypeError):
        return (1, float("inf"), stand_str.lower(), name_str)


class ParticipantsService:
    """Service managing participant data loading, retrieval, sorting, and formatting."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or PARTICIPANTS_PATH

    def get_participants(self) -> List[Participant]:
        """Load, parse, and return all participants sorted by stand number."""
        if not os.path.exists(self.file_path):
            return []

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_participants = data.get("participants") if isinstance(data, dict) else []
            if not isinstance(raw_participants, list):
                return []

            participants = []
            for item in raw_participants:
                if isinstance(item, dict):
                    participants.append(Participant.from_dict(item))

            participants.sort(key=sort_participant_key)
            return participants
        except Exception:
            return []

    def get_participant_by_index(self, index: int) -> Optional[Participant]:
        """Get participant by sorted list index."""
        participants = self.get_participants()
        if 0 <= index < len(participants):
            return participants[index]
        return None

    def get_participant(self, query: str) -> Optional[Participant]:
        """Find participant by stand or name or index."""
        participants = self.get_participants()
        clean = query.strip().lower()

        # Try index if purely numeric query
        try:
            idx = int(clean)
            if 0 <= idx < len(participants):
                return participants[idx]
        except ValueError:
            pass

        # Try exact stand match
        for p in participants:
            if p.stand.strip().lower() == clean:
                return p

        # Try exact name match
        for p in participants:
            if p.name.strip().lower() == clean:
                return p

        # Try substring name match
        for p in participants:
            if clean in p.name.strip().lower():
                return p

        return None

    def format_participant_details(self, query_or_index: Any) -> str:
        """Format full participant information as Markdown."""
        participant = None
        if isinstance(query_or_index, Participant):
            participant = query_or_index
        elif isinstance(query_or_index, int):
            participant = self.get_participant_by_index(query_or_index)
        elif isinstance(query_or_index, str):
            # Check if it's integer index
            if query_or_index.isdigit():
                participant = self.get_participant_by_index(int(query_or_index))
            if not participant:
                participant = self.get_participant(query_or_index)

        if not participant:
            return "👥 *Участник*\n\nИнформация об участнике не найдена."

        return participant.format_markdown()
