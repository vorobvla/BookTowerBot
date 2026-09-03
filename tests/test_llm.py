"""Tests for LLMJsonConverter and LLM JSON conversion module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from admin.llm import (
    InputType,
    LLMJsonConverter,
    TransferToJson,
    from_file,
    from_url,
    transfer_to_json,
)
from admin.llm.transfer_to_json import load_prompt


def test_input_type_enum():
    assert InputType.TEXT == "text"
    assert InputType.CSV == "csv"
    assert InputType.WEB == "web"
    assert InputType.HTML == "html"


def test_load_prompt_replaces_placeholders():
    prompt = load_prompt("participants", InputType.CSV)
    assert "csv" in prompt
    assert "participants" in prompt
    assert "#Participants" in prompt or "# Participants" in prompt or "data_shema.md" not in prompt
    assert "{{input_text_type}}" not in prompt
    assert "{{entity_name}}" not in prompt
    assert "{{documentation}}" not in prompt


@patch("httpx.post")
def test_converter_transfer_to_json_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"participants": [{"stand": "1", "name": "Publisher A"}]}\n```'
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    converter = LLMJsonConverter(
        api_key="test-key",
        model_name="test-model",
        base_url="https://api.example.com",
    )
    result = converter.transfer_to_json(
        input_text="Stand 1: Publisher A",
        entity_name="participants",
        input_type=InputType.TEXT,
    )

    data = json.loads(result)
    assert data["participants"][0]["name"] == "Publisher A"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["model"] == "test-model"
    assert "Authorization" in call_kwargs["headers"]


@patch("httpx.get")
@patch("httpx.post")
def test_converter_from_url(mock_post, mock_get):
    mock_get_resp = MagicMock()
    mock_get_resp.text = "<html><body><h1>Schedule</h1><p>Event at 10:00</p></body></html>"
    mock_get_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_get_resp

    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"timetable": []}'
                }
            }
        ]
    }
    mock_post_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_post_resp

    converter = LLMJsonConverter(
        api_key="test-key",
        model_name="test-model",
        base_url="https://api.example.com",
    )
    result = converter.from_url("https://example.com/schedule", "timetables")
    assert json.loads(result) == {"timetable": []}

    mock_get.assert_called_once_with("https://example.com/schedule", timeout=30.0, follow_redirects=True)
    post_payload = mock_post.call_args.kwargs["json"]
    assert post_payload["messages"][1]["content"] == mock_get_resp.text
    assert "html" in post_payload["messages"][0]["content"]


@patch("httpx.post")
def test_converter_from_file_csv(mock_post, tmp_path: Path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("name,stand\nPublisher B,Stand 2\n", encoding="utf-8")

    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"participants": [{"name": "Publisher B", "stand": "Stand 2"}]}'
                }
            }
        ]
    }
    mock_post_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_post_resp

    converter = LLMJsonConverter(
        api_key="test-key",
        model_name="test-model",
        base_url="https://api.example.com",
    )
    result = converter.from_file(csv_file, "participants")
    assert json.loads(result)["participants"][0]["name"] == "Publisher B"

    post_payload = mock_post.call_args.kwargs["json"]
    assert post_payload["messages"][1]["content"] == "name,stand\nPublisher B,Stand 2\n"
    assert "csv" in post_payload["messages"][0]["content"]


@patch("httpx.post")
def test_converter_from_file_txt(mock_post, tmp_path: Path):
    txt_file = tmp_path / "data.txt"
    txt_file.write_text("Event details here", encoding="utf-8")

    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"timetables": []}'
                }
            }
        ]
    }
    mock_post_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_post_resp

    converter = LLMJsonConverter(
        api_key="test-key",
        model_name="test-model",
        base_url="https://api.example.com",
    )
    result = converter.from_file(txt_file, "timetables")
    assert json.loads(result) == {"timetables": []}

    post_payload = mock_post.call_args.kwargs["json"]
    assert "text" in post_payload["messages"][0]["content"]


def test_missing_env_vars_raises_value_error(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL_NAME", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)

    converter = LLMJsonConverter(api_key=None, model_name=None, base_url=None)

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is not set"):
        converter.transfer_to_json("test", "participants")

    converter.api_key = "key"
    with pytest.raises(ValueError, match="LLM_MODEL_NAME is not set"):
        converter.transfer_to_json("test", "participants")

    converter.model_name = "model"
    with pytest.raises(ValueError, match="OPENROUTER_BASE_URL is not set"):
        converter.transfer_to_json("test", "participants")


@patch("httpx.post")
def test_convenience_functions(mock_post, tmp_path: Path):
    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"recs": []}'
                }
            }
        ]
    }
    mock_post_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_post_resp

    # test transfer_to_json convenience function
    res = transfer_to_json(
        "Book recommendations",
        "recommendations",
        api_key="key",
        model_name="model",
        base_url="https://api.example.com",
    )
    assert json.loads(res) == {"recs": []}

    # test from_file convenience function
    f = tmp_path / "sample.csv"
    f.write_text("a,b\n1,2", encoding="utf-8")
    res_file = from_file(
        f,
        "recommendations",
        api_key="key",
        model_name="model",
        base_url="https://api.example.com",
    )
    assert json.loads(res_file) == {"recs": []}


@patch("httpx.post")
def test_converter_logs_operations(mock_post, caplog):
    import logging
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"participants": []}'}}]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    converter = LLMJsonConverter(api_key="k", model_name="m", base_url="https://api.example.com")
    with caplog.at_level(logging.INFO):
        converter.transfer_to_json("test input", "participants")

    assert any("Starting LLM transfer" in record.message for record in caplog.records)
    assert any("Received LLM response" in record.message for record in caplog.records)
