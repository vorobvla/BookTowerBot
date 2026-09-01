"""Registry coordinating sections for command, callback, and text routing."""

from typing import List, Optional

from bot.sections.base import BaseSection
from bot.sections.help import Help
from bot.sections.map import Map
from bot.sections.recommendations import Recommendations
from bot.sections.start import Start
from bot.sections.timetable import Timetable


class SectionRegistry:
    """Registry coordinating sections for command, callback, and text routing."""

    def __init__(self, sections: Optional[List[BaseSection]] = None):
        self.sections: List[BaseSection] = sections or [
            Start(),
            Help(),
            Map(),
            Timetable(),
            Recommendations(),
        ]

    def find_by_command(self, command: str) -> Optional[BaseSection]:
        """Find matching section for command."""
        for section in self.sections:
            if section.matches_command(command):
                return section
        return None

    def find_by_callback(self, callback_data: str) -> Optional[BaseSection]:
        """Find matching section for callback query data."""
        for section in self.sections:
            if section.matches_callback(callback_data):
                return section
        return None

    def find_by_text(self, text: str) -> Optional[BaseSection]:
        """Find matching section for text message / button / alias."""
        for section in self.sections:
            if section.matches_text(text):
                return section
        return None


# Default shared registry instance
default_registry = SectionRegistry()
