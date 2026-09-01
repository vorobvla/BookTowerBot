"""Content and text templates for BookTowerBot."""

START_MESSAGE = (
    "📚 *Welcome to BookTowerBot!*\n\n"
    "I am here to help you navigate the event efficiently and get the most out of your visit.\n\n"
    "You can use the menu buttons below or type commands directly:\n"
    "• 🗺 /map — View the venue map and pavilion layout\n"
    "• 📅 /timetable — Check the schedule of talks and signings\n"
    "• ⭐ /recommendations — Discover recommended books and booths\n"
    "• ℹ️ /help — Show help information\n\n"
    "Please select an option to get started:"
)

HELP_MESSAGE = (
    "ℹ️ *BookTowerBot Help & Navigation*\n\n"
    "Available Commands:\n"
    "• `/start` — Start or restart the bot and show main menu\n"
    "• `/map` — Display venue layout and pavilion guide\n"
    "• `/timetable` — View event schedule and session times\n"
    "• `/recommendations` or `/recs` — View curated recommendations\n"
    "• `/help` — Display this help message\n\n"
    "You can also use the persistent keyboard buttons at any time."
)

MAP_MESSAGE = (
    "🗺 *BookTower Venue Map*\n\n"
    "```\n"
    "+----------------------------------------------+\n"
    "|               [ NORTH ENTRANCE ]             |\n"
    "|                                              |\n"
    "|  +-------------------+    +---------------+  |\n"
    "|  |   Pavilion A      |    |  Pavilion B   |  |\n"
    "|  |   (Fiction)       |    |  (Non-Fiction)|  |\n"
    "|  +-------------------+    +---------------+  |\n"
    "|                                              |\n"
    "|  +-------------------+    +---------------+  |\n"
    "|  |   Main Stage      |    |  Pavilion C   |  |\n"
    "|  |   (Keynotes)      |    |  (Comics/Kids)|  |\n"
    "|  +-------------------+    +---------------+  |\n"
    "|                                              |\n"
    "|  [ Info Desk ]   [ Food Court ]   [ Restroom ]|\n"
    "+----------------------------------------------+\n"
    "```\n\n"
    "📍 *Zone Directory:*\n"
    "• *Pavilion A:* Contemporary Fiction, Classics, Poetry (Booths A1–A40)\n"
    "• *Pavilion B:* Science, History, Biographies, Tech (Booths B1–B40)\n"
    "• *Pavilion C:* Graphic Novels, Manga, Young Adult (Booths C1–C30)\n"
    "• *Main Stage:* Author talks, panel discussions, award ceremonies\n"
    "• *Info Desk:* Central Hall (Lost & Found, Program Guides)"
)

TIMETABLE_MESSAGE = (
    "📅 *BookTower Event Timetable*\n\n"
    "🗓 *Today's Schedule:*\n\n"
    "⏰ *10:00 - 11:00* | Main Stage\n"
    "• Opening Ceremony & Keynote Address\n\n"
    "⏰ *11:30 - 13:00* | Pavilion A (Signing Area 1)\n"
    "• Bestselling Fiction Author Meet & Greet\n\n"
    "⏰ *13:00 - 14:00* | Food Court & Central Courtyard\n"
    "• Lunch Break & Acoustic Performance\n\n"
    "⏰ *14:30 - 16:00* | Main Stage\n"
    "• Panel: The Future of Digital and Print Publishing\n\n"
    "⏰ *16:30 - 18:00* | Pavilion B (Workshop Room)\n"
    "• Creative Writing & Translation Workshop\n\n"
    "⏰ *18:30 - 19:30* | Main Stage\n"
    "• Daily Literary Awards and Closing Remarks"
)

RECOMMENDATIONS_MESSAGE = (
    "⭐ *Curated Recommendations for Visitors*\n\n"
    "🏆 *Must-Visit Booths:*\n"
    "1. *Booth A12 (Artisan Press):* Exclusive signed editions & prints\n"
    "2. *Booth B05 (SciTech Books):* 30% discount on science releases\n"
    "3. *Booth C18 (Indie Comic Vault):* Debut graphic novels\n\n"
    "📖 *Featured Book Picks:*\n"
    "• *'Echoes of the Horizon'* — Fiction Highlight of the Month\n"
    "• *'The Architecture of Thought'* — Recommended Non-Fiction\n"
    "• *'Skybound Chronicles'* — Best Young Adult Release\n\n"
    "💡 *Tip:* Visit popular signing areas early to secure your spot in queue!"
)

# Button label constants
BTN_MAP = "🏢 План ярмарки"
BTN_TIMETABLE = "📅 Расписание"
BTN_RECOMMENDATIONS = "📚 Рекомендации"
BTN_HELP = "ℹ️ Помощь"
