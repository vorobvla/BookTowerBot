"""Recommendations section for featured books and category compilations."""

from typing import Optional
from telegram import Message
from telegram.constants import ParseMode

from bot.content import BTN_RECOMMENDATIONS, RECOMMENDATIONS_MESSAGE
from bot.keyboards import CB_RECOMMENDATIONS
from bot.recommendations.keyboards import (
    CB_REC_CATEGORY_PREFIX,
    CB_RECS_CATEGORIES,
    get_categories_inline_keyboard,
    get_recommendation_details_keyboard,
)
from bot.recommendations.service import RecommendationsService
from bot.sections.base import BaseSection


class Recommendations(BaseSection):
    """Recommendations section handling book recommendations and category selections."""

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

    def __init__(self, service: Optional[RecommendationsService] = None):
        self.service = service or RecommendationsService()

    def get_text_content(self) -> str:
        return RECOMMENDATIONS_MESSAGE

    def get_display_text(self) -> str:
        categories = self.service.get_category_names()
        if not categories:
            return self.get_text_content()
        formatted_cats = [f"• {c}" for c in categories]
        return f"{self.get_text_content()}\n\n" + "\n".join(formatted_cats)

    def get_reply_markup(self, inline: bool = False):
        categories = self.service.get_category_names()
        return get_categories_inline_keyboard(categories=categories)

    def matches_callback(self, callback_data: str) -> bool:
        """Check whether callback data belongs to the recommendations flow."""
        return (
            callback_data == self.callback_data
            or callback_data == CB_RECS_CATEGORIES
            or callback_data.startswith(CB_REC_CATEGORY_PREFIX)
        )

    async def send_response(self, target: Message, inline: Optional[bool] = None) -> None:
        """Send recommendations initial response with category selection buttons."""
        await target.reply_text(
            text=self.get_text_content(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_reply_markup(inline=True),
        )

    async def handle_callback_query(self, query) -> None:
        """Handle interactive inline recommendations callbacks."""
        data = query.data

        if data == self.callback_data or data == CB_RECS_CATEGORIES:
            await self._show_categories(query)
        elif data.startswith(CB_REC_CATEGORY_PREFIX):
            category_name = data[len(CB_REC_CATEGORY_PREFIX):]
            await self._show_books(query, category_name)
        else:
            await self._show_categories(query)

    async def _show_categories(self, query) -> None:
        markup = self.get_reply_markup(inline=True)
        await self._edit_or_reply(query, self.get_text_content(), markup)

    async def _show_books(self, query, category_name: str) -> None:
        text = self.service.format_category_recommendations(category_name)
        markup = get_recommendation_details_keyboard()
        await self._edit_or_reply(query, text, markup)

    async def _edit_or_reply(self, query, text: str, markup) -> None:
        if hasattr(query, "edit_message_text") and callable(query.edit_message_text):
            try:
                await query.edit_message_text(
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup,
                )
                return
            except Exception:
                pass

        if getattr(query, "message", None):
            await query.message.reply_text(
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=markup,
            )


RecommendationsSection = Recommendations
