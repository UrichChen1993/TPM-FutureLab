from types import SimpleNamespace

import pytest

import storage.factory as factory
from storage.memory_backend import InMemoryRepository


def settings(backend: str):
    return SimpleNamespace(
        data_backend=backend,
        dynamodb_table="homewellness-test",
        aws_region="ap-northeast-1",
    )


def test_factory_returns_memory_repository(monkeypatch):
    monkeypatch.setattr(factory, "load_settings", lambda: settings(" MEMORY "))
    assert isinstance(factory.get_repository(), InMemoryRepository)


def test_factory_builds_dynamodb_repository(monkeypatch):
    captured = {}

    class FakeDynamoDBRepository:
        def __init__(self, table_name: str, region: str):
            captured.update(table_name=table_name, region=region)

    monkeypatch.setattr(factory, "load_settings", lambda: settings("dynamodb"))
    monkeypatch.setattr(factory, "DynamoDBRepository", FakeDynamoDBRepository)

    assert isinstance(factory.get_repository(), FakeDynamoDBRepository)
    assert captured == {
        "table_name": "homewellness-test",
        "region": "ap-northeast-1",
    }


def test_factory_rejects_unknown_backend(monkeypatch):
    monkeypatch.setattr(factory, "load_settings", lambda: settings("dynamo"))
    with pytest.raises(ValueError, match="Unsupported DATA_BACKEND"):
        factory.get_repository()
