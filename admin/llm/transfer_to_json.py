"""LLM-based converter to transform text, CSV, or web pages into BookTower JSON entities."""

from enum import Enum
import logging
import os
from pathlib import Path
import re
from typing import Optional, Union
from dotenv import load_dotenv
import httpx

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROMPT_FILE = Path(__file__).resolve().parent / "transfer_to_json.prompt.txt"
DOC_FILE = PROJECT_ROOT / "doc" / "data_shema.md"

load_dotenv(PROJECT_ROOT / ".env")


class InputType(str, Enum):
    """Input text types for LLM conversion prompt."""

    TEXT = "text"
    CSV = "csv"
    WEB = "web"
    HTML = "html"


class LLMJsonConverter:
    """Class to convert text, CSV, or HTML into schema-compliant JSON using LLM."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model_name or os.getenv("LLM_MODEL_NAME")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL")
        temp_env = os.getenv("LLM_TEMPERATURE")
        self.temperature = (
            temperature
            if temperature is not None
            else (float(temp_env) if temp_env is not None else None)
        )

    def _load_prompt(self, entity_name: str, input_text_type: str) -> str:
        """Load the prompt template and insert documentation and entity parameters."""
        logger.debug("Loading prompt template for entity '%s' with input type '%s'", entity_name, input_text_type)
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            template = f.read()

        with open(DOC_FILE, "r", encoding="utf-8") as f:
            doc = f.read()

        return (
            template.replace("{{input_text_type}}", input_text_type)
            .replace("{{entity_name}}", entity_name)
            .replace("{{documentation}}", doc)
        )

    def transfer_to_json(
        self,
        input_text: str,
        entity_name: str,
        input_type: Union[InputType, str] = InputType.TEXT,
    ) -> str:
        """Base method to send input text to LLM and return the parsed JSON string."""
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is not set in environment or passed to converter")
        if not self.model_name:
            raise ValueError("LLM_MODEL_NAME is not set in environment or passed to converter")
        if not self.base_url:
            raise ValueError("OPENROUTER_BASE_URL is not set in environment or passed to converter")

        type_str = input_type.value if isinstance(input_type, Enum) else str(input_type)
        logger.info(
            "Starting LLM transfer to JSON for entity '%s' (input_type: %s, input length: %d chars)",
            entity_name,
            type_str,
            len(input_text),
        )

        system_prompt = self._load_prompt(entity_name, type_str)

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text},
            ],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            logger.debug(
                "Sending request to LLM API '%s/chat/completions' (model: %s)",
                self.base_url.rstrip("/"),
                self.model_name,
            )
            resp = httpx.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()

            raw = data["choices"][0]["message"]["content"].strip()
            logger.info("Received LLM response (status: %d, response length: %d chars)", resp.status_code, len(raw))

            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, flags=re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
            logger.debug("Cleaned JSON output length: %d chars", len(raw))
            return raw
        except Exception as e:
            logger.error("LLM transfer failed for entity '%s': %s", entity_name, e, exc_info=True)
            raise

    def from_url(self, url: str, entity_name: str) -> str:
        """Fetch content from a web URL and convert it to JSON using HTML input type."""
        logger.info("Fetching web page from URL '%s' for entity '%s'", url, entity_name)
        try:
            resp = httpx.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            logger.info("Successfully fetched %d chars from URL '%s' (status: %d)", len(resp.text), url, resp.status_code)
        except Exception as e:
            logger.error("Failed to fetch web page from URL '%s': %s", url, e, exc_info=True)
            raise

        return self.transfer_to_json(resp.text, entity_name, InputType.HTML)

    def from_file(self, file_path: Union[str, Path], entity_name: str) -> str:
        """Load content from a text file path (.csv -> CSV, otherwise -> TEXT) and convert to JSON."""
        path_str = str(file_path)
        input_type = InputType.CSV if path_str.lower().endswith(".csv") else InputType.TEXT
        logger.info("Loading file '%s' for entity '%s' (detected type: %s)", path_str, entity_name, input_type.value)
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            logger.info("Successfully read %d chars from file '%s'", len(content), path_str)
        except Exception as e:
            logger.error("Failed to read file '%s': %s", path_str, e, exc_info=True)
            raise

        return self.transfer_to_json(content, entity_name, input_type)

    # Convenience aliases
    convert = transfer_to_json
    from_web = from_url
    from_web_url = from_url
    transfer_from_url = from_url
    transfer_from_file = from_file


TransferToJson = LLMJsonConverter


def load_prompt(entity_name: str, input_text_type: str = "text") -> str:
    """Helper to load rendered prompt template."""
    return LLMJsonConverter()._load_prompt(entity_name, input_text_type)


def transfer_to_json(
    input_text: str,
    entity_name: str,
    input_type: Union[InputType, str] = InputType.TEXT,
    **kwargs,
) -> str:
    """Convenience function to convert text into JSON using LLM."""
    converter = LLMJsonConverter(**kwargs)
    return converter.transfer_to_json(input_text, entity_name, input_type)


def from_url(url: str, entity_name: str, **kwargs) -> str:
    """Convenience function to fetch web URL and convert to JSON."""
    converter = LLMJsonConverter(**kwargs)
    return converter.from_url(url, entity_name)


def from_file(file_path: Union[str, Path], entity_name: str, **kwargs) -> str:
    """Convenience function to load file and convert to JSON."""
    converter = LLMJsonConverter(**kwargs)
    return converter.from_file(file_path, entity_name)
