"""Content and text templates for BookTowerBot."""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _resolve_relative_path(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        return str((PROJECT_ROOT / p).resolve())
    return str(p.resolve())


ASSETS_PATH = _resolve_relative_path(
    os.getenv(
        "ASSETS_PATH",
        str(PROJECT_ROOT / "assets")
        if (PROJECT_ROOT / "assets").exists()
        else str(PROJECT_ROOT / ".assets"),
    )
)

MAP_DIR = _resolve_relative_path(os.getenv("MAP_DIR", os.path.join(ASSETS_PATH, "map")))
MAP_PATH = _resolve_relative_path(os.getenv("MAP_PATH", os.path.join(MAP_DIR, "map.png")))
TIMETABLES_PATH = _resolve_relative_path(os.getenv("TIMETABLES_PATH", os.path.join(ASSETS_PATH, "timetables")))
RECS_PATH = _resolve_relative_path(os.getenv("RECS_PATH", os.path.join(ASSETS_PATH, "recs", "recs.json")))
PARTICIPANTS_PATH = _resolve_relative_path(os.getenv("PARTICIPANTS_PATH", os.path.join(ASSETS_PATH, "participants", "participants.json")))
WISHLIST_DB_PATH = _resolve_relative_path(os.getenv("WISHLIST_DB_PATH", os.path.join(ASSETS_PATH, "db", "wishlist.db")))

START_MESSAGE = (
    "📚 *Добро пожаловать в BookTowerBot!*\n\n"
    "Я помогу вам сориентироваться на мероприятии и провести время с максимальной пользой.\n\n"
    "Вы можете использовать кнопки меню ниже или вводить команды напрямую:\n"
    "• 🏢 /map — Посмотреть карту площадки и схему павильонов\n"
    "• 📅 /timetables — Расписание выступлений и автограф-сессий\n"
    "• 🎈 /children — Детская программа мероприятий\n"
    "• 📚 /recommendations — Рекомендации книг и стендов\n"
    "• 👥 /participants — Список участников и номера их стендов\n"
    "• 📝 /wishlist — Вишлист и желаемых книг\n"
    "• ℹ️ /help — Справка и помощь\n\n"
    "Пожалуйста, выберите интересующий раздел:"
)

HELP_MESSAGE = (
    "ℹ️ *Справка и навигация BookTowerBot*\n\n"
    "Доступные команды:\n"
    "• `/start` — Запустить или перезапустить бота и открыть главное меню\n"
    "• `/map` — Показать карту площадки и схему павильонов\n"
    "• `/timetables` — Расписание событий и мероприятий\n"
    "• `/children` — Детская программа мероприятий\n"
    "• `/recommendations` или `/recs` — Подборка рекомендаций\n"
    "• `/participants` — Список участников и расположение их стендов\n"
    "• `/wishlist` — Вишлист (добавить книгу, посмотреть список)\n"
    "• `/help` — Показать это справочное сообщение\n\n"
    "Вы также можете в любой момент воспользоваться кнопками меню."
)

MAP_MESSAGE = (
    ""
)

MAP_UNAVAILABLE_MESSAGE = (
    "🗺 *Карта площадки*\n\n"
    "К сожалению, карта сейчас недоступна по техническим причинам. "
    "Приносим извинения за доставленные неудобства!"
)

TIMETABLE_MESSAGE = (
    "📅 *Расписание мероприятий*\n\n"
    "Пожалуйста, выберите интересующую вас дату:"
)

CHILDREN_ACTIVITY_MESSAGE = (
    "🎈 *Детская программа*\n\n"
    "Пожалуйста, выберите интересующую вас дату:"
)

RECOMMENDATIONS_MESSAGE = (
    "⭐ *Рекомендации книг и стендов*\n\n"
    "Пожалуйста, выберите интересующую вас подборку:"
)

PARTICIPANTS_MESSAGE = (
    "👥 *Участники ярмарки*\n\n"
    "Пожалуйста, выберите участника, чтобы узнать подробную информацию и номер стенда:"
)

WISHLIST_MESSAGE = (
    "📝 *Вишлист (Wishlist)*\n\n"
    "Здесь вы можете сохранять книги, которые хотите купить или найти на ярмарке.\n\n"
    "Пожалуйста, выберите действие:"
)

WISHLIST_ADD_PROMPT = (
    "✍️ *Добавление книги в вишлист*\n\n"
    "Пожалуйста, введите название книги сообщением:"
)

WISHLIST_EDIT_PROMPT = (
    "✏️ *Редактирование книги*\n\n"
    "Пожалуйста, выберите книгу для изменения:"
)

WISHLIST_REMOVE_PROMPT = (
    "🗑 *Удаление книги*\n\n"
    "Пожалуйста, выберите книгу для удаления из вишлиста:"
)

WISHLIST_EMPTY_MESSAGE = (
    "📭 *Ваш вишлист пока пуст.*\n\n"
    "Нажмите «Добавить книгу» (или введите /addbook), чтобы добавить первую книгу в список."
)

UNKNOWN_COMMAND_MESSAGE = (
    "Команда не распознана. Пожалуйста, используйте кнопки меню ниже "
    "или введите `/help`, чтобы посмотреть все доступные опции."
)

# Button label constants
BTN_MAP = "🏢 План ярмарки"
BTN_TIMETABLE = "📅 Расписание"
BTN_CHILDREN_ACTIVITY = "🎈 Детская программа"
BTN_RECOMMENDATIONS = "📚 Рекомендации"
BTN_PARTICIPANTS = "👥 Участники"
BTN_WISHLIST = "📝 Вишлист"
BTN_WISHLIST_ADD = "➕ Добавить книгу"
BTN_WISHLIST_GET = "📋 Мой список"
BTN_WISHLIST_EDIT = "✏️ Изменить"
BTN_WISHLIST_REMOVE = "🗑 Удалить"
BTN_SHOW_PARTICIPANTS = "📍 Информация о стендах участников"
BTN_SHOW_STANDS = "📍 Информация о стендах"
BTN_SHOW_STANDS_INFO = "📍 Информация о стендах"
BTN_BACK_TO_MAP = "« Назад к плану ярмарки"
BTN_HELP = "ℹ️ Помощь"

# Callback data constants
CB_MAP = "action_map"
CB_TIMETABLE = "action_timetable"
CB_CHILDREN_ACTIVITY = "section_children_activity"
CB_RECOMMENDATIONS = "action_recommendations"
CB_PARTICIPANTS = "action_participants"
CB_WISHLIST = "action_wishlist"
CB_WISHLIST_ADD = "wishlist_add"
CB_WISHLIST_GET = "wishlist_get"
CB_WISHLIST_EDIT = "wishlist_edit"
CB_WISHLIST_REMOVE = "wishlist_remove"
CB_STANDS = "action_stands"
CB_SHOW_STANDS = "action_stands"
CB_HELP = "action_help"
CB_STAND_PREFIX = "stand:"

# Dictionary binding button texts to callback data
BUTTON_CALLBACK_MAP = {
    BTN_MAP: CB_MAP,
    BTN_TIMETABLE: CB_TIMETABLE,
    BTN_CHILDREN_ACTIVITY: CB_CHILDREN_ACTIVITY,
    BTN_RECOMMENDATIONS: CB_RECOMMENDATIONS,
    BTN_PARTICIPANTS: CB_PARTICIPANTS,
    BTN_WISHLIST: CB_WISHLIST,
    "Wishlist": CB_WISHLIST,
    "wishlist": CB_WISHLIST,
    "Вишлист": CB_WISHLIST,
    "Список желаемого": CB_WISHLIST,
    BTN_WISHLIST_ADD: CB_WISHLIST_ADD,
    "Add Book": CB_WISHLIST_ADD,
    "Add book": CB_WISHLIST_ADD,
    "Добавить книгу": CB_WISHLIST_ADD,
    BTN_WISHLIST_GET: CB_WISHLIST_GET,
    "GetList": CB_WISHLIST_GET,
    "Get List": CB_WISHLIST_GET,
    "Мой список": CB_WISHLIST_GET,
    "Список книг": CB_WISHLIST_GET,
    BTN_WISHLIST_EDIT: CB_WISHLIST_EDIT,
    "Edit": CB_WISHLIST_EDIT,
    "edit": CB_WISHLIST_EDIT,
    "Редактировать": CB_WISHLIST_EDIT,
    "Изменить": CB_WISHLIST_EDIT,
    BTN_WISHLIST_REMOVE: CB_WISHLIST_REMOVE,
    "Remove": CB_WISHLIST_REMOVE,
    "remove": CB_WISHLIST_REMOVE,
    "Удалить": CB_WISHLIST_REMOVE,
    "Delete": CB_WISHLIST_REMOVE,
    BTN_SHOW_PARTICIPANTS: CB_PARTICIPANTS,
    BTN_SHOW_STANDS: CB_STANDS,
    BTN_SHOW_STANDS_INFO: CB_STANDS,
    "Show stands info": CB_STANDS,
    "📍 Информация о стендах": CB_STANDS,
    BTN_BACK_TO_MAP: CB_MAP,
    BTN_HELP: CB_HELP,
}
