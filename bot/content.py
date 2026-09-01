"""Content and text templates for BookTowerBot."""

import os
from pathlib import Path

ASSETS_PATH = os.getenv(
    "ASSETS_PATH",
    str(Path(__file__).parent.parent / "assets")
    if (Path(__file__).parent.parent / "assets").exists()
    else str(Path(__file__).parent.parent / ".assets"),
)

MAP_PATH = os.path.join(ASSETS_PATH, "maps", "map.png")
TIMETABLES_PATH = os.path.join(ASSETS_PATH, "timetables")
RECS_PATH = os.path.join(ASSETS_PATH, "recs", "recs.json")

START_MESSAGE = (
    "📚 *Добро пожаловать в BookTowerBot!*\n\n"
    "Я помогу вам сориентироваться на мероприятии и провести время с максимальной пользой.\n\n"
    "Вы можете использовать кнопки меню ниже или вводить команды напрямую:\n"
    "• 🏢 /map — Посмотреть карту площадки и схему павильонов\n"
    "• 📅 /timetables — Расписание выступлений и автограф-сессий\n"
    "• 📚 /recommendations — Рекомендации книг и стендов\n"
    "• ℹ️ /help — Справка и помощь\n\n"
    "Пожалуйста, выберите интересующий раздел:"
)

HELP_MESSAGE = (
    "ℹ️ *Справка и навигация BookTowerBot*\n\n"
    "Доступные команды:\n"
    "• `/start` — Запустить или перезапустить бота и открыть главное меню\n"
    "• `/map` — Показать карту площадки и схему павильонов\n"
    "• `/timetables` — Расписание событий и мероприятий\n"
    "• `/recommendations` или `/recs` — Подборка рекомендаций\n"
    "• `/help` — Показать это справочное сообщение\n\n"
    "Вы также можете в любой момент воспользоваться кнопками меню."
)

MAP_MESSAGE = (
    ""
)

TIMETABLE_MESSAGE = (
    "📅 *Расписание мероприятий*\n\n"
    "Пожалуйста, выберите интересующую вас дату:"
)

RECOMMENDATIONS_MESSAGE = (
    "⭐ *Рекомендации книг и стендов*\n\n"
    "Пожалуйста, выберите интересующую вас подборку:"
)

UNKNOWN_COMMAND_MESSAGE = (
    "Команда не распознана. Пожалуйста, используйте кнопки меню ниже "
    "или введите `/help`, чтобы посмотреть все доступные опции."
)

# Button label constants
BTN_MAP = "🏢 План ярмарки"
BTN_TIMETABLE = "📅 Расписание"
BTN_RECOMMENDATIONS = "📚 Рекомендации"
BTN_HELP = "ℹ️ Помощь"
