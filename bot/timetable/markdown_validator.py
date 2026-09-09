"""Markdown syntax validator for Telegram Markdown v1 formatting."""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class MarkdownValidator:
    """Validates that text conforms to Telegram Markdown (v1) formatting rules."""

    @classmethod
    def validate(cls, text: str) -> bool:
        """
        Validate Telegram Markdown (v1) syntax.

        Raises ValueError with descriptive Russian error message if invalid.
        Returns True if valid.
        """
        if not text:
            return True

        n = len(text)
        i = 0
        stack: List[Tuple[str, int]] = []

        while i < n:
            # Handle escape character
            if text[i] == "\\":
                if i + 1 >= n:
                    raise ValueError(
                        "Некорректная разметка Markdown: символ экранирования '\\' в конце строки"
                    )
                i += 2
                continue

            # If inside pre-formatted code block (```)
            if stack and stack[-1][0] == "```":
                if text[i : i + 3] == "```":
                    stack.pop()
                    i += 3
                else:
                    i += 1
                continue

            # If inside inline code (`)
            if stack and stack[-1][0] == "`":
                if text[i] == "`":
                    stack.pop()
                    i += 1
                else:
                    i += 1
                continue

            # Start of pre block
            if text[i : i + 3] == "```":
                stack.append(("```", i))
                i += 3
                continue

            # Start of inline code
            if text[i] == "`":
                stack.append(("`", i))
                i += 1
                continue

            # Start of inline link [text](url)
            if text[i] == "[":
                link_close = -1
                j = i + 1
                while j < n:
                    if text[j] == "\\":
                        j += 2
                        continue
                    if text[j] == "]":
                        link_close = j
                        break
                    if text[j] == "[":
                        raise ValueError(
                            f"Некорректная разметка Markdown: незакрытая скобка '[' на позиции {i + 1}"
                        )
                    j += 1

                if link_close == -1 or link_close + 1 >= n or text[link_close + 1] != "(":
                    raise ValueError(
                        f"Некорректная разметка Markdown: незакрытая ссылка [текст](url) на позиции {i + 1}"
                    )

                url_close = -1
                k = link_close + 2
                while k < n:
                    if text[k] == "\\":
                        k += 2
                        continue
                    if text[k] == ")":
                        url_close = k
                        break
                    if text[k] in ("(", "\n"):
                        raise ValueError(
                            f"Некорректная разметка Markdown: некорректный URL в ссылке на позиции {link_close + 2}"
                        )
                    k += 1

                if url_close == -1:
                    raise ValueError(
                        f"Некорректная разметка Markdown: незакрытый URL в ссылке на позиции {link_close + 2}"
                    )

                i = url_close + 1
                continue

            if text[i] == "]":
                raise ValueError(
                    f"Некорректная разметка Markdown: лишняя закрывающая скобка ']' на позиции {i + 1}"
                )

            # Bold (*) or Italic (_)
            if text[i] in ("*", "_"):
                char = text[i]
                if stack and stack[-1][0] == char:
                    stack.pop()
                elif any(s[0] == char for s in stack):
                    raise ValueError(
                        f"Некорректная разметка Markdown: некорректное пересечение тегов '{char}' на позиции {i + 1}"
                    )
                else:
                    stack.append((char, i))
                i += 1
                continue

            i += 1

        if stack:
            ent, pos = stack[-1]
            names = {
                "```": "блок кода (```)",
                "`": "встроенный код (`)",
                "*": "жирный шрифт (*)",
                "_": "курсив (_)",
            }
            raise ValueError(
                f"Некорректная разметка Markdown: незакрытый {names.get(ent, ent)} начиная с позиции {pos + 1}"
            )

        return True
