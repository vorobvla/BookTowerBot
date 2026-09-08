"""Master classes module for BookTowerBot."""

from bot.masterclasses.keyboards import (
    MASTER_CLASSES_CALLBACK_MAP,
    get_master_class_details_keyboard,
    get_master_classes_inline_keyboard,
)

__all__ = [
    "MASTER_CLASSES_CALLBACK_MAP",
    "get_master_classes_inline_keyboard",
    "get_master_class_details_keyboard",
]
