import importlib


def test_app_module_imports_without_running_streamlit():
    module = importlib.import_module("app")
    assert hasattr(module, "main")
