"""Modular sections package for BookTowerBot."""

from bot.sections.base import BaseSection
from bot.sections.children_activity import ChildrenActivity, ChildrenActivitySection
from bot.sections.help import Help, HelpSection
from bot.sections.map import Map, MapSection
from bot.sections.master_classes import MasterClasses, MasterClassesSection
from bot.sections.participants import Participants, ParticipantsSection
from bot.sections.recommendations import Recommendations, RecommendationsSection
from bot.sections.registry import SectionRegistry, default_registry
from bot.sections.start import Start, StartSection
from bot.sections.timetable import Timetable, TimetableSection
from bot.sections.wishlist import Wishlist, WishlistSection

__all__ = [
    "BaseSection",
    "Start",
    "StartSection",
    "Help",
    "HelpSection",
    "Map",
    "MapSection",
    "Timetable",
    "TimetableSection",
    "ChildrenActivity",
    "ChildrenActivitySection",
    "MasterClasses",
    "MasterClassesSection",
    "Recommendations",
    "RecommendationsSection",
    "Participants",
    "ParticipantsSection",
    "Wishlist",
    "WishlistSection",
    "SectionRegistry",
    "default_registry",
]
