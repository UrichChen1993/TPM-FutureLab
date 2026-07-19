import importlib

from app import extract_display_text


def test_app_module_imports_without_running_streamlit():
    module = importlib.import_module("app")
    assert hasattr(module, "main")


def test_extract_display_text_hides_provider_signature_metadata():
    content = [{
        "type": "text",
        "text": "好的。",
        "extras": {"signature": "sensitive-provider-metadata"},
    }]

    assert extract_display_text(content) == "好的。"


def test_extract_display_text_combines_multiple_text_blocks_only():
    content = [
        {"type": "text", "text": "第一段"},
        {"type": "tool_call", "name": "record_dose_self_report"},
        {"type": "text", "text": "第二段"},
    ]

    assert extract_display_text(content) == "第一段\n第二段"
