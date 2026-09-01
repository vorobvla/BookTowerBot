"""Recommendations section for featured books and booth picks."""

from bot.content import BTN_RECOMMENDATIONS, RECOMMENDATIONS_MESSAGE
from bot.keyboards import CB_RECOMMENDATIONS
from bot.sections.base import BaseSection


class Recommendations(BaseSection):
    """Recommendations section handling featured books and booth picks."""

    name = "recommendations"
    commands = ["recommendations", "recs"]
    button_text = BTN_RECOMMENDATIONS
    callback_data = CB_RECOMMENDATIONS
    aliases = {
        "рекомендации",
        "recommendations",
        "recs",
        "recommendation",
        "/recommendations",
        "/recs",
    }
    use_reply_keyboard = False

    def get_text_content(self) -> str:
        return RECOMMENDATIONS_MESSAGE


RecommendationsSection = Recommendations
